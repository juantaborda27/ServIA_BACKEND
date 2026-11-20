from typing import Any, Optional
from pydantic import BaseModel


class NotificacionCreate(BaseModel):
    usuario_id: str
    titulo: str
    mensaje: str
    tipo: Optional[str] = "sistema"
    referencia_id: Optional[str] = None
    data: Optional[Any] = None


class NotificacionResponse(BaseModel):
    id: str
    usuario_id: str
    titulo: str
    mensaje: str
    tipo: str
    leida: bool
    referencia_id: Optional[str] = None
    created_at: Any


class ListaNotificacionesResponse(BaseModel):
    total: int
    no_leidas: int
    notificaciones: list[NotificacionResponse] = []
