# <NOMBRE DEL PROYECTO> — instrucciones para Claude Code

> Plantilla de **agent-board**. Rellena lo marcado con `<…>` al empezar el proyecto.

Qué es: <una o dos frases del objetivo>.
Arranque: <cómo se ejecuta>. Panel: `python board/server.py` → http://localhost:8020
Tests: `<comando de tests, p. ej. python -m pytest tests -q>`

## Tu papel: consultor
La sesión principal es el **consultor**: habla con el responsable (respuestas breves y directas), decide prioridades
con él y delega en los agentes de `.claude/agents/`: `arquitecto`, `desarrollador`, `tester`, `investigador`, `experto`.
- Tareas independientes → agentes **en paralelo**, cada uno en su propia copia (worktree git); el consultor integra
  las ramas, pasa la suite completa y sube.
- El **tester** trabaja de forma continua: verifica lo entregado y convierte cada fallo en una tarea nueva.

## Panel (obligatorio)
`board/board.json` es la fuente de verdad. **Nunca lo edites a mano**: usa `board/board.py` (tiene bloqueo).
- Crear: `python board/board.py add "Título" --owner <rol> --est <min> --prio alta|media|baja --desc "criterio de aceptación"`
  (`--manual "qué tiene que hacer el responsable"` si necesita instalar algo, un archivo o una decisión).
- Mover: `python board/board.py move T-012 doing|review|human|blocked|done --by <rol> --msg "..."`
- Nota: `python board/board.py note T-012 "texto"` · Listar: `python board/board.py list`

Estados: `backlog` → `next` → `doing` → `review` → `done`, más `human` (te necesita) y `blocked`.

## Estimaciones
En **minutos de agente**. El tiempo real NO se escribe: se mide con `started_at`/`finished_at` al pasar por `doing`.
Calibración inicial (ajústala con los datos del panel): lo nuevo o de calidad difícil de medir tarda **2–3×** lo
estimado; interfaz, tests y documentación, la mitad. Si una tarea pasa de **1,5×**, se anota causa y nueva previsión
antes de seguir. Cada agente registra su propio inicio y fin (no se cierra en bloque).

## Calidad
- Antes de cambiar una regla o un algoritmo, mira el caso real (datos, captura, salida).
- Para resultados medibles: **verdad de referencia independiente** + tests elemento a elemento, no solo totales.
- Ninguna tarea se da por hecha sin la suite en verde.

## Commits (obligatorio)
- Autoría: la del responsable (configurada en el repo). Sin líneas de coautoría automáticas.
- En **inglés**, **Conventional Commits**: `type(scope): summary` en imperativo, ≤72 caracteres
  (`feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `chore`), con la tarea al final: `(T-012)`.

## Ejecución autónoma
`run-agents.bat` / `./run-agents.sh` (→ `board/runner.py`) ejecuta las tareas solas con `claude -p --agent <rol>`:
revisión (tester) → próximo → backlog, por prioridad. Permisos: solo código y tests (sin instalar, sin push).
Commit antes y después de cada tarea. Pausa: botón en el panel o archivo `board/STOP`. Logs en `board/runs/`.

## Código
<estructura del proyecto: carpetas principales y qué hay en cada una>
