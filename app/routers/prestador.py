from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.services.dependencies import get_prestador_service
from app.services.prestador_service import PrestadorService

from app.schemas.prestador import PrestadorCreate, PrestadorUpdate


router = APIRouter(
    prefix="/prestadores",
    tags=["Prestadores"]
)



@router.post("")
async def create_prestador(
    data: PrestadorCreate,
    current_user=Depends(get_current_user),
    services: PrestadorService = Depends(get_prestador_service)
):

    return await services.create_prestador(
        data,
        current_user.id
    )


@router.get("")
async def list_prestadores(
    disponible: Optional[bool] = None,
    verificado: Optional[bool] = None,
    categoria_id: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    services: PrestadorService = Depends(get_prestador_service)
):

    return await services.list_prestadores(
        disponible=disponible,
        verificado=verificado,
        categoria_id=categoria_id,
        limit=limit,
        offset=offset,
    )


@router.get("/mi-perfil")
async def get_mi_perfil_prestador(
    current_user=Depends(get_current_user),
    services: PrestadorService = Depends(get_prestador_service)
):
    return await services.get_prestador(current_user.id)


@router.get("/{prestador_id}")
async def get_prestador(
    prestador_id: str,
    services: PrestadorService = Depends(get_prestador_service)
):

    return await services.get_prestador(prestador_id)


@router.put("/{prestador_id}")
async def update_prestador(
    prestador_id: str,
    data: PrestadorUpdate,
    current_user=Depends(get_current_user),
    services: PrestadorService = Depends(get_prestador_service)
):

    return await services.update_prestador(
        prestador_id,
        data,
        current_user.id
    )


@router.delete("/{prestador_id}")
async def delete_prestador(
    prestador_id: str,
    current_user=Depends(get_current_user),
    services: PrestadorService = Depends(get_prestador_service)
):

    return await services.delete_prestador(
        prestador_id,
        current_user.id
    )