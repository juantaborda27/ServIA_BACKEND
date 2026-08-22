from app.core.supabase import supabase


class UsuarioRepository:

    def get_by_id(self, user_id: str):

        response = (
            supabase
            .table("usuarios")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )

        return response.data

    def update(self, user_id: str, data: dict):

        response = (
            supabase
            .table("usuarios")
            .update(data)
            .eq("id", user_id)
            .execute()
        )

        return response.data

    def delete(self, user_id: str):

        response = (
            supabase
            .table("usuarios")
            .update({
                "activo": False
            })
            .eq("id", user_id)
            .execute()
        )

        return response.data