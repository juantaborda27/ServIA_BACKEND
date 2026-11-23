import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import DATABASE_URL
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.categoria import Categoria
from app.models.cliente import Cliente
from app.models.conversacion import Conversacion
from app.models.especialidad import Especialidad
from app.models.mensaje import Mensaje
from app.models.notificacion import Notificacion
from app.models.postulacion import Postulacion
from app.models.prestador import Prestador
from app.models.publicacion import Publicacion
from app.models.usuario import Usuario
from app.repositories.conversacion_repository import ConversacionRepository
from app.services.conversacion_service import ConversacionService
from app.main import app


@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with SessionLocal() as session:
            yield session
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def _crear_usuario(db: AsyncSession, prefix: str, es_prestador: bool = False, categoria_id: uuid.UUID | None = None) -> Usuario:
    uid = uuid.uuid4()
    user = Usuario(
        id=uid,
        email=f"{prefix}_{uid.hex[:8]}@test.local",
        hashed_password=hash_password("TestPass123!"),
        nombre_completo=f"Usuario {prefix}",
        telefono="3001234567",
        ubicacion="Valledupar",
        activo=True,
    )
    db.add(user)
    await db.flush()
    if es_prestador:
        db.add(Prestador(id=uid, descripcion="Prestador test", disponible=True, verificado=True))
        if categoria_id:
            db.add(Especialidad(prestador_id=uid, categoria_id=categoria_id))
    await db.commit()
    return user


async def _limpiar_usuarios(db: AsyncSession, user_ids: list[uuid.UUID]):
    if not user_ids:
        return
    await db.execute(sa_delete(Mensaje).where(or_(Mensaje.id_remitente.in_(user_ids), Mensaje.id_destinatario.in_(user_ids))))
    await db.execute(sa_delete(Publicacion).where(Publicacion.usuario_id.in_(user_ids)))
    await db.execute(sa_delete(Usuario).where(Usuario.id.in_(user_ids)))
    await db.commit()


async def _get_categoria_id(db: AsyncSession) -> uuid.UUID:
    cat = (await db.execute(select(Categoria).limit(1))).scalar_one()
    return cat.id


