import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Las variables inyectadas por ECS/Docker deben prevalecer sobre el archivo local.
load_dotenv(override=False)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
CHAT_RETENTION_DAYS = int(os.getenv("CHAT_RETENTION_DAYS", "30"))
REDIS_URL = os.getenv("REDIS_URL", "").strip() or None
if not REDIS_URL and os.getenv("REDIS_HOST"):
    redis_scheme = "rediss" if os.getenv("REDIS_TLS", "false").lower() in {"1", "true", "yes", "on"} else "redis"
    redis_password = quote_plus(os.getenv("REDIS_PASSWORD", ""))
    redis_auth = f":{redis_password}@" if redis_password else ""
    REDIS_URL = (
        f"{redis_scheme}://{redis_auth}{os.environ['REDIS_HOST']}:"
        f"{os.getenv('REDIS_PORT', '6379')}/0"
    )
REDIS_CHAT_CHANNEL = os.getenv("REDIS_CHAT_CHANNEL", "servia:chat:events").strip()
REDIS_REQUIRED = os.getenv("REDIS_REQUIRED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and os.getenv("DB_HOST"):
    db_user = quote_plus(os.getenv("DB_USER", "servia_admin"))
    db_password = quote_plus(os.getenv("DB_PASSWORD", ""))
    DATABASE_URL = (
        f"postgresql+asyncpg://{db_user}:{db_password}@{os.environ['DB_HOST']}:"
        f"{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'servia')}"
    )
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurada")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY no está configurada")

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip() or None
AWS_S3_REGION = os.getenv("AWS_S3_REGION", os.getenv("AWS_REGION", "us-east-1"))
S3_PRESIGNED_URL_TTL_SECONDS = int(os.getenv("S3_PRESIGNED_URL_TTL_SECONDS", "3600"))
MAX_PUBLICATION_IMAGE_BYTES = int(os.getenv("MAX_PUBLICATION_IMAGE_BYTES", str(12 * 1024 * 1024)))
SQL_ECHO = os.getenv("SQL_ECHO", "false").strip().lower() in {"1", "true", "yes", "on"}
