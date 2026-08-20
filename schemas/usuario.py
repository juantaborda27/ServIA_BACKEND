from pydantic import BaseModel
from typing import Optional


class UsuarioCreate(BaseModel):
    nombre_completo: str
    telefono: Optional[str] = None
    ubicacion: Optional[str] = None


class UsuarioResponse(BaseModel):
    id: str
    nombre_completo: str
    telefono: Optional[str] = None
    foto_perfil: Optional[str] = None
    ubicacion: Optional[str] = None
    activo: bool