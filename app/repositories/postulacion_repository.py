from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversacion import Conversacion
from app.models.especialidad import Especialidad
from app.models.notificacion import Notificacion
from app.models.postulacion import Postulacion
from app.models.prestador import Prestador
from app.models.publicacion import Publicacion


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

        stmt = select(Postulacion).options(
            selectinload(Postulacion.conversacion)
        )

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

    async def actualizar_estado_publicacion(self, publicacion_id: str, nuevo_estado: str):
        from app.models.publicacion import Publicacion
        stmt = (
            sa_update(Publicacion)
            .where(Publicacion.id == publicacion_id)
            .values(estado=nuevo_estado)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def delete(self, postulacion_id: str) -> Optional[Postulacion]:
        stmt = select(Postulacion).where(Postulacion.id == postulacion_id)
        result = await self.db.execute(stmt)
        postulacion = result.scalar_one_or_none()

        if not postulacion:
            return None

        await self.db.delete(postulacion)
        await self.db.commit()
        return postulacion

    async def crear_con_validaciones(self, data: dict, prestador_id: str) -> Postulacion:
        try:
            prestador = (
                await self.db.execute(
                    select(Prestador)
                    .options(selectinload(Prestador.usuario))
                    .where(Prestador.id == prestador_id)
                )
            ).scalar_one_or_none()
            if not prestador:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Debes estar registrado como prestador para enviar ofertas",
                )

            pub = (
                await self.db.execute(
                    select(Publicacion).where(Publicacion.id == data["publicacion_id"])
                )
            ).scalar_one_or_none()
            if not pub:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Publicación no encontrada",
                )

            if str(pub.usuario_id) == str(prestador_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puedes ofertar en tu propia publicación",
                )

            if pub.estado != "activo":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La publicación no está disponible para recibir ofertas",
                )

            if await self._prestador_tiene_trabajo_activo(prestador_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya tienes un servicio activo en curso; debes completarlo o cancelarlo antes de ofertar",
                )

            esp = (
                await self.db.execute(
                    select(Especialidad).where(
                        Especialidad.prestador_id == prestador_id,
                        Especialidad.categoria_id == pub.categoria_id,
                    )
                )
            ).scalar_one_or_none()
            if not esp:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes la especialidad requerida para esta categoría",
                )

            existente = (
                await self.db.execute(
                    select(Postulacion).where(
                        Postulacion.publicacion_id == data["publicacion_id"],
                        Postulacion.prestador_id == prestador_id,
                    )
                )
            ).scalar_one_or_none()

            if existente:
                if existente.estado in ("pendiente", "en_espera", "aceptada"):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya tienes una postulación activa para esta publicación",
                    )
                existente.precio_ofertado = data["precio_ofertado"]
                existente.disponibilidad = data["disponibilidad"]
                existente.mensaje = data["mensaje"]
                existente.estado = "pendiente"
                existente.retirada_at = None
                postulacion = existente
            else:
                data["estado"] = "pendiente"
                data["prestador_id"] = prestador_id
                postulacion = Postulacion(**data)
                self.db.add(postulacion)

            await self.db.flush()

            notif = Notificacion(
                usuario_id=pub.usuario_id,
                titulo="¡Nueva propuesta recibida!",
                mensaje=f"Un profesional ha enviado una oferta de $ {float(data['precio_ofertado']):,.0f} para tu solicitud.",
                tipo="oferta_recibida",
                referencia_id=str(pub.id),
                data={
                    "role": "cliente",
                    "destination": "publication_offers",
                    "publication_id": str(pub.id),
                    "offer_id": str(postulacion.id),
                },
            )
            self.db.add(notif)
            await self.db.commit()
            await self.db.refresh(postulacion)
            return postulacion
        except Exception:
            await self.db.rollback()
            raise

    async def _prestador_tiene_trabajo_activo(self, prestador_id: str) -> bool:
        stmt = (
            select(Postulacion.id)
            .join(Publicacion, Publicacion.id == Postulacion.publicacion_id)
            .where(
                Postulacion.prestador_id == prestador_id,
                Postulacion.estado == "aceptada",
                Publicacion.estado.in_(["acuerdo", "en_progreso", "pendiente_confirmacion"]),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def prestador_tiene_trabajo_activo(self, prestador_id: str) -> bool:
        """Fuente de verdad de ocupaciÃ³n; no depende de Prestador.disponible."""
        return await self._prestador_tiene_trabajo_activo(prestador_id)

    async def aceptar_postulacion(
        self,
        postulacion_id: str,
        user_id: str,
    ) -> str:
        try:
            postulacion = (
                await self.db.execute(
                    select(Postulacion)
                    .where(Postulacion.id == postulacion_id)
                )
            ).scalar_one_or_none()
            if not postulacion:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Postulación no encontrada",
                )

            # Bloquear prestador primero y luego publicación
            prestador = (
                await self.db.execute(
                    select(Prestador)
                    .options(selectinload(Prestador.usuario))
                    .where(Prestador.id == postulacion.prestador_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not prestador or (prestador.usuario and not prestador.usuario.activo):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El prestador no se encuentra activo",
                )

            # Orden global de bloqueos: prestador -> postulación -> publicación.
            # Evita deadlocks cuando dos clientes intentan aceptar al mismo prestador.
            postulacion = (
                await self.db.execute(
                    select(Postulacion)
                    .where(Postulacion.id == postulacion_id)
                    .with_for_update()
                )
            ).scalar_one()

            pub = (
                await self.db.execute(
                    select(Publicacion)
                    .where(Publicacion.id == postulacion.publicacion_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not pub:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Publicación no encontrada",
                )

            if str(pub.usuario_id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo el propietario de la publicación puede aceptar ofertas",
                )

            if pub.estado != "activo":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La publicación no está activa (estado actual: '{pub.estado}')",
                )

            if postulacion.estado != "pendiente":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Solo se pueden aceptar postulaciones pendientes",
                )

            if await self._prestador_tiene_trabajo_activo(str(prestador.id)):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El prestador ya tiene otro servicio activo en este momento",
                )

            postulacion.estado = "aceptada"
            pub.estado = "acuerdo"
            prestador.disponible = False

            # Las demás ofertas de esta publicación ya no fueron seleccionadas.
            stmt_no_seleccionadas = (
                sa_update(Postulacion)
                .where(Postulacion.publicacion_id == pub.id)
                .where(Postulacion.id != postulacion.id)
                .where(Postulacion.estado.in_(["pendiente", "en_espera"]))
                .values(estado="rechazada")
            )
            await self.db.execute(stmt_no_seleccionadas)

            # El mismo prestador no puede ser aceptado en otras publicaciones
            # mientras tenga este trabajo activo.
            await self.db.execute(
                sa_update(Postulacion)
                .where(Postulacion.prestador_id == prestador.id)
                .where(Postulacion.id != postulacion.id)
                .where(Postulacion.estado == "pendiente")
                .values(estado="en_espera")
            )

            conversacion = (
                await self.db.execute(
                    select(Conversacion).where(
                        Conversacion.id_postulacion == postulacion.id
                    )
                )
            ).scalar_one_or_none()
            if conversacion:
                conversacion.estado = "activa"
                conversacion.closed_at = None
                conversacion.delete_after = None
            else:
                conversacion = Conversacion(id_postulacion=postulacion.id, estado="activa")
                self.db.add(conversacion)
                await self.db.flush()

            notif = Notificacion(
                usuario_id=postulacion.prestador_id,
                titulo="¡Tu oferta fue aceptada!",
                mensaje="El cliente ha seleccionado tu propuesta. ¡Comunícate por mensaje para coordinar los detalles!",
                tipo="oferta_aceptada",
                referencia_id=str(pub.id),
                data={
                    "role": "profesional",
                    "destination": "chat",
                    "publication_id": str(pub.id),
                    "offer_id": str(postulacion.id),
                    "conversation_id": str(conversacion.id_conversacion),
                },
            )
            self.db.add(notif)
            await self.db.commit()

            return str(conversacion.id_conversacion)
        except Exception:
            await self.db.rollback()
            raise

    async def retirar_postulacion(self, postulacion_id: str, prestador_id: str) -> Postulacion:
        try:
            postulacion = (
                await self.db.execute(
                    select(Postulacion)
                    .options(selectinload(Postulacion.publicacion))
                    .where(Postulacion.id == postulacion_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not postulacion:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Postulación no encontrada",
                )

            if str(postulacion.prestador_id) != str(prestador_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso sobre esta postulación",
                )

            if postulacion.estado not in ("pendiente", "en_espera"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede retirar una postulación en estado '{postulacion.estado}'",
                )

            postulacion.estado = "retirada"
            postulacion.retirada_at = datetime.now(timezone.utc)

            if postulacion.publicacion:
                self.db.add(
                    Notificacion(
                        usuario_id=postulacion.publicacion.usuario_id,
                        titulo="Oferta retirada",
                        mensaje="Un prestador ha retirado su oferta de tu publicación.",
                        tipo="postulacion_retirada",
                        referencia_id=str(postulacion.publicacion_id),
                        data={
                            "role": "cliente",
                            "destination": "publication_offers",
                            "publication_id": str(postulacion.publicacion_id),
                            "offer_id": str(postulacion.id),
                        },
                    )
                )

            await self.db.commit()
            await self.db.refresh(postulacion)
            return postulacion
        except Exception:
            await self.db.rollback()
            raise
