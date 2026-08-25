from typing import Optional

from app.core.supabase import supabase


class PublicacionRepository:

    def create(self, data: dict):

        response = (
            supabase
            .table("publicaciones")
            .insert(data)
            .execute()
        )

        return response.data[0] if response.data else None

    def get_by_id(self, publicacion_id: str):

        response = (
            supabase
            .table("publicaciones")
            .select("*")
            .eq("id", publicacion_id)
            .single()
            .execute()
        )

        return response.data

    def list(
        self,
        estado: Optional[str] = None,
        categoria_id: Optional[str] = None,
        usuario_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):

        query = supabase.table("publicaciones").select("*")

        if estado:
            query = query.eq("estado", estado)

        if categoria_id:
            query = query.eq("categoria_id", categoria_id)

        if usuario_id:
            query = query.eq("usuario_id", usuario_id)

        response = (
            query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return response.data

    def update(self, publicacion_id: str, data: dict):

        response = (
            supabase
            .table("publicaciones")
            .update(data)
            .eq("id", publicacion_id)
            .execute()
        )

        return response.data[0] if response.data else None

    def delete(self, publicacion_id: str):

        response = (
            supabase
            .table("publicaciones")
            .delete()
            .eq("id", publicacion_id)
            .execute()
        )

        return response.data[0] if response.data else None