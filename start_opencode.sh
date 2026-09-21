#!/usr/bin/env bash
# start_opencode.sh — Supervisor hands-free del motor de opencode (Layer 2/3).
#
# Lanza el TUI de opencode dentro de una sesión tmux y arranca el watcher
# (flujo_motor_fallback.py watch --daemon) que detecta el agotamiento de la
# cuota free del motor, conmuta la config global a Qwen3.8 Max 0902 y relanza
# la sesión con el nuevo motor (auto-restore al recuperarse la cuota).
#
# Subcomandos:
#   start      (default) lanza TUI en tmux lanzando antes una sonda pre-flight
#   relaunch   cierra la sesión TUI actual y la relanza (usado por el watcher)
#   attach     conecta a la sesión tmux del TUI (si existe)
#   stop       cierra TUI y detiene el watcher
#   status     estado de la sesión tmux y del watcher
#
# Uso: ./start_opencode.sh [start|relaunch|attach|stop|status] [-s SESSION]
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${SESSION_TMUX_OPENCODE:-oc}"
PYTHON="${CONDA_PREFIX:+$CONDA_PREFIX/bin/python3}"
PYTHON="${PYTHON:-python3}"
FLUJO="$SCRIPT_DIR/flujo_motor_fallback.py"
WATCH_LOG="$SCRIPT_DIR/.tmp/motor_watch.log"
WATCH_PID="$SCRIPT_DIR/.tmp/motor_watch.pid"

if command -v /home/cero/.opencode/bin/opencode >/dev/null 2>&1; then
  OPENCODE="/home/cero/.opencode/bin/opencode"
else
  OPENCODE="$(command -v opencode)" || { echo "opencode no encontrado" >&2; exit 1; }
fi

cmd="${1:-start}"
if [ "$1" = "-s" ] || [ "$1" = "--session" ]; then
  SESSION="$2"
  shift 2
  cmd="${1:-start}"
fi
shift || true

mkdir -p "$SCRIPT_DIR/.tmp"

stop_watcher() {
  if [ -f "$WATCH_PID" ]; then
    kill "$(cat "$WATCH_PID")" 2>/dev/null && rm -f "$WATCH_PID" || true
  fi
}

start_watcher() {
  stop_watcher
  nohup "$PYTHON" "$FLUJO" watch --daemon --intervalo "${MOTOR_WATCH_INTERVALO:-900}" \
    --no-relaunch >"$WATCH_LOG" 2>&1 &
  echo $! > "$WATCH_PID"
}

tmux_present() {
  command -v tmux >/dev/null 2>&1
}

session_live() {
  tmux_present && tmux has-session -t "$SESSION" 2>/dev/null
}

preflight() {
  # Sonda pre-flight: agotada -> conmuta (1 confirmación) para que el TUI
  # arranque directamente con el motor correcto.
  "$PYTHON" "$FLUJO" check >/dev/null 2>&1
  local rc=$?
  if [ "$rc" -eq 1 ]; then
    "$PYTHON" "$FLUJO" switch --confirmaciones 1 --no-alert >/dev/null 2>&1
    echo "[motor] cuota free agotada -> config cambiada a motor de respaldo" >&2
  elif [ "$rc" -gt 1 ]; then
    echo "[motor] sonda indefinida/infra (rc=$rc); se arranca con el motor actual" >&2
  fi
}

launch_tui() {
  tmux new-session -d -s "$SESSION" -- "$OPENCODE"
}

case "$cmd" in
  start)
    tmux_present || { echo "tmux no está instalado; instala tmux para el modo hands-free" >&2; exit 1; }
    if session_live; then
      echo "[tui] sesión $SESSION ya activa"
      if [ -t 0 ]; then tmux attach -t "$SESSION"; fi
      exit 0
    fi
    preflight
    launch_tui
    start_watcher
    echo "[tui] TUI de opencode lanzado en tmux '$SESSION'"
    echo "[watch] watcher del motor en .tmp/motor_watch.log"
    if [ -t 0 ]; then
      echo "[uso] tmux attach -t $SESSION"
      exec tmux attach -t "$SESSION"
    fi
    ;;
  relaunch)
    tmux_present || { echo "tmux no está instalado" >&2; exit 1; }
    if session_live; then
      tmux kill-session -t "$SESSION" 2>/dev/null || true
      sleep 1
    fi
    launch_tui
    echo "[tui] sesión $SESSION relanzada"
    ;;
  attach)
    if session_live; then
      exec tmux attach -t "$SESSION"
    else
      echo "[tui] no hay sesión $SESSION; usa ./start_opencode.sh start" >&2
      exit 1
    fi
    ;;
  stop)
    stop_watcher
    if session_live; then tmux kill-session -t "$SESSION" 2>/dev/null; fi
    echo "[tui] TUI y watcher detenidos"
    ;;
  status)
    if session_live; then echo "[tui] sesión $SESSION activa"; else echo "[tui] sin sesión"; fi
    if [ -f "$WATCH_PID" ] && kill -0 "$(cat "$WATCH_PID")" 2>/dev/null; then
      echo "[watch] activo (pid $(cat "$WATCH_PID"))"
    else
      echo "[watch] detenido"
    fi
    ;;
  *)
    echo "uso: $0 [start|relaunch|attach|stop|status] [-s NOMBRE]" >&2
    exit 2
    ;;
esac