import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.admin_connections: list[WebSocket] = []
        self.worker_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket, role: str):
        await ws.accept()
        if role == "admin":
            self.admin_connections.append(ws)
        else:
            self.worker_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.admin_connections:
            self.admin_connections.remove(ws)
        if ws in self.worker_connections:
            self.worker_connections.remove(ws)

    async def broadcast_admins(self, data: dict):
        message = json.dumps(data)
        dead = []
        for ws in self.admin_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_workers(self, data: dict):
        message = json.dumps(data)
        dead = []
        for ws in self.worker_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
