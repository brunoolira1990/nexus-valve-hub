#!/usr/bin/env python3
"""3b-Frontend (A): tipo substituido + service reemitir + badge."""
import shutil, sys, pathlib, datetime

def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# --- 1. types/index.ts ---
T = pathlib.Path("src/types/index.ts")
s = T.read_text(encoding="utf-8")
s = replace_once(
    s,
    "export type CertificadoQualidadeStatus = 'rascunho' | 'emitido' | 'cancelado';",
    "export type CertificadoQualidadeStatus =\n"
    "  | 'rascunho'\n"
    "  | 'emitido'\n"
    "  | 'cancelado'\n"
    "  | 'substituido';",
    "types-status",
)
shutil.copyfile(T, T.with_suffix(f".ts.bak_{stamp}"))
T.write_text(s, encoding="utf-8")
print(f"  escrito: {T}")

# --- 2. services/api/qualidade.ts ---
S = pathlib.Path("src/services/api/qualidade.ts")
s = S.read_text(encoding="utf-8")
s = replace_once(
    s,
    "  obterPdfBlob: async (id: number, preview = false) => getPdfBlob(id, preview),\n",
    "  obterPdfBlob: async (id: number, preview = false) => getPdfBlob(id, preview),\n"
    "  reemitir: async (id: number) =>\n"
    "    (await api.post<CertificadoQualidade>(`${base}${id}/reemitir/`)).data,\n",
    "service-reemitir",
)
shutil.copyfile(S, S.with_suffix(f".ts.bak_{stamp}"))
S.write_text(s, encoding="utf-8")
print(f"  escrito: {S}")

# --- 3. lib/certificadoStatusUi.ts ---
U = pathlib.Path("src/lib/certificadoStatusUi.ts")
s = U.read_text(encoding="utf-8")
s = replace_once(
    s,
    "  if (s === 'cancelado') return { label: 'Cancelado', className: 'erp-badge-danger' };\n",
    "  if (s === 'cancelado') return { label: 'Cancelado', className: 'erp-badge-danger' };\n"
    "  if (s === 'substituido')\n"
    "    return { label: 'Substituído', className: 'erp-badge-info' };\n",
    "badge-substituido",
)
shutil.copyfile(U, U.with_suffix(f".ts.bak_{stamp}"))
U.write_text(s, encoding="utf-8")
print(f"  escrito: {U}")

print("\nOK. Rode: npx tsc --noEmit")
