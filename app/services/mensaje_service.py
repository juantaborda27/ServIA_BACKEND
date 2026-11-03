import uuid

from fastapi import HTTPException, status

from app.repositories.mensaje_repository import MensajeRepository
from app.schemas.mensaje import MensajeCreate
from app.repositories.conversacion_repository import ConversacionRepository


class MensajeService:

    def __init__(self, repository: MensajeRepository, conversacion_repository: ConversacionRepository):
        self.repository = repository
        self.conversacion_repository = conversacion_repository

    async def crear_mensaje(self, data: MensajeCreate):
        mensaje_data = data.model_dump()
        conversacion = await self.conversacion_repository.get_by_id(
            mensaje_data["id_conversacion"]
        )
        if not conversacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )
        if conversacion.estado != "activa":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden enviar mensajes a una conversación que no está activa"
            )
        mensaje = await self.repository.create(mensaje_data)

        return mensaje

    async def listar_mensajes_por_conversacion(
        self,
        conversacion_id: uuid.UUID,
    ):
        mensajes = await self.repository.get_by_conversacion(
            conversacion_id
        )

        return mensajes