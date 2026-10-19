import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:PasswordSegura123@localhost:5432/servia_db")
# Asegurar compatibilidad con driver asíncrono asyncpg si viene en formato postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "_Av13cu#7-LfUNXa+xMUz6Y")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurada")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY no está configurada")
