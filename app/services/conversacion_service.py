
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.repositories.conversacion_repository import ConversacionRepository
from app.schemas.conversacion import ConversacionUpdate


class ConversacionService:

    def __init__(self, repository: ConversacionRepository):
        self.repository = repository

    async def get_conversacion(
        self, conversacion_id: uuid.UUID
    ):
        conversacion = await self.repository.get_by_id(
            conversacion_id
        )

        if conversacion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )

        return conversacion

    async def list_conversaciones(
        self,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):
        return await self.repository.list_all(
            estado=estado,
            limit=limit,
            offset=offset,
        )

    async def update_conversacion(
        self,
        conversacion_id: uuid.UUID,
        data: ConversacionUpdate,
    ):
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

        conversacion = await self.repository.update_estado(
            conversacion_id,
            estado,
        )

        if conversacion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada",
            )

        return conversacion
