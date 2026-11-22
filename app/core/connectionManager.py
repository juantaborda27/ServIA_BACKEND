from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        key = str(user_id)
        if key not in self.active_connections:
            self.active_connections[key] = set()
        self.active_connections[key].add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        key = str(user_id)
        if key in self.active_connections:
            self.active_connections[key].discard(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

    def is_connected(self, user_id: str) -> bool:
        return str(user_id) in self.active_connections

    def get_connections(self, user_id: str) -> set[WebSocket]:
        return set(self.active_connections.get(str(user_id), set()))

