from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class NivelUrgencia(str, Enum):
    ahora = "ahora"
    hoy = "hoy"
    esta_semana = "esta semana"
    no_tengo_prisa = "no tengo prisa"


class EstadoPublicacion(str, Enum):
    activo = "activo"
    con_ofertas = "con_ofertas"
    acuerdo = "acuerdo"
    en_progreso = "en_progreso"
    terminado = "terminado"
    cancelado = "cancelado"
    expirado = "expirado"
    en_disputa = "en_disputa"


class PublicacionCreate(BaseModel):
    descripcion: str
    categoria_id: str
    urgencia: NivelUrgencia
    direccion: Optional[str] = "Valledupar, Cesar"
    barrio: Optional[str] = "Valledupar"
    referencia: Optional[str] = None
    ciudad: Optional[str] = "Valledupar"
    latitud: Optional[float] = None
    longitud: Optional[float] = None


class PublicacionUpdate(BaseModel):
    descripcion: Optional[str] = None
    categoria_id: Optional[str] = None
    urgencia: Optional[NivelUrgencia] = None
    direccion: Optional[str] = None
    barrio: Optional[str] = None
    referencia: Optional[str] = None
    ciudad: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None


class PublicacionEstadoUpdate(BaseModel):
    estado: EstadoPublicacion


class PublicacionResponse(BaseModel):
    id: str
    descripcion: str
    categoria_id: str
    urgencia: NivelUrgencia
    usuario_id: str
    direccion: Optional[str] = None
    barrio: Optional[str] = None
    referencia: Optional[str] = None
    ciudad: Optional[str] = "Valledupar"
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    ha_sido_calificada: bool = False
    estado: EstadoPublicacion
    created_at: Any
    updated_at: Any
    categoria: Optional[Any] = None
    usuario: Optional[Any] = None
