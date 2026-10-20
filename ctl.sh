#!/usr/bin/env bash
# testtgbot — управление стеком docker compose (lb на 127.0.0.1:$LB_PORT).
# Usage: ./ctl.sh start|stop|restart|status|logs [service]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

_env_val() { { grep -E "^$1=" "$ROOT/.env" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | tr -d ' "'; }
PORT="$(_env_val LB_PORT)"; PORT="${PORT:-5218}"

if [[ -t 1 ]]; then C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else C_OK=""; C_ERR=""; C_DIM=""; C_RESET=""; fi
msg() { echo "${C_DIM}[ctl]${C_RESET} $*"; }
ok()  { echo "${C_OK}✓${C_RESET} $*"; }
err() { echo "${C_ERR}✗${C_RESET} $*" >&2; }

# Бот без токена не стартует; без webhook — polling, а он допускает только одну реплику.
bot_scale() {
  if [[ -z "$(_env_val BOT_TOKEN)" ]]; then echo 0
  elif [[ -z "$(_env_val WEBHOOK_BASE_URL)" ]]; then echo 1
  else local n; n="$(_env_val BOT_REPLICAS)"; echo "${n:-2}"; fi
}

start() {
  local bots; bots="$(bot_scale)"
  msg "docker compose up (бот: $bots реплик)"
  docker compose up -d --build --scale bot="$bots"
  for _ in $(seq 1 60); do
    curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && { ok "запущен → http://127.0.0.1:$PORT (testtgbot.localhost)"; return; }
    sleep 1
  done
  err "не поднялся, см. ./ctl.sh logs"; return 1
}

stop()   { docker compose down; ok "остановлен"; }
status() {
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then ok "running :$PORT"; else msg "stopped"; docker compose ps; return 3; fi
  docker compose ps --format 'table {{.Service}}\t{{.Name}}\t{{.Status}}'
}

case "${1:-help}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) shift; docker compose logs -f --tail 100 "$@" ;;
  *) echo "Usage: $0 start|stop|restart|status|logs [service]"; exit 1 ;;
esac
