#!/usr/bin/env bash
# Выкладка на сервер: rsync исходников + docker compose up --build там же.
# .env на сервере заполняется руками один раз (см. .env.example) и сюда не копируется.
# Разово до первого деплоя: DNS testtgbot.riakovlev.ru → сервер,
#   dash-nginx add testtgbot.riakovlev.ru <LB_PORT> && dash-nginx cert testtgbot.riakovlev.ru
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST=ryakovlev
DIR=apps/testtgbot

ssh "$HOST" "mkdir -p $DIR"
rsync -az --delete \
  --exclude .git --exclude .env --exclude var --exclude node_modules --exclude .next \
  --exclude __pycache__ --exclude 'e2e/*.png' \
  "$ROOT/" "$HOST:$DIR/"
ssh "$HOST" "cd $DIR && test -f .env || { echo '✗ нет $DIR/.env на сервере — заполни по .env.example'; exit 1; }
  docker compose up -d --build --remove-orphans && docker compose ps --format 'table {{.Service}}\t{{.Name}}\t{{.Status}}'"
echo "✓ https://testtgbot.riakovlev.ru"
