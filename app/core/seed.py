from sqlalchemy.dialects.postgresql import insert
from app.models.categoria import Categoria

CATEGORIAS = [
    ("b42848e1-c8fd-4ab7-9cc0-21d25f360bda", "Limpieza", "Servicios de limpieza general y profunda para hogares u oficinas.", "cleaning_services"),
    ("25c52bf4-f66b-4f83-bae9-365075e8546a", "Albañilería", "Construcción, remodelaciones y reparaciones estructurales.", "construction"),
    ("79ff9223-a11e-448a-b383-88e947de7efe", "Pintura", "Pintura de interiores, exteriores y acabados.", "format_paint"),
    ("8866df0e-386c-4130-bec1-a5535573a181", "Climatización", "Instalación y mantenimiento de aire acondicionado y calefacción.", "ac_unit"),
    ("309b7658-ec49-4ed9-8e1d-babef448ae87", "Plomería", "Fugas, tuberías, grifos, instalaciones sanitarias", "ti-droplet"),
    ("6cdb3be6-7f4b-48d5-8ccb-bcde129a86ed", "Electricidad", "Instalaciones, cortos, tableros, cableado", "ti-bolt"),
    ("092c10e9-3f3e-430b-bffa-a493f00be823", "Carpintería", "Muebles, puertas, closets, reparación de madera", "ti-hammer"),
    ("327708fe-3d6a-40dd-a95b-a3010ac9de0d", "Cerrajería", "Cambio de chapas, llaves, apertura de puertas", "ti-key"),
    ("395845b8-332e-4f95-b686-d6e824a62a78", "Jardinería", "Poda, diseño de jardines, mantenimiento de áreas verdes", "ti-plant-2"),
    ("a38e04db-de6c-46d1-9639-6e99110b94df", "Limpieza del hogar", "Limpieza profunda, rutinaria, post obra", "ti-spray"),
    ("43ccdfae-2bbb-4904-9824-b326e9e966b1", "Techos e impermeabilización", "Goteras, membranas, reparación de tejados", "ti-home-2"),
    ("75597730-d042-4b18-979f-9a5205dde131", "Drywall y cielo raso", "Instalación y reparación de paneles de yeso", "ti-layout-board"),
    ("8ebe6587-f1f5-4fa8-8ad6-43ba21714d7b", "Aire acondicionado", "Instalación, mantenimiento, recarga de gas", "ti-air-conditioning"),
    ("f1d3e8cb-6c54-481e-aacc-afa5fd1b88db", "Refrigeración", "Neveras, congeladores, cuartos fríos", "ti-temperature-snow"),
    ("6017401d-bdd3-4a8e-8834-749e9545c856", "Gasfitería", "Instalación y reparación de gas domiciliario", "ti-flame"),
    ("6f5ecc04-d60b-481e-9bef-f9f022f75717", "Instalación de pisos", "Cerámica, porcelanato, laminado, alfombra", "ti-layout-grid"),
    ("b94591be-b28d-42c4-9ad2-9fcd22307e94", "Vidriería y aluminio", "Ventanas, espejos, estructuras de aluminio", "ti-window"),
    ("c8495666-2db2-4981-a508-fe2671e5b189", "Control de plagas", "Fumigación, roedores, insectos", "ti-bug"),
    ("bc7ee3e3-5815-4dbf-93ca-ec510ae1767e", "Mudanzas", "Transporte de muebles, embalaje, cargue", "ti-truck"),
    ("867ce311-05ed-48fe-bcfe-67bd0b28e6d3", "Remodelación", "Reformas integrales, ampliaciones", "ti-tools"),
    ("717c493a-ca8b-4f88-b451-0d89232cf5d2", "Decoración de interiores", "Diseño, ambientación, asesoría estética", "ti-sofa"),
    ("c3fd927e-28a2-43aa-91b6-3a7beca24245", "Soldadura y estructuras metálicas", "Rejas, portones, estructuras", "ti-tools-kitchen-2"),
    ("9e161b76-b6ea-44a4-99e2-aebdf215d93d", "Impermeabilización de tanques", "Tanques de agua, cisternas", "ti-droplet-half-2"),
    ("9c2f2df7-72e1-48e2-b0bd-d40b84429ba3", "Automatización del hogar", "Domótica, cámaras, cerraduras inteligentes", "ti-smart-home"),
    ("8936202d-d9f8-4774-bdae-eca37db04a04", "Piscinas", "Mantenimiento, reparación, limpieza", "ti-pool"),
    ("17d871cf-6507-4149-8206-7f6e8e57be40", "Electrodomésticos", "Reparación de lavadoras, neveras, estufas", "ti-device-desktop"),
    ("b5e66ffa-abfe-4098-920b-ee9490c26667", "Mecánica automotriz a domicilio", "Diagnóstico y reparación básica", "ti-car"),
]


async def seed_categorias(conn):
    rows = [
        {"id": i, "nombre": n, "descripcion": d, "icono": ic}
        for i, n, d, ic in CATEGORIAS
    ]
    stmt = insert(Categoria.__table__).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await conn.execute(stmt)