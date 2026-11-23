from app.repositories.notificacion_repository import NotificacionRepository
from app.schemas.notificacion import (
    ListaNotificacionesResponse,
    NotificacionCreate,
    NotificacionResponse,
)


class NotificacionService:

    def __init__(self, repository: NotificacionRepository):
        self.repository = repository

    async def create_notificacion(self, data: NotificacionCreate) -> NotificacionResponse:
        payload = data.model_dump(exclude_unset=True)
        notif = await self.repository.create(payload)
        return NotificacionResponse(
            id=str(notif.id),
            usuario_id=str(notif.usuario_id),
            titulo=notif.titulo,
            mensaje=notif.mensaje,
            tipo=notif.tipo,
            leida=notif.leida,
            referencia_id=notif.referencia_id,
            data=notif.data,
            created_at=notif.created_at.isoformat() if notif.created_at else None,
        )

    async def list_notificaciones(
        self, user_id: str, rol: str, limit: int = 50, offset: int = 0
    ) -> ListaNotificacionesResponse:
        total = await self.repository.count_total(user_id, rol)
        no_leidas = await self.repository.count_unread(user_id, rol)
        items = await self.repository.list_by_user(user_id, rol, limit, offset)

        dtos = [
            NotificacionResponse(
                id=str(n.id),
                usuario_id=str(n.usuario_id),
                titulo=n.titulo,
                mensaje=n.mensaje,
                tipo=n.tipo,
                leida=n.leida,
                referencia_id=n.referencia_id,
                data=n.data,
                created_at=n.created_at.isoformat() if n.created_at else None,
            )
            for n in items
        ]

        return ListaNotificacionesResponse(
            total=total,
            no_leidas=no_leidas,
            notificaciones=dtos,
        )

    async def mark_as_read(self, notif_id: str, user_id: str, rol: str) -> bool:
        return await self.repository.mark_as_read(notif_id, user_id, rol)

    async def mark_all_as_read(self, user_id: str, rol: str) -> int:
        return await self.repository.mark_all_as_read(user_id, rol)

    async def delete_notificacion(self, notif_id: str, user_id: str, rol: str) -> bool:
        return await self.repository.delete(notif_id, user_id, rol)
