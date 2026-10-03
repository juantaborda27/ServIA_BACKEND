from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import AuthService
from app.repositories.auth_repository import AuthRepository
from app.core.database import get_db  # ajusta al path real de tu dependencia de sesión

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/register")
async def register(data: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(data)


@router.post("/refresh")
async def refresh(data: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    return await service.refresh(data)