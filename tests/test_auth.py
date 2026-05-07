import pytest

from aspireupdater.auth import hash_password, verify_password


class TestHashPassword:
    def test_returns_two_hex_strings(self):
        hsh, salt = hash_password("password123")
        assert isinstance(hsh, str)
        assert isinstance(salt, str)
        # Must be valid hex
        bytes.fromhex(hsh)
        bytes.fromhex(salt)

    def test_random_salt_each_call(self):
        h1, s1 = hash_password("password")
        h2, s2 = hash_password("password")
        assert h1 != h2
        assert s1 != s2

    def test_deterministic_with_fixed_salt(self):
        salt = bytes(32)
        h1, _ = hash_password("password", salt)
        h2, _ = hash_password("password", salt)
        assert h1 == h2

    def test_different_passwords_different_hashes(self):
        salt = bytes(32)
        h1, _ = hash_password("password1", salt)
        h2, _ = hash_password("password2", salt)
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password(self):
        hsh, salt = hash_password("mypassword")
        assert verify_password("mypassword", hsh, salt) is True

    def test_wrong_password(self):
        hsh, salt = hash_password("mypassword")
        assert verify_password("wrongpassword", hsh, salt) is False

    def test_tampered_hash(self):
        hsh, salt = hash_password("mypassword")
        bad_hash  = "0" * len(hsh)
        assert verify_password("mypassword", bad_hash, salt) is False

    def test_invalid_salt_hex_returns_false(self):
        hsh, _ = hash_password("mypassword")
        assert verify_password("mypassword", hsh, "not-valid-hex!!") is False

    def test_empty_password(self):
        hsh, salt = hash_password("")
        assert verify_password("", hsh, salt) is True
        assert verify_password("notempty", hsh, salt) is False
