from typing import Optional

from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postulacion import Postulacion
from app.models.prestador import Prestador
from app.models.publicacion import Publicacion
from app.models.resena import Resena
from app.models.usuario import Usuario


class ResenaRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Resena:
        resena = Resena(**data)
        self.db.add(resena)
        # Marcamos la publicación como calificada
        pub_stmt = (
            sa_update(Publicacion)
            .where(Publicacion.id == data["publicacion_id"])
            .values(ha_sido_calificada=True)
        )
        await self.db.execute(pub_stmt)
        await self.db.commit()
        await self.db.refresh(resena)
        return await self.get_by_id(str(resena.id))

    async def get_by_id(self, resena_id: str) -> Optional[Resena]:
        stmt = (
            select(Resena)
            .options(
                selectinload(Resena.cliente),
                selectinload(Resena.publicacion),
                selectinload(Resena.prestador).selectinload(Prestador.usuario),
            )
            .where(Resena.id == resena_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_publicacion_id(self, publicacion_id: str) -> Optional[Resena]:
        stmt = (
            select(Resena)
            .options(
                selectinload(Resena.cliente),
                selectinload(Resena.prestador).selectinload(Prestador.usuario),
            )
            .where(Resena.publicacion_id == publicacion_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_prestador(
        self, prestador_id: str, limit: int = 50, offset: int = 0
    ) -> list[Resena]:
        stmt = (
            select(Resena)
            .options(
                selectinload(Resena.cliente),
                selectinload(Resena.publicacion),
            )
            .where(Resena.prestador_id == prestador_id)
            .order_by(Resena.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_resumen_prestador(self, prestador_id: str) -> dict:
        stmt = (
            select(
                func.coalesce(func.avg(Resena.calificacion), 0.0).label("promedio"),
                func.count(Resena.id).label("total"),
            )
            .where(Resena.prestador_id == prestador_id)
        )
        result = await self.db.execute(stmt)
        row = result.one()
        return {
            "promedio": round(float(row.promedio), 1),
            "total_resenas": int(row.total),
        }

    async def get_resena_pendiente_cliente(self, cliente_id: str) -> Optional[dict]:
        """Busca si el cliente tiene alguna publicación finalizada que NO haya calificado aún."""
        stmt = (
            select(Publicacion, Postulacion)
            .join(Postulacion, Postulacion.publicacion_id == Publicacion.id)
            .options(
                selectinload(Publicacion.categoria),
                selectinload(Postulacion.prestador).selectinload(Prestador.usuario),
            )
            .where(
                Publicacion.usuario_id == cliente_id,
                Publicacion.estado == "terminado",
                Publicacion.ha_sido_calificada == False,
                Postulacion.estado == "aceptada",
            )
            .order_by(Publicacion.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        first_row = result.first()
        if not first_row:
            return None

        pub, post = first_row
        prestador_user = post.prestador.usuario if post.prestador else None
        return {
            "publicacion_id": str(pub.id),
            "titulo": pub.descripcion[:60],
            "descripcion": pub.descripcion,
            "categoria": {
                "id": str(pub.categoria.id) if pub.categoria else str(pub.categoria_id),
                "nombre": pub.categoria.nombre if pub.categoria else "Servicio",
                "icono": (pub.categoria.icono or "construct-outline") if pub.categoria else "construct-outline",
            },
            "prestador_id": str(post.prestador_id),
            "prestador_nombre": prestador_user.nombre_completo if prestador_user else "Profesional",
            "prestador_foto": prestador_user.foto_perfil if prestador_user else None,
            "precio_acordado": float(post.precio_ofertado),
            "fecha": pub.updated_at.isoformat() if pub.updated_at else None,
        }
