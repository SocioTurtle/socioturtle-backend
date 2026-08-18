from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Socioturtle"
    environment: str = "development"
    debug: bool = True

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    database_url: str = "sqlite:///./socioturtle.db"

    captcha_provider: str = "local"
    captcha_ttl_seconds: int = 300
    hcaptcha_secret: str = ""

    otp_ttl_seconds: int = 600  # 10 minutes
    otp_resend_cooldown_seconds: int = 30
    otp_max_attempts: int = 5
    otp_verified_window_minutes: int = 15  # how long a verified email stays usable to register

    log_level: str = "INFO"
    log_json: bool = True
    log_file: str | None = "logs/app.log"

    cors_origins: list[str] = ["http://localhost:5173"]

    # Public URLs used to build links inside emails. Must be absolute and
    # externally reachable — a localhost value produces dead invite links.
    public_app_url: str = "http://localhost:5173"
    public_api_url: str = "http://127.0.0.1:8000"

    # console | smtp | resend
    email_backend: str = "console"
    email_from: str = "admin@socioturtle.com"
    email_from_name: str = "SocioTurtle"
    email_reply_to: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    resend_api_key: str = ""

    invite_ttl_hours: int = 168  # 7 days
    newsletter_batch_pause_seconds: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()