def _auth(user: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def test_ubicacion_distancia_y_privacidad(db_session: AsyncSession):
    categoria = await _get_categoria_id(db_session)
    cliente = await _crear_usuario(db_session, "geo_cli")
    prestador = await _crear_usuario(db_session, "geo_pres", True, categoria)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = {"latitud": 10.47, "longitud": -73.24, "direccion": "Dirección base"}
            assert (await client.put("/prestadores/mi-ubicacion", json=base)).status_code in (401, 403)
            updated = await client.put("/prestadores/mi-ubicacion", json=base, headers=_auth(prestador))
            assert updated.status_code == 200, updated.text
            assert updated.json() == base
            public_profile = (await client.get(f"/prestadores/{prestador.id}")).json()
            assert not any(key.startswith("base_") for key in public_profile)

            payload = {
                "descripcion": "Solicitud ubicación", "urgencia": "hoy", "categoria_id": str(categoria),
                "latitud": 10.48, "longitud": -73.24, "direccion": "Dirección privada",
                "referencia": "Portón azul",
            }
            incomplete = {key: value for key, value in payload.items() if key != "longitud"}
            assert (await client.post("/publicaciones", json=incomplete, headers=_auth(cliente))).status_code == 422
            created = await client.post("/publicaciones", json=payload, headers=_auth(cliente))
            assert created.status_code == 200, created.text
            publication_id = created.json()["id"]
            path = f"/publicaciones/{publication_id}"

            public_detail = (await client.get(path)).json()
            assert public_detail["latitud"] is None and public_detail["direccion"] is None
            updated_point = await client.put(
                path, json={"latitud": 10.481, "longitud": -73.24}, headers=_auth(cliente),
            )
            assert updated_point.status_code == 200, updated_point.text
            restored = await client.put(
                path, json={"latitud": payload["latitud"], "longitud": payload["longitud"]},
                headers=_auth(cliente),
            )
            assert restored.status_code == 200, restored.text
            private_detail = (await client.get(path, headers=_auth(cliente))).json()
            assert private_detail["direccion"] == payload["direccion"]

            feed = (await client.get("/publicaciones/categorias-prestador", headers=_auth(prestador))).json()
            listing = next(item for item in feed if item["id"] == publication_id)
            assert listing["distancia_km"] == pytest.approx(1.1)
            assert listing["solicitud_tiene_punto"] and listing["prestador_tiene_punto"]
            assert listing["latitud"] is None and listing["referencia"] is None

            offer = await client.post(
                "/postulaciones", headers=_auth(prestador),
                json={"publicacion_id": publication_id, "precio_ofertado": 50_000, "disponibilidad": "Hoy", "mensaje": "Disponible"},
            )
            assert offer.status_code == 200, offer.text
            offers = (await client.get("/postulaciones", params={"publicacion_id": publication_id}, headers=_auth(cliente))).json()
            assert offers[0]["distancia_km"] == pytest.approx(1.1)
            offer_id = offer.json()["id"]
            public_offer = (await client.get(f"/postulaciones/{offer_id}")).json()
            assert public_offer["publicacion"]["direccion"] is None
            accepted = await client.patch(f"/postulaciones/{offer_id}/estado", json={"estado": "aceptada"}, headers=_auth(cliente))
            assert accepted.status_code == 200, accepted.text
            changed = await client.put(path, json={"direccion": "Otra dirección"}, headers=_auth(cliente))
            assert changed.status_code == 409
            assigned_detail = (await client.get(path, headers=_auth(prestador))).json()
            assert assigned_detail["referencia"] == payload["referencia"]
            jobs = await client.get("/publicaciones/trabajos", headers=_auth(prestador))
            assert jobs.status_code == 200, jobs.text
            assert jobs.json()[0]["distancia_km"] == pytest.approx(1.1)
    finally:
        await _limpiar_usuarios(db_session, [cliente.id, prestador.id])


async def test_categorias_y_notificaciones_contrato(db_session: AsyncSession):
    cat_id = await _get_categoria_id(db_session)
    cliente = await _crear_usuario(db_session, "cat_cli")
    otro = await _crear_usuario(db_session, "cat_otro")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/categorias")
            assert r.status_code == 200
            data = r.json()
            assert "items" in data and len(data["items"]) > 0
            assert {"id", "nombre", "descripcion", "icono"}.issubset(data["items"][0].keys())

            notif = Notificacion(
                usuario_id=cliente.id,
                titulo="Test",
                mensaje="Detalle",
                tipo="oferta_recibida",
                referencia_id=str(cat_id),
                data={"destination": "publication_offers", "publication_id": str(cat_id)},
            )
            db_session.add(notif)
            await db_session.commit()

            r_list = await client.get("/notificaciones", headers=_auth(cliente))
            assert r_list.status_code == 200
            notifs = r_list.json()["notificaciones"]
            assert any(n["data"] and n["data"].get("destination") == "publication_offers" for n in notifs)

            r_otro = await client.patch(f"/notificaciones/{notif.id}/leer", headers=_auth(otro))
            assert r_otro.status_code == 404

            r_del_otro = await client.delete(f"/notificaciones/{notif.id}", headers=_auth(otro))
            assert r_del_otro.status_code == 404
    finally:
        await _limpiar_usuarios(db_session, [cliente.id, otro.id])


async def test_ofertas_retirada_y_validaciones(db_session: AsyncSession):
    cat_id = await _get_categoria_id(db_session)
    cliente = await _crear_usuario(db_session, "cli_of")
    prestador = await _crear_usuario(db_session, "pres_of", es_prestador=True, categoria_id=cat_id)
    otro_pres = await _crear_usuario(db_session, "pres_otro", es_prestador=True, categoria_id=cat_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_pub = await client.post(
                "/publicaciones",
                json={"descripcion": "Necesito plomería urgente", "categoria_id": str(cat_id), "urgencia": "hoy"},
                headers=_auth(cliente),
            )
            assert r_pub.status_code == 200
            pub_id = r_pub.json()["id"]

            # No ofertar a publicación propia
            r_own = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "Yo"},
                headers=_auth(cliente),
            )
            assert r_own.status_code in (400, 403)

            # Crear oferta válida
            r_of = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 60000, "disponibilidad": "Hoy 3pm", "mensaje": "Disponible"},
                headers=_auth(prestador),
            )
            assert r_of.status_code == 200
            of_id = r_of.json()["id"]

            # No duplicar oferta activa
            r_dup = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 65000, "disponibilidad": "Hoy", "mensaje": "Dup"},
                headers=_auth(prestador),
            )
            assert r_dup.status_code == 409

            # No retirar oferta ajena
            r_ret_ajena = await client.patch(f"/postulaciones/{of_id}/retirar", headers=_auth(otro_pres))
            assert r_ret_ajena.status_code == 403

            # Retirar oferta propia
            r_ret = await client.patch(f"/postulaciones/{of_id}/retirar", headers=_auth(prestador))
            assert r_ret.status_code == 200
            assert r_ret.json()["estado"] == "retirada"
            assert r_ret.json()["retirada_at"] is not None

            # Una oferta retirada puede volver a enviarse; DELETE tambiÃ©n la retira
            # lÃ³gicamente para conservar historial y evitar el falso duplicado activo.
            r_recrear = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 62000, "disponibilidad": "MaÃ±ana", "mensaje": "Nueva oferta"},
                headers=_auth(prestador),
            )
            assert r_recrear.status_code == 200
            assert r_recrear.json()["id"] == of_id
            r_delete = await client.delete(
                f"/postulaciones/{of_id}",
                headers=_auth(prestador),
            )
            assert r_delete.status_code == 200
            assert r_delete.json()["estado"] == "retirada"
    finally:
        await _limpiar_usuarios(db_session, [cliente.id, prestador.id, otro_pres.id])


