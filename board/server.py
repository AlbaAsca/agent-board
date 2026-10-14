"""Servidor del panel: http://localhost:8020/  (FastAPI, sin dependencias del proyecto).

Uso: python board/server.py [--port 8020]
Puede convivir con el servidor de tu proyecto (otro puerto).
"""
import argparse
import importlib.util
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

HERE = Path(__file__).parent
BOARD = HERE / "board.json"
app = FastAPI(title="Panel de agentes")


def _bd():
    spec = importlib.util.spec_from_file_location("board", HERE / "board.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@app.get("/")
def panel():
    return FileResponse(HERE / "panel.html", headers={"Cache-Control": "no-store"})


@app.get("/api/board")
def get_board():
    return Response(BOARD.read_text(encoding="utf-8"), media_type="application/json", headers={"Cache-Control": "no-store"})


EDITABLE = {"title", "owner", "priority", "estimate_min", "desc", "deps", "manual"}


@app.patch("/api/board/task/{tid}")
async def patch_task(tid: str, request: Request):
    """Edita una tarea. El estado pasa por set_status para que los tiempos reales se registren solos."""
    body, bd = await request.json(), _bd()

    def f(b):
        t = bd.task(b, tid)
        changed = [k for k in EDITABLE if k in body and body[k] != t.get(k)]
        for k in changed:
            t[k] = body[k]
        if "manual" in changed:
            t["auto"] = not body["manual"]
        if changed:
            bd.log(t, "tú", "editada: " + ", ".join(changed))
        if body.get("status") and body["status"] != t["status"]:
            bd.set_status(b, t, body["status"], "tú")
        if body.get("note"):
            bd.log(t, "tú", body["note"])
    try:
        bd.update(f)
    except (StopIteration, AssertionError) as e:
        raise HTTPException(400, str(e) or "tarea no encontrada")
    return {"ok": True}


@app.delete("/api/board/task/{tid}")
def delete_task(tid: str):
    bd = _bd()

    def f(b):
        n = len(b["tasks"])
        b["tasks"] = [t for t in b["tasks"] if t["id"] != tid]
        if len(b["tasks"]) == n:
            raise HTTPException(404, "tarea no encontrada")
    bd.update(f)
    return {"ok": True}


@app.post("/api/board/task")
async def create_task(request: Request):
    body, bd = await request.json(), _bd()
    try:
        t = bd.update(lambda b: bd.new_task(b, body["title"], body["owner"], body.get("estimate_min") or 10,
                                            body.get("priority", "media"), body.get("desc", ""),
                                            body.get("status", "backlog"), body.get("manual") or None, "tú"))
    except (KeyError, AssertionError) as e:
        raise HTTPException(400, str(e))
    return {"id": t["id"]}


@app.post("/api/board/runner")
async def runner_toggle(request: Request):
    enabled, bd = bool((await request.json()).get("enabled")), _bd()

    def f(b):
        b.setdefault("runner", {})["enabled"] = enabled
    bd.update(f)
    return {"enabled": enabled}


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8020)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port)
