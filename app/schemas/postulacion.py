from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EstadoPostulacion(str, Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"
    en_espera = "en_espera"


class PostulacionCreate(BaseModel):
    publicacion_id: str
    precio_ofertado: float
    disponibilidad: str
    mensaje: str


class PostulacionUpdate(BaseModel):
    precio_ofertado: Optional[float] = None
    disponibilidad: Optional[str] = None
    mensaje: Optional[str] = None


class PostulacionEstadoUpdate(BaseModel):
    estado: EstadoPostulacion


class PostulacionResponse(BaseModel):
    id: str
    publicacion_id: str
    prestador_id: str
    precio_ofertado: float
    disponibilidad: str
    mensaje: str
    estado: EstadoPostulacion