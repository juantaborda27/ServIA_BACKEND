from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.especialidad import Especialidad
from app.models.publicacion import Publicacion


class PublicacionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Publicacion:
        publicacion = Publicacion(**data)
        self.db.add(publicacion)
        await self.db.commit()
        await self.db.refresh(publicacion)
        return publicacion

    async def get_by_id(self, publicacion_id: str) -> Optional[Publicacion]:
        stmt = (
            select(Publicacion)
            .options(
                selectinload(Publicacion.usuario),
                selectinload(Publicacion.categoria),
            )
            .where(Publicacion.id == publicacion_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        prestador_id: Optional[str] = None,
        estado: Optional[str] = None,
        categoria_id: Optional[str] = None,
        usuario_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        incluir_usuario: bool = False,
        incluir_categoria: bool = False,
    ) -> list[Publicacion]:

        stmt = select(Publicacion)

        options = []
        if incluir_usuario:
            options.append(selectinload(Publicacion.usuario))
        if incluir_categoria:
            options.append(selectinload(Publicacion.categoria))
        if options:
            stmt = stmt.options(*options)

        if prestador_id:
            # 1. Categorías en las que el prestador tiene especialidad
            especialidades_stmt = select(Especialidad.categoria_id).where(
                Especialidad.prestador_id == prestador_id
            )
            result = await self.db.execute(especialidades_stmt)
            categoria_ids = [row[0] for row in result.all()]

            if not categoria_ids:
                return []  # sin especialidades declaradas -> no ve nada

            # 2. Filtramos publicaciones solo dentro de esas categorías
            stmt = stmt.where(Publicacion.categoria_id.in_(categoria_ids))

        if estado:
            stmt = stmt.where(Publicacion.estado == estado)

        if categoria_id:
            stmt = stmt.where(Publicacion.categoria_id == categoria_id)

        if usuario_id:
            stmt = stmt.where(Publicacion.usuario_id == usuario_id)

        stmt = (
            stmt.order_by(Publicacion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, publicacion_id: str, data: dict) -> Optional[Publicacion]:
        stmt = select(Publicacion).where(Publicacion.id == publicacion_id)
        result = await self.db.execute(stmt)
        publicacion = result.scalar_one_or_none()

        if not publicacion:
            return None

        for key, value in data.items():
            setattr(publicacion, key, value)

        await self.db.commit()
        await self.db.refresh(publicacion)
        return publicacion

    async def delete(self, publicacion_id: str) -> Optional[Publicacion]:
        stmt = select(Publicacion).where(Publicacion.id == publicacion_id)
        result = await self.db.execute(stmt)
        publicacion = result.scalar_one_or_none()

        if not publicacion:
            return None

        await self.db.delete(publicacion)
        await self.db.commit()
        return publicacion