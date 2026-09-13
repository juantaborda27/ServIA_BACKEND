from typing import Optional

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postulacion import Postulacion
from app.models.prestador import Prestador


class PostulacionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Postulacion:
        data["estado"] = "pendiente"
        postulacion = Postulacion(**data)
        self.db.add(postulacion)
        await self.db.commit()
        await self.db.refresh(postulacion)
        return postulacion

    async def get_by_id(self, postulacion_id: str) -> Optional[Postulacion]:
        stmt = (
            select(Postulacion)
            .options(
                # nombre_completo/telefono/foto_perfil viven en usuarios,
                # por eso bajamos un nivel más: prestador -> usuario
                selectinload(Postulacion.prestador).selectinload(Prestador.usuario),
                selectinload(Postulacion.publicacion),
            )
            .where(Postulacion.id == postulacion_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        publicacion_id: Optional[str] = None,
        prestador_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        incluir_prestador: bool = False,
    ) -> list[Postulacion]:

        stmt = select(Postulacion)

        if incluir_prestador:
            stmt = stmt.options(
                selectinload(Postulacion.prestador).selectinload(Prestador.usuario)
            )

        if publicacion_id:
            stmt = stmt.where(Postulacion.publicacion_id == publicacion_id)

        if prestador_id:
            stmt = stmt.where(Postulacion.prestador_id == prestador_id)

        if estado:
            stmt = stmt.where(Postulacion.estado == estado)

        stmt = (
            stmt.order_by(Postulacion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_activa(
        self, publicacion_id: str, prestador_id: str
    ) -> Optional[Postulacion]:
        """Busca si el prestador ya tiene una postulación activa
        (pendiente/en_espera) para esta publicación."""

        stmt = (
            select(Postulacion)
            .where(Postulacion.publicacion_id == publicacion_id)
            .where(Postulacion.prestador_id == prestador_id)
            .where(Postulacion.estado.in_(["pendiente", "en_espera"]))
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def update(self, postulacion_id: str, data: dict) -> Optional[Postulacion]:
        stmt = select(Postulacion).where(Postulacion.id == postulacion_id)
        result = await self.db.execute(stmt)
        postulacion = result.scalar_one_or_none()

        if not postulacion:
            return None

        for key, value in data.items():
            setattr(postulacion, key, value)

        await self.db.commit()
        await self.db.refresh(postulacion)
        return postulacion

    async def poner_en_espera_otras(
        self, publicacion_id: str, postulacion_id_aceptada: str
    ) -> list[Postulacion]:
        """Al aceptar una oferta, las demás pendientes quedan en espera
        (no rechazadas), por si el cliente se arrepiente y quiere volver
        a considerarlas."""

        stmt = (
            sa_update(Postulacion)
            .where(Postulacion.publicacion_id == publicacion_id)
            .where(Postulacion.id != postulacion_id_aceptada)
            .where(Postulacion.estado == "pendiente")
            .values(estado="en_espera")
            .returning(Postulacion)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return list(result.scalars().all())

    async def delete(self, postulacion_id: str) -> Optional[Postulacion]:
        stmt = select(Postulacion).where(Postulacion.id == postulacion_id)
        result = await self.db.execute(stmt)
        postulacion = result.scalar_one_or_none()

        if not postulacion:
            return None

        await self.db.delete(postulacion)
        await self.db.commit()
        return postulacion