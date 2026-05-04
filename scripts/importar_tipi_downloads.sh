#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR_HOST="$PROJECT_ROOT/backend/tmp/importacoes_ncm"
TARGET_DIR_CONTAINER="/app/tmp/importacoes_ncm"
SUPPORTED_EXT_REGEX='(pdf|xlsx|csv|txt)'

MANUAL_PATH=""
DO_IMPORT=false
DESATIVAR_AUSENTES=false

print_help() {
  cat <<EOF
Uso:
  ./$SCRIPT_NAME [arquivo] [--importar] [--desativar-ausentes] [--help]

Descrição:
  Localiza arquivo TIPI/NCM em Downloads (ou usa caminho manual), copia para
  backend/tmp/importacoes_ncm e executa importar_ncms no container backend.

Comportamento padrão:
  - Executa somente prévia (--dry-run)
  - Importação real apenas com --importar
  - Para PDF em importação real, adiciona --confirmar-pdf automaticamente

Exemplos:
  ./$SCRIPT_NAME
  ./$SCRIPT_NAME ~/Downloads/TIPI.pdf
  ./$SCRIPT_NAME ~/Downloads/TIPI.pdf --importar
  ./$SCRIPT_NAME ~/Downloads/TIPI.xlsx --importar --desativar-ausentes
EOF
}

err() {
  echo "Erro: $*" >&2
}

expand_path() {
  local raw="$1"
  if [[ "$raw" == "~/"* ]]; then
    echo "${HOME}/${raw#"~/"}"
  else
    echo "$raw"
  fi
}

has_supported_ext() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  local lower="${file,,}"
  [[ "$lower" =~ \.($SUPPORTED_EXT_REGEX)$ ]]
}

discover_download_dirs() {
  local dirs=()
  dirs+=("$HOME/Downloads")
  dirs+=("/home/$USER/Downloads")

  if [[ -d "/mnt/c/Users" ]]; then
    local d
    for d in /mnt/c/Users/*/Downloads; do
      [[ -d "$d" ]] && dirs+=("$d")
    done
  fi

  printf '%s\n' "${dirs[@]}" | awk 'NF && !seen[$0]++'
}

pick_latest_candidate() {
  local files=()
  local d
  while IFS= read -r d; do
    [[ -d "$d" ]] || continue
    while IFS= read -r f; do
      files+=("$f")
    done < <(rg --files -g "*.{pdf,xlsx,csv,txt}" "$d" 2>/dev/null || true)
  done < <(discover_download_dirs)

  if [[ ${#files[@]} -eq 0 ]]; then
    return 1
  fi

  local best_file=""
  local best_ts=0
  local candidate
  for candidate in "${files[@]}"; do
    [[ -f "$candidate" ]] || continue
    local name_lower
    name_lower="$(basename "$candidate" | tr '[:upper:]' '[:lower:]')"
    if [[ "$name_lower" != *tipi* && "$name_lower" != *ncm* ]]; then
      continue
    fi
    local ts
    ts="$(stat -c %Y "$candidate" 2>/dev/null || echo 0)"
    if (( ts > best_ts )); then
      best_ts=$ts
      best_file="$candidate"
    fi
  done

  if [[ -n "$best_file" ]]; then
    echo "$best_file"
    return 0
  fi

  # fallback: latest compatible file
  for candidate in "${files[@]}"; do
    [[ -f "$candidate" ]] || continue
    local ts
    ts="$(stat -c %Y "$candidate" 2>/dev/null || echo 0)"
    if (( ts > best_ts )); then
      best_ts=$ts
      best_file="$candidate"
    fi
  done

  if [[ -n "$best_file" ]]; then
    echo "$best_file"
    return 0
  fi
  return 1
}

print_recent_compatible_files() {
  local files=()
  local d
  while IFS= read -r d; do
    [[ -d "$d" ]] || continue
    while IFS= read -r f; do
      files+=("$f")
    done < <(rg --files -g "*.{pdf,xlsx,csv,txt}" "$d" 2>/dev/null || true)
  done < <(discover_download_dirs)

  if [[ ${#files[@]} -eq 0 ]]; then
    return 0
  fi

  printf '%s\n' "${files[@]}" \
    | while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        printf '%s|%s\n' "$(stat -c %Y "$f" 2>/dev/null || echo 0)" "$f"
      done \
    | sort -t'|' -k1,1nr \
    | head -n 10 \
    | cut -d'|' -f2
}

ensure_docker_ready() {
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker não está disponível no PATH."
    echo "Inicie os containers com:"
    echo "docker compose up -d"
    exit 1
  fi

  if ! docker compose ps >/dev/null 2>&1; then
    err "Docker não está disponível. Inicie os containers com:"
    echo "docker compose up -d"
    exit 1
  fi
}

parse_args() {
  while (($#)); do
    case "$1" in
      --help|-h)
        print_help
        exit 0
        ;;
      --importar)
        DO_IMPORT=true
        ;;
      --desativar-ausentes)
        DESATIVAR_AUSENTES=true
        ;;
      --*)
        err "Opção desconhecida: $1"
        print_help
        exit 1
        ;;
      *)
        if [[ -n "$MANUAL_PATH" ]]; then
          err "Informe apenas um caminho de arquivo."
          print_help
          exit 1
        fi
        MANUAL_PATH="$1"
        ;;
    esac
    shift
  done
}

main() {
  parse_args "$@"
  cd "$PROJECT_ROOT"

  local source_file=""
  if [[ -n "$MANUAL_PATH" ]]; then
    source_file="$(expand_path "$MANUAL_PATH")"
    if ! has_supported_ext "$source_file"; then
      err "Arquivo inválido ou extensão não suportada: $source_file"
      echo "Extensões aceitas: .pdf, .xlsx, .csv, .txt"
      exit 1
    fi
  else
    source_file="$(pick_latest_candidate || true)"
    if [[ -z "$source_file" ]]; then
      echo "Nenhum arquivo TIPI/NCM encontrado em Downloads."
      echo "Informe o caminho manual:"
      echo "./scripts/importar_tipi_downloads.sh /caminho/arquivo.xlsx"
      echo ""
      echo "Arquivos compatíveis recentes encontrados:"
      print_recent_compatible_files || true
      exit 1
    fi
  fi

  mkdir -p "$TARGET_DIR_HOST"

  local filename
  filename="$(basename "$source_file")"
  local target_file_host="$TARGET_DIR_HOST/$filename"
  local target_file_container="$TARGET_DIR_CONTAINER/$filename"
  cp "$source_file" "$target_file_host"

  ensure_docker_ready

  local args=(python manage.py importar_ncms "$target_file_container" --fonte TIPI)
  local ext="${filename##*.}"
  ext="${ext,,}"

  if [[ "$DO_IMPORT" == false ]]; then
    args+=(--dry-run)
  else
    if [[ "$ext" == "pdf" ]]; then
      args+=(--confirmar-pdf)
    fi
  fi

  if [[ "$DESATIVAR_AUSENTES" == true ]]; then
    args+=(--desativar-ausentes)
  fi

  local command_str
  command_str="docker compose exec backend ${args[*]}"

  echo "Arquivo localizado:"
  echo "$source_file"
  echo ""
  echo "Copiando para:"
  echo "${target_file_host#$PROJECT_ROOT/}"
  echo ""
  if [[ "$DO_IMPORT" == false ]]; then
    echo "Executando prévia:"
  else
    echo "Executando importação real:"
  fi
  echo "$command_str"
  echo ""

  docker compose exec backend "${args[@]}"
}

main "$@"
