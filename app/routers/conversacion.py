from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.schemas.conversacion import ConversacionUpdate
from app.schemas.mensaje import MensajeResponse
from app.services.conversacion_service import ConversacionService
from app.services.dependencies import get_conversacion_service, get_mensaje_service
from app.services.mensaje_service import MensajeService

router = APIRouter(
    prefix="/conversaciones",
    tags=["Conversaciones"],
)


@router.get("")
async def list_conversaciones(
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
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
        user_id=current_user.id,
        rol=rol,
        estado=estado,
        limit=limit,
        offset=offset,
    )


@router.get("/{conversacion_id}")
async def get_conversacion(
    conversacion_id: UUID,
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
    current_user=Depends(get_current_user),
    services: ConversacionService = Depends(get_conversacion_service),
):
    return await services.get_conversacion(conversacion_id, current_user.id, rol)


@router.get(
    "/{conversacion_id}/mensajes",
    response_model=list[MensajeResponse],
)
async def get_mensajes_conversacion(
    conversacion_id: UUID,
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
    current_user=Depends(get_current_user),
    services: MensajeService = Depends(get_mensaje_service),
):
    return await services.listar_mensajes_por_conversacion(
        conversacion_id,
        current_user.id,
        rol,
    )


@router.patch("/{conversacion_id}")
async def update_conversacion(
    conversacion_id: UUID,
    data: ConversacionUpdate,
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
    current_user=Depends(get_current_user),
    services: ConversacionService = Depends(get_conversacion_service),
):
    return await services.update_conversacion(
        conversacion_id,
        data,
        current_user.id,
        rol,
    )
