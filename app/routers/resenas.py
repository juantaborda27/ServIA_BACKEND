from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.schemas.resena import ResenaCreate, ResenaResponse, ResumenCalificaciones
from app.services.dependencies import get_resena_service
from app.services.resena_service import ResenaService


router = APIRouter(
    prefix="/resenas",
    tags=["Reseñas y Calificaciones"]
)


@router.post("", response_model=ResenaResponse)
async def create_resena(
    data: ResenaCreate,
    current_user=Depends(get_current_user),
    services: ResenaService = Depends(get_resena_service)
):
    """Crea una reseña obligatoria para un servicio completado/terminado."""
    return await services.create_resena(data, current_user.id)


@router.get("/pendiente")
async def get_resena_pendiente(
    current_user=Depends(get_current_user),
    services: ResenaService = Depends(get_resena_service)
):
    """Verifica si el cliente autenticado tiene alguna reseña pendiente por realizar."""
    return await services.get_resena_pendiente(current_user.id)


@router.get("/prestador/{prestador_id}", response_model=ResumenCalificaciones)
async def get_resenas_prestador(
    prestador_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    services: ResenaService = Depends(get_resena_service)
):
    """Obtiene el resumen de calificaciones y la lista de reseñas de un prestador."""
    return await services.get_resenas_prestador(
        prestador_id=prestador_id,
        limit=limit,
        offset=offset
    )


@router.get("/publicacion/{publicacion_id}", response_model=Optional[ResenaResponse])
async def get_resena_publicacion(
    publicacion_id: str,
    services: ResenaService = Depends(get_resena_service)
):
    """Obtiene la reseña asociada a una publicación."""
    return await services.get_resena_publicacion(publicacion_id)
