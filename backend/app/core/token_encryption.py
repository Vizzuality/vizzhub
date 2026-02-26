"""Fernet symmetric encryption for OAuth tokens at rest."""

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().oauth_encryption_key
    if not key:
        raise ValueError(
            "OAUTH_ENCRYPTION_KEY environment variable is required. "
            "Generate with: python -c "
            "\"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string. Returns original plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
