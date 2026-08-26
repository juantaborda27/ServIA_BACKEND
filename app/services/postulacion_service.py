from typing import Optional

from fastapi import HTTPException, status

from app.repositories.postulacion_repository import PostulacionRepository
from app.repositories.post_repository import PublicacionRepository
from app.schemas.postulacion import (
    EstadoPostulacion,
    PostulacionCreate,
    PostulacionUpdate,
)


class PostulacionService:

    def __init__(self):

        self.repository = PostulacionRepository()
        self.publicacion_repository = PublicacionRepository()

    def create_postulacion(self, data: PostulacionCreate, prestador_id: str):

        activa = self.repository.get_activa(data.publicacion_id, prestador_id)

        if activa:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya tienes una postulación activa para esta publicación"
            )

        payload = data.model_dump(mode="json")
        payload["prestador_id"] = prestador_id

        postulacion = self.repository.create(payload)

        if not postulacion:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear la postulación"
            )

        return postulacion

    def get_postulacion(self, postulacion_id: str):

        postulacion = self.repository.get_by_id(postulacion_id)

        if not postulacion:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Postulación no encontrada"
            )

        return postulacion

    def list_postulaciones(
        self,
        publicacion_id: Optional[str] = None,
        prestador_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        incluir_prestador: bool = False,
    ):

        return self.repository.list(
            publicacion_id=publicacion_id,
            prestador_id=prestador_id,
            estado=estado,
            limit=limit,
            offset=offset,
            incluir_prestador=incluir_prestador,
        )

    def update_postulacion(
        self,
        postulacion_id: str,
        data: PostulacionUpdate,
        prestador_id: str,
    ):

        postulacion = self.get_postulacion(postulacion_id)
        self._verificar_dueno_postulacion(postulacion, prestador_id)

        update_data = data.model_dump(exclude_unset=True, mode="json")

        return self.repository.update(postulacion_id, update_data)

    def cambiar_estado(
        self,
        postulacion_id: str,
        nuevo_estado: EstadoPostulacion,
        user_id: str,
    ):

        postulacion = self.get_postulacion(postulacion_id)
        self._verificar_dueno_publicacion(postulacion, user_id)

        actualizada = self.repository.update(
            postulacion_id,
            {"estado": nuevo_estado.value}
        )

        if nuevo_estado == EstadoPostulacion.aceptada:
            self.repository.poner_en_espera_otras(
                postulacion["publicacion_id"],
                postulacion_id,
            )

        return actualizada

    def revertir_aceptacion(self, postulacion_id: str, user_id: str):
        """Si el cliente se arrepiente, vuelve la postulación aceptada a pendiente."""

        postulacion = self.get_postulacion(postulacion_id)
        self._verificar_dueno_publicacion(postulacion, user_id)

        if postulacion["estado"] != "aceptada":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede revertir una postulación aceptada"
            )

        return self.repository.update(postulacion_id, {"estado": "pendiente"})

    def delete_postulacion(self, postulacion_id: str, prestador_id: str):

        postulacion = self.get_postulacion(postulacion_id)
        self._verificar_dueno_postulacion(postulacion, prestador_id)

        self.repository.delete(postulacion_id)

        return {"message": "Postulación eliminada correctamente"}