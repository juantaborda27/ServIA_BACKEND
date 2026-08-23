from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ServicioBase(BaseModel):
    nombre: str
    descripcion: str
    precioDesde: Decimal
    precioHasta: Decimal
    duracionEstimada: int
    categoria_id: str

class ServicioCreate(ServicioBase):
    pass 

class ServicioUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio_desde: Decimal = Field(alias="precioDesde")
    precio_hasta: Decimal = Field(alias="precioHasta")
    duracion_estimada: int = Field(alias="duracionEstimada")
    categoria_id: Optional[str] = None

class ServicioResponse(ServicioBase):
    id: str
    prestador_id: str
    activo: bool
    fechaPublicacion: Optional[datetime] = None
