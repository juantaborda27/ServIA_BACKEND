from fastapi import APIRouter
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Autenticacion"],
)

auth_service = AuthService()


@router.post("/register")
def register(data: RegisterRequest):
    return auth_service.register(data)


@router.post("/login")
def login(data: LoginRequest):
    return auth_service.login(data)

@router.post("/refresh")
def refresh(data: RefreshRequest):

    return auth_service.refresh(data)