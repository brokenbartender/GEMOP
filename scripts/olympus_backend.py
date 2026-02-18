import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from watchfiles import awatch

app = FastAPI(title="Olympus Backend")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
JOBS_DIR = REPO_ROOT / ".agent-jobs"
IPC_DIR = REPO_ROOT / ".gemini/ipc"

class HydraManager:
    """Manages the real-time WebSocket connections for the Goetic Swarm."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[Hydra] New connection established. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = HydraManager()

@app.websocket("/ws/hydra")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Initial State Sync
        await websocket.send_json({"type": "init", "data": "Connecting to the Motherboard..."})
        
        # Start watching for system changes
        while True:
            # We keep the connection alive
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def watch_system_events():
    """Watches logs and IPC files to broadcast to the Hydra graph."""
    print(f"[Hydra] Watching for system events in {REPO_ROOT}")
    
    # Watch for IPC status updates (Agent Breathing)
    async for changes in awatch(str(IPC_DIR), str(JOBS_DIR)):
        for change_type, path_str in changes:
            p = Path(path_str)
            
            # 1. Agent Status Changes
            if p.suffix == ".status":
                agent_name = p.stem
                state = p.read_text(encoding="utf-8").strip()
                await manager.broadcast({
                    "type": "agent_update",
                    "agent": agent_name,
                    "state": state,
                    "ts": os.path.getmtime(p)
                })

            # 2. Log Updates (Ariadne's Thread)
            if p.name == "triad_orchestrator.log":
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if lines:
                    await manager.broadcast({
                        "type": "log_event",
                        "content": lines[-1],
                        "ts": os.path.getmtime(p)
                    })

            # 3. Lifecycle Events (Granular JSON)
            if p.name == "lifecycle.jsonl":
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if lines:
                    try:
                        event = json.loads(lines[-1])
                        await manager.broadcast({
                            "type": "lifecycle_event",
                            "payload": event,
                            "ts": os.path.getmtime(p)
                        })
                    except: pass

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(watch_system_events())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
