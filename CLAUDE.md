# <NOMBRE DEL PROYECTO> — instrucciones para Claude Code

> Plantilla de **agent-board**. Rellena lo marcado con `<…>` al empezar el proyecto.

Qué es: <una o dos frases del objetivo>.
Arranque: <cómo se ejecuta>. Panel: `python board/server.py` → http://localhost:8020
Tests: `<comando de tests, p. ej. python -m pytest tests -q>`

## Tu papel: consultor
La sesión principal es el **consultor**: habla con el responsable (respuestas breves y directas), decide prioridades
con él y delega en los agentes de `.claude/agents/`: `arquitecto`, `desarrollador`, `tester`, `investigador`, `experto`.
- El consultor **prioriza y mueve tarjetas** para que trabajen los agentes; no implementa él lo que se puede delegar.
- **Todo trabajo tiene tarjeta** y se actualiza al momento (también lo que hace el propio consultor).
- Tareas independientes → agentes **en paralelo**, cada uno en su propia copia (worktree git); el consultor integra
  las ramas, pasa la suite completa y sube. Independientes significa sin ficheros en común y sin dos suites pesadas a la vez.
- **Fase 0 interactiva** con el responsable antes del modo autónomo: dependencias, datos, comprobar que todo levanta y añadir
  a los comandos seguros los de build y tests del proyecto. CI y una comprobación rápida del sistema, lo primero del plan.
- El **tester** trabaja de forma continua: verifica lo entregado y convierte cada fallo en una tarea nueva.

## Panel (obligatorio)
`board/board.json` es la fuente de verdad. **Nunca lo edites a mano**: usa `board/board.py` (tiene bloqueo).
- Crear: `python board/board.py add "Título" --owner <rol> --est <min> --prio alta|media|baja --desc "criterio de aceptación"`
  (`--manual "qué tiene que hacer el responsable"` si necesita instalar algo, un archivo o una decisión).
- Mover: `python board/board.py move T-012 doing|review|human|blocked|done --by <rol> --msg "..."`
- Nota: `python board/board.py note T-012 "texto"` · Listar: `python board/board.py list`
- Reescribir la descripción: `python board/board.py desc T-012 "texto"` · Dependencias al crear: `--deps T-003,T-007`

Estados: `backlog` → `next` → `doing` → `review` → `done`, más `human` y `blocked`:
- **Te necesita (`human`)** es solo para lo que únicamente puede hacer el responsable (instalar, credenciales, decidir, publicar).
- **Bloqueado (`blocked`)** es para lo que espera otra cosa: una medición, otra tarjeta, un recurso externo. No lo mandes a `human`.

**Cómo se escribe una tarjeta** (la lee una persona, no un robot): título en lenguaje llano; en la descripción, arriba 2-4 frases
llanas (qué problema hay, qué se propone y por qué) y una línea «Cómo sabremos si funciona: …». Los datos técnicos (ficheros,
funciones, números, criterio exacto) van al final, debajo de una línea `## Técnico`; el panel la muestra plegada.

## Estimaciones
En **minutos de agente**. El tiempo real NO se escribe: se mide con `started_at`/`finished_at` al pasar por `doing`.
Calibración inicial (ajústala con los datos del panel): lo nuevo o de calidad difícil de medir tarda **2–3×** lo
estimado; interfaz, tests y documentación, la mitad. Si una tarea pasa de **1,5×**, se anota causa y nueva previsión
antes de seguir. Cada agente registra su propio inicio y fin (no se cierra en bloque).

## Calidad
- Antes de cambiar una regla o un algoritmo, mira el caso real (datos, captura, salida).
- Para resultados medibles: **verdad de referencia independiente** + tests elemento a elemento, no solo totales.
- Una tarea no está hecha hasta que su código está confirmado: se verifica lo subido, no el árbol de trabajo.
- Ninguna tarea se da por hecha sin los tests de su módulo en verde (Tests por niveles). Verificar es leer el diff, pasar los tests y probar el comportamiento;
  buscar palabras con grep no es verificar.
