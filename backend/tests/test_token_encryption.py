"""Tests for OAuth token encryption helpers."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.token_encryption import decrypt_token, encrypt_token

TEST_KEY = Fernet.generate_key().decode()


class TestEncryptToken:
    """Test token encryption."""

    def test_encrypt_token_returns_different_string(self) -> None:
        """Encrypted value should differ from plaintext."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            plaintext = "my-secret-token"
            encrypted = encrypt_token(plaintext)
            assert encrypted != plaintext
            assert isinstance(encrypted, str)

    def test_encrypt_token_produces_valid_fernet_output(self) -> None:
        """Output should be decodable by Fernet."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            encrypted = encrypt_token("test-value")
            f = Fernet(TEST_KEY.encode())
            result = f.decrypt(encrypted.encode()).decode()
            assert result == "test-value"

    def test_encrypt_token_raises_without_key(self) -> None:
        """Should raise ValueError when encryption key is missing."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = ""
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                encrypt_token("test")


class TestDecryptToken:
    """Test token decryption."""

    def test_decrypt_token_roundtrip(self) -> None:
        """Encrypting then decrypting should return original value."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            original = "access-token-xyz-123"
            encrypted = encrypt_token(original)
            decrypted = decrypt_token(encrypted)
            assert decrypted == original

    def test_decrypt_token_raises_without_key(self) -> None:
        """Should raise ValueError when encryption key is missing."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = ""
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                decrypt_token("some-ciphertext")

    def test_decrypt_token_raises_on_invalid_ciphertext(self) -> None:
        """Should raise on corrupted/invalid ciphertext."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            with pytest.raises(Exception):
                decrypt_token("not-valid-fernet-data")

    def test_encrypt_decrypt_empty_string(self) -> None:
        """Should handle empty string."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            encrypted = encrypt_token("")
            assert decrypt_token(encrypted) == ""

    def test_encrypt_decrypt_unicode(self) -> None:
        """Should handle unicode characters."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            original = "token-with-unicode-\u00e9\u00e8\u00ea"
            encrypted = encrypt_token(original)
            assert decrypt_token(encrypted) == original
