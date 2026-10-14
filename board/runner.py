"""Runner autónomo: coge tareas del panel y las ejecuta con Claude Code (`claude -p --agent <rol>`).

Orden: 1) tareas en Revisión → las verifica el tester; 2) Próximo; 3) Backlog (por prioridad).
Salta: Te necesita, Bloqueado, tareas del consultor (son tuyas) y dependencias sin terminar.
Mide tiempo real, turnos y coste de cada ejecución, y hace commit git antes y después.
Se pausa desde el panel (botón Pausar) o creando el archivo board/STOP.

Uso: python board/runner.py [--once] [--dry-run] [--claude RUTA]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import board as bd  # noqa: E402

ROOT = Path(__file__).parents[1]
STOP = Path(__file__).with_name("STOP")
LOGDIR = Path(__file__).with_name("runs")
RESULT_RE = re.compile(r"RESULT:\s*(done|review|human|blocked|fail)\b\s*[—:-]?\s*(.*)", re.I)
MAX_FAILS = 3

# Permisos "código y tests": edita archivos, ejecuta python/pytest/git local. Nada de instalar ni push.
ALLOWED = ["Read", "Edit", "Write", "Glob", "Grep", "WebSearch", "WebFetch",
           "Bash(python *)", "Bash(py *)", "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)",
           "Bash(ls*)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(mkdir *)"]
DENIED = ["Bash(python -m pip *)", "Bash(py -m pip *)", "Bash(pip *)", "Bash(npm *)", "Bash(npx *)",
          "Bash(winget *)", "Bash(choco *)", "Bash(curl *)", "Bash(wget *)", "Bash(git push*)",
          "Bash(git reset*)", "Bash(rm -rf*)", "Bash(python -m playwright install*)"]

RULES = """Reglas (modo autónomo, permisos: solo código y tests):
- Nadie va a responder preguntas: decide tú dentro de tu rol, con el criterio más sensato.
- Sigue CLAUDE.md. Trabaja SOLO en esta tarea. Si ves otras mejoras o bugs, regístralos con
  `python board/board.py add "Título" --owner <rol> --est <minutos de agente> --prio <alta|media|baja> --desc "..." --by {owner}`.
  Las estimaciones son en MINUTOS DE AGENTE (lo que tardarías tú), no horas humanas.
- NO edites board/board.json a mano: usa siempre board/board.py.
- NO instales software ni dependencias, no descargues binarios, no hagas git push. Si la tarea lo
  necesita, o necesita un archivo o una decisión del responsable, para y termina con RESULT: human explicando
  exactamente qué tiene que hacer ella (pasos concretos).
