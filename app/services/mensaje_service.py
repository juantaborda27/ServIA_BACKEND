import uuid

from fastapi import HTTPException, status

from app.repositories.mensaje_repository import MensajeRepository
from app.schemas.mensaje import MensajeCreate


class MensajeService:

    def __init__(self, repository: MensajeRepository):
        self.repository = repository

    async def crear_mensaje(self, data: MensajeCreate):
        mensaje_data = data.model_dump()

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