async def test_ciclo_completo_aceptacion_trabajos_y_chat(db_session: AsyncSession):
    cat_id = await _get_categoria_id(db_session)
    cliente = await _crear_usuario(db_session, "cli_ciclo")
    prestador = await _crear_usuario(db_session, "pres_ciclo", es_prestador=True, categoria_id=cat_id)
    pres2 = await _crear_usuario(db_session, "pres2_ciclo", es_prestador=True, categoria_id=cat_id)
    tercero = await _crear_usuario(db_session, "tercero_ciclo")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            pub_resp = await client.post(
                "/publicaciones",
                json={"descripcion": "Reparación tubería cocina", "categoria_id": str(cat_id), "urgencia": "ahora"},
                headers=_auth(cliente),
            )
            pub_id = pub_resp.json()["id"]

            pub2_resp = await client.post(
                "/publicaciones",
                json={"descripcion": "Otra reparación", "categoria_id": str(cat_id), "urgencia": "hoy"},
                headers=_auth(tercero),
            )
            pub2_id = pub2_resp.json()["id"]

            of1_id = (await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 80000, "disponibilidad": "Ya", "mensaje": "Oferta 1"},
                headers=_auth(prestador),
            )).json()["id"]

            of2_id = (await client.post(
                "/postulaciones",
                json={"publicacion_id": pub_id, "precio_ofertado": 90000, "disponibilidad": "Mañana", "mensaje": "Oferta 2"},
                headers=_auth(pres2),
            )).json()["id"]

            # Tercero no puede aceptar
            r_acep_ter = await client.patch(
                f"/postulaciones/{of1_id}/estado",
                json={"estado": "aceptada"},
                headers=_auth(tercero),
            )
            assert r_acep_ter.status_code == 403

            # Cliente acepta oferta 1
            r_acep = await client.patch(
                f"/postulaciones/{of1_id}/estado",
                json={"estado": "aceptada"},
                headers=_auth(cliente),
            )
            assert r_acep.status_code == 200
            conv_id = r_acep.json()["id_conversacion"]

            # No retirar ni borrar oferta aceptada
            assert (await client.patch(f"/postulaciones/{of1_id}/retirar", headers=_auth(prestador))).status_code == 409
            assert (await client.delete(f"/postulaciones/{of1_id}", headers=_auth(prestador))).status_code == 409

            # Prestador ocupado no puede ofertar en otra publicación
            r_ocup = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub2_id, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "Ocupado"},
                headers=_auth(prestador),
            )
            assert r_ocup.status_code == 409

            # Chat: tercero no puede leer, participantes sí
            assert (await client.get(f"/conversaciones/{conv_id}/mensajes")).status_code in (401, 403)
            assert (await client.get(f"/conversaciones/{conv_id}/mensajes", headers=_auth(tercero))).status_code == 403
            assert (await client.get(f"/conversaciones/{conv_id}/mensajes", headers=_auth(cliente))).status_code == 200
            assert (await client.get(f"/conversaciones/{conv_id}/mensajes?rol=profesional", headers=_auth(cliente))).status_code == 403
            assert (await client.get(f"/conversaciones/{conv_id}/mensajes?rol=profesional", headers=_auth(prestador))).status_code == 200
            assert (await client.get(f"/conversaciones/{conv_id}?rol=cliente", headers=_auth(prestador))).status_code == 403
            r_conv_profesional = await client.get(
                f"/conversaciones/{conv_id}?rol=profesional",
                headers=_auth(prestador),
            )
            assert r_conv_profesional.status_code == 200
            assert r_conv_profesional.json()["rol"] == "profesional"
            assert r_conv_profesional.json()["partner"]["id"] == str(cliente.id)
            assert (await client.get(f"/chat/conversacion/{conv_id}", headers=_auth(tercero))).status_code == 403

            # Transición inválida: completar sin iniciar -> 409
            assert (await client.patch(f"/publicaciones/{pub_id}/completar", headers=_auth(cliente))).status_code == 403

            # Tercero o cliente no puede iniciar trabajo (solo prestador asignado)
            assert (await client.patch(f"/publicaciones/{pub_id}/iniciar", headers=_auth(cliente))).status_code == 403
            assert (await client.patch(f"/publicaciones/{pub_id}/iniciar", headers=_auth(prestador))).status_code == 200

            # Tercero no puede completar
            assert (await client.patch(f"/publicaciones/{pub_id}/completar", headers=_auth(tercero))).status_code == 403

            # Completar trabajo libera prestador y cierra chat
            r_comp = await client.patch(f"/publicaciones/{pub_id}/completar", headers=_auth(prestador))
            assert r_comp.status_code == 200
            assert r_comp.json()["estado"] == "pendiente_confirmacion"
            assert r_comp.json()["completion_requested_at"] is not None

            r_trabajos_pendientes = await client.get(
                "/publicaciones/trabajos?tipo=activos",
                headers=_auth(prestador),
            )
            trabajo_pendiente = next(
                t for t in r_trabajos_pendientes.json() if t["id"] == pub_id
            )
            assert trabajo_pendiente["awaiting_client_confirmation"] is True
            assert trabajo_pendiente["can_complete"] is False

            r_perfil_ocupado = await client.get(
                "/prestadores/mi-perfil",
                headers=_auth(prestador),
            )
            assert r_perfil_ocupado.json()["ocupado"] is True
            assert r_perfil_ocupado.json()["disponible"] is False

            assert (await client.post(
                "/postulaciones",
                json={"publicacion_id": pub2_id, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "Aun ocupado"},
                headers=_auth(prestador),
            )).status_code == 409

            r_conv_pendiente = await client.get(
                f"/conversaciones/{conv_id}",
                headers=_auth(cliente),
            )
            assert r_conv_pendiente.json()["estado"] == "activa"

            notifs_cliente = (await client.get(
                "/notificaciones?rol=cliente",
                headers=_auth(cliente),
            )).json()["notificaciones"]
            assert any(n["tipo"] == "finalizacion_pendiente" for n in notifs_cliente)

            assert (await client.patch(
                f"/publicaciones/{pub_id}/confirmar-finalizacion",
                headers=_auth(prestador),
            )).status_code == 403
            r_confirmar = await client.patch(
                f"/publicaciones/{pub_id}/confirmar-finalizacion",
                headers=_auth(cliente),
            )
            assert r_confirmar.status_code == 200
            assert r_confirmar.json()["estado"] == "terminado"
            assert r_confirmar.json()["completed_at"] is not None

            notifs_profesional = (await client.get(
                "/notificaciones?rol=profesional",
                headers=_auth(prestador),
            )).json()["notificaciones"]
            assert any(n["tipo"] == "servicio_completado" for n in notifs_profesional)

            # No se puede cancelar un trabajo ya terminado
            assert (await client.patch(f"/publicaciones/{pub_id}/cancelar", headers=_auth(cliente))).status_code == 409

            # Conversación cerrada
            r_conv = await client.get(f"/conversaciones/{conv_id}", headers=_auth(cliente))
            assert r_conv.status_code == 200
            assert r_conv.json()["estado"] == "cerrada"

            historial = (await client.get(
                "/publicaciones/trabajos?tipo=historial",
                headers=_auth(prestador),
            )).json()
            trabajo_terminado = next(t for t in historial if t["id"] == pub_id)
            assert trabajo_terminado["estado"] == "terminado"
            assert trabajo_terminado["awaiting_client_confirmation"] is False

            # La disponibilidad se deriva de trabajos activos, incluso si la
            # antigua bandera persistida queda obsoleta.
            prestador_model = (await db_session.execute(
                select(Prestador).where(Prestador.id == prestador.id)
            )).scalar_one()
            prestador_model.disponible = False
            await db_session.commit()
            perfil_liberado = (await client.get(
                "/prestadores/mi-perfil",
                headers=_auth(prestador),
            )).json()
            assert perfil_liberado["disponible"] is True
            assert perfil_liberado["ocupado"] is False
            prestadores_disponibles = (await client.get(
                "/prestadores?disponible=true",
            )).json()
            assert any(str(p["id"]) == str(prestador.id) for p in prestadores_disponibles)

            # Prestador vuelve a estar disponible para ofertar
            r_post_libre = await client.post(
                "/postulaciones",
                json={"publicacion_id": pub2_id, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "Libre"},
                headers=_auth(prestador),
            )
            assert r_post_libre.status_code == 200
    finally:
        await _limpiar_usuarios(db_session, [cliente.id, prestador.id, pres2.id, tercero.id])


