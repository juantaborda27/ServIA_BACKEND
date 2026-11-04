
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.services.dependencies import get_conversacion_service
from app.services.conversacion_service import ConversacionService
from app.schemas.conversacion import ConversacionUpdate


router = APIRouter(
    prefix="/conversaciones",
    tags=["Conversaciones"],
)


@router.get("")
async def list_conversaciones(
    estado: Optional[str] = Query(
        default=None,
        pattern="^(activa|cerrada)$",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    services: ConversacionService = Depends(get_conversacion_service),
):
    return await services.list_conversaciones(
        estado=estado,
        limit=limit,
        offset=offset,
    )


@router.get("/{conversacion_id}")
async def get_conversacion(
    conversacion_id: UUID,
    current_user=Depends(get_current_user),
    services: ConversacionService = Depends(get_conversacion_service),
):
    return await services.get_conversacion(conversacion_id)


@router.patch("/{conversacion_id}")
async def update_conversacion(
    conversacion_id: UUID,
    data: ConversacionUpdate,
    current_user=Depends(get_current_user),
    services: ConversacionService = Depends(get_conversacion_service),
):
    return await services.update_conversacion(
        conversacion_id,
        data,
    )
