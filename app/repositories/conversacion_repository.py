
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversacion import Conversacion


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
                selectinload(Conversacion.postulacion),
            )
            .where(
                Conversacion.id_conversacion == conversacion_id
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversacion]:

        stmt = select(Conversacion).options(
            selectinload(Conversacion.postulacion)
        )

        if estado:
            stmt = stmt.where(Conversacion.estado == estado)

        stmt = stmt.offset(offset).limit(limit)

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

        await self.db.commit()
        await self.db.refresh(conversacion)

        return conversacion
