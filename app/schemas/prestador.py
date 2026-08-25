from pydantic import BaseModel, Field
from typing import Optional
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
    descripcion: str = Field(..., max_length=500)
    disponible: bool = True
    verificado: bool = False


class PrestadorCreate(PrestadorBase):
    id: UUID  # mismo id que el usuario (FK a usuarios.id)
    categoria_ids: list[UUID] = []  # ids de las categorías a asignar como especialidades


class PrestadorUpdate(BaseModel):
    descripcion: Optional[str] = None
    disponible: Optional[bool] = None
    verificado: Optional[bool] = None
    categoria_ids: Optional[list[UUID]] = None  # si se envía, reemplaza las especialidades actuales


class PrestadorResponse(PrestadorBase):
    id: UUID
    fecha_creacion: datetime
    categorias: list[CategoriaResponse] = []  # categorías combinadas aquí

    class Config:
        from_attributes = True