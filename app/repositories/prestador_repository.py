from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.especialidad import Especialidad
from app.models.prestador import Prestador


class PrestadorRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Prestador:
        prestador = Prestador(**data)
        self.db.add(prestador)
        await self.db.commit()
        await self.db.refresh(prestador)
        return prestador

    async def get_by_id(self, prestador_id: str) -> Optional[Prestador]:
        stmt = (
            select(Prestador)
            .options(
                selectinload(Prestador.usuario),
                selectinload(Prestador.especialidades).selectinload(
                    Especialidad.categoria
                ),
            )
            .where(Prestador.id == prestador_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        disponible: Optional[bool] = None,
        verificado: Optional[bool] = None,
        categoria_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Prestador]:

        stmt = select(Prestador).options(
            selectinload(Prestador.usuario),
            selectinload(Prestador.especialidades).selectinload(Especialidad.categoria),
        )

        if disponible is not None:
            stmt = stmt.where(Prestador.disponible == disponible)

        if verificado is not None:
            stmt = stmt.where(Prestador.verificado == verificado)

        if categoria_id:
            # Subquery en vez de JOIN para no duplicar filas de Prestador
            subq = select(Especialidad.prestador_id).where(
                Especialidad.categoria_id == categoria_id
            )
            stmt = stmt.where(Prestador.id.in_(subq))

        stmt = (
            stmt.order_by(Prestador.fecha_creacion.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, prestador_id: str, data: dict) -> Optional[Prestador]:
        stmt = select(Prestador).where(Prestador.id == prestador_id)
        result = await self.db.execute(stmt)
        prestador = result.scalar_one_or_none()

        if not prestador:
            return None

        for key, value in data.items():
            setattr(prestador, key, value)

        await self.db.commit()
        await self.db.refresh(prestador)
        return prestador

    async def delete(self, prestador_id: str) -> Optional[Prestador]:
        stmt = select(Prestador).where(Prestador.id == prestador_id)
        result = await self.db.execute(stmt)
        prestador = result.scalar_one_or_none()

        if not prestador:
            return None

        await self.db.delete(prestador)
        await self.db.commit()
        return prestador

    # --- Manejo de especialidades (tabla intermedia) ---

    async def add_especialidades(
        self, prestador_id: str, categoria_ids: list[str]
    ) -> list[Especialidad]:

        especialidades = [
            Especialidad(prestador_id=prestador_id, categoria_id=categoria_id)
            for categoria_id in categoria_ids
        ]

        self.db.add_all(especialidades)
        await self.db.commit()

        for especialidad in especialidades:
            await self.db.refresh(especialidad)

        return especialidades

    async def replace_especialidades(
        self, prestador_id: str, categoria_ids: list[str]
    ) -> list[Especialidad]:

        # Elimina las especialidades actuales del prestador
        await self.db.execute(
            sa_delete(Especialidad).where(Especialidad.prestador_id == prestador_id)
        )
        await self.db.commit()

        # Inserta las nuevas
        if not categoria_ids:
            return []

        return await self.add_especialidades(prestador_id, categoria_ids)

    async def remove_especialidad(
        self, prestador_id: str, categoria_id: str
    ) -> list[Especialidad]:

        stmt = (
            sa_delete(Especialidad)
            .where(Especialidad.prestador_id == prestador_id)
            .where(Especialidad.categoria_id == categoria_id)
            .returning(Especialidad)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return list(result.scalars().all())