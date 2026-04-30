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


settings = Settings()  # pyright: ignore
