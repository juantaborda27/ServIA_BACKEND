from fastapi import HTTPException, status
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import RegisterRequest, LoginRequest


class AuthService:

    def __init__(self):
        self.repository = AuthRepository()

    def register(self, data: RegisterRequest) -> dict:
        response = self.repository.register_user(data)

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario"
            )

        return {
            "message": "Usuario registrado correctamente",
            "user_id": response.user.id
        }

    def login(self, data: LoginRequest) -> dict:
        response = self.repository.login_user(data)

        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        return {
            "message": "Inicio de sesión exitoso",
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id
        }