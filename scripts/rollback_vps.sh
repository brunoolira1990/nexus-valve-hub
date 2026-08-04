#!/usr/bin/env bash
# Rollback para commit anterior registrado em .deploy_previous_commit (ou argumento).
#
# Uso:
#   ./scripts/rollback_vps.sh
#   ./scripts/rollback_vps.sh abc1234
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vps_common.sh
source "${SCRIPT_DIR}/lib/vps_common.sh"

require_app_dir
cd "${APP_DIR}"

TARGET_COMMIT="${1:-}"
if [[ -z "${TARGET_COMMIT}" ]]; then
  if [[ ! -f "${APP_DIR}/.deploy_previous_commit" ]]; then
    echo "ERRO: informe o commit ou garanta que ${APP_DIR}/.deploy_previous_commit existe." >&2
    exit 1
  fi
  TARGET_COMMIT="$(cat "${APP_DIR}/.deploy_previous_commit")"
fi

echo "[rollback] Alvo: ${TARGET_COMMIT}"
read -r -p "Confirmar checkout + rebuild? (digite SIM): " CONFIRM
if [[ "${CONFIRM}" != "SIM" ]]; then
  echo "Cancelado."
  exit 1
fi

echo "[rollback] Backup antes do rollback..."
"${SCRIPT_DIR}/backup_db.sh" pre_rollback

git fetch --all --prune
git checkout "${TARGET_COMMIT}"

compose config > /dev/null
compose build
compose up -d

compose exec -T backend python manage.py check
record_deploy_state rollback
echo "[rollback] Concluído em $(git rev-parse HEAD)"
