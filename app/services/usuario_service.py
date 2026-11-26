from fastapi import HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder

from app.core.storage import image_storage
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate


class UsuarioService:

    def __init__(self,repository: UsuarioRepository):

        self.repository = repository

    async def get_profile(self, user_id: str):

        usuario = await self.repository.get_by_id(user_id)

        if not usuario:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        return self._serialize_profile(usuario)

    async def update_profile(
        self,
        user_id: str,
        data: UsuarioCreate
    ):

        update_data = data.model_dump(
            exclude_unset=True
        )

        usuario = await self.repository.update(
            user_id,
            update_data
        )

        return self._serialize_profile(usuario) if usuario else None

    async def upload_profile_photo(self, user_id: str, file: UploadFile):
        usuario = await self.repository.get_by_id(user_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        stored = await image_storage.upload_profile(user_id, file)
        previous_photo = usuario.foto_perfil
        try:
            updated = await self.repository.update(user_id, {"foto_perfil": stored.key})
            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado",
                )
        except Exception:
            await image_storage.delete(stored.key)
            raise

        if previous_photo and previous_photo != stored.key:
            if not previous_photo.startswith(("https://", "http://")):
                await image_storage.delete(previous_photo)

        return self._serialize_profile(updated)

    @staticmethod
    def _serialize_profile(usuario):
        data = jsonable_encoder(usuario, exclude={"hashed_password"})
        data["foto_perfil"] = image_storage.resolve_url(usuario.foto_perfil)
        return data

    async def deactivate_account(self, user_id: str):

        await self.repository.delete(user_id)

        return {
            "message": "Cuenta desactivada correctamente"
        }