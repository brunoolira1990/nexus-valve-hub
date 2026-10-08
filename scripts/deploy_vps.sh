#!/usr/bin/env bash
# Deploy controlado do ERP na VPS (Git pull + backup + build + up + checks).
#
# Uso na VPS:
#   cd /opt/nexus-erp-prod
#   git fetch && git checkout producao-local   # ou branch acordada
#   ./scripts/deploy_vps.sh
#
# Variáveis opcionais:
#   APP_DIR=/opt/nexus-erp-prod
#   SKIP_BACKUP=1          # não recomendado
#   SKIP_PULL=1            # apenas rebuild/up (já fez git pull)
#   SKIP_MIGRATE_CHECK=1   # pula showmigrations pós-deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vps_common.sh
source "${SCRIPT_DIR}/lib/vps_common.sh"

require_app_dir
cd "${APP_DIR}"

PREVIOUS_COMMIT="$(git rev-parse HEAD)"
echo "[deploy] Commit atual (antes do pull): ${PREVIOUS_COMMIT}"
echo "${PREVIOUS_COMMIT}" > "${APP_DIR}/.deploy_previous_commit"

if [[ "${SKIP_PULL:-}" != "1" ]]; then
  echo "[deploy] git fetch + pull..."
  git fetch --all --prune
  git pull --ff-only
fi

NEW_COMMIT="$(git rev-parse HEAD)"
echo "[deploy] Novo commit: ${NEW_COMMIT}"

if [[ "${SKIP_BACKUP:-}" != "1" ]]; then
  echo "[deploy] Backup do banco antes de subir nova versão..."
  "${SCRIPT_DIR}/backup_db.sh" pre_deploy
  if [[ -d "${APP_DIR}/data/media" ]]; then
    MEDIA_BACKUP="${BACKUP_ROOT}/media/media_pre_deploy_$(date +%Y%m%d_%H%M%S).tar.gz"
    mkdir -p "${BACKUP_ROOT}/media"
    echo "[deploy] Backup opcional de data/media -> ${MEDIA_BACKUP}"
    tar -czf "${MEDIA_BACKUP}" -C "${APP_DIR}/data" media 2>/dev/null || echo "[deploy] AVISO: sem pasta data/media local para tar"
  fi
fi

echo "[deploy] Validando compose..."
compose config > /dev/null

echo "[deploy] Build das imagens..."
compose build

echo "[deploy] Subindo stack..."
compose up -d

echo "[deploy] Aguardando backend healthy..."
TRIES=0
until compose ps backend 2>/dev/null | grep -q healthy; do
  TRIES=$((TRIES + 1))
  if [[ ${TRIES} -gt 60 ]]; then
    echo "[deploy] ERRO: backend não ficou healthy em tempo hábil." >&2
    compose logs --tail=80 backend || true
    exit 1
  fi
  sleep 5
done

echo "[deploy] Checks Django..."
compose exec -T backend python manage.py check
compose exec -T backend python manage.py create_groups
compose exec -T backend python manage.py verificar_prontidao_producao || true

if [[ "${SKIP_MIGRATE_CHECK:-}" != "1" ]]; then
  echo "[deploy] Migrations aplicadas (showmigrations --plan últimas 5 linhas):"
  compose exec -T backend python manage.py showmigrations --plan | tail -5
fi

record_deploy_state deploy
echo "[deploy] Concluído."
echo "[deploy] Commit anterior salvo em ${APP_DIR}/.deploy_previous_commit"
echo "[deploy] Teste local: curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:\${ERP_HTTP_PORT:-18080}/"
echo "[deploy] Rollback: ./scripts/rollback_vps.sh"
