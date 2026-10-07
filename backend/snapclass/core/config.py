"""App configuration.

Every value can be overridden with an environment variable of the same name
(for example JWT_SECRET or DATABASE_URL). Secrets have no defaults on purpose.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Infrastructure
    database_url: str = "postgresql+psycopg://snapclass:snapclass@localhost:5432/snapclass"
    redis_url: str = "redis://localhost:6379/0"
    media_dir: str = "./media"

    # Auth
    jwt_secret: str = Field(min_length=32)  # required, read from the environment
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_limit_per_ip_per_minute: int = 5
    login_limit_per_account_per_hour: int = 10

    # Web
    frontend_url: str = "http://localhost:5173"  # used to build join links
    cors_origins: str = "http://localhost:5173"  # comma separated list

    # Business rules
    join_code_hours: int = 72
    delete_enrollment_media: bool = True  # FR-A7: delete raw photos/audio after embedding
    signed_url_seconds: int = 300
    max_photo_mb: int = 8
    max_audio_mb: int = 10
    stuck_session_minutes: int = 10

    # ML model files (downloaded into the Docker image at build time)
    face_detector_path: str = "models/face_detection_yunet_2023mar.onnx"
    face_recognizer_path: str = "models/face_recognition_sface_2021dec.onnx"

    # Seed data (used only by scripts/seed.py)
    admin_email: str = ""
    admin_password: str = ""

    # Weekly email (optional). If SMTP_HOST is empty the email is only logged.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "snapclass@localhost"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
