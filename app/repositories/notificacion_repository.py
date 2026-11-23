import uuid
from typing import Optional
from sqlalchemy import and_, func, or_, select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import Notificacion


class NotificacionRepository:

    ROLE_FALLBACK_TYPES = {
        "cliente": {
            "oferta_recibida",
            "postulacion_retirada",
            "servicio_iniciado",
            "servicio_completado",
            "servicio_cancelado",
        },
        "profesional": {"oferta_aceptada", "calificacion_recibida", "servicio_cancelado"},
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Notificacion:
        notif = Notificacion(**data)
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    def _role_condition(self, rol: str):
        stored_role = Notificacion.data["role"].astext
        return or_(
            stored_role == rol,
            and_(
                stored_role.is_(None),
                Notificacion.tipo.in_(self.ROLE_FALLBACK_TYPES.get(rol, set())),
            ),
        )

    async def list_by_user(
        self, user_id: str, rol: str, limit: int = 50, offset: int = 0
    ) -> list[Notificacion]:
        stmt = (
            select(Notificacion)
            .where(Notificacion.usuario_id == user_id, self._role_condition(rol))
            .order_by(Notificacion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_unread(self, user_id: str, rol: str) -> int:
        stmt = (
            select(func.count(Notificacion.id))
            .where(
                Notificacion.usuario_id == user_id,
                Notificacion.leida == False,
                self._role_condition(rol),
            )
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_total(self, user_id: str, rol: str) -> int:
        stmt = (
            select(func.count(Notificacion.id))
            .where(Notificacion.usuario_id == user_id, self._role_condition(rol))
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def mark_as_read(self, notif_id: str, user_id: str, rol: str) -> bool:
        stmt = (
            sa_update(Notificacion)
            .where(
                Notificacion.id == notif_id,
                Notificacion.usuario_id == user_id,
                self._role_condition(rol),
            )
            .values(leida=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: str, rol: str) -> int:
        stmt = (
            sa_update(Notificacion)
            .where(
                Notificacion.usuario_id == user_id,
                Notificacion.leida == False,
                self._role_condition(rol),
            )
            .values(leida=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete(self, notif_id: str, user_id: str, rol: str) -> bool:
        stmt = (
            sa_delete(Notificacion)
            .where(
                Notificacion.id == notif_id,
                Notificacion.usuario_id == user_id,
                self._role_condition(rol),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
