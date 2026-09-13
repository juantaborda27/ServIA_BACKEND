from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.servicio import Servicio


class ServicioRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Servicio:
        servicio = Servicio(**data)
        self.db.add(servicio)
        await self.db.commit()
        await self.db.refresh(servicio)
        return servicio

    async def get_by_id(self, servicio_id: str) -> Optional[Servicio]:
        stmt = select(Servicio).where(Servicio.id == servicio_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, servicio_id: str, data: dict) -> Optional[Servicio]:
        stmt = select(Servicio).where(Servicio.id == servicio_id)
        result = await self.db.execute(stmt)
        servicio = result.scalar_one_or_none()

        if not servicio:
            return None

        for key, value in data.items():
            setattr(servicio, key, value)

        await self.db.commit()
        await self.db.refresh(servicio)
        return servicio

    async def delete(self, servicio_id: str) -> Optional[Servicio]:
        stmt = select(Servicio).where(Servicio.id == servicio_id)
        result = await self.db.execute(stmt)
        servicio = result.scalar_one_or_none()

        if not servicio:
            return None

        await self.db.delete(servicio)
        await self.db.commit()
        return servicio