import time
from unittest.mock import patch

from admin.auth import _generate_token, _validate_token, COOKIE_EXPIRY_DAYS


class TestGenerateToken:
    def test_generates_token_with_username_timestamp_signature(self):
        token = _generate_token("admin")

        parts = token.split(":")
        assert len(parts) == 3
        assert parts[0] == "admin"
        assert parts[1].isdigit()  # timestamp
        assert len(parts[2]) == 64  # sha256 hex

    def test_different_usernames_produce_different_tokens(self):
        token1 = _generate_token("admin")
        token2 = _generate_token("user")

        assert token1 != token2

    def test_tokens_generated_at_same_time_have_same_timestamp(self):
        with patch("admin.auth.time.time", return_value=1000000):
            token1 = _generate_token("admin")
            token2 = _generate_token("admin")

        assert token1 == token2


class TestValidateToken:
    def test_valid_token_returns_username(self):
        token = _generate_token("admin")

        result = _validate_token(token)

        assert result == "admin"

    def test_expired_token_returns_none(self):
        expired_time = time.time() - (COOKIE_EXPIRY_DAYS * 24 * 60 * 60 + 1)
        with patch("admin.auth.time.time", return_value=expired_time):
            token = _generate_token("admin")

        result = _validate_token(token)

        assert result is None

    def test_invalid_signature_returns_none(self):
        token = _generate_token("admin")
        parts = token.split(":")
        tampered_token = f"{parts[0]}:{parts[1]}:{'a' * 64}"

        result = _validate_token(tampered_token)

        assert result is None

    def test_tampered_username_returns_none(self):
        token = _generate_token("admin")
        parts = token.split(":")
        tampered_token = f"hacker:{parts[1]}:{parts[2]}"

        result = _validate_token(tampered_token)

        assert result is None

    def test_tampered_timestamp_returns_none(self):
        token = _generate_token("admin")
        parts = token.split(":")
        tampered_token = f"{parts[0]}:9999999999:{parts[2]}"

        result = _validate_token(tampered_token)

        assert result is None

    def test_malformed_token_too_few_parts_returns_none(self):
        result = _validate_token("admin:123")

        assert result is None

    def test_malformed_token_too_many_parts_returns_none(self):
        result = _validate_token("admin:123:sig:extra")

        assert result is None

    def test_empty_token_returns_none(self):
        result = _validate_token("")

        assert result is None

    def test_token_with_invalid_timestamp_returns_none(self):
        token = _generate_token("admin")
        parts = token.split(":")
        tampered_token = f"{parts[0]}:not_a_number:{parts[2]}"

        result = _validate_token(tampered_token)

        assert result is None
