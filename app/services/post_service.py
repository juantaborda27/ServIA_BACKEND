from typing import Optional

from fastapi import HTTPException, status

from app.repositories.post_repository import PublicacionRepository
from app.schemas.post import (
    EstadoPublicacion,
    PublicacionCreate,
    PublicacionUpdate,
)


class PublicacionService:

    def __init__(self):

        self.repository = PublicacionRepository()

    def create_publicacion(self, data: PublicacionCreate, user_id: str):

        payload = data.model_dump(mode="json")
        payload["usuario_id"] = user_id

        publicacion = self.repository.create(payload)

        if not publicacion:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear la publicación"
            )

        return publicacion

    def get_publicacion(self, publicacion_id: str):

        publicacion = self.repository.get_by_id(publicacion_id)

        if not publicacion:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Publicación no encontrada"
            )

        return publicacion

    def list_publicaciones(
        self,
        estado: Optional[str] = None,
        categoria_id: Optional[str] = None,
        usuario_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):

        return self.repository.list(
            estado=estado,
            categoria_id=categoria_id,
            usuario_id=usuario_id,
            limit=limit,
            offset=offset,
        )

    def update_publicacion(
        self,
        publicacion_id: str,
        data: PublicacionUpdate,
        user_id: str,
    ):

        publicacion = self.get_publicacion(publicacion_id)
        self._verificar_dueno(publicacion, user_id)

        update_data = data.model_dump(exclude_unset=True, mode="json")

        return self.repository.update(publicacion_id, update_data)

    def cambiar_estado(
        self,
        publicacion_id: str,
        nuevo_estado: EstadoPublicacion,
        user_id: str,
    ):

        publicacion = self.get_publicacion(publicacion_id)
        self._verificar_dueno(publicacion, user_id)

        return self.repository.update(
            publicacion_id,
            {"estado": nuevo_estado.value}
        )

    def delete_publicacion(self, publicacion_id: str, user_id: str):

        publicacion = self.get_publicacion(publicacion_id)
        self._verificar_dueno(publicacion, user_id)

        self.repository.delete(publicacion_id)

        return {"message": "Publicación eliminada correctamente"}

    @staticmethod
    def _verificar_dueno(publicacion: dict, user_id: str):

        if publicacion["usuario_id"] != user_id:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre esta publicación"
            )