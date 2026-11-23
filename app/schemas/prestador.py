from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime


class CategoriaResponse(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str] = None
    icono: Optional[str] = None

    class Config:
        from_attributes = True


class PrestadorBase(BaseModel):
    descripcion: str = Field(
        ...,
        min_length=20,
        max_length=500
    )
    disponible: bool = True
    verificado: bool = False


class PrestadorCreate(BaseModel):
    descripcion: str = Field(
        ...,
        min_length=20,
        max_length=500
    )
    categoria_ids: list[UUID] = Field(
        ...,
        min_length=1
    )


class PrestadorUpdate(BaseModel):
    descripcion: Optional[str] = Field(
        default=None,
        min_length=20,
        max_length=500
    )
    disponible: Optional[bool] = None
    verificado: Optional[bool] = None
    categoria_ids: Optional[list[UUID]] = None


class PrestadorResponse(PrestadorBase):
    id: UUID
    fecha_creacion: datetime
    categorias: list[CategoriaResponse] = []

    class Config:
        from_attributes = True


class UbicacionPrestador(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    direccion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=250)]
