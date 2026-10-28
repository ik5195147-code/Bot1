#!/usr/bin/env bash
# Starts Pyhost. First run asks for a panel password and saves it in config.env
cd "$(dirname "$0")"
[ -f config.env ] && . ./config.env
if [ -z "$HOST_PASSWORD" ]; then
  read -rsp "Panel-er jonno ekta password dao: " HOST_PASSWORD
  echo
  printf 'export HOST_PASSWORD=%q\nexport PORT=8080\n' "$HOST_PASSWORD" > config.env
  chmod 600 config.env
fi
export HOST_PASSWORD
export PORT="${PORT:-8080}"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
exec python hosting_server.py
