from enum import Enum
from typing import Optional

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


class PublicacionUpdate(BaseModel):
    descripcion: Optional[str] = None
    categoria_id: Optional[str] = None
    urgencia: Optional[NivelUrgencia] = None


class PublicacionEstadoUpdate(BaseModel):
    estado: EstadoPublicacion


class PublicacionResponse(BaseModel):
    id: str
    descripcion: str
    categoria_id: str
    urgencia: NivelUrgencia
    usuario_id: str
    estado: EstadoPublicacion
    created_at: str
    updated_at: str