from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import CHAT_RETENTION_DAYS
from app.core.ubicacion import distancia_km
from app.models.conversacion import Conversacion
from app.models.especialidad import Especialidad
from app.models.notificacion import Notificacion
from app.models.postulacion import Postulacion
from app.models.prestador import Prestador
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
            .where(Postulacion.prestador_id == prestador_id)
            .order_by(Publicacion.updated_at.desc())
        )
        if "cancelado" in estados:
            stmt = stmt.where(
                or_(
                    and_(
                        Postulacion.estado == "aceptada",
                        Publicacion.estado.in_(estados),
                    ),
                    and_(
                        Publicacion.estado == "cancelado",
                        Postulacion.conversacion.has(),
                    ),
                )
            )
        else:
            stmt = stmt.where(
                Postulacion.estado == "aceptada",
                Publicacion.estado.in_(estados),
            )
        result = await self.db.execute(stmt)
        rows = result.all()
        prestador = await self.db.get(Prestador, prestador_id) if rows else None

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
                "categoria": {
                    "id": str(pub.categoria.id) if pub.categoria else str(pub.categoria_id),
                    "nombre": pub.categoria.nombre if pub.categoria else "Servicio",
                    "icono": (pub.categoria.icono or "construct-outline") if pub.categoria else "construct-outline",
                },
                "client": cliente_info["nombre_completo"],
                "cliente": cliente_info,
                "location": f"{pub.barrio or 'Valledupar'} - {pub.direccion or 'Dirección no especificada'}",
                "direccion": pub.direccion or "Valledupar, Cesar",
                "barrio": pub.barrio or "Valledupar",
                "referencia": pub.referencia or "",
                "distancia_km": distancia_km(prestador, pub),
                "schedule": post.disponibilidad,
                "price": float(post.precio_ofertado),
                "precio_ofertado": float(post.precio_ofertado),
                "status": (
                    "Completado"
                    if pub.estado == "terminado"
                    else (
                        "Cancelado"
                        if pub.estado == "cancelado"
                        else (
                            "Pendiente de confirmaciÃ³n"
                            if pub.estado == "pendiente_confirmacion"
                            else ("En progreso" if pub.estado == "en_progreso" else "Acuerdo")
                        )
                    )
                ),
                "estado": pub.estado,
                "postulacion_estado": post.estado,
                "can_start": pub.estado == "acuerdo",
                "can_complete": pub.estado == "en_progreso",
                "awaiting_client_confirmation": pub.estado == "pendiente_confirmacion",
                "can_cancel": pub.estado in ("acuerdo", "en_progreso", "pendiente_confirmacion"),
                "started_at": pub.started_at.isoformat() if pub.started_at else None,
                "completion_requested_at": pub.completion_requested_at.isoformat() if pub.completion_requested_at else None,
                "completed_at": pub.completed_at.isoformat() if pub.completed_at else None,
                "cancelled_at": pub.cancelled_at.isoformat() if pub.cancelled_at else None,
                "cancellation_reason": pub.cancellation_reason,
                "ha_sido_calificada": pub.ha_sido_calificada,
                "resena": resena_info,
                "created_at": pub.created_at.isoformat() if pub.created_at else None,
                "updated_at": pub.updated_at.isoformat() if pub.updated_at else None,
            })
        return trabajos

    async def update(self, publicacion_id: str, data: dict) -> Optional[Publicacion]:
        stmt = select(Publicacion).where(Publicacion.id == publicacion_id)
        changes_location = bool(
            {"latitud", "longitud", "direccion", "barrio", "ciudad", "referencia"} & data.keys()
        )
        if changes_location:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        publicacion = result.scalar_one_or_none()

        if not publicacion:
            return None

        if changes_location and publicacion.estado != "activo":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La ubicación solo se puede corregir mientras la solicitud está abierta.",
            )

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

    async def get_postulacion_aceptada(self, publicacion_id: str) -> Optional[Postulacion]:
        stmt = (
            select(Postulacion)
            .where(
                Postulacion.publicacion_id == publicacion_id,
                Postulacion.estado == "aceptada",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _reactivar_ofertas_prestador(self, prestador_id) -> None:
        publicaciones_activas = select(Publicacion.id).where(Publicacion.estado == "activo")
        await self.db.execute(
            sa_update(Postulacion)
            .where(
                Postulacion.prestador_id == prestador_id,
                Postulacion.estado == "en_espera",
                Postulacion.publicacion_id.in_(publicaciones_activas),
            )
            .values(estado="pendiente")
        )

    async def iniciar_trabajo_atomico(self, publicacion_id: str, user_id: str) -> Publicacion:
        try:
            stmt = (
                select(Publicacion)
                .where(Publicacion.id == publicacion_id)
                .with_for_update()
            )
            pub = (await self.db.execute(stmt)).scalar_one_or_none()
            if not pub:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

            post_aceptada = await self.get_postulacion_aceptada(publicacion_id)
            if not post_aceptada or str(post_aceptada.prestador_id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo el prestador asignado puede iniciar este servicio",
                )

            if pub.estado != "acuerdo":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede iniciar el servicio desde el estado '{pub.estado}'",
                )

            pub.estado = "en_progreso"
            pub.started_at = datetime.now(timezone.utc)

            notif = Notificacion(
                usuario_id=pub.usuario_id,
                titulo="¡El prestador ha iniciado el servicio!",
                mensaje="Tu servicio ya se encuentra en progreso.",
                tipo="servicio_iniciado",
                referencia_id=str(pub.id),
                data={
                    "role": "cliente",
                    "destination": "job_detail",
                    "publication_id": str(pub.id),
                },
            )
            self.db.add(notif)
            await self.db.commit()
            return await self.get_by_id(publicacion_id)
        except Exception:
            await self.db.rollback()
            raise

    async def solicitar_finalizacion_atomico(self, publicacion_id: str, user_id: str) -> Publicacion:
        try:
            stmt = (
                select(Publicacion)
                .where(Publicacion.id == publicacion_id)
                .with_for_update()
            )
            pub = (await self.db.execute(stmt)).scalar_one_or_none()
            if not pub:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

            post_aceptada = await self.get_postulacion_aceptada(publicacion_id)
            es_prestador = post_aceptada is not None and str(post_aceptada.prestador_id) == str(user_id)
            if not es_prestador:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo el profesional asignado puede reportar la finalizaciÃ³n",
                )

            if pub.estado != "en_progreso":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede completar el servicio desde el estado '{pub.estado}'",
                )

            pub.estado = "pendiente_confirmacion"
            pub.completion_requested_at = datetime.now(timezone.utc)

            self.db.add(
                Notificacion(
                    usuario_id=pub.usuario_id,
                    titulo="Confirma la finalizaciÃ³n del servicio",
                    mensaje="El profesional reportÃ³ que el trabajo terminÃ³. Revisa y confirma la finalizaciÃ³n.",
                    tipo="finalizacion_pendiente",
                    referencia_id=str(pub.id),
                    data={
                        "role": "cliente",
                        "destination": "job_detail",
                        "publication_id": str(pub.id),
                        "provider_id": str(post_aceptada.prestador_id),
                    },
                )
            )

            await self.db.commit()
            return await self.get_by_id(publicacion_id)
        except Exception:
            await self.db.rollback()
            raise

    async def confirmar_finalizacion_atomico(self, publicacion_id: str, user_id: str) -> Publicacion:
        try:
            pub = (
                await self.db.execute(
                    select(Publicacion)
                    .where(Publicacion.id == publicacion_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not pub:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PublicaciÃ³n no encontrada",
                )

            if str(pub.usuario_id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo el cliente propietario puede confirmar la finalizaciÃ³n",
                )
            if pub.estado != "pendiente_confirmacion":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede confirmar la finalizaciÃ³n desde el estado '{pub.estado}'",
                )

            post_aceptada = await self.get_postulacion_aceptada(publicacion_id)
            if not post_aceptada:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La publicaciÃ³n no tiene un profesional asignado",
                )

            now = datetime.now(timezone.utc)
            pub.estado = "terminado"
            pub.completed_at = now

            prestador = (
                await self.db.execute(
                    select(Prestador)
                    .where(Prestador.id == post_aceptada.prestador_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if prestador:
                prestador.disponible = True
                await self._reactivar_ofertas_prestador(prestador.id)

            conv = (
                await self.db.execute(
                    select(Conversacion)
                    .where(Conversacion.id_postulacion == post_aceptada.id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if conv and conv.estado != "cerrada":
                conv.estado = "cerrada"
                conv.closed_at = now
                conv.delete_after = now + timedelta(days=CHAT_RETENTION_DAYS)

            self.db.add(
                Notificacion(
                    usuario_id=post_aceptada.prestador_id,
                    titulo="FinalizaciÃ³n confirmada",
                    mensaje="El cliente confirmÃ³ que el servicio finalizÃ³ correctamente.",
                    tipo="servicio_completado",
                    referencia_id=str(pub.id),
                    data={
                        "role": "profesional",
                        "destination": "job_detail",
                        "publication_id": str(pub.id),
                    },
                )
            )

            await self.db.commit()
            return await self.get_by_id(publicacion_id)
        except Exception:
            await self.db.rollback()
            raise

    async def cancelar_trabajo_atomico(
        self,
        publicacion_id: str,
        user_id: str,
        motivo: Optional[str] = None,
    ) -> Publicacion:
        try:
            stmt = (
                select(Publicacion)
                .where(Publicacion.id == publicacion_id)
                .with_for_update()
            )
            pub = (await self.db.execute(stmt)).scalar_one_or_none()
            if not pub:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

            if pub.estado not in ("activo", "acuerdo", "en_progreso", "pendiente_confirmacion"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede cancelar el servicio desde el estado '{pub.estado}'",
                )

            post_aceptada = await self.get_postulacion_aceptada(publicacion_id)
            es_cliente = str(pub.usuario_id) == str(user_id)
            es_prestador = post_aceptada is not None and str(post_aceptada.prestador_id) == str(user_id)

            if pub.estado == "activo":
                if not es_cliente:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Solo el propietario puede cancelar una publicación activa",
                    )
            else:
                if not (es_cliente or es_prestador):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes permiso para cancelar este servicio",
                    )

            now = datetime.now(timezone.utc)
            pub.estado = "cancelado"
            pub.cancelled_at = now
            pub.cancelled_by = user_id
            pub.cancellation_reason = motivo

            await self.db.execute(
                sa_update(Postulacion)
                .where(
                    Postulacion.publicacion_id == pub.id,
                    Postulacion.estado.in_(["pendiente", "en_espera", "aceptada"]),
                )
                .values(estado="rechazada")
            )

            if post_aceptada:
                prestador = (
                    await self.db.execute(
                        select(Prestador)
                        .where(Prestador.id == post_aceptada.prestador_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if prestador:
                    prestador.disponible = True
                    await self._reactivar_ofertas_prestador(prestador.id)

                conv = (
                    await self.db.execute(
                        select(Conversacion)
                        .where(Conversacion.id_postulacion == post_aceptada.id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if conv and conv.estado != "cerrada":
                    conv.estado = "cerrada"
                    conv.closed_at = now
                    conv.delete_after = now + timedelta(days=CHAT_RETENTION_DAYS)

                destinations = (
                    (pub.usuario_id, "cliente"),
                    (post_aceptada.prestador_id, "profesional"),
                )
                for dest_uid, role in destinations:
                    self.db.add(
                        Notificacion(
                            usuario_id=dest_uid,
                            titulo="Servicio cancelado",
                            mensaje=motivo or "El servicio ha sido cancelado.",
                            tipo="servicio_cancelado",
                            referencia_id=str(pub.id),
                            data={
                                "role": role,
                                "destination": "job_detail",
                                "publication_id": str(pub.id),
                            },
                        )
                    )

            await self.db.commit()
            return await self.get_by_id(publicacion_id)
        except Exception:
            await self.db.rollback()
            raise
