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

    def __init__(self,repository: PostulacionRepository, publicacion_repository: PublicacionRepository):

        self.repository = repository
        self.publicacion_repository = publicacion_repository

    async def create_postulacion(self, data: PostulacionCreate, prestador_id: str):

        activa = await self.repository.get_activa(data.publicacion_id, prestador_id)

        if activa:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya tienes una postulación activa para esta publicación"
            )

        payload = data.model_dump(mode="json")
        payload["prestador_id"] = prestador_id

        postulacion = await self.repository.create(payload)

        if not postulacion:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear la postulación"
            )

        return postulacion

    async def get_postulacion(self, postulacion_id: str):

        postulacion = await self.repository.get_by_id(postulacion_id)

        if not postulacion:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Postulación no encontrada"
            )

        return postulacion

    async def list_postulaciones(
        self,
        user_id: str,
        publicacion_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        incluir_prestador: bool = False,
    ):
        prestador_id = user_id

        if publicacion_id:
            publicacion = await self.publicacion_repository.get_by_id(
                publicacion_id
            )
            if not publicacion:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Publicación no encontrada",
                )

            if str(publicacion.usuario_id) == str(user_id):
                prestador_id = None
            incluir_prestador = (
                incluir_prestador
                or str(publicacion.usuario_id) == str(user_id)
            )

        postulaciones = await self.repository.list_all(
            publicacion_id=publicacion_id,
            prestador_id=prestador_id,
            estado=estado,
            limit=limit,
            offset=offset,
            incluir_prestador=incluir_prestador,
        )
        return [
            self._serializar_postulacion(postulacion, incluir_prestador)
            for postulacion in postulaciones
        ]

    async def update_postulacion(
        self,
        postulacion_id: str,
        data: PostulacionUpdate,
        prestador_id: str,
    ):

        postulacion = await self.get_postulacion(postulacion_id)
        await self._verificar_dueno_postulacion(postulacion, prestador_id)

        update_data = data.model_dump(exclude_unset=True, mode="json")

        return await self.repository.update(postulacion_id, update_data)

    async def cambiar_estado(
        self,
        postulacion_id: str,
        nuevo_estado: EstadoPostulacion,
        user_id: str,
    ):
        postulacion = await self.get_postulacion(postulacion_id)

        if nuevo_estado == EstadoPostulacion.aceptada:
            await self._verificar_dueno_publicacion(postulacion, user_id)

            if postulacion.estado != "pendiente":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo se pueden aceptar postulaciones pendientes",
                )

            id_conversacion = await self.repository.aceptar_postulacion(
                postulacion_id=postulacion_id,
                publicacion_id=str(postulacion.publicacion_id),
            )

            return {
                "message": "Postulación aceptada correctamente",
                "id_conversacion": id_conversacion,
                "estado": "aceptada",
            }

        if nuevo_estado == EstadoPostulacion.rechazada:
            await self._verificar_dueno_publicacion(postulacion, user_id)
            if postulacion.estado not in ("pendiente", "en_espera"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo se pueden rechazar postulaciones pendientes",
                )
            return await self.repository.update(
                postulacion_id,
                {"estado": nuevo_estado.value},
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado de postulación no permitido",
        )

    async def revertir_aceptacion(self, postulacion_id: str, user_id: str):
        """Si el cliente se arrepiente, vuelve la postulación aceptada a pendiente."""

        postulacion = await self.get_postulacion(postulacion_id)
        await self._verificar_dueno_publicacion(postulacion, user_id)

        if postulacion.estado != "aceptada":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede revertir una postulación aceptada"
            )

        return await self.repository.update(postulacion_id, {"estado": "pendiente"})

    async def delete_postulacion(self, postulacion_id: str, prestador_id: str):

        postulacion = await self.get_postulacion(postulacion_id)
        await self._verificar_dueno_postulacion(postulacion, prestador_id)

        await self.repository.delete(postulacion_id)

        return {"message": "Postulación eliminada correctamente"}

    @staticmethod
    def _serializar_postulacion(postulacion, incluir_prestador: bool) -> dict:
        prestador = None
        if incluir_prestador and postulacion.prestador:
            usuario = postulacion.prestador.usuario
            prestador = {
                "id": str(postulacion.prestador.id),
                "descripcion": postulacion.prestador.descripcion,
                "usuario": {
                    "id": str(usuario.id),
                    "nombre_completo": usuario.nombre_completo,
                    "foto_perfil": usuario.foto_perfil,
                },
            }

        conversacion = postulacion.conversacion
        return {
            "id": str(postulacion.id),
            "publicacion_id": str(postulacion.publicacion_id),
            "prestador_id": str(postulacion.prestador_id),
            "precio_ofertado": float(postulacion.precio_ofertado),
            "disponibilidad": postulacion.disponibilidad,
            "mensaje": postulacion.mensaje,
            "estado": postulacion.estado,
            "created_at": postulacion.created_at,
            "updated_at": postulacion.updated_at,
            "id_conversacion": (
                str(conversacion.id_conversacion) if conversacion else None
            ),
            "prestador": prestador,
        }

    @staticmethod
    async def _verificar_dueno_postulacion(postulacion, prestador_id: str):
        if str(postulacion.prestador_id) != str(prestador_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre esta postulación",
            )

    @staticmethod
    async def _verificar_dueno_publicacion(postulacion, user_id: str):
        if str(postulacion.publicacion.usuario_id) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre esta publicación",
            )