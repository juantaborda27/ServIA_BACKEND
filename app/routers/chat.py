from fastapi import APIRouter, WebSocket, WebSocketException, status, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from app.core.security import decode_token
from app.services.dependencies import get_mensaje_service
from app.services.mensaje_service import MensajeService
from app.schemas.mensaje import MensajeCreate, MensajeResponse
import json
import uuid
router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)



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

@router.get(
    "/conversacion/{conversacion_id}",
    response_model=list[MensajeResponse])
async def get_chat(conversacion_id: uuid.UUID,services: MensajeService = Depends(get_mensaje_service)):
     return await services.listar_mensajes_por_conversacion(conversacion_id)
    

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, services: MensajeService = Depends(get_mensaje_service),id_conversacion: uuid.UUID = None):
    try:
        user_id = decode_token(token).get("sub")
        await websocket.accept()
        websocket_connections[user_id] = websocket
        print(websocket_connections)
        while True:
            data = await websocket.receive_text()
            data = json.loads(data)
            destino = data["destino"]
            mensaje = data["mensaje"]
            id_conversacion = data["id_conversacion"]
            ws=websocket_connections[destino]
            await ws.send_text(f"Message text was: {mensaje}")
            datos = {
                "id_remitente": user_id,
                "id_destinatario": destino,
                "contenido": mensaje,
                "id_conversacion": id_conversacion}
            datos = MensajeCreate(**datos)
            await services.crear_mensaje(datos)
    except WebSocketDisconnect:
        del websocket_connections[user_id]
        print(websocket_connections)
    except ValueError:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido o expirado")

