from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketException, status, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.core.security import decode_token, InvalidTokenError
from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.notificacion import Notificacion
from app.services.dependencies import get_mensaje_service
from app.services.mensaje_service import MensajeService
from app.schemas.mensaje import MensajeCreate, MensajeResponse
from app.core.connectionManager import ConnectionManager
import json
import uuid
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
async def get_chat(conversacion_id: uuid.UUID,services: MensajeService = Depends(get_mensaje_service)):
     return await services.listar_mensajes_por_conversacion(conversacion_id)
    

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    services: MensajeService = Depends(get_mensaje_service)
):
    is_conected = False
    user_id = None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Token inválido o expirado")
        await manager_connection.connect(str(user_id), websocket)
        is_conected = True

        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                await websocket.send_text(json.dumps({"error": "Formato de mensaje inválido"}))
                continue

            destino = data.get("destino")
            mensaje = data.get("mensaje")
            id_conversacion = data.get("id_conversacion")

            if not destino or not mensaje or not id_conversacion:
                await websocket.send_text(json.dumps({"error": "Faltan campos obligatorios: destino, mensaje o id_conversacion"}))
                continue

            try:
                datos = MensajeCreate(
                    id_remitente=uuid.UUID(str(user_id)),
                    id_destinatario=uuid.UUID(str(destino)),
                    contenido=str(mensaje).strip(),
                    id_conversacion=uuid.UUID(str(id_conversacion)),
                )
                nuevo_mensaje = await services.crear_mensaje(datos)

                fecha_iso = (
                    nuevo_mensaje.fecha_hora.isoformat()
                    if getattr(nuevo_mensaje, "fecha_hora", None)
                    else ""
                )

                payload_outgoing = {
                    "id": str(nuevo_mensaje.id_mensaje),
                    "id_mensaje": str(nuevo_mensaje.id_mensaje),
                    "id_conversacion": str(nuevo_mensaje.id_conversacion),
                    "id_remitente": str(nuevo_mensaje.id_remitente),
                    "id_destinatario": str(nuevo_mensaje.id_destinatario),
                    "contenido": nuevo_mensaje.contenido,
                    "mensaje": nuevo_mensaje.contenido,
                    "fecha_hora": fecha_iso,
                    "created_at": fecha_iso,
                }
                msg_json = json.dumps(payload_outgoing)

                # 1. Enviar a todas las conexiones activas del destinatario
                connections = manager_connection.get_connections(str(destino))
                for ws in connections:
                    try:
                        await ws.send_text(msg_json)
                    except (WebSocketDisconnect, RuntimeError) as e:
                        print(f"Error sending message to {destino}: {e}")
                        manager_connection.disconnect(str(destino), ws)

                # 2. Confirmar al remitente con el ID y timestamp reales
                try:
                    await websocket.send_text(msg_json)
                except (WebSocketDisconnect, RuntimeError):
                    pass

                # 3. Notificación al destinatario
                try:
                    from app.models.notificacion import Notificacion
                    notif = Notificacion(
                        usuario_id=uuid.UUID(str(destino)),
                        titulo="Nuevo mensaje",
                        mensaje=str(mensaje).strip()[:120],
                        tipo="chat",
                        referencia_id=str(id_conversacion),
                    )
                    services.repository.db.add(notif)
                    await services.repository.db.commit()
                except Exception as notif_err:
                    print(f"Error generando notificación de chat: {notif_err}")

            except HTTPException as http_e:
                await websocket.send_text(json.dumps({"error": http_e.detail}))
            except Exception as e:
                print(f"Error al procesar mensaje en WS: {e}")
                await websocket.send_text(json.dumps({"error": "No se pudo guardar el mensaje"}))

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
    except InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido o expirado")
    finally:
        if is_conected and user_id:
            manager_connection.disconnect(str(user_id), websocket)

