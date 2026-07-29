import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _normalize_db_uri(uri: str) -> str:
    if uri and uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


class Config:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-inseguro")
    SQLALCHEMY_DATABASE_URI: str = _normalize_db_uri(
        os.getenv("DATABASE_URL", "sqlite:///siam_dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": 10,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "max_overflow": 20,
    }
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int | None = 3600
    RATELIMIT_ENABLED: bool = True
    RATELIMIT_STORAGE_URI: str = "memory://"
    RATELIMIT_STRATEGY: str = "moving-window"
    RATELIMIT_DEFAULT: str = "200/hour;20/minute"
    JSON_AS_ASCII: bool = False


class DevelopmentConfig(Config):
    DEBUG: bool = True
    WTF_CSRF_ENABLED: bool = True
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
    }


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=8)
    PREFERRED_URL_SCHEME: str = "https"
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024
    SEND_FILE_MAX_AGE_DEFAULT: timedelta = timedelta(hours=1)
    RATELIMIT_STORAGE_URI: str = os.getenv(
        "RATELIMIT_STORAGE_URI", "memory://"
    )

    @classmethod
    def validate(cls) -> None:
        missing: list[str] = []
        if not os.getenv("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not os.getenv("DATABASE_URL"):
            missing.append("DATABASE_URL")
        if missing:
            raise ValueError(
                f"Production requires env vars: {', '.join(missing)}"
            )


class TestingConfig(Config):
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}
    WTF_CSRF_ENABLED: bool = False
    RATELIMIT_ENABLED: bool = False


config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
