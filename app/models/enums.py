from sqlalchemy import Enum

# NOTA: create_type=False porque estos tipos ENUM ya existen en Postgres
# (creados con CREATE TYPE en tu base de datos). SQLAlchemy solo debe
# referenciarlos, no intentar crearlos de nuevo al hacer create_all().

# Confirmado a partir de tus schemas Pydantic (PostulacionEstadoUpdate)
EstadoPostulacionEnum = Enum(
    "pendiente",
    "aceptada",
    "rechazada",
    "en_espera",
    name="estado_postulacion",
    create_type=False,
)

# ⚠️ ASUNCIÓN - verifica los valores reales con:
# SELECT unnest(enum_range(NULL::nivel_urgencia));
NivelUrgenciaEnum = Enum(
    "ahora",
    "hoy",
    "esta semana",
    "no tengo prisa",
    name="nivel_urgencia",
    create_type=False,
)

# ⚠️ ASUNCIÓN - verifica los valores reales con:
# SELECT unnest(enum_range(NULL::estado_publicacion));
EstadoPublicacionEnum = Enum(
    "activo",
    "acuerdo",
    "en_progreso",
    "terminado",
    "cancelado",
    "expirado",
    name="estado_publicacion",
    create_type=False,
)
