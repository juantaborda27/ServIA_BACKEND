from typing import Optional

from fastapi import HTTPException, status

from app.models.notificacion import Notificacion
from app.repositories.post_repository import PublicacionRepository
from app.repositories.resena_repository import ResenaRepository
from app.schemas.resena import ResenaCreate, ResenaResponse, ResumenCalificaciones


class ResenaService:

    def __init__(
        self,
        repository: ResenaRepository,
        post_repository: PublicacionRepository,
    ):
        self.repository = repository
        self.post_repository = post_repository

    async def create_resena(self, data: ResenaCreate, cliente_id: str) -> ResenaResponse:
        publicacion = await self.post_repository.get_by_id(data.publicacion_id)
        if not publicacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Publicación no encontrada",
            )

        if str(publicacion.usuario_id) != str(cliente_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el cliente contratante puede calificar este servicio",
            )

        if publicacion.estado != "terminado":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El servicio debe estar en estado 'terminado' para poder calificarlo",
            )

        if not data.comentario or len(data.comentario.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El comentario de la reseña es obligatorio y debe tener al menos 3 caracteres",
            )

        if data.calificacion < 1 or data.calificacion > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La calificación debe ser entre 1 y 5 estrellas",
            )

        existente = await self.repository.get_by_publicacion_id(data.publicacion_id)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta publicación ya fue calificada previamente",
            )

        payload = {
            "publicacion_id": data.publicacion_id,
            "cliente_id": cliente_id,
            "prestador_id": data.prestador_id,
            "calificacion": data.calificacion,
            "comentario": data.comentario.strip(),
        }

        resena = await self.repository.create(payload)
        cliente_nombre = resena.cliente.nombre_completo if resena.cliente else "Cliente"
        cliente_foto = resena.cliente.foto_perfil if resena.cliente else None

        # Notificar al prestador sobre la nueva calificación
        try:
            notif = Notificacion(
                usuario_id=data.prestador_id,
                titulo="¡Nueva calificación recibida!",
                mensaje=f"{cliente_nombre} te ha calificado con {data.calificacion} estrellas: \"{data.comentario}\"",
                tipo="calificacion_recibida",
                referencia_id=data.publicacion_id,
            )
            self.repository.db.add(notif)
            await self.repository.db.commit()
        except Exception as e:
            print("Error creando notificación de reseña:", e)

        return ResenaResponse(
            id=str(resena.id),
            publicacion_id=str(resena.publicacion_id),
            cliente_id=str(resena.cliente_id),
            prestador_id=str(resena.prestador_id),
            calificacion=resena.calificacion,
            comentario=resena.comentario,
            created_at=resena.created_at.isoformat() if resena.created_at else None,
            cliente_nombre=cliente_nombre,
            cliente_foto=cliente_foto,
        )

    async def get_resenas_prestador(
        self, prestador_id: str, limit: int = 50, offset: int = 0
    ) -> ResumenCalificaciones:
        resumen = await self.repository.get_resumen_prestador(prestador_id)
        lista = await self.repository.list_by_prestador(prestador_id, limit, offset)

        resenas_dto = []
        for r in lista:
            resenas_dto.append(
                ResenaResponse(
                    id=str(r.id),
                    publicacion_id=str(r.publicacion_id),
                    cliente_id=str(r.cliente_id),
                    prestador_id=str(r.prestador_id),
                    calificacion=r.calificacion,
                    comentario=r.comentario,
                    created_at=r.created_at.isoformat() if r.created_at else None,
                    cliente_nombre=r.cliente.nombre_completo if r.cliente else "Cliente",
                    cliente_foto=r.cliente.foto_perfil if r.cliente else None,
                )
            )

        return ResumenCalificaciones(
            prestador_id=prestador_id,
            promedio=resumen["promedio"],
            total_resenas=resumen["total_resenas"],
            resenas=resenas_dto,
        )

    async def get_resena_publicacion(self, publicacion_id: str) -> Optional[ResenaResponse]:
        resena = await self.repository.get_by_publicacion_id(publicacion_id)
        if not resena:
            return None

        return ResenaResponse(
            id=str(resena.id),
            publicacion_id=str(resena.publicacion_id),
            cliente_id=str(resena.cliente_id),
            prestador_id=str(resena.prestador_id),
            calificacion=resena.calificacion,
            comentario=resena.comentario,
            created_at=resena.created_at.isoformat() if resena.created_at else None,
            cliente_nombre=resena.cliente.nombre_completo if resena.cliente else "Cliente",
            cliente_foto=resena.cliente.foto_perfil if resena.cliente else None,
        )

    async def get_resena_pendiente(self, cliente_id: str) -> Optional[dict]:
        return await self.repository.get_resena_pendiente_cliente(cliente_id)
