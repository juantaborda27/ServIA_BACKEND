from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.services.dependencies import get_publicacion_service
from app.services.post_service import PublicacionService
from app.schemas.post import (
    EstadoPublicacion,
    PublicacionCreate,
    PublicacionEstadoUpdate,
    PublicacionUpdate,
)


router = APIRouter(
    prefix="/publicaciones",
    tags=["Publicaciones"]
)


@router.post("")
async def create_publicacion(
    data: PublicacionCreate,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.create_publicacion(
        data,
        current_user.id
    )


@router.get("")
async def list_publicaciones(
    estado: Optional[EstadoPublicacion] = None,
    categoria_id: Optional[str] = None,
    usuario_id: Optional[str] = None,
    barrio: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.list_publicaciones(
        estado=estado.value if estado else None,
        categoria_id=categoria_id,
        usuario_id=usuario_id,
        barrio=barrio,
        limit=limit,
        offset=offset,
        incluir_usuario=True,
        incluir_categoria=True,
    )


@router.get("/categorias-prestador")
async def get_publicaciones_categorias_prestador(
    barrio: Optional[str] = None,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.list_publicaciones(
        prestador_id=current_user.id,
        estado="activo",
        barrio=barrio,
        incluir_usuario=True,
        incluir_categoria=True,
    )


@router.get("/mis-publicaciones")
async def get_publicaciones_by_usuario(
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.get_publicaciones_by_usuario(
        usuario_id=current_user.id
    )


@router.get("/trabajos")
async def get_trabajos_prestador(
    tipo: str = Query("activos", description="'activos' o 'completados'"),
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    """Obtiene el historial de trabajos asignados al prestador autenticado."""
    return await services.get_trabajos_prestador(
        prestador_id=current_user.id,
        tipo=tipo
    )


@router.patch("/{publicacion_id}/iniciar")
async def iniciar_trabajo(
    publicacion_id: str,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.iniciar_trabajo(
        publicacion_id=publicacion_id,
        user_id=current_user.id
    )


@router.patch("/{publicacion_id}/completar")
async def completar_trabajo(
    publicacion_id: str,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    """Marca el trabajo como terminado; esto desbloquea y exige la reseña obligatoria del cliente."""
    return await services.completar_trabajo(
        publicacion_id=publicacion_id,
        user_id=current_user.id
    )


@router.get("/{publicacion_id}")
async def get_publicacion(
    publicacion_id: str,
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.get_publicacion(publicacion_id)


@router.put("/{publicacion_id}")
async def update_publicacion(
    publicacion_id: str,
    data: PublicacionUpdate,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.update_publicacion(
        publicacion_id,
        data,
        current_user.id
    )


@router.patch("/{publicacion_id}/estado")
async def cambiar_estado_publicacion(
    publicacion_id: str,
    data: PublicacionEstadoUpdate,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.cambiar_estado(
        publicacion_id,
        data.estado,
        current_user.id
    )


@router.delete("/{publicacion_id}")
async def delete_publicacion(
    publicacion_id: str,
    current_user=Depends(get_current_user),
    services: PublicacionService = Depends(get_publicacion_service)
):
    return await services.delete_publicacion(
        publicacion_id,
        current_user.id
    )
