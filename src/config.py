from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class AdminScopedUser:
    password: str
    bot_id: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_dsn: str

    api_key: str | None = None

    # Admin panel settings
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_cookie_secret: str = "default-secret-change-in-production"
    # Ограниченные пользователи: login:password:bot_id через «;»
    admin_scoped_users: str = ""

    def scoped_admin_users(self) -> dict[str, AdminScopedUser]:
        """Парсит ADMIN_SCOPED_USERS."""
        result: dict[str, AdminScopedUser] = {}
        raw = self.admin_scoped_users.strip()
        if not raw:
            return result
        for entry in raw.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) != 3:
                continue
            login, password, bot_id_str = parts
            login = login.strip()
            if not login:
                continue
            result[login] = AdminScopedUser(
                password=password, bot_id=int(bot_id_str.strip())
            )
        return result

    google_service_account_file: str = "google_key.json"
    google_path_zoomer: str | None = None
    google_path_open21: str | None = None
    google_path_friends: str | None = None
    google_path_social: str | None = None

    @property
    def google_exports_enabled(self) -> bool:
        return bool(
            self.google_path_zoomer
            or self.google_path_open21
            or self.google_path_friends
            or self.google_path_social
        )


settings = Settings()  # pyright: ignore
