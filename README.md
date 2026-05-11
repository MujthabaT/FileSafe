# FileSafe

FileSafe is a secure file sharing web application developed as a Master’s final-year academic project.
The system demonstrates a practical implementation of encrypted file storage using modern cryptographic primitives, with a focus on correctness, isolation, and clarity rather than production-scale infrastructure.

The application ensures that files are encrypted before storage and can only be decrypted by their rightful owners.

---

## Overview

FileSafe implements a hybrid cryptographic model combining symmetric and asymmetric encryption to securely store and retrieve user files. Each user is cryptographically isolated, and file confidentiality and integrity are preserved throughout the upload and download lifecycle.

The project intentionally avoids cloud integration to reduce architectural noise and to focus on the core security mechanisms described in the accompanying research paper.

---

## Key Features

- User authentication with secure password hashing
- Per-user RSA key pair generation
- AES-GCM encryption for file confidentiality and integrity
- RSA-OAEP key wrapping for secure AES key storage
- User-scoped file access and isolation
- Secure upload, download, and deletion of files
- Minimal, consistent UI without JavaScript frameworks

---

## Cryptographic Design

FileSafe uses a hybrid encryption approach:

- AES-GCM
  - Used for encrypting file contents
  - Provides both confidentiality and integrity verification
  - A unique AES key is generated per file

- RSA
  - Used to encrypt (wrap) the AES key
  - Each user has a unique RSA key pair
  - Public keys are stored in the database
  - Private keys are stored locally and never exposed

Only encrypted data is written to disk. Plaintext files exist only in memory during processing.

---

## Technology Stack

- Backend: Python, Flask
- Frontend: HTML, CSS
- Database: SQLite
- Cryptography: cryptography (Python library)
- Storage: Local filesystem (encrypted files only)

---

## Project Structure

FileSafe/
│
├── app.py                # Flask application entry point
├── users.db              # SQLite database
├── uploads/              # Encrypted files (.enc)
├── keys/                 # User private RSA keys
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── signin.html
│   ├── signup.html
│   └── dashboard.html
│
└── static/
    └── style.css

---

## Application Workflow (Post-Login)

1. Authentication
   - User logs in using email and password
   - Server-side session is established upon successful authentication

2. Homepage
   - Authenticated users are redirected to a secure homepage
   - Acts as an entry point before accessing the dashboard

3. Dashboard Access
   - Dashboard displays upload functionality and user file list
   - Access is restricted to authenticated users only

4. File Upload
   - File is read into memory
   - AES key is generated
   - File is encrypted using AES-GCM
   - AES key is encrypted using the user’s RSA public key
   - Encrypted file is stored on disk
   - Metadata is stored in the database

5. File Listing
   - Dashboard queries the database using the user’s session ID
   - Users can only view their own files

6. File Download
   - Ownership is verified
   - AES key is decrypted using the user’s RSA private key
   - File is decrypted using AES-GCM
   - Integrity is verified automatically
   - Decrypted file is sent to the user

7. File Deletion
   - Encrypted file is removed from disk
   - Corresponding database record is deleted
   - Action is restricted to file owners only

8. Logout
   - Session is destroyed
   - User is redirected to the sign-in page

---

## Security Properties

- Files stored on disk are always encrypted
- Users cannot access files belonging to others
- Integrity verification prevents tampered file downloads
- The server cannot read file contents without user authorization

---

## Design Scope and Limitations

- Cloud storage is intentionally excluded
- Session expiration and advanced access controls are out of scope
- The system is designed for academic demonstration, not production deployment

---

## Project Status

- Core functionality complete
- Encryption and decryption verified
- Matches the workflow described in the research paper

---

## Author

Mujthaba  
Final-Year Project
