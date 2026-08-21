from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nombre_completo: str
    telefono: str | None = None
    ubicacion: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str