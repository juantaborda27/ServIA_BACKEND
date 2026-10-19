
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mensaje import Mensaje


class MensajeRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Mensaje:
        mensaje = Mensaje(**data)

        try:
            self.db.add(mensaje)
            await self.db.commit()
            await self.db.refresh(mensaje)
            return mensaje
        except Exception:
            await self.db.rollback()
            raise

    async def get_by_conversacion(
        self,
        conversacion_id: uuid.UUID,
    ) -> list[Mensaje]:

        stmt = (
            select(Mensaje)
            .options(
                selectinload(Mensaje.remitente),
                selectinload(Mensaje.destinatario),
            )
            .where(Mensaje.id_conversacion == conversacion_id)
            .order_by(Mensaje.fecha_hora.asc())
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
