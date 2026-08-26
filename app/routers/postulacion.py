from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user

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

postulacion_service = PostulacionService()


@router.post("")
def create_postulacion(
    data: PostulacionCreate,
    current_user=Depends(get_current_user)
):

    return postulacion_service.create_postulacion(
        data,
        current_user.id
    )


@router.get("")
def list_postulaciones(
    publicacion_id: Optional[str] = None,
    estado: Optional[EstadoPostulacion] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):

    return postulacion_service.list_postulaciones(
        publicacion_id=publicacion_id,
        estado=estado.value if estado else None,
        limit=limit,
        offset=offset,
    )


@router.get("/{postulacion_id}")
def get_postulacion(postulacion_id: str):

    return postulacion_service.get_postulacion(postulacion_id)


@router.put("/{postulacion_id}")
def update_postulacion(
    postulacion_id: str,
    data: PostulacionUpdate,
    current_user=Depends(get_current_user)
):

    return postulacion_service.update_postulacion(
        postulacion_id,
        data,
        current_user.id
    )


@router.patch("/{postulacion_id}/estado")
def cambiar_estado_postulacion(
    postulacion_id: str,
    data: PostulacionEstadoUpdate,
    current_user=Depends(get_current_user)
):

    return postulacion_service.cambiar_estado(
        postulacion_id,
        data.estado,
        current_user.id
    )


@router.post("/{postulacion_id}/revertir")
def revertir_aceptacion_postulacion(
    postulacion_id: str,
    current_user=Depends(get_current_user)
):

    return postulacion_service.revertir_aceptacion(
        postulacion_id,
        current_user.id
    )


@router.delete("/{postulacion_id}")
def delete_postulacion(
    postulacion_id: str,
    current_user=Depends(get_current_user)
):

    return postulacion_service.delete_postulacion(
        postulacion_id,
        current_user.id
    )