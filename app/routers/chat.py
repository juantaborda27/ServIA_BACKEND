from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from app.core.security import decode_token, InvalidTokenError
from app.dependencies.auth import get_current_user
from app.services.dependencies import get_mensaje_service
from app.services.mensaje_service import MensajeService
from app.schemas.mensaje import MensajeCreate, MensajeResponse
from app.core.connectionManager import ConnectionManager
import json
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

manager_connection = ConnectionManager()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="connectWebSocket(event)">
            <input type="text" id="token" placeholder="Enter your token" autocomplete="off"/>
            <button>Connect</button>
        </form>
        <form style="margin-bottom: 10px; display:flexbox; flex-direction: column;" action="" onsubmit="sendMessage(event)">
            <input type="text" id="destino" placeholder="Enter destination user ID" autocomplete="off"/>
            <input type="text" id="id_conversacion" placeholder="Enter conversation ID" autocomplete="off"/>
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws;
            function connectWebSocket(event) {
            var tokenInput = document.getElementById('token');
            ws = new WebSocket("ws://localhost:8000/chat/ws?token=" + tokenInput.value);
            event.preventDefault()

            ws.onmessage = function(event) {
            var messages = document.getElementById('messages')
            var message = document.createElement('li')
            var content = document.createTextNode(event.data)
            message.appendChild(content)
            messages.appendChild(message)
            };
                        
            ws.onclose = function(event) {
            console.log("WebSocket closed with code: " + event.code + ", reason: " + event.reason);
                };
            }
            
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                var destino = document.getElementById("destino")
                var id_conversacion = document.getElementById("id_conversacion")
                ws.send(JSON.stringify({destino: destino.value, mensaje: input.value, id_conversacion: id_conversacion.value}))
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""

websocket_connections = {}


@router.get("/")
async def get():
    return HTMLResponse(html)

@router.get("/no-leidos")
async def get_mensajes_no_leidos(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(func.count(Notificacion.id)).where(
        Notificacion.usuario_id == current_user.id,
        Notificacion.tipo == "chat",
        Notificacion.leida == False,
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return {"no_leidos": count}


@router.patch("/marcar-leidos")
async def marcar_mensajes_leidos(
    conversacion_id: Optional[uuid.UUID] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        update(Notificacion)
        .where(
            Notificacion.usuario_id == current_user.id,
            Notificacion.tipo == "chat",
            Notificacion.leida == False,
        )
    )
    if conversacion_id:
        stmt = stmt.where(Notificacion.referencia_id == str(conversacion_id))
    stmt = stmt.values(leida=True)
    await db.execute(stmt)
    await db.commit()
    return {"message": "Mensajes marcados como leídos"}


@router.get(
    "/conversacion/{conversacion_id}",
    response_model=list[MensajeResponse])
async def get_chat(
    conversacion_id: uuid.UUID,
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
    current_user=Depends(get_current_user),
    services: MensajeService = Depends(get_mensaje_service),
):
    return await services.listar_mensajes_por_conversacion(conversacion_id, current_user.id, rol)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    rol: str = Query("cliente", pattern="^(cliente|profesional)$"),
    services: MensajeService = Depends(get_mensaje_service),
):
    is_connected = False
    user_id = None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Token inválido o expirado")
        connection_key = manager_connection.build_key(user_id, rol)
        await manager_connection.connect(connection_key, websocket)
        is_connected = True
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
                datos = MensajeCreate(
                    id_remitente=user_id,
                    id_destinatario=payload["destino"],
                    contenido=payload["mensaje"],
                    id_conversacion=payload["id_conversacion"],
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
                await websocket.send_json({"type": "error", "detail": f"Payload inválido: {exc}"})
                continue

            try:
                mensaje_guardado = await services.crear_mensaje(datos, rol)
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "detail": exc.detail})
                continue

            evento = {
                "type": "message",
                "message": {
                    "id_mensaje": str(mensaje_guardado.id_mensaje),
                    "contenido": mensaje_guardado.contenido,
                    "id_conversacion": str(mensaje_guardado.id_conversacion),
                    "id_remitente": str(mensaje_guardado.id_remitente),
                    "id_destinatario": str(mensaje_guardado.id_destinatario),
                    "fecha_hora": mensaje_guardado.fecha_hora.isoformat() if mensaje_guardado.fecha_hora else None,
                },
            }

            destino_str = str(mensaje_guardado.id_destinatario)
            rol_destino = "profesional" if rol == "cliente" else "cliente"
            destino_key = manager_connection.build_key(destino_str, rol_destino)
            for ws in manager_connection.get_connections(destino_key):
                try:
                    await ws.send_json(evento)
                except (WebSocketDisconnect, RuntimeError) as e:
                    logger.warning("Error enviando mensaje WS a %s: %s", destino_str, e)
                    manager_connection.disconnect(destino_key, ws)

            await websocket.send_json(evento)

    except WebSocketDisconnect:
        logger.info("Usuario %s desconectado de WS", user_id)
    except InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido o expirado")
    finally:
        if is_connected and user_id:
            connection_key = manager_connection.build_key(user_id, rol)
            manager_connection.disconnect(connection_key, websocket)

