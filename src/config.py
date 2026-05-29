from pydantic_settings import BaseSettings, SettingsConfigDict


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

    google_service_account_file: str = "google_key.json"
    google_path_zoomer: str | None = None
    google_path_open21: str | None = None
    google_path_friends: str | None = None

    @property
    def google_exports_enabled(self) -> bool:
        return bool(
            self.google_path_zoomer
            or self.google_path_open21
            or self.google_path_friends
        )


settings = Settings()  # pyright: ignore
