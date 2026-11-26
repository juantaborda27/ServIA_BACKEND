import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.core.storage import image_storage
from app.models.conversacion import Conversacion
from app.repositories.conversacion_repository import ConversacionRepository
from app.schemas.conversacion import ConversacionUpdate

logger = logging.getLogger(__name__)


class ConversacionService:

    def __init__(self, repository: ConversacionRepository):
        self.repository = repository

    @staticmethod
    def _verificar_participante(
        conversacion: Conversacion,
        user_id: uuid.UUID,
        rol: str,
    ) -> None:
        post = conversacion.postulacion
        pub = post.publicacion if post else None
        es_cliente = pub is not None and str(pub.usuario_id) == str(user_id)
        es_prestador = post is not None and str(post.prestador_id) == str(user_id)
        tiene_acceso = es_cliente if rol == "cliente" else es_prestador
        if not tiene_acceso:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a esta conversación",
            )

    @staticmethod
    def _serializar_conversacion(
        conversacion: Conversacion,
        user_id: uuid.UUID,
        rol: str,
    ) -> dict:
        post = conversacion.postulacion
        pub = post.publicacion if post else None
        partner_user = None
        if rol == "cliente" and post and post.prestador:
            partner_user = post.prestador.usuario
        elif rol == "profesional" and pub:
            partner_user = pub.usuario

        mensajes = sorted(
            conversacion.mensajes or [],
            key=lambda m: m.fecha_hora,
        )
        last_msg = mensajes[-1] if mensajes else None

        return {
            "id_conversacion": str(conversacion.id_conversacion),
            "id_postulacion": str(conversacion.id_postulacion),
            "rol": rol,
            "estado": conversacion.estado,
            "created_at": conversacion.created_at.isoformat() if conversacion.created_at else None,
            "closed_at": conversacion.closed_at.isoformat() if conversacion.closed_at else None,
            "delete_after": conversacion.delete_after.isoformat() if conversacion.delete_after else None,
            "publication": {
                "id": str(pub.id),
                "descripcion": pub.descripcion,
                "estado": pub.estado,
            } if pub else None,
            "offer": {
                "id": str(post.id),
                "precio_ofertado": float(post.precio_ofertado),
            } if post else None,
            "partner": {
                "id": str(partner_user.id),
                "nombre_completo": partner_user.nombre_completo,
                "foto_perfil": image_storage.resolve_url(partner_user.foto_perfil),
            } if partner_user else None,
            "last_message": {
                "contenido": last_msg.contenido,
                "fecha_hora": last_msg.fecha_hora.isoformat() if last_msg.fecha_hora else None,
            } if last_msg else None,
            "unread_count": 0,
        }

    async def get_conversacion(
        self,
        conversacion_id: uuid.UUID,
        user_id: uuid.UUID,
        rol: str,
    ):
        conversacion = await self.repository.get_by_id(conversacion_id)
        if conversacion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )
        self._verificar_participante(conversacion, user_id, rol)
        return self._serializar_conversacion(conversacion, user_id, rol)

    async def list_conversaciones(
        self,
        user_id: uuid.UUID,
        rol: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        conversaciones = await self.repository.list_by_user(
            user_id=user_id,
            rol=rol,
            estado=estado,
            limit=limit,
            offset=offset,
        )
        items = [self._serializar_conversacion(c, user_id, rol or "cliente") for c in conversaciones]
        return {"items": items, "total": len(items)}

    async def update_conversacion(
        self,
        conversacion_id: uuid.UUID,
        data: ConversacionUpdate,
        user_id: uuid.UUID,
        rol: str,
    ):
        conversacion_actual = await self.repository.get_by_id(conversacion_id)
        if conversacion_actual is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )
        self._verificar_participante(conversacion_actual, user_id, rol)

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se enviaron cambios",
            )
        if set(update_data) != {"estado"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permite modificar el estado",
            )

        estado = update_data["estado"]
        if estado not in {"activa", "cerrada"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Estado de conversación inválido",
            )

        return await self.repository.update_estado(conversacion_id, estado)

    async def limpiar_conversaciones_expiradas(self) -> dict:
        resumen = await self.repository.limpiar_expiradas()
        logger.info("Limpieza programada de conversaciones ejecutada: %s", resumen)
        return resumen
