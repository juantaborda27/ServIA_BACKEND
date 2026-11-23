from app.core.calles_valledupar import direccion_cercana


def test_sugiere_calle_cercana_y_solo_numero_cuando_hay_dato_cercano():
    street = {
        "tags": {"name": "Carrera 27", "highway": "residential"},
        "geometry": [{"lat": 10.47, "lon": -73.25}, {"lat": 10.48, "lon": -73.25}],
    }
    address = {
        "lat": 10.475, "lon": -73.25,
        "tags": {"addr:street": "Carrera 27", "addr:housenumber": "12A-34"},
    }
    assert direccion_cercana([street, address], 10.475, -73.25)["direccion"] == "Carrera 27 12A-34"
    assert direccion_cercana([street, address], 10.476, -73.25)["direccion"] == "Carrera 27"
    assert direccion_cercana([street, address], 10.476, -73.27)["direccion"] == ""
