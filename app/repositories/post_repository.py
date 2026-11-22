from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.especialidad import Especialidad
from app.models.postulacion import Postulacion
from app.models.publicacion import Publicacion


class PublicacionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Publicacion:
        publicacion = Publicacion(**data)
        self.db.add(publicacion)
        await self.db.commit()
        await self.db.refresh(publicacion)
        return await self.get_by_id(str(publicacion.id))

    async def get_by_id(self, publicacion_id: str) -> Optional[Publicacion]:
        stmt = (
            select(Publicacion)
            .options(
                selectinload(Publicacion.usuario),
                selectinload(Publicacion.categoria),
                selectinload(Publicacion.resenas),
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
        barrio: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        incluir_usuario: bool = True,
        incluir_categoria: bool = True,
    ) -> list[Publicacion]:

        stmt = select(Publicacion)

        options = []
        if incluir_usuario:
            options.append(selectinload(Publicacion.usuario))
        if incluir_categoria:
            options.append(selectinload(Publicacion.categoria))
        options.append(selectinload(Publicacion.resenas))
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

        if barrio:
            stmt = stmt.where(Publicacion.barrio.ilike(f"%{barrio}%"))

        stmt = (
            stmt.order_by(Publicacion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_trabajos_prestador(
        self,
        prestador_id: str,
        estados: list[str],
    ) -> list[dict]:
        stmt = (
            select(Publicacion, Postulacion)
            .join(Postulacion, Postulacion.publicacion_id == Publicacion.id)
            .options(
                selectinload(Publicacion.usuario),
                selectinload(Publicacion.categoria),
                selectinload(Publicacion.resenas),
                selectinload(Postulacion.conversacion),
            )
            .where(
                Postulacion.prestador_id == prestador_id,
                Postulacion.estado == "aceptada",
                Publicacion.estado.in_(estados),
            )
            .order_by(Publicacion.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        trabajos = []
        for pub, post in rows:
            cliente_info = {
                "id": str(pub.usuario.id) if pub.usuario else "",
                "nombre_completo": pub.usuario.nombre_completo if pub.usuario else "Cliente",
                "telefono": pub.usuario.telefono if pub.usuario else "",
                "ubicacion": pub.usuario.ubicacion if pub.usuario else "",
                "foto_perfil": pub.usuario.foto_perfil if pub.usuario else None,
            }
            resena_info = None
            if pub.resenas:
                r = pub.resenas[0]
                resena_info = {
                    "id": str(r.id),
                    "calificacion": r.calificacion,
                    "comentario": r.comentario,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }

            trabajos.append({
                "id": str(pub.id),
                "publicacion_id": str(pub.id),
                "postulacion_id": str(post.id),
                "conversation_id": str(post.conversacion.id_conversacion) if getattr(post, "conversacion", None) else None,
                "cliente_id": str(pub.usuario_id),
                "title": pub.descripcion[:50] + ("..." if len(pub.descripcion) > 50 else ""),
                "description": pub.descripcion,
                "categoria_id": str(pub.categoria_id),
                "categoria_nombre": pub.categoria.nombre if pub.categoria else "Servicio",
                "categoria_icono": pub.categoria.icono if pub.categoria else "construct-outline",
                "client": cliente_info["nombre_completo"],
                "cliente": cliente_info,
                "location": f"{pub.barrio or 'Valledupar'} - {pub.direccion or 'Dirección no especificada'}",
                "direccion": pub.direccion or "Valledupar, Cesar",
                "barrio": pub.barrio or "Valledupar",
                "referencia": pub.referencia or "",
                "schedule": post.disponibilidad,
                "price": float(post.precio_ofertado),
                "precio_ofertado": float(post.precio_ofertado),
                "status": "Completado" if pub.estado == "terminado" else ("En camino" if pub.estado == "en_progreso" else "Acuerdo"),
                "estado": pub.estado,
                "ha_sido_calificada": pub.ha_sido_calificada,
                "resena": resena_info,
                "created_at": pub.created_at.isoformat() if pub.created_at else None,
                "updated_at": pub.updated_at.isoformat() if pub.updated_at else None,
            })
        return trabajos

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
        return await self.get_by_id(publicacion_id)

    async def delete(self, publicacion_id: str) -> Optional[Publicacion]:
        stmt = select(Publicacion).where(Publicacion.id == publicacion_id)
        result = await self.db.execute(stmt)
        publicacion = result.scalar_one_or_none()

        if not publicacion:
            return None

        await self.db.delete(publicacion)
        await self.db.commit()
        return publicacion
