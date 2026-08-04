#!/usr/bin/env bash
# Funções compartilhadas pelos scripts de deploy VPS.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nexus-erp-prod}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-${APP_DIR}/backups}"
DEPLOY_STATE_FILE="${DEPLOY_STATE_FILE:-${APP_DIR}/.deploy-state}"

compose() {
  docker compose -f "${APP_DIR}/${COMPOSE_FILE}" --env-file "${APP_DIR}/.env" "$@"
}

require_app_dir() {
  if [[ ! -d "${APP_DIR}" ]]; then
    echo "ERRO: diretório ${APP_DIR} não existe." >&2
    exit 1
  fi
  if [[ ! -f "${APP_DIR}/.env" ]]; then
    echo "ERRO: ${APP_DIR}/.env não encontrado. Crie manualmente a partir de .env.example." >&2
    exit 1
  fi
  if [[ ! -f "${APP_DIR}/${COMPOSE_FILE}" ]]; then
    echo "ERRO: ${APP_DIR}/${COMPOSE_FILE} não encontrado." >&2
    exit 1
  fi
}

load_env_db_defaults() {
  # shellcheck disable=SC1091
  set -a
  source "${APP_DIR}/.env"
  set +a
  DB_USER="${DB_USER:-postgres}"
  DB_NAME="${DB_NAME:-nexus_erp}"
}

record_deploy_state() {
  local action="$1"
  mkdir -p "$(dirname "${DEPLOY_STATE_FILE}")"
  {
    echo "last_action=${action}"
    echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "commit=$(git -C "${APP_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "branch=$(git -C "${APP_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  } > "${DEPLOY_STATE_FILE}"
}
