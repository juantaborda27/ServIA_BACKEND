from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user

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

publicacion_service = PublicacionService()


@router.post("")
def create_publicacion(
    data: PublicacionCreate,
    current_user=Depends(get_current_user)
):

    return publicacion_service.create_publicacion(
        data,
        current_user.id
    )


@router.get("")
def list_publicaciones(
    estado: Optional[EstadoPublicacion] = None,
    categoria_id: Optional[str] = None,
    usuario_id: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):

    return publicacion_service.list_publicaciones(
        estado=estado.value if estado else None,
        categoria_id=categoria_id,
        usuario_id=usuario_id,
        limit=limit,
        offset=offset,
    )

@router.get("/categorias-prestador")
def get_publicaciones_categorias_prestador(
    current_user=Depends(get_current_user)
):
    return publicacion_service.list_publicaciones(
        prestador_id=current_user.id,
        incluir_usuario=True
    )

@router.get("/mis-publicaciones")
def get_publicaciones_by_usuario(
    current_user=Depends(get_current_user)
):
    return publicacion_service.get_publicaciones_by_usuario(
        usuario_id=current_user.id
    )
@router.get("/{publicacion_id}")
def get_publicacion(publicacion_id: str):

    return publicacion_service.get_publicacion(publicacion_id)


@router.put("/{publicacion_id}")
def update_publicacion(
    publicacion_id: str,
    data: PublicacionUpdate,
    current_user=Depends(get_current_user)
):

    return publicacion_service.update_publicacion(
        publicacion_id,
        data,
        current_user.id
    )


@router.patch("/{publicacion_id}/estado")
def cambiar_estado_publicacion(
    publicacion_id: str,
    data: PublicacionEstadoUpdate,
    current_user=Depends(get_current_user)
):

    return publicacion_service.cambiar_estado(
        publicacion_id,
        data.estado,
        current_user.id
    )


@router.delete("/{publicacion_id}")
def delete_publicacion(
    publicacion_id: str,
    current_user=Depends(get_current_user)
):

    return publicacion_service.delete_publicacion(
        publicacion_id,
        current_user.id
    )
