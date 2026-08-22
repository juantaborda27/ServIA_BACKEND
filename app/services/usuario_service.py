from fastapi import HTTPException, status

from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate


class UsuarioService:

    def __init__(self):

        self.repository = UsuarioRepository()

    def get_profile(self, user_id: str):

        usuario = self.repository.get_by_id(user_id)

        if not usuario:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        return usuario

    def update_profile(
        self,
        user_id: str,
        data: UsuarioCreate
    ):

        update_data = data.model_dump(
            exclude_unset=True
        )

        usuario = self.repository.update(
            user_id,
            update_data
        )

        return usuario

    def deactivate_account(self, user_id: str):

        self.repository.delete(user_id)

        return {
            "message": "Cuenta desactivada correctamente"
        }