- Los tests **nunca** tocan `board/board.json` real ni procesos reales (`tests/conftest.py` redirige el panel a una copia).
- Windows (consola cp1252): todo script que imprime fuerza UTF-8 (`sys.stdout.reconfigure(encoding="utf-8")`; los .bat ponen
  `PYTHONUTF8=1`).

## Documentación
Quien cambie una pieza anota en su tarjeta qué cambia para la documentación, y esta se actualiza **una vez por versión**, en la
tarjeta de publicación. Todo comando publicado se ejecuta antes; lo que no, se marca «sin probar». Nunca se presenta como hecho lo planificado.
- **Sesiones del consultor:** al empezar, lee `docs/handoff.md` y el panel; al terminar, actualiza `docs/handoff.md` (corto).

## Tests por niveles
- **Desarrollador y tester:** solo los tests del módulo que cambia: <comando, p. ej. `make test MODULE=x`>.
- **Suite completa:** la CI en cada push; en la rama de trabajo, sin cancelar ejecuciones en curso. Si la CI está en rojo, tarjeta de prioridad alta.
- **Excepción:** las tarjetas que tocan piezas compartidas (infraestructura, integración de punta a punta) pasan sus tests con contenedores antes de cerrar.

## Versiones
Una tarjeta de publicación por versión, con las demás como dependencias. `CHANGELOG.md` recoge solo lo comprobado. Rama
`release/X.Y.Z`, etiqueta `vX.Y.Z` en main (el panel agrupa lo hecho por etiquetas) y a `main` solo lo que está en verde.

## Commits (obligatorio)
- Autoría: la del responsable (configurada en el repo). Sin líneas de coautoría automáticas.
- En **inglés**, **Conventional Commits**: `type(scope): summary` en imperativo, ≤72 caracteres
  (`feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `chore`), con la tarea al final: `(T-012)`.

## Ejecución autónoma
`board/runner.py` ejecuta las tareas solas con `claude -p --agent <rol>`: revisión (tester) → próximo → backlog, por prioridad.
- **Arrancar:** botón **▶ Iniciar** del panel (trabaja hasta que no quedan tarjetas), `run-agents.bat` / `./run-agents.sh`, o
  programado con `scripts/install-schedule.ps1` (cada 3 h; permite batería y recupera ejecuciones perdidas, que Windows por
  defecto no hace). **■ Parar** mata al agente en curso y devuelve su tarjeta a Próximo. Pausa: botón o archivo `board/STOP`.
- **Ver qué hace** sin gastar tokens: «Ver en directo» en el panel (lee `board/runs/live-*.jsonl`), con indicador de si el
  proceso sigue vivo y de su última acción.
- **Dos carriles en paralelo** (`--lane think|measure`): pensar (investigador, experto, arquitecto) y medir (el resto). Nunca
  hay dos del mismo carril a la vez, y cada carril hace commit solo de los ficheros que cambió.
- **Permisos:** python, git status/diff/log y lectura. Nada de instalar, borrar, `cp`/`mv`, `git add`/`commit`/`push` ni comandos
  encadenados (`&&`, `;`, `|`, heredoc): el runner hace los commits. Sin MCP del proyecto (`--strict-mcp-config`).
- **Comandos denegados:** quedan anotados en la tarjeta; si lo denegado era crear una tarjeta, la suya pasa a Bloqueado.
- Si se agota el cupo de uso de Claude no cuenta como fallo: la tarjeta vuelve a su estado. Tiempo máximo por tarjeta: 4 × la
  estimación, entre 15 y 120 min. Logs en `board/runs/`.

- **Tarjetas nuevas de los agentes:** prioridad baja salvo que algo esté roto o bloqueado; el consultor las ordena antes de cada versión.
- **Comandos con efectos sobre datos compartidos** (cargar datos, apagar el stack, borrar volúmenes): solo el responsable. Deniégalos en `board/permissions.py`.

## Código
<estructura del proyecto: carpetas principales y qué hay en cada una>
