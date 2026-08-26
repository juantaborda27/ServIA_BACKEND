from typing import Optional

from app.core.supabase import supabase


class PostulacionRepository:

    def create(self, data: dict):
        data["estado"] = "pendiente"  
        response = (
            supabase
            .table("postulaciones")
            .insert(data)
            .execute()
        )

        return response.data[0] if response.data else None

    def get_by_id(self, postulacion_id: str):

        response = (
            supabase
            .table("postulaciones")
            .select(
                "*, "
                "prestador:usuarios(nombre_completo, telefono, foto_perfil), "
                "publicacion:publicaciones(usuario_id, estado)"
            )
            .eq("id", postulacion_id)
            .single()
            .execute()
        )

        return response.data

    def list(
        self,
        publicacion_id: Optional[str] = None,
        prestador_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        incluir_prestador: bool = False,
    ):

        campos = ["*"]
        if incluir_prestador:
            campos.append("prestador:usuarios(nombre_completo, foto_perfil)")

        query = supabase.table("postulaciones").select(", ".join(campos))

        if publicacion_id:
            query = query.eq("publicacion_id", publicacion_id)

        if prestador_id:
            query = query.eq("prestador_id", prestador_id)

        if estado:
            query = query.eq("estado", estado)

        response = (
            query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return response.data

    def get_activa(self, publicacion_id: str, prestador_id: str):
        """Busca si el prestador ya tiene una postulación activa (pendiente/en_espera) para esta publicación."""

        response = (
            supabase
            .table("postulaciones")
            .select("id, estado")
            .eq("publicacion_id", publicacion_id)
            .eq("prestador_id", prestador_id)
            .in_("estado", ["pendiente", "en_espera"])
            .execute()
        )

        return response.data[0] if response.data else None

    def update(self, postulacion_id: str, data: dict):

        response = (
            supabase
            .table("postulaciones")
            .update(data)
            .eq("id", postulacion_id)
            .execute()
        )

        return response.data[0] if response.data else None

    def poner_en_espera_otras(self, publicacion_id: str, postulacion_id_aceptada: str):
        """Al aceptar una oferta, las demás pendientes quedan en espera (no rechazadas),
        por si el cliente se arrepiente y quiere volver a considerarlas."""

        response = (
            supabase
            .table("postulaciones")
            .update({"estado": "en_espera"})
            .eq("publicacion_id", publicacion_id)
            .neq("id", postulacion_id_aceptada)
            .eq("estado", "pendiente")
            .execute()
        )

        return response.data

    def delete(self, postulacion_id: str):

        response = (
            supabase
            .table("postulaciones")
            .delete()
            .eq("id", postulacion_id)
            .execute()
        )

        return response.data[0] if response.data else None