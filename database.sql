CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    public_key    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id  INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    enc_key  LONGBLOB NOT NULL,
    nonce    BLOB NOT NULL,
    tag      BLOB NOT NULL,
    path     VARCHAR(500) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
