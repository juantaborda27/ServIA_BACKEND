import asyncio
import gzip
import json
from math import cos, radians
from pathlib import Path
from tempfile import gettempdir
from time import monotonic, time

import httpx

# La consulta descarga cartografía pública de toda la zona. El punto del
# usuario se compara en memoria y nunca forma parte de la consulta externa.
BOUNDS = (10.41, -73.30, 10.51, -73.20)
QUERY = (
    '[out:json][timeout:20];('
    f'way[highway][name]{BOUNDS};'
    f'nwr["addr:housenumber"]["addr:street"]{BOUNDS};'
    ');out geom;'
)
ENDPOINTS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
_lock = asyncio.Lock()
_elements = []
_next_fetch = 0
_cache_file = Path(gettempdir()) / "servia-calles-valledupar-v1.json.gz"
_cache_ttl = 7 * 24 * 3600


async def _cartografia():
    global _elements, _next_fetch
    async with _lock:
        if monotonic() < _next_fetch:
            return _elements
        if not _elements:
            try:
                with gzip.open(_cache_file, "rt", encoding="utf-8") as source:
                    _elements = json.load(source)
                remaining = _cache_ttl - (time() - _cache_file.stat().st_mtime)
                if _elements and remaining > 0:
                    _next_fetch = monotonic() + remaining
                    return _elements
            except (OSError, ValueError):
                pass
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for endpoint in ENDPOINTS:
                try:
                    response = await client.get(
                        endpoint, params={"data": QUERY},
                        headers={"User-Agent": "ServIA/1.0"},
                        timeout=10,
                    )
                    response.raise_for_status()
                    elements = response.json()["elements"]
                    if elements:
                        _elements = elements
                        _next_fetch = monotonic() + _cache_ttl
                        try:
                            with gzip.open(_cache_file, "wt", encoding="utf-8") as cache:
                                json.dump(elements, cache, ensure_ascii=False)
                        except OSError:
                            pass
                        return _elements
                except (httpx.HTTPError, ValueError, KeyError):
                    continue
        _next_fetch = monotonic() + 120
        return _elements


def direccion_cercana(elements, lat, lon):
    scale = 111_195 * cos(radians(lat))

    def xy(point):
        return (point["lon"] - lon) * scale, (point["lat"] - lat) * 111_195

    street = number = None
    street_limit, address_limit = 100**2, 30**2
    for element in elements:
        tags = element.get("tags", {})
        coords = element.get("geometry") or (
            [element] if "lat" in element and "lon" in element else []
        )
        points = [xy(point) for point in coords if point and "lat" in point and "lon" in point]
        if points and tags.get("addr:street") and tags.get("addr:housenumber"):
            x, y = (sum(axis) / len(points) for axis in zip(*points))
            delta = x * x + y * y
            if delta < address_limit:
                address_limit = delta
                number = tags
        if tags.get("highway") and tags.get("name"):
            for (x, y), (end_x, end_y) in zip(points, points[1:]):
                dx, dy = end_x - x, end_y - y
                length = dx * dx + dy * dy
                t = max(0, min(1, -(x * dx + y * dy) / length)) if length else 0
                delta = (x + t * dx) ** 2 + (y + t * dy) ** 2
                if delta < street_limit:
                    street_limit = delta
                    street = tags["name"]
    if number:
        result = f'{number["addr:street"]} {number["addr:housenumber"]}'
    else:
        result = street or ""
    return {
        "direccion": result,
        "barrio": (number.get("addr:suburb") or number.get("addr:neighbourhood")) if number else None,
        "ciudad": "Valledupar" if result else None,
    }


async def sugerir_direccion_valledupar(lat, lon):
    south, west, north, east = BOUNDS
    elements = await _cartografia() if south <= lat <= north and west <= lon <= east else []
    return direccion_cercana(elements, lat, lon)
