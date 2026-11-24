from typing import Optional

from fastapi import HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder

from app.core.ubicacion import distancia_km
from app.core.storage import image_storage
from app.repositories.prestador_repository import PrestadorRepository

from app.repositories.post_repository import PublicacionRepository
from app.schemas.post import (
    EstadoPublicacion,
    PublicacionCreate,
    PublicacionUpdate,
)


class PublicacionService:

    def __init__(self, repository: PublicacionRepository):
        self.repository = repository

    async def create_publicacion(self, data: PublicacionCreate, user_id: str):
        payload = data.model_dump(mode="json")
        payload["usuario_id"] = user_id

        publicacion = await self.repository.create(payload)
        if not publicacion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear la publicación"
            )
        return publicacion

    async def get_publicacion(self, publicacion_id: str):
        publicacion = await self.repository.get_by_id(publicacion_id)
        if not publicacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Publicación no encontrada"
            )
        return publicacion

    async def list_publicaciones(
        self,
        estado: Optional[str] = None,
        prestador_id: Optional[str] = None,
        categoria_id: Optional[str] = None,
        usuario_id: Optional[str] = None,
        barrio: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        incluir_usuario: bool = True,
        incluir_categoria: bool = True,
    ):
        return await self.repository.list_all(
            estado=estado,
            prestador_id=prestador_id,
            categoria_id=categoria_id,
            usuario_id=usuario_id,
            barrio=barrio,
            limit=limit,
            offset=offset,
            incluir_usuario=incluir_usuario,
            incluir_categoria=incluir_categoria,
        )

    async def update_publicacion(
        self,
        publicacion_id: str,
        data: PublicacionUpdate,
        user_id: str,
    ):
        publicacion = await self.get_publicacion(publicacion_id)
        await self._verificar_dueno(publicacion, user_id)

        update_data = data.model_dump(exclude_unset=True, mode="json")
        return await self.repository.update(publicacion_id, update_data)

    @staticmethod
    def _publicacion_visible(publicacion, prestador=None, detalle_privado=False):
        data = jsonable_encoder(publicacion, exclude={"usuario", "resenas", "imagenes"})
        if not detalle_privado:
            for field in ("direccion", "referencia", "latitud", "longitud"):
                data[field] = None
        data["distancia_km"] = distancia_km(prestador, publicacion)
        data["solicitud_tiene_punto"] = publicacion.latitud is not None and publicacion.longitud is not None
        data["prestador_tiene_punto"] = bool(
            prestador and prestador.base_latitud is not None and prestador.base_longitud is not None
        )
        data["imagenes"] = [
            {
                "id": str(image.id),
                "url": image_storage.signed_url(image.s3_key),
                "content_type": image.content_type,
            }
            for image in getattr(publicacion, "imagenes", [])
        ]
        return data

    async def upload_images(
        self,
        publicacion_id: str,
        files: list[UploadFile],
        user_id: str,
    ):
        publicacion = await self.get_publicacion(publicacion_id)
        await self._verificar_dueno(publicacion, user_id)

        if not files:
            raise HTTPException(status_code=400, detail="Envía al menos una imagen")
        if len(publicacion.imagenes) + len(files) > 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Una publicación puede tener como máximo 5 imágenes",
            )

        stored = []
        try:
            for file in files:
                stored.append(await image_storage.upload(publicacion_id, file))
            publicacion = await self.repository.add_images(
                publicacion_id,
                [(image.key, image.content_type) for image in stored],
            )
        except Exception:
            for image in stored:
                await image_storage.delete(image.key)
            raise

        return self._publicacion_visible(publicacion, detalle_privado=True)

    async def list_publicaciones_visibles(self, prestador_id=None, **filters):
        publicaciones = await self.list_publicaciones(prestador_id=prestador_id, **filters)
        prestador = None
        if prestador_id is not None:
            prestador = await PrestadorRepository(self.repository.db).get_by_id(prestador_id)
        return [self._publicacion_visible(pub, prestador) for pub in publicaciones]

    async def get_publicacion_visible(self, publicacion_id, user_id=None):
        publicacion = await self.get_publicacion(publicacion_id)
        if user_id is None:
            return self._publicacion_visible(publicacion)
        if publicacion.usuario_id == user_id:
            return self._publicacion_visible(publicacion, detalle_privado=True)
        asignada = await self.repository.get_postulacion_aceptada(publicacion_id)
        prestador = await PrestadorRepository(self.repository.db).get_by_id(user_id)
        return self._publicacion_visible(
            publicacion,
            prestador,
            detalle_privado=asignada is not None and asignada.prestador_id == user_id,
        )

    TRANSICIONES_PERMITIDAS = {
        "activo": {"acuerdo", "cancelado"},
        "acuerdo": {"en_progreso", "cancelado"},
        "en_progreso": {"pendiente_confirmacion", "cancelado"},
        "pendiente_confirmacion": {"terminado", "cancelado"},
    }

    async def cambiar_estado(
        self,
        publicacion_id: str,
        nuevo_estado: EstadoPublicacion,
        user_id: str,
    ):
        publicacion = await self.get_publicacion(publicacion_id)
        permitidos = self.TRANSICIONES_PERMITIDAS.get(publicacion.estado, set())
        if nuevo_estado.value not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transición no permitida de '{publicacion.estado}' a '{nuevo_estado.value}'",
            )

        if nuevo_estado == EstadoPublicacion.cancelado:
            return await self.cancelar_trabajo(publicacion_id, user_id)
        if nuevo_estado == EstadoPublicacion.en_progreso:
            return await self.iniciar_trabajo(publicacion_id, user_id)
        if nuevo_estado == EstadoPublicacion.terminado:
            return await self.confirmar_finalizacion(publicacion_id, user_id)
        if nuevo_estado == EstadoPublicacion.pendiente_confirmacion:
            return await self.completar_trabajo(publicacion_id, user_id)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usa el endpoint específico de aceptación de oferta para pasar a 'acuerdo'",
        )

    async def iniciar_trabajo(self, publicacion_id: str, user_id: str):
        """Solo el prestador asignado puede iniciar un servicio en estado 'acuerdo'."""
        return await self.repository.iniciar_trabajo_atomico(publicacion_id, str(user_id))

    async def completar_trabajo(self, publicacion_id: str, user_id: str):
        """El prestador asignado solicita confirmaciÃ³n de finalizaciÃ³n."""
        return await self.repository.solicitar_finalizacion_atomico(publicacion_id, str(user_id))

    async def confirmar_finalizacion(self, publicacion_id: str, user_id: str):
        """Solo el cliente propietario confirma y termina definitivamente el servicio."""
        return await self.repository.confirmar_finalizacion_atomico(publicacion_id, str(user_id))

    async def cancelar_trabajo(
        self,
        publicacion_id: str,
        user_id: str,
        motivo: Optional[str] = None,
    ):
        """Cancela el servicio, libera al prestador y cierra la conversación si aplica."""
        return await self.repository.cancelar_trabajo_atomico(
            publicacion_id, str(user_id), motivo
        )

    async def get_trabajos_prestador(self, prestador_id: str, tipo: str = "activos"):
        if tipo in ("historial", "completados"):
            estados = ["terminado", "cancelado"]
        else:
            estados = ["acuerdo", "en_progreso", "pendiente_confirmacion"]

        return await self.repository.get_trabajos_prestador(prestador_id, estados)

    async def delete_publicacion(self, publicacion_id: str, user_id: str):
        publicacion = await self.get_publicacion(publicacion_id)
        await self._verificar_dueno(publicacion, user_id)

        await self.repository.delete(publicacion_id)
        for image in publicacion.imagenes:
            await image_storage.delete(image.s3_key)
        return {"message": "Publicación eliminada correctamente"}

    @staticmethod
    async def _verificar_dueno(publicacion, user_id: str):
        owner_id = str(publicacion.usuario_id) if hasattr(publicacion, "usuario_id") else str(publicacion.get("usuario_id"))
        if owner_id != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre esta publicación"
            )

    async def get_publicaciones_by_usuario(self, usuario_id: str):
        return await self.repository.list_all(usuario_id=usuario_id)
