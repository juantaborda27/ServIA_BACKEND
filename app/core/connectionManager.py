import asyncio
import contextlib
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import REDIS_CHAT_CHANNEL, REDIS_REQUIRED, REDIS_URL


logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(
        self,
        redis_url: str | None = REDIS_URL,
        channel: str = REDIS_CHAT_CHANNEL,
        redis_required: bool = REDIS_REQUIRED,
    ):
        self.active_connections: dict[str, set[WebSocket]] = {}
        self.redis_url = redis_url
        self.channel = channel
        self.redis_required = redis_required
        self.redis: Redis | None = None
        self.pubsub = None
        self.listener_task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.redis_url:
            logger.warning(
                "REDIS_URL no está configurada; el chat en tiempo real solo funcionará "
                "dentro de este contenedor."
            )
            return

        try:
            self.redis = Redis.from_url(
                self.redis_url,
                decode_responses=True,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.redis.ping()
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(self.channel)
            self.listener_task = asyncio.create_task(
                self._listen_for_events(),
                name="servia-redis-chat-listener",
            )
            logger.info("Chat distribuido conectado a Redis en el canal %s", self.channel)
        except RedisError as exc:
            await self.stop()
            if self.redis_required:
                raise RuntimeError("No fue posible conectar con Redis") from exc
            logger.warning(
                "Redis no está disponible; se usará entrega WebSocket local: %s",
                exc,
            )

    async def stop(self) -> None:
        if self.listener_task:
            self.listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.listener_task
            self.listener_task = None
        if self.pubsub:
            with contextlib.suppress(RedisError):
                await self.pubsub.unsubscribe(self.channel)
                await self.pubsub.aclose()
            self.pubsub = None
        if self.redis:
            with contextlib.suppress(RedisError):
                await self.redis.aclose()
            self.redis = None

    async def _listen_for_events(self) -> None:
        while True:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if not message:
                    await asyncio.sleep(0.01)
                    continue
                envelope = json.loads(message["data"])
                await self._deliver_local(envelope["destination"], envelope["event"])
            except asyncio.CancelledError:
                raise
            except (RedisError, json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Error consumiendo un evento de chat desde Redis: %s", exc)
                await asyncio.sleep(1)

    @staticmethod
    def build_key(user_id: str, rol: str) -> str:
        return f"{user_id}:{rol}"

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

    async def broadcast(self, destination: str, event: dict) -> None:
        if self.redis:
            try:
                await self.redis.publish(
                    self.channel,
                    json.dumps(
                        {"destination": str(destination), "event": event},
                        ensure_ascii=False,
                    ),
                )
                return
            except RedisError as exc:
                logger.error("No se pudo publicar el mensaje de chat en Redis: %s", exc)
        await self._deliver_local(destination, event)

    async def _deliver_local(self, destination: str, event: dict) -> None:
        for websocket in self.get_connections(destination):
            try:
                await websocket.send_json(event)
            except (WebSocketDisconnect, RuntimeError) as exc:
                logger.warning("Error enviando evento a un WebSocket local: %s", exc)
                self.disconnect(destination, websocket)


manager_connection = ConnectionManager()

