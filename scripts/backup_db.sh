#!/usr/bin/env bash
# Backup do Postgres do ERP (formato custom, comprimido).
# Uso: ./scripts/backup_db.sh <tag>
#   tag = pre_deploy | pre_rollback | manual | auto
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/vps_common.sh"

TAG="${1:-manual}"
BACKUP_DIR="${BACKUP_ROOT}/db"
mkdir -p "${BACKUP_DIR}"

load_env_db_defaults

DATA=$(date +%Y%m%d_%H%M%S)
ARQUIVO="${BACKUP_DIR}/nexus_${TAG}_${DATA}.dump"
LOG_FILE="${BACKUP_ROOT}/backup.log"
mkdir -p "${BACKUP_ROOT}"

cd "${APP_DIR}"

echo "[$(date '+%F %T')] [${TAG}] Iniciando backup..." >> "${LOG_FILE}"

if compose exec -T db pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
       --format=custom --no-owner --no-privileges > "${ARQUIVO}" 2>> "${LOG_FILE}"; then
    TAMANHO=$(ls -lh "${ARQUIVO}" | awk '{print $5}')
    echo "[$(date '+%F %T')] [${TAG}] OK: ${ARQUIVO} (${TAMANHO})" >> "${LOG_FILE}"

    if compose exec -T db pg_restore --list < "${ARQUIVO}" > /dev/null 2>> "${LOG_FILE}"; then
        echo "[$(date '+%F %T')] [${TAG}] Integridade OK" >> "${LOG_FILE}"
    else
        echo "[$(date '+%F %T')] [${TAG}] AVISO: falha na validacao de integridade" >> "${LOG_FILE}"
    fi

    find "${BACKUP_DIR}" -name "nexus_auto_*.dump" -mtime +14 -delete
else
    echo "[$(date '+%F %T')] [${TAG}] ERRO: pg_dump falhou" >> "${LOG_FILE}"
    rm -f "${ARQUIVO}"
    exit 1
fi

echo "${ARQUIVO}"
