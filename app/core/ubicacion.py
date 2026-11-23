from math import asin, cos, isfinite, radians, sin, sqrt


def distancia_km(prestador, publicacion) -> float | None:
    if prestador is None:
        return None
    points = (
        prestador.base_latitud, prestador.base_longitud,
        publicacion.latitud, publicacion.longitud,
    )
    if any(
        value is None or not isfinite(value) or abs(value) > limit
        for value, limit in zip(points, (90, 180, 90, 180))
    ):
        return None
    lat1, lon1, lat2, lon2 = map(radians, points)
    haversine = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return round(12_742 * asin(sqrt(max(0, min(1, haversine)))), 1)
