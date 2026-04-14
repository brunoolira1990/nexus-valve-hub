#!/bin/sh
set -e
cd /app
if [ ! -d node_modules/vite ]; then
  echo "[frontend] Instalando dependências (node_modules vazio no volume)..."
  npm ci
fi
exec "$@"
