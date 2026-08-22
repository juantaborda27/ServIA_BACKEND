from app.core.supabase import supabase
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest


class AuthRepository:

    def register_user(self, data: RegisterRequest):
        return supabase.auth.sign_up({
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

    def login_user(self, data: LoginRequest):
        return supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

    def refresh_session(self, data: RefreshRequest):

        return supabase.auth.refresh_session(
            data.refresh_token
        )

    def logout_user(self, access_token: str):

        return supabase.auth.admin.sign_out(
            access_token
        )