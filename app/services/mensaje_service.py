import uuid

from fastapi import HTTPException, status

from app.repositories.conversacion_repository import ConversacionRepository
from app.repositories.mensaje_repository import MensajeRepository
from app.schemas.mensaje import MensajeCreate


class MensajeService:

    def __init__(
        self,
        repository: MensajeRepository,
        conversacion_repository: ConversacionRepository,
    ):
        self.repository = repository
        self.conversacion_repository = conversacion_repository

    @staticmethod
    def _obtener_contraparte(
        conversacion,
        remitente_id: uuid.UUID,
        rol: str,
    ) -> uuid.UUID:
        post = conversacion.postulacion
        pub = post.publicacion if post else None
        if not post or not pub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contexto de conversación no encontrado",
            )

        if rol == "cliente" and str(pub.usuario_id) == str(remitente_id):
            return post.prestador_id
        if rol == "profesional" and str(post.prestador_id) == str(remitente_id):
            return pub.usuario_id

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No perteneces a esta conversación",
        )

    async def crear_mensaje(self, data: MensajeCreate, rol: str):
        mensaje_data = data.model_dump()
        conversacion = await self.conversacion_repository.get_by_id(
            mensaje_data["id_conversacion"]
        )
        if not conversacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )

        contraparte_real = self._obtener_contraparte(
            conversacion,
            mensaje_data["id_remitente"],
            rol,
        )

        if str(mensaje_data["id_destinatario"]) != str(contraparte_real):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El destinatario no corresponde a la contraparte de la conversación",
            )

        if conversacion.estado != "activa":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pueden enviar mensajes a una conversación cerrada",
            )

        pub = conversacion.postulacion.publicacion if conversacion.postulacion else None
        if pub and pub.estado in ("terminado", "cancelado"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pueden enviar mensajes cuando el servicio está terminado o cancelado",
            )

        return await self.repository.create(mensaje_data)

    async def listar_mensajes_por_conversacion(
        self,
        conversacion_id: uuid.UUID,
        user_id: uuid.UUID,
        rol: str,
    ):
        conversacion = await self.conversacion_repository.get_by_id(conversacion_id)
        if not conversacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )
        self._obtener_contraparte(conversacion, user_id, rol)
        return await self.repository.get_by_conversacion(conversacion_id)
