from fastapi import HTTPException, status
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token


class AuthService:

    def __init__(self, repository: AuthRepository):
        self.repository = repository

    async def register(self, data: RegisterRequest) -> dict:
        existente = await self.repository.get_by_email(data.email)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo ya está registrado"
            )

        usuario = await self.repository.create_user(data)
        return {
            "message": "Usuario registrado correctamente",
            "user_id": str(usuario.id)
        }

    async def login(self, data: LoginRequest) -> TokenResponse:
        usuario = await self.repository.get_by_email(data.email)

        if not usuario or not verify_password(data.password, usuario.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )

        return TokenResponse(
            access_token=create_access_token(usuario.id),
            refresh_token=create_refresh_token(usuario.id),
            user_id=str(usuario.id)
        )

    async def refresh(self, data: RefreshRequest) -> dict:
        try:
            payload = decode_token(data.refresh_token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido o expirado"
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no es de tipo refresh"
            )

        user_id = payload["sub"]
        return {
            "access_token": create_access_token(user_id),
            "refresh_token": create_refresh_token(user_id)
        }