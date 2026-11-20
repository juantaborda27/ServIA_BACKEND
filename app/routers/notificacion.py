from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.notificacion import (
    ListaNotificacionesResponse,
    NotificacionCreate,
    NotificacionResponse,
)
from app.services.dependencies import get_notificacion_service
from app.services.notificacion_service import NotificacionService

router = APIRouter(
    prefix="/notificaciones",
    tags=["Notificaciones"]
)


@router.get("", response_model=ListaNotificacionesResponse)
async def list_mis_notificaciones(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    services: NotificacionService = Depends(get_notificacion_service),
):
    """Retorna las notificaciones del usuario autenticado ordenadas de la más reciente a la más antigua."""
    return await services.list_notificaciones(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )


@router.patch("/{notificacion_id}/leer")
async def marcar_notificacion_leida(
    notificacion_id: str,
    current_user = Depends(get_current_user),
    services: NotificacionService = Depends(get_notificacion_service),
):
    """Marca una notificación específica como leída."""
    ok = await services.mark_as_read(notificacion_id, current_user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada o no pertenece al usuario"
        )
    return {"message": "Notificación marcada como leída"}


@router.patch("/leer-todas")
async def marcar_todas_leidas(
    current_user = Depends(get_current_user),
    services: NotificacionService = Depends(get_notificacion_service),
):
    """Marca todas las notificaciones pendientes del usuario como leídas."""
    marcadas = await services.mark_all_as_read(current_user.id)
    return {"message": f"{marcadas} notificaciones marcadas como leídas"}


@router.delete("/{notificacion_id}")
async def eliminar_notificacion(
    notificacion_id: str,
    current_user = Depends(get_current_user),
    services: NotificacionService = Depends(get_notificacion_service),
):
    """Elimina una notificación del usuario."""
    ok = await services.delete_notificacion(notificacion_id, current_user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada o no pertenece al usuario"
        )
    return {"message": "Notificación eliminada correctamente"}
