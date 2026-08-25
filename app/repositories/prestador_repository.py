from typing import Optional

from app.core.supabase import supabase


class PrestadorRepository:

    def create(self, data: dict):

        response = (
            supabase
            .table("prestadores")
            .insert(data)
            .execute()
        )

        return response.data[0] if response.data else None

    def get_by_id(self, prestador_id: str):

        response = (
            supabase
            .table("prestadores")
            .select("*, categorias:especialidades(categoria:categorias(*))")
            .eq("id", prestador_id)
            .single()
            .execute()
        )

        return response.data

    def list(
        self,
        disponible: Optional[bool] = None,
        verificado: Optional[bool] = None,
        categoria_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):

        query = supabase.table("prestadores").select(
            "*, categorias:especialidades(categoria:categorias(*))"
        )

        if disponible is not None:
            query = query.eq("disponible", disponible)

        if verificado is not None:
            query = query.eq("verificado", verificado)

        if categoria_id:
            query = query.eq("especialidades.categoria_id", categoria_id)

        response = (
            query
            .order("fecha_creacion", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return response.data

    def update(self, prestador_id: str, data: dict):

        response = (
            supabase
            .table("prestadores")
            .update(data)
            .eq("id", prestador_id)
            .execute()
        )

        return response.data[0] if response.data else None

    def delete(self, prestador_id: str):

        response = (
            supabase
            .table("prestadores")
            .delete()
            .eq("id", prestador_id)
            .execute()
        )

        return response.data[0] if response.data else None

    # --- Manejo de especialidades (tabla intermedia) ---

    def add_especialidades(self, prestador_id: str, categoria_ids: list[str]):

        rows = [
            {"prestador_id": prestador_id, "categoria_id": categoria_id}
            for categoria_id in categoria_ids
        ]

        response = (
            supabase
            .table("especialidades")
            .insert(rows)
            .execute()
        )

        return response.data

    def replace_especialidades(self, prestador_id: str, categoria_ids: list[str]):

        # Elimina las especialidades actuales del prestador
        (
            supabase
            .table("especialidades")
            .delete()
            .eq("prestador_id", prestador_id)
            .execute()
        )

        # Inserta las nuevas
        if not categoria_ids:
            return []

        return self.add_especialidades(prestador_id, categoria_ids)

    def remove_especialidad(self, prestador_id: str, categoria_id: str):

        response = (
            supabase
            .table("especialidades")
            .delete()
            .eq("prestador_id", prestador_id)
            .eq("categoria_id", categoria_id)
            .execute()
        )

        return response.data