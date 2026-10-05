from unittest.mock import patch

from admin.auth import get_allowed_bot_id, verify_credentials
from config import Settings


class TestScopedAdminUsersConfig:
    def test_parses_single_user(self):
        s = Settings(
            postgres_dsn="postgresql://x",
            admin_scoped_users="svoi:secret:8713389924",
        )
        users = s.scoped_admin_users()
        assert users["svoi"].password == "secret"
        assert users["svoi"].bot_id == 8713389924

    def test_parses_multiple_users(self):
        s = Settings(
            postgres_dsn="postgresql://x",
            admin_scoped_users="a:1:111; b:2:222",
        )
        users = s.scoped_admin_users()
        assert users["a"].bot_id == 111
        assert users["b"].bot_id == 222


class TestVerifyCredentials:
    def test_admin_full_access(self):
        with patch("admin.auth.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            mock_settings.admin_password = "pass"
            mock_settings.scoped_admin_users.return_value = {}
            assert verify_credentials("admin", "pass") is True
            assert verify_credentials("admin", "wrong") is False

    def test_scoped_user(self):
        from config import AdminScopedUser

        with patch("admin.auth.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            mock_settings.admin_password = "pass"
            mock_settings.scoped_admin_users.return_value = {
                "svoi": AdminScopedUser(password="svoi", bot_id=8713389924),
            }
            assert verify_credentials("svoi", "svoi") is True
            assert verify_credentials("svoi", "wrong") is False


class TestGetAllowedBotId:
    def test_admin_sees_all_bots(self):
        with patch("admin.auth.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            mock_settings.scoped_admin_users.return_value = {}
            assert get_allowed_bot_id("admin") is None

    def test_scoped_user_fixed_bot(self):
        from config import AdminScopedUser

        with patch("admin.auth.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            mock_settings.scoped_admin_users.return_value = {
                "svoi": AdminScopedUser(password="svoi", bot_id=8713389924),
            }
            assert get_allowed_bot_id("svoi") == 8713389924
