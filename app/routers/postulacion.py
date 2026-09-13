from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.services.dependencies import get_postulacion_service
from app.services.postulacion_service import PostulacionService

from app.schemas.postulacion import (
    EstadoPostulacion,
    PostulacionCreate,
    PostulacionEstadoUpdate,
    PostulacionUpdate,
)


router = APIRouter(
    prefix="/postulaciones",
    tags=["Postulaciones"]
)



@router.post("")
async def create_postulacion(
    data: PostulacionCreate,
    current_user=Depends(get_current_user),
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.create_postulacion(
        data,
        current_user.id
    )


@router.get("")
async def list_postulaciones(
    publicacion_id: Optional[str] = None,
    estado: Optional[EstadoPostulacion] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    incluir_prestador: bool = Query(False),
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.list_postulaciones(
        publicacion_id=publicacion_id,
        estado=estado.value if estado else None,
        limit=limit,
        offset=offset,
        incluir_prestador=incluir_prestador
    )


@router.get("/{postulacion_id}")
async def get_postulacion(
    postulacion_id: str,
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.get_postulacion(postulacion_id)


@router.put("/{postulacion_id}")
async def update_postulacion(
    postulacion_id: str,
    data: PostulacionUpdate,
    current_user=Depends(get_current_user),
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.update_postulacion(
        postulacion_id,
        data,
        current_user.id
    )


@router.patch("/{postulacion_id}/estado")
async def cambiar_estado_postulacion(
    postulacion_id: str,
    data: PostulacionEstadoUpdate,
    current_user=Depends(get_current_user),
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.cambiar_estado(
        postulacion_id,
        data.estado,
        current_user.id
    )


@router.post("/{postulacion_id}/revertir")
async def revertir_aceptacion_postulacion(
    postulacion_id: str,
    current_user=Depends(get_current_user),
    services: PostulacionService = Depends(get_postulacion_service) 
):

    return await services.revertir_aceptacion(
        postulacion_id,
        current_user.id
    )


@router.delete("/{postulacion_id}")
async def delete_postulacion(
    postulacion_id: str,
    current_user=Depends(get_current_user),
    services: PostulacionService = Depends(get_postulacion_service)
):

    return await services.delete_postulacion(
        postulacion_id,
        current_user.id
    )