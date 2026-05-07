import hashlib
import secrets


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return digest.hex(), salt.hex()


def verify_password(password, stored_hash, stored_salt):
    try:
        salt   = bytes.fromhex(stored_salt)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return secrets.compare_digest(digest.hex(), stored_hash)
    except Exception:
        return False
