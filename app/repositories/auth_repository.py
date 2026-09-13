from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.usuario import Usuario  # ajusta el path real a tu modelo
from app.schemas.auth import RegisterRequest
from app.core.security import hash_password


class AuthRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Usuario | None:
        result = await self.db.execute(select(Usuario).where(Usuario.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> Usuario | None:
        result = await self.db.execute(select(Usuario).where(Usuario.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, data: RegisterRequest) -> Usuario:
        nuevo_usuario = Usuario(
            email=data.email,
            hashed_password=hash_password(data.password),
            nombre_completo=data.nombre_completo,
            telefono=data.telefono,
            ubicacion=data.ubicacion,
        )
        self.db.add(nuevo_usuario)
        await self.db.commit()
        await self.db.refresh(nuevo_usuario)
        return nuevo_usuario