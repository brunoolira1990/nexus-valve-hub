
#!/bin/bash
set -euo pipefail

# Configurações
PROJETO_DIR="$HOME/Projetos/nexus-valve-hub"
BACKUP_DIR="$PROJETO_DIR/backups"
DIAS_RETENCAO=14
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-nexus_erp}"
DATA=$(date +%Y%m%d_%H%M%S)
ARQUIVO="$BACKUP_DIR/nexus_auto_${DATA}.sql"
LOG_FILE="$BACKUP_DIR/backup.log"

cd "$PROJETO_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando backup..." >> "$LOG_FILE"

if docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner --no-privileges > "$ARQUIVO" 2>> "$LOG_FILE"; then
    TAMANHO=$(ls -lh "$ARQUIVO" | awk '{print $5}')
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup OK: $ARQUIVO ($TAMANHO)" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERRO no backup! Verifique o container do banco." >> "$LOG_FILE"
    # Remove arquivo incompleto, se foi criado
    rm -f "$ARQUIVO"
    exit 1
fi

# Validação básica de integridade do dump gerado
if ! docker compose exec -T db pg_restore --list < "$ARQUIVO" > /dev/null 2>> "$LOG_FILE"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: backup gerado mas falhou na validação de integridade ($ARQUIVO)" >> "$LOG_FILE"
fi

# Rotação: apaga backups automáticos mais antigos que DIAS_RETENCAO dias
# (não mexe nos backups manuais "antes_deploy", só nos "nexus_auto_*")
find "$BACKUP_DIR" -name "nexus_auto_*.sql" -mtime "+$DIAS_RETENCAO" -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup concluído. Retenção: $DIAS_RETENCAO dias." >> "$LOG_FILE"
