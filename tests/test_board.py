"""Pruebas mínimas del panel: CLI con bloqueo, tiempos medidos y API del servidor."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture()
def board(tmp_path, monkeypatch):
    d = tmp_path / "board"
    shutil.copytree(ROOT / "board", d, ignore=shutil.ignore_patterns("runs", "__pycache__", ".lock"))
    return d


def cli(d, *args):
    return subprocess.run([sys.executable, str(d / "board.py"), *args], capture_output=True, text=True, check=True).stdout


def test_flujo_de_tarea(board):
    tid = cli(board, "add", "Probar el panel", "--owner", "desarrollador", "--est", "10", "--prio", "alta").strip().split()[-1]
    cli(board, "move", tid, "doing", "--by", "desarrollador")
    cli(board, "move", tid, "review", "--by", "desarrollador", "--msg", "hecho")
    cli(board, "move", tid, "done", "--by", "tester")
    t = next(t for t in json.loads((board / "board.json").read_text(encoding="utf-8"))["tasks"] if t["id"] == tid)
    assert t["status"] == "done" and t["started_at"] and t["finished_at"] and t["actual_min"] is not None


def test_api(board, monkeypatch):
    from fastapi.testclient import TestClient
    sys.path.insert(0, str(board))
    import importlib
    import server
    importlib.reload(server)
    c = TestClient(server.app)
    assert "Panel" in c.get("/").text
    tid = c.post("/api/board/task", json={"title": "Desde la API", "owner": "tester"}).json()["id"]
    assert c.patch(f"/api/board/task/{tid}", json={"status": "next"}).json()["ok"]
    assert any(t["id"] == tid and t["status"] == "next" for t in c.get("/api/board").json()["tasks"])
    assert c.post("/api/board/runner", json={"enabled": True}).json()["enabled"] is True
    assert c.delete(f"/api/board/task/{tid}").json()["ok"]
