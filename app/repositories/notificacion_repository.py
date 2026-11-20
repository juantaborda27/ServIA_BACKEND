import uuid
from typing import Optional
from sqlalchemy import func, select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import Notificacion


class NotificacionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Notificacion:
        notif = Notificacion(**data)
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def list_by_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[Notificacion]:
        stmt = (
            select(Notificacion)
            .where(Notificacion.usuario_id == user_id)
            .order_by(Notificacion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_unread(self, user_id: str) -> int:
        stmt = (
            select(func.count(Notificacion.id))
            .where(Notificacion.usuario_id == user_id, Notificacion.leida == False)
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_total(self, user_id: str) -> int:
        stmt = (
            select(func.count(Notificacion.id))
            .where(Notificacion.usuario_id == user_id)
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def mark_as_read(self, notif_id: str, user_id: str) -> bool:
        stmt = (
            sa_update(Notificacion)
            .where(Notificacion.id == notif_id, Notificacion.usuario_id == user_id)
            .values(leida=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: str) -> int:
        stmt = (
            sa_update(Notificacion)
            .where(Notificacion.usuario_id == user_id, Notificacion.leida == False)
            .values(leida=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete(self, notif_id: str, user_id: str) -> bool:
        stmt = (
            sa_delete(Notificacion)
            .where(Notificacion.id == notif_id, Notificacion.usuario_id == user_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