async def test_concurrencia_aceptacion_mismo_prestador(db_session: AsyncSession):
    cat_id = await _get_categoria_id(db_session)
    cli1 = await _crear_usuario(db_session, "conc_cli1")
    cli2 = await _crear_usuario(db_session, "conc_cli2")
    pres = await _crear_usuario(db_session, "conc_pres", es_prestador=True, categoria_id=cat_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            p1 = (await client.post("/publicaciones", json={"descripcion": "Pub 1", "categoria_id": str(cat_id), "urgencia": "hoy"}, headers=_auth(cli1))).json()["id"]
            p2 = (await client.post("/publicaciones", json={"descripcion": "Pub 2", "categoria_id": str(cat_id), "urgencia": "hoy"}, headers=_auth(cli2))).json()["id"]

            o1 = (await client.post("/postulaciones", json={"publicacion_id": p1, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "O1"}, headers=_auth(pres))).json()["id"]
            o2 = (await client.post("/postulaciones", json={"publicacion_id": p2, "precio_ofertado": 50000, "disponibilidad": "Hoy", "mensaje": "O2"}, headers=_auth(pres))).json()["id"]

            r1, r2 = await asyncio.gather(
                client.patch(f"/postulaciones/{o1}/estado", json={"estado": "aceptada"}, headers=_auth(cli1)),
                client.patch(f"/postulaciones/{o2}/estado", json={"estado": "aceptada"}, headers=_auth(cli2)),
            )
            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [200, 409], f"Expected [200, 409], got {codes}"

            oferta_en_espera = o2 if r1.status_code == 200 else o1
            r_retirar_espera = await client.patch(
                f"/postulaciones/{oferta_en_espera}/retirar",
                headers=_auth(pres),
            )
            assert r_retirar_espera.status_code == 200
            assert r_retirar_espera.json()["estado"] == "retirada"
    finally:
        await _limpiar_usuarios(db_session, [cli1.id, cli2.id, pres.id])


async def test_limpieza_conversaciones_expiradas(db_session: AsyncSession):
    cat_id = await _get_categoria_id(db_session)
    cli = await _crear_usuario(db_session, "clean_cli")
    pres = await _crear_usuario(db_session, "clean_pres", es_prestador=True, categoria_id=cat_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            pub_id = (await client.post("/publicaciones", json={"descripcion": "Clean pub", "categoria_id": str(cat_id), "urgencia": "hoy"}, headers=_auth(cli))).json()["id"]
            of_id = (await client.post("/postulaciones", json={"publicacion_id": pub_id, "precio_ofertado": 40000, "disponibilidad": "Hoy", "mensaje": "Ok"}, headers=_auth(pres))).json()["id"]
            conv_id = (await client.patch(f"/postulaciones/{of_id}/estado", json={"estado": "aceptada"}, headers=_auth(cli))).json()["id_conversacion"]

            # Cancelar trabajo para cerrar chat
            assert (await client.patch(f"/publicaciones/{pub_id}/cancelar", json={"motivo": "Cambio de planes"}, headers=_auth(cli))).status_code == 200

            # Forzar delete_after al pasado
            conv = (await db_session.execute(select(Conversacion).where(Conversacion.id_conversacion == uuid.UUID(conv_id)))).scalar_one()
            conv.delete_after = datetime.now(timezone.utc) - timedelta(days=1)
            await db_session.commit()

            svc = ConversacionService(ConversacionRepository(db_session))
            res1 = await svc.limpiar_conversaciones_expiradas()
            assert res1["conversaciones_eliminadas"] >= 1
            # Idempotente
            res2 = await svc.limpiar_conversaciones_expiradas()
            assert res2["conversaciones_eliminadas"] == 0
    finally:
        await _limpiar_usuarios(db_session, [cli.id, pres.id])


def test_websocket_seguridad_y_formato():
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _setup():
        async with SessionLocal() as db:
            cat_id = await _get_categoria_id(db)
            cli = await _crear_usuario(db, "ws_cli")
            pres = await _crear_usuario(db, "ws_pres", es_prestador=True, categoria_id=cat_id)
            tercero = await _crear_usuario(db, "ws_ter")
            return cli, pres, tercero, cat_id

    async def _cleanup(ids):
        async with SessionLocal() as db:
            await _limpiar_usuarios(db, ids)
        await engine.dispose()

    cli, pres, tercero, cat_id = asyncio.run(_setup())
    try:
        with TestClient(app) as tc:
            pub_id = tc.post("/publicaciones", json={"descripcion": "WS pub", "categoria_id": str(cat_id), "urgencia": "hoy"}, headers=_auth(cli)).json()["id"]
            of_id = tc.post("/postulaciones", json={"publicacion_id": pub_id, "precio_ofertado": 45000, "disponibilidad": "Hoy", "mensaje": "WS"}, headers=_auth(pres)).json()["id"]
            conv_id = tc.patch(f"/postulaciones/{of_id}/estado", json={"estado": "aceptada"}, headers=_auth(cli)).json()["id_conversacion"]

            tok_cli = create_access_token(str(cli.id))
            with tc.websocket_connect(f"/chat/ws?token={tok_cli}&rol=cliente") as ws:
                # Destino arbitrario rechazado
                ws.send_json({"destino": str(tercero.id), "mensaje": "Hack", "id_conversacion": conv_id})
                err = ws.receive_json()
                assert err["type"] == "error"

                # Mensaje válido devuelve formato estructurado
                ws.send_json({"destino": str(pres.id), "mensaje": "Hola prestador", "id_conversacion": conv_id})
                ok = ws.receive_json()
                assert ok["type"] == "message"
                assert ok["message"]["contenido"] == "Hola prestador"
                assert ok["message"]["id_destinatario"] == str(pres.id)

            tok_pres = create_access_token(str(pres.id))
            with tc.websocket_connect(f"/chat/ws?token={tok_pres}&rol=cliente") as ws_rol_incorrecto:
                ws_rol_incorrecto.send_json({"destino": str(cli.id), "mensaje": "Cruce", "id_conversacion": conv_id})
                err_rol = ws_rol_incorrecto.receive_json()
                assert err_rol["type"] == "error"

            with tc.websocket_connect(f"/chat/ws?token={tok_pres}&rol=profesional") as ws_profesional:
                ws_profesional.send_json({"destino": str(cli.id), "mensaje": "Hola cliente", "id_conversacion": conv_id})
                ok_profesional = ws_profesional.receive_json()
                assert ok_profesional["type"] == "message"
                assert ok_profesional["message"]["contenido"] == "Hola cliente"
                assert ok_profesional["message"]["id_destinatario"] == str(cli.id)
    finally:
        asyncio.run(_cleanup([cli.id, pres.id, tercero.id]))
