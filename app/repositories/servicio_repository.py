from app.core.supabase import supabase

class ServicioRepository:
    def create(self, data: dict):
        response = supabase.table("servicios").insert(data).execute()
        return response.data[0] if response.data else None

    def get_by_id(self, servicio_id: str):
        response = supabase.table("servicios").select("*").eq("id", servicio_id).single().execute()
        return response.data

    def update(self, servicio_id: str, data: dict):
        response = supabase.table("servicios").update(data).eq("id", servicio_id).execute()
        return response.data[0] if response.data else None

    def delete(self, servicio_id: str):
        response = supabase.table("servicios").delete().eq("id", servicio_id).execute()
        return response.data