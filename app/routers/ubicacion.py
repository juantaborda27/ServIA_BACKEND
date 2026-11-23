import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.core.calles_valledupar import sugerir_direccion_valledupar

router = APIRouter(prefix="/ubicaciones", tags=["Ubicaciones"])


class Punto(BaseModel):
    latitud: Annotated[float, Field(ge=-90, le=90)]
    longitud: Annotated[float, Field(ge=-180, le=180)]


@router.post("/direccion", dependencies=[Depends(get_current_user)])
async def buscar_direccion(punto: Punto):
    # Instancia OSM/Nominatim autorizada para procesar ubicaciones privadas.
    base_url = os.getenv("SERVIA_GEOCODER_URL")
    if not base_url:
        return await sugerir_direccion_valledupar(punto.latitud, punto.longitud)

    try:
        url = httpx.URL(base_url.rstrip("/") + "/reverse")
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.host.lower().rstrip(".") == "nominatim.openstreetmap.org"
        ):
            raise HTTPException(503, "Escribe la dirección manualmente.")
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                url,
                params={
                    "lat": punto.latitud, "lon": punto.longitud,
                    "format": "jsonv2", "accept-language": "es",
                },
                headers={"User-Agent": "ServIA/1.0"},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, httpx.InvalidURL, ValueError):
        raise HTTPException(502, "No se pudo consultar la dirección.")

    address = result.get("address") if isinstance(result, dict) else None
    if not isinstance(address, dict):
        return {"direccion": "", "barrio": None, "ciudad": None}
    road = address.get("road") or address.get("pedestrian")
    number = address.get("house_number")
    return {
        "direccion": " ".join(filter(None, (road, number))) if road else "",
        "barrio": address.get("suburb") or address.get("neighbourhood"),
        "ciudad": address.get("city") or address.get("town") or address.get("municipality"),
    }
