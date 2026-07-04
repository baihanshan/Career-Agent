#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.local/logs"

CONDA_ENV="${CONDA_ENV:-carrer_agent}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL="${BACKEND_URL:-http://$HOST:$BACKEND_PORT}"
FRONTEND_URL="${FRONTEND_URL:-http://$HOST:$FRONTEND_PORT}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"

BACKEND_PID=""
FRONTEND_PID=""

usage() {
  cat <<EOF
CareerPilot Agent local launcher

Usage:
  scripts/start_app.sh [--no-browser]

Environment overrides:
  CONDA_ENV=carrer_agent
  BACKEND_PORT=8000
  FRONTEND_PORT=3000
  OPEN_BROWSER=0

The launcher starts the FastAPI backend and Next.js frontend, then opens:
  $FRONTEND_URL
EOF
}

for arg in "$@"; do
  case "$arg" in
    --help|-h)
      usage
      exit 0
      ;;
    --no-browser)
      OPEN_BROWSER=0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage
      exit 2
      ;;
  esac
done

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

find_conda() {
  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return
  fi

  for candidate in \
    "$HOME/miniforge3/bin/conda" \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done

  echo ""
}

require_command() {
  local command_name="$1"
  local install_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    echo "$install_hint" >&2
    exit 1
  fi
}

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

url_ok() {
  local url="$1"
  curl -fsS "$url" >/dev/null 2>&1
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"

  for _ in $(seq 1 "$attempts"); do
    if url_ok "$url"; then
      return 0
    fi
    sleep 1
  done

  echo "$label did not become ready at $url" >&2
  return 1
}

open_browser() {
  if [[ "$OPEN_BROWSER" != "1" ]]; then
    return
  fi

  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
}

ensure_backend_environment() {
  local conda_bin="$1"

  if ! "$conda_bin" env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
    echo "Creating conda environment: $CONDA_ENV"
    "$conda_bin" create -n "$CONDA_ENV" python="$PYTHON_VERSION" -y
  fi

  if ! "$conda_bin" run -n "$CONDA_ENV" python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Installing backend dependencies into conda environment: $CONDA_ENV"
    "$conda_bin" run -n "$CONDA_ENV" pip install -r "$ROOT_DIR/requirements-dev.txt"
  fi
}

ensure_frontend_environment() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

start_backend() {
  local conda_bin="$1"
  local log_file="$LOG_DIR/backend.log"

  if url_ok "$BACKEND_URL/health"; then
    echo "Backend is already running at $BACKEND_URL"
    return
  fi

  if port_in_use "$BACKEND_PORT"; then
    echo "Port $BACKEND_PORT is already in use, but $BACKEND_URL/health is not healthy." >&2
    echo "Stop the process on that port or set BACKEND_PORT to another value." >&2
    exit 1
  fi

  echo "Starting backend at $BACKEND_URL"
  (
    cd "$ROOT_DIR"
    "$conda_bin" run -n "$CONDA_ENV" uvicorn backend.app.main:app \
      --reload \
      --log-level debug \
      --host "$HOST" \
      --port "$BACKEND_PORT"
  ) >>"$log_file" 2>&1 &
  BACKEND_PID="$!"

  wait_for_url "$BACKEND_URL/health" "Backend" 90
}

start_frontend() {
  local log_file="$LOG_DIR/frontend.log"

  if url_ok "$FRONTEND_URL"; then
    echo "Frontend is already running at $FRONTEND_URL"
    return
  fi

  if port_in_use "$FRONTEND_PORT"; then
    echo "Port $FRONTEND_PORT is already in use, but $FRONTEND_URL is not reachable." >&2
    echo "Stop the process on that port or set FRONTEND_PORT to another value." >&2
    exit 1
  fi

  echo "Starting frontend at $FRONTEND_URL"
  (
    cd "$FRONTEND_DIR"
    NEXT_PUBLIC_API_BASE_URL="$BACKEND_URL" npm run dev -- -H "$HOST" -p "$FRONTEND_PORT"
  ) >>"$log_file" 2>&1 &
  FRONTEND_PID="$!"

  wait_for_url "$FRONTEND_URL" "Frontend" 90
}

main() {
  mkdir -p "$LOG_DIR"

  require_command npm "Install Node.js and npm, then run this launcher again."
  require_command curl "Install curl, then run this launcher again."
  require_command lsof "Install lsof, then run this launcher again."

  local conda_bin
  conda_bin="$(find_conda)"
  if [[ -z "$conda_bin" ]]; then
    echo "Could not find conda." >&2
    echo "Install Miniforge, Miniconda, or Anaconda, then run this launcher again." >&2
    exit 1
  fi

  ensure_backend_environment "$conda_bin"
  ensure_frontend_environment
  start_backend "$conda_bin"
  start_frontend
  open_browser

  cat <<EOF

CareerPilot Agent is running:
  Frontend: $FRONTEND_URL
  Backend:  $BACKEND_URL

Logs:
  $LOG_DIR/backend.log
  $LOG_DIR/frontend.log

Press Ctrl+C in this terminal to stop services started by this launcher.
EOF

  if [[ -n "$FRONTEND_PID" ]]; then
    wait "$FRONTEND_PID"
  elif [[ -n "$BACKEND_PID" ]]; then
    wait "$BACKEND_PID"
  fi
}

main
