from typing import Optional

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from app.core.ubicacion import distancia_km

from app.models.notificacion import Notificacion
from app.repositories.post_repository import PublicacionRepository
from app.repositories.postulacion_repository import PostulacionRepository
from app.services.post_service import PublicacionService
from app.schemas.postulacion import (
    EstadoPostulacion,
    PostulacionCreate,
    PostulacionUpdate,
)


class PostulacionService:

    def __init__(self, repository: PostulacionRepository, publicacion_repository: PublicacionRepository):
        self.repository = repository
        self.publicacion_repository = publicacion_repository

    async def create_postulacion(self, data: PostulacionCreate, prestador_id: str):
        payload = data.model_dump(mode="json")
        return await self.repository.crear_con_validaciones(payload, str(prestador_id))

    async def get_postulacion(self, postulacion_id: str):
        postulacion = await self.repository.get_by_id(postulacion_id)
        if not postulacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Postulación no encontrada"
            )
        return postulacion

    async def get_postulacion_visible(self, postulacion_id: str):
        postulacion = await self.get_postulacion(postulacion_id)
        data = jsonable_encoder(postulacion, exclude={"prestador", "publicacion"})
        if postulacion.publicacion is not None:
            data["publicacion"] = PublicacionService._publicacion_visible(postulacion.publicacion)
        return data

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
        publicacion = None

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
        ocupacion_por_prestador = {}
        if incluir_prestador:
            for postulacion in postulaciones:
                prestador_id_actual = str(postulacion.prestador_id)
                if prestador_id_actual not in ocupacion_por_prestador:
                    ocupacion_por_prestador[prestador_id_actual] = (
                        await self.repository.prestador_tiene_trabajo_activo(
                            prestador_id_actual
                        )
                    )
        return [
            self._serializar_postulacion(
                postulacion,
                incluir_prestador,
                ocupacion_por_prestador.get(str(postulacion.prestador_id), False),
                publicacion,
            )
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
        if nuevo_estado == EstadoPostulacion.aceptada:
            id_conversacion = await self.repository.aceptar_postulacion(
                postulacion_id=postulacion_id,
                user_id=str(user_id),
            )
            return {
                "message": "Postulación aceptada correctamente",
                "id_conversacion": id_conversacion,
                "estado": "aceptada",
            }

        postulacion = await self.get_postulacion(postulacion_id)
        if nuevo_estado == EstadoPostulacion.rechazada:
            await self._verificar_dueno_publicacion(postulacion, user_id)
            if postulacion.estado not in ("pendiente", "en_espera"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Solo se pueden rechazar postulaciones pendientes o en espera",
                )
            return await self.repository.update(
                postulacion_id,
                {"estado": nuevo_estado.value},
            )

        if nuevo_estado == EstadoPostulacion.retirada:
            return await self.retirar_postulacion(postulacion_id, user_id)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado de postulación no permitido",
        )

    async def retirar_postulacion(self, postulacion_id: str, prestador_id: str):
        postulacion = await self.repository.retirar_postulacion(
            postulacion_id=postulacion_id,
            prestador_id=str(prestador_id),
        )
        return {
            "message": "Postulación retirada correctamente",
            "id": str(postulacion.id),
            "estado": postulacion.estado,
            "retirada_at": postulacion.retirada_at,
        }

    async def revertir_aceptacion(self, postulacion_id: str, user_id: str):
        """Si el cliente se arrepiente, vuelve la postulación aceptada a pendiente."""
        postulacion = await self.get_postulacion(postulacion_id)
        await self._verificar_dueno_publicacion(postulacion, user_id)

        if postulacion.estado != "aceptada":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede revertir una postulación aceptada"
            )

        pub_id = str(getattr(postulacion, "publicacion_id", None) or postulacion.get("publicacion_id"))
        await self.repository.actualizar_estado_publicacion(pub_id, "activo")
        return await self.repository.update(postulacion_id, {"estado": "pendiente"})

    async def delete_postulacion(self, postulacion_id: str, prestador_id: str):
        postulacion = await self.get_postulacion(postulacion_id)
        await self._verificar_dueno_postulacion(postulacion, prestador_id)

        if postulacion.estado == "aceptada":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar una postulación aceptada",
            )

        if postulacion.estado in ("pendiente", "en_espera"):
            return await self.retirar_postulacion(postulacion_id, prestador_id)

        await self.repository.delete(postulacion_id)
        return {"message": "Postulación eliminada correctamente"}

    @staticmethod
    def _serializar_postulacion(
        postulacion,
        incluir_prestador: bool,
        ocupado: bool = False,
        publicacion=None,
    ) -> dict:
        prestador = None
        if incluir_prestador and postulacion.prestador:
            usuario = postulacion.prestador.usuario
            prestador = {
                "id": str(postulacion.prestador.id),
                "descripcion": postulacion.prestador.descripcion,
                "disponible": not ocupado,
                "ocupado": ocupado,
                "usuario": {
                    "id": str(usuario.id),
                    "nombre_completo": usuario.nombre_completo,
                    "foto_perfil": usuario.foto_perfil,
                },
            }

        conversacion = postulacion.conversacion
        return {
            "distancia_km": (
                distancia_km(postulacion.prestador, publicacion)
                if publicacion is not None and incluir_prestador else None
            ),
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
