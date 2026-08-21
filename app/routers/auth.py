from fastapi import APIRouter
from app.schemas.auth import RegisterRequest, LoginRequest
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