import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import CHAT_RETENTION_DAYS
from app.models.conversacion import Conversacion
from app.models.mensaje import Mensaje
from app.models.postulacion import Postulacion
from app.models.prestador import Prestador
from app.models.publicacion import Publicacion


class ConversacionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self, conversacion_id: uuid.UUID
    ) -> Optional[Conversacion]:
        stmt = (
            select(Conversacion)
            .options(
                selectinload(Conversacion.mensajes),
                selectinload(Conversacion.postulacion).selectinload(Postulacion.publicacion).selectinload(Publicacion.usuario),
                selectinload(Conversacion.postulacion).selectinload(Postulacion.prestador).selectinload(Prestador.usuario),
            )
            .where(Conversacion.id_conversacion == conversacion_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        rol: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversacion]:
        stmt = (
            select(Conversacion)
            .join(Postulacion, Conversacion.id_postulacion == Postulacion.id)
            .join(Publicacion, Postulacion.publicacion_id == Publicacion.id)
            .options(
                selectinload(Conversacion.mensajes),
                selectinload(Conversacion.postulacion).selectinload(Postulacion.publicacion).selectinload(Publicacion.usuario),
                selectinload(Conversacion.postulacion).selectinload(Postulacion.prestador).selectinload(Prestador.usuario),
            )
        )

        if rol == "cliente":
            stmt = stmt.where(Publicacion.usuario_id == user_id)
        elif rol == "profesional":
            stmt = stmt.where(Postulacion.prestador_id == user_id)
        else:
            stmt = stmt.where(
                or_(Publicacion.usuario_id == user_id, Postulacion.prestador_id == user_id)
            )

        if estado:
            stmt = stmt.where(Conversacion.estado == estado)

        stmt = stmt.order_by(Conversacion.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_estado(
        self,
        conversacion_id: uuid.UUID,
        nuevo_estado: str,
    ) -> Optional[Conversacion]:
        stmt = select(Conversacion).where(
            Conversacion.id_conversacion == conversacion_id
        )
        result = await self.db.execute(stmt)
        conversacion = result.scalar_one_or_none()

        if conversacion is None:
            return None

        conversacion.estado = nuevo_estado
        if nuevo_estado == "cerrada":
            now = datetime.now(timezone.utc)
            conversacion.closed_at = now
            conversacion.delete_after = now + timedelta(days=CHAT_RETENTION_DAYS)
        else:
            conversacion.closed_at = None
            conversacion.delete_after = None

        await self.db.commit()
        await self.db.refresh(conversacion)
        return conversacion

    async def limpiar_expiradas(self) -> dict:
        now = datetime.now(timezone.utc)
        stmt = select(Conversacion).where(
            Conversacion.estado == "cerrada",
            Conversacion.delete_after.is_not(None),
            Conversacion.delete_after <= now,
        )
        conversaciones = list((await self.db.execute(stmt)).scalars().all())
        if not conversaciones:
            return {"conversaciones_eliminadas": 0, "mensajes_eliminados": 0}

        conv_ids = [c.id_conversacion for c in conversaciones]
        del_msgs = await self.db.execute(
            sa_delete(Mensaje).where(Mensaje.id_conversacion.in_(conv_ids))
        )
        del_convs = await self.db.execute(
            sa_delete(Conversacion).where(Conversacion.id_conversacion.in_(conv_ids))
        )
        await self.db.commit()
        return {
            "conversaciones_eliminadas": del_convs.rowcount or 0,
            "mensajes_eliminados": del_msgs.rowcount or 0,
        }
