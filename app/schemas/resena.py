from typing import Any, Optional
from pydantic import BaseModel, Field


class ResenaCreate(BaseModel):
    publicacion_id: str
    prestador_id: str
    calificacion: int = Field(..., ge=1, le=5, description="Calificación entre 1 y 5 estrellas")
    comentario: str = Field(..., min_length=3, description="Comentario u opinión obligatoria sobre el servicio recibido")


class ResenaResponse(BaseModel):
    id: str
    publicacion_id: str
    cliente_id: str
    prestador_id: str
    calificacion: int
    comentario: str
    created_at: Any
    cliente_nombre: Optional[str] = None
    cliente_foto: Optional[str] = None


class ResumenCalificaciones(BaseModel):
    prestador_id: str
    promedio: float
    total_resenas: int
    resenas: list[ResenaResponse] = []
