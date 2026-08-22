from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user

from app.services.usuario_service import UsuarioService

from app.schemas.usuario import UsuarioCreate


router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)

usuario_service = UsuarioService()


@router.get("/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):

    return usuario_service.get_profile(
        current_user.id
    )


@router.put("/me")
def update_my_profile(
    data: UsuarioCreate,
    current_user=Depends(get_current_user)
):

    return usuario_service.update_profile(
        current_user.id,
        data
    )


@router.delete("/me")
def deactivate_my_account(
    current_user=Depends(get_current_user)
):

    return usuario_service.deactivate_account(
        current_user.id
    )