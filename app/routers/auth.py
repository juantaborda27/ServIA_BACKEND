from fastapi import APIRouter, Depends, HTTPException

from app.core.supabase import supabase
from app.schemas.auth import RegisterRequest, LoginRequest

router = APIRouter(
    prefix="/auth",
    tags=["Autenticacion"],
)

@router.post("/register")
def register(data: RegisterRequest):

    response = supabase.auth.sign_up({
        "email": data.email,
        "password": data.password,
        "options": {
            "data": {
                "nombre_completo": data.nombre_completo,
                "telefono": data.telefono,
                "ubicacion": data.ubicacion
            }
        }
    })

    if not response.user:
        raise HTTPException(
            status_code=400,
            detail="No se pudo crear el usuario"
        )

    return {
        "message": "Usuario registrado correctamente",
        "user_id": response.user.id
    }


@router.post("/login")
def login(data: LoginRequest):

    response = supabase.auth.sign_in_with_password({
        "email": data.email,
        "password": data.password
    })

    if not response.user or not response.session:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    return {
        "message": "Inicio de sesión exitoso",
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user_id": response.user.id
    }