- Si tocas código: ejecuta los tests del proyecto (comando en CLAUDE.md) y déjalos en verde; añade tests nuevos si procede.
- Responde en español. Tu ÚLTIMA línea debe ser exactamente:
  RESULT: <estado> — <resumen en una frase>
  {states}"""

STATES_DEV = "Estados: review (hecho, falta verificar), human (necesita al responsable), blocked (no puedes avanzar)."
STATES_DOC = "Estados: done (terminado), human (necesita al responsable), blocked (no puedes avanzar)."
STATES_QA = "Estados: done (verificado OK), fail (no pasa: explica cómo reproducirlo), human, blocked."


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def set_runner(**kw):
    def f(b):
        b.setdefault("runner", {}).update(kw, heartbeat=now())
    bd.update(f)


def enabled():
    if STOP.exists():
        return False
    return bd.load().get("runner", {}).get("enabled", True)


def pick(b):
    """Siguiente tarea ejecutable: (tarea, modo) con modo 'verify' o 'work'."""
    # tareas que necesitan algo del responsable (manual) solo corren cuando el responsable las mueve a Próximo
    ok = lambda t: t["owner"] != "consultor" and bd.deps_done(b, t) and (t.get("auto", True) or t["status"] == "next")
    key = lambda t: (bd.PRIO.get(t.get("priority"), 1), t["id"])
    rev = sorted([t for t in b["tasks"] if t["status"] == "review" and ok(t)], key=key)
    if rev:
        return rev[0], "verify"
    for st in ("next", "backlog"):
        c = sorted([t for t in b["tasks"] if t["status"] == st and ok(t)], key=key)
        if c:
            return c[0], "work"
    return None, None


def build_prompt(t, mode, agent):
    hist = "\n".join(f"- {l['t'][:16]} {l['by']}: {l['msg']}" for l in t.get("log", [])[-8:])
    if mode == "verify":
        head = (f"Eres el TESTER. Verifica la tarea {t['id']} «{t['title']}» que el {t['owner']} ha dejado en Revisión.\n"
                "Revisa el cambio (git log/diff), ejecuta los tests del proyecto y añade un test que cubra la tarea si no existe.")
        states = STATES_QA
    else:
        head = f"Eres el agente «{agent}». Ejecuta la tarea {t['id']}: {t['title']}"
        states = STATES_DEV if agent == "desarrollador" else STATES_DOC
    return (f"{head}\n\nDescripción: {t.get('desc') or '(sin descripción)'}\n"
            f"Estimación: {t.get('estimate_min') or '?'} min\nHistorial reciente:\n{hist}\n\n"
            + RULES.format(owner=agent, states=states))


def git(*args):
    if not (ROOT / ".git").exists() or not shutil.which("git"):
        return
    subprocess.run(["git", *args],  # identidad: la configurada en el repo
                   cwd=ROOT, capture_output=True)


def run_claude(claude, prompt, agent, timeout_s):
    cmd = [claude, "-p", "--agent", agent, "--output-format", "json",
           "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--max-turns", "80", "--allowedTools", *ALLOWED, "--disallowedTools", *DENIED]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", capture_output=True,
                           cwd=ROOT, timeout=timeout_s)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, code = (e.stdout or ""), "timeout", -1
    data = {}
    try:
        data = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except (json.JSONDecodeError, IndexError):
        pass
    text = data.get("result") if isinstance(data.get("result"), str) else out
    return dict(text=text or "", err=err[-2000:] if err else "", code=code, secs=time.time() - t0,
                turns=data.get("num_turns"), cost=data.get("total_cost_usd"),
                usage=data.get("usage") or {}, is_error=data.get("is_error", code != 0))


def finish(tid, mode, agent, r):
    m = None
    for line in reversed(r["text"].strip().splitlines()):
        m = RESULT_RE.search(line)
        if m:
            break
    verdict = m.group(1).lower() if m else ("blocked" if r["is_error"] else "review")
    summary = (m.group(2).strip() if m else (r["err"] or r["text"][-300:]).strip())[:400] or "sin resumen"
    u = r["usage"]
    toks = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) \
        + (u.get("cache_creation_input_tokens") or 0)

    def f(b):
        t = bd.task(b, tid)
        if mode == "verify":
            new = {"done": "done", "fail": "next", "human": "human"}.get(verdict, "blocked")
            if new == "next":
                t["owner"] = "desarrollador"
        else:
            new = {"done": "done", "review": "review", "human": "human"}.get(verdict, "blocked")
            if new == "done" and agent == "desarrollador":
                new = "review"  # el código siempre lo verifica el tester
        runs = t.setdefault("runs", [])
        runs.append(dict(agent=agent, mode=mode, at=now(), min=round(r["secs"] / 60, 1), turns=r["turns"],
                         tokens=toks or None, cost_usd=r["cost"], verdict=verdict))
        if verdict == "human" and summary:
            t["manual"], t["auto"] = summary, False
        bd.set_status(b, t, new, agent, f"{verdict.upper()}: {summary}")
        return new
    return bd.update(f), verdict, summary


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="ejecuta una tarea y sale")
    ap.add_argument("--dry-run", action="store_true", help="muestra qué haría sin ejecutar")
    ap.add_argument("--claude", default=os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude")
    ap.add_argument("--idle", type=int, default=30, help="segundos de espera cuando no hay tareas")
    o = ap.parse_args()
    LOGDIR.mkdir(exist_ok=True)
    fails = 0
    print(f"Runner en marcha · claude = {o.claude}\nPausa: botón en el panel o crea board/STOP · Ctrl+C para salir")
    set_runner(state="idle", current=None, message="Runner en marcha", pid=os.getpid())

    def recover(b):  # tareas que se quedaron "En curso" si el runner se cortó
        for x in b["tasks"]:
            if x["status"] == "doing" and x["owner"] != "consultor":
                bd.set_status(b, x, "next", "runner", "interrumpida (runner reiniciado); se reintentará")
        for a in b["agents"]:
            if a["id"] != "consultor":
                a.update(status="idle", current=None)
    bd.update(recover)
    try:
        while True:
            if not enabled():
                set_runner(state="paused", current=None, message="En pausa")
                time.sleep(5)
                continue
            b = bd.load()
            t, mode = pick(b)
            if not t:
                set_runner(state="idle", current=None, message="Sin tareas ejecutables")
                if o.once:
                    break
                time.sleep(o.idle)
                continue
            agent = "tester" if mode == "verify" else t["owner"]
            print(f"\n[{now()[11:19]}] {t['id']} · {agent} · {mode} · {t['title']}")
            if o.dry_run:
                print(build_prompt(t, mode, agent)); break
            tid = t["id"]

            def start(b):
                x = bd.task(b, tid)
                if mode == "verify":
                    bd.log(x, "tester", "verificando")
                    x["verify_started"] = now()
                    for a in b["agents"]:
                        if a["id"] == "tester":
                            a.update(status="working", current=tid)
                else:
                    bd.set_status(b, x, "doing", "runner", f"empieza {agent}")
            bd.update(start)
            set_runner(state="working", current=tid, agent=agent, started=now(), message=f"{agent} con {tid}")
            git("add", "-A"); git("commit", "-q", "-m", f"chore(runner): checkpoint before {tid}")

            est = t.get("estimate_min") or 15
            r = run_claude(o.claude, build_prompt(t, mode, agent), agent, timeout_s=int(min(60, max(15, est * 4)) * 60))
            (LOGDIR / f"{tid}-{agent}-{datetime.now():%Y%m%d-%H%M%S}.txt").write_text(
                f"{r['text']}\n\n--- stderr ---\n{r['err']}", encoding="utf-8")
            new, verdict, summary = finish(tid, mode, agent, r)
            if mode == "verify":
                def free(b):
                    for a in b["agents"]:
                        if a["id"] == "tester" and a.get("current") == tid:
                            a.update(status="idle", current=None)
                bd.update(free)
            git("add", "-A"); git("commit", "-q", "-m", f"chore(runner): {tid} {verdict} by {agent}")
            git("push", "-q")  # sincroniza con GitHub (lo hace el runner, nunca el agente)
            print(f"  → {new} en {r['secs'] / 60:.1f} min · {summary}")

            fails = fails + 1 if (r["is_error"] or verdict == "blocked") else 0
            if fails >= MAX_FAILS:
                set_runner(state="paused", current=None, message=f"Pausado tras {MAX_FAILS} fallos seguidos; revisa board/runs/")
                bd.update(lambda b: b["runner"].update(enabled=False))
                fails = 0
            if o.once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        set_runner(state="stopped", current=None, message="Runner parado")


if __name__ == "__main__":
    main()
