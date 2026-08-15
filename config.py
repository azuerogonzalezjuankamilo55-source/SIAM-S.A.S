import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _normalize_db_uri(uri: str | None) -> str | None:
    if not uri:
        return uri
    uri = uri.strip().strip("\"'")
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://") :]
    return uri


def validate_database_url(uri: str) -> None:
    from sqlalchemy.engine.url import make_url

    try:
        make_url(uri)
    except Exception:
        raise ValueError("Invalid DATABASE_URL format")


class Config:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-inseguro")
    SQLALCHEMY_DATABASE_URI: str = _normalize_db_uri(
        os.getenv("DATABASE_URL", "sqlite:///siam_dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
    }
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int | None = 3600
    RATELIMIT_ENABLED: bool = True
    RATELIMIT_STORAGE_URI: str = "memory://"
    RATELIMIT_STRATEGY: str = "moving-window"
    RATELIMIT_DEFAULT: str = "200/hour;20/minute"
    JSON_AS_ASCII: bool = False

    # Límites de subida de archivos (MB), configurables por variables de entorno.
    FILE_MAX_IMAGE_MB: float = float(os.getenv("FILE_MAX_IMAGE_MB", "5"))
    FILE_MAX_VIDEO_MB: float = float(os.getenv("FILE_MAX_VIDEO_MB", "100"))
    FILE_MAX_PDF_MB: float = float(os.getenv("FILE_MAX_PDF_MB", "15"))
    MAX_CONTENT_LENGTH: int = int(
        float(os.getenv("MAX_CONTENT_LENGTH_MB", "110")) * 1024 * 1024
    )


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
    MAX_CONTENT_LENGTH: int = int(
        float(os.getenv("MAX_CONTENT_LENGTH_MB", "110")) * 1024 * 1024
    )
    SEND_FILE_MAX_AGE_DEFAULT: timedelta = timedelta(hours=1)
    RATELIMIT_STORAGE_URI: str = os.getenv(
        "RATELIMIT_STORAGE_URI", "memory://"
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "2")),
        "max_overflow": int(os.getenv("DB_POOL_OVERFLOW", "2")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        "pool_pre_ping": True,
    }

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
        uri = _normalize_db_uri(os.getenv("DATABASE_URL"))
        if uri:
            validate_database_url(uri)


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
