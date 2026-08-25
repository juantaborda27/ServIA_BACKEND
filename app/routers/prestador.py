from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user

from app.services.prestador_service import PrestadorService

from app.schemas.prestador import PrestadorCreate, PrestadorUpdate


router = APIRouter(
    prefix="/prestadores",
    tags=["Prestadores"]
)

prestador_service = PrestadorService()


@router.post("")
def create_prestador(
    data: PrestadorCreate,
    current_user=Depends(get_current_user)
):

    return prestador_service.create_prestador(
        data,
        current_user.id
    )


@router.get("")
def list_prestadores(
    disponible: Optional[bool] = None,
    verificado: Optional[bool] = None,
    categoria_id: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):

    return prestador_service.list_prestadores(
        disponible=disponible,
        verificado=verificado,
        categoria_id=categoria_id,
        limit=limit,
        offset=offset,
    )


@router.get("/mi-perfil")
def get_mi_perfil_prestador(
    current_user=Depends(get_current_user)
):
    return prestador_service.get_prestador(current_user.id)


@router.get("/{prestador_id}")
def get_prestador(prestador_id: str):

    return prestador_service.get_prestador(prestador_id)


@router.put("/{prestador_id}")
def update_prestador(
    prestador_id: str,
    data: PrestadorUpdate,
    current_user=Depends(get_current_user)
):

    return prestador_service.update_prestador(
        prestador_id,
        data,
        current_user.id
    )


@router.delete("/{prestador_id}")
def delete_prestador(
    prestador_id: str,
    current_user=Depends(get_current_user)
):

    return prestador_service.delete_prestador(
        prestador_id,
        current_user.id
    )