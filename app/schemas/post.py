from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class NivelUrgencia(str, Enum):
    ahora = "ahora"
    hoy = "hoy"
    esta_semana = "esta semana"
    no_tengo_prisa = "no tengo prisa"


class EstadoPublicacion(str, Enum):
    activo = "activo"
    acuerdo = "acuerdo"
    en_progreso = "en_progreso"
    pendiente_confirmacion = "pendiente_confirmacion"
    terminado = "terminado"
    cancelado = "cancelado"
    expirado = "expirado"
    en_disputa = "en_disputa"


class CoordenadasPublicacion(BaseModel):
    latitud: Optional[float] = Field(default=None, ge=-90, le=90)
    longitud: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validar_par(self):
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("Envía latitud y longitud juntas")
        if ("latitud" in self.model_fields_set) != ("longitud" in self.model_fields_set):
            raise ValueError("Envía latitud y longitud juntas")
        return self


class PublicacionCreate(CoordenadasPublicacion):
    descripcion: str
    categoria_id: str
    urgencia: NivelUrgencia
    direccion: Optional[str] = "Valledupar, Cesar"
    barrio: Optional[str] = "Valledupar"
    referencia: Optional[str] = None
    ciudad: Optional[str] = "Valledupar"


class PublicacionUpdate(CoordenadasPublicacion):
    descripcion: Optional[str] = None
    categoria_id: Optional[str] = None
    urgencia: Optional[NivelUrgencia] = None
    direccion: Optional[str] = None
    barrio: Optional[str] = None
    referencia: Optional[str] = None
    ciudad: Optional[str] = None


class PublicacionEstadoUpdate(BaseModel):
    estado: EstadoPublicacion


class PublicacionCancelarRequest(BaseModel):
    motivo: Optional[str] = None


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
    imagenes: list[Any] = Field(default_factory=list)
