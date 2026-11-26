from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.auth import get_current_user

from app.services.usuario_service import UsuarioService

from app.schemas.usuario import UsuarioCreate
from app.services.dependencies import get_usuario_service

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)


@router.get("/me")
async def get_my_profile(
    current_user=Depends(get_current_user),
    services: UsuarioService = Depends(get_usuario_service)
):

    return await services.get_profile(
        current_user.id
    )


@router.put("/me")
async def update_my_profile(
    data: UsuarioCreate,
    current_user=Depends(get_current_user),
    services: UsuarioService = Depends(get_usuario_service)
):

    return await services.update_profile(
        current_user.id,
        data
    )


@router.post("/me/foto-perfil")
async def upload_my_profile_photo(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    services: UsuarioService = Depends(get_usuario_service),
):
    return await services.upload_profile_photo(current_user.id, file)


@router.delete("/me")
async def deactivate_my_account(
    current_user=Depends(get_current_user),
    services: UsuarioService = Depends(get_usuario_service)
):

    return await services.deactivate_account(
        current_user.id
    )