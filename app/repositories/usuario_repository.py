from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usuario import Usuario


class UsuarioRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[Usuario]:
        stmt = select(Usuario).where(Usuario.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user_id: str, data: dict) -> Optional[Usuario]:
        stmt = select(Usuario).where(Usuario.id == user_id)
        result = await self.db.execute(stmt)
        usuario = result.scalar_one_or_none()

        if not usuario:
            return None

        for key, value in data.items():
            setattr(usuario, key, value)

        await self.db.commit()
        await self.db.refresh(usuario)
        return usuario

    async def delete(self, user_id: str) -> Optional[Usuario]:
        """Soft delete: marca al usuario como inactivo en vez de borrar el registro."""
        return await self.update(user_id, {"activo": False})