import io
import os
import secrets
import mysql.connector
from functools import wraps
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from prometheus_flask_exporter import PrometheusMetrics


# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Prometheus monitoring — exposes /metrics endpoint
metrics = PrometheusMetrics(app)
metrics.info('app_info', 'FileSafe Application', version='1.0.0')

# Folders for encrypted files and RSA keys — created at startup
os.makedirs('uploads', exist_ok=True)
os.makedirs('keys', exist_ok=True)


# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'filesafe'),
    'charset':  'utf8mb4'
}


def get_db():
    """Opens and returns a MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)


# ─────────────────────────────────────────
# LOGIN GUARD
# ─────────────────────────────────────────

def login_required(f):
    """Redirects to signin if user is not logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────
# ENCRYPTION FUNCTIONS
# ─────────────────────────────────────────

def generate_rsa_keys(user_id):
    """
    Generates RSA-2048 key pair for a user.
    Private key saved to disk (persistent Docker volume).
    Returns public key as string for storing in database.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()

    # Serialize to PEM format (text representation of the key)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Save private key to file
    with open(f'keys/user_{user_id}_private.pem', 'wb') as f:
        f.write(private_pem)

    return public_pem.decode('utf-8')


def aes_gcm_encrypt(data: bytes):
    """
    Encrypts file bytes with AES-256-GCM.
    Returns: ciphertext, aes_key, nonce, tag
    """
    key = secrets.token_bytes(32)   # 256-bit random key
    nonce = secrets.token_bytes(12)   # 96-bit random nonce

    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce),
        backend=default_backend()
    ).encryptor()

    ciphertext = encryptor.update(data) + encryptor.finalize()

    return ciphertext, key, nonce, encryptor.tag


def aes_gcm_decrypt(ciphertext, key, nonce, tag):
    """
    Decrypts AES-256-GCM ciphertext back to original bytes.
    """
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce, tag),
        backend=default_backend()
    ).decryptor()

    return decryptor.update(ciphertext) + decryptor.finalize()


def rsa_encrypt_key(public_key_pem: str, aes_key: bytes):
    """
    Encrypts the AES key using user's RSA public key.
    Only the matching private key can decrypt it.
    """
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode('utf-8'),
        backend=default_backend()
    )
    return public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def rsa_decrypt_key(user_id: int, encrypted_aes_key: bytes):
    """
    Loads the user's RSA private key from disk and
    decrypts the encrypted AES key.
    """
    with open(f'keys/user_{user_id}_private.pem', 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key.decrypt(
        encrypted_aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return render_template('index.html', show_logout=True)


# ── Sign In ───────────────────────────────

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            return redirect(url_for('home'))

        return render_template('signin.html', error='Invalid email or password')

    return render_template('signin.html')


# ── Sign Up ───────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        password_hash = generate_password_hash(password, method='pbkdf2:sha256')

        conn = get_db()
        cursor = conn.cursor()

        try:
            # Insert user first with empty public key placeholder
            cursor.execute(
                'INSERT INTO users (email, password_hash, public_key) VALUES (%s, %s, %s)',
                (email, password_hash, '')
            )
            conn.commit()
            user_id = cursor.lastrowid

            # Generate RSA keys for this user
            public_key = generate_rsa_keys(user_id)

            # Store public key in database
            cursor.execute(
                'UPDATE users SET public_key = %s WHERE id = %s',
                (public_key, user_id)
            )
            conn.commit()
            cursor.close()
            conn.close()

            return redirect(url_for('signin'))

        except mysql.connector.IntegrityError:
            cursor.close()
            conn.close()
            return render_template('signup.html', error='Email already registered')

    return render_template('signup.html')


# ── Logout ────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))


# ── Dashboard — view files + upload ───────

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # ── Handle file upload (POST) ──
    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename == '':
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard'))

        data = file.read()

        # Get user's public RSA key from database
        cursor.execute('SELECT public_key FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()

        # Step 1: encrypt file with AES-256-GCM
        ciphertext, aes_key, nonce, tag = aes_gcm_encrypt(data)

        # Step 2: encrypt the AES key with RSA public key
        encrypted_key = rsa_encrypt_key(user['public_key'], aes_key)

        # Step 3: save encrypted file to disk (Docker volume)
        enc_filename = f'{secrets.token_hex(16)}.enc'
        enc_path = os.path.join('uploads', enc_filename)
        with open(enc_path, 'wb') as f:
            f.write(ciphertext)

        # Step 4: save metadata to database
        cursor.execute("""
            INSERT INTO files (user_id, filename, enc_key, nonce, tag, path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            file.filename,
            encrypted_key,   # bytes — stored as LONGBLOB
            nonce,           # bytes — stored as BLOB
            tag,             # bytes — stored as BLOB
            enc_path
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('dashboard', uploaded=1))

    # ── Show user's files (GET) ──
    cursor.execute(
        'SELECT id, filename FROM files WHERE user_id = %s',
        (session['user_id'],)
    )
    files = cursor.fetchall()
    cursor.close()
    conn.close()

    uploaded = request.args.get('uploaded')
    return render_template('dashboard.html', files=files, uploaded=uploaded, show_logout=True)


# ── Download ──────────────────────────────

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch file record — only if it belongs to this user
    cursor.execute("""
        SELECT filename, enc_key, nonce, tag, path
        FROM files
        WHERE id = %s AND user_id = %s
    """, (file_id, session['user_id']))
    record = cursor.fetchone()
    cursor.close()
    conn.close()

    if not record:
        return 'File not found or access denied', 404

    # Read encrypted file from disk
    with open(record['path'], 'rb') as f:
        ciphertext = f.read()

    # Decrypt AES key using RSA private key
    aes_key = rsa_decrypt_key(session['user_id'], bytes(record['enc_key']))

    # Decrypt file using AES key
    plaintext = aes_gcm_decrypt(
        ciphertext,
        aes_key,
        bytes(record['nonce']),
        bytes(record['tag'])
    )

    # Send original file to browser
    return send_file(
        io.BytesIO(plaintext),
        as_attachment=True,
        download_name=record['filename']
    )


# ── Delete ────────────────────────────────

@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch file — only if it belongs to this user
    cursor.execute("""
        SELECT path FROM files
        WHERE id = %s AND user_id = %s
    """, (file_id, session['user_id']))
    record = cursor.fetchone()

    if not record:
        cursor.close()
        conn.close()
        return 'File not found or access denied', 404

    # Delete encrypted file from disk
    if os.path.exists(record['path']):
        os.remove(record['path'])

    # Delete metadata from database
    cursor.execute('DELETE FROM files WHERE id = %s', (file_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))


# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
