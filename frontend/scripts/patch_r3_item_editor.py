#!/usr/bin/env python3
"""Rodada 3 (A) — botao 'Puxar componentes do CF vinculado', remove 'Adicionar componentes padrao'."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/ItemEditor.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src

def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 1. ComponentesProps: remove onAddPadrao, adiciona onPuxarComponentesDoCfVinculado + puxandoComponentes
src = replace_once(
    src,
    "  lista: ItemCertificadoQualidadeComponente[];\n"
    "  onAdd: (nome?: string) => void;\n"
    "  onAddPadrao: () => void;\n",
    "  lista: ItemCertificadoQualidadeComponente[];\n"
    "  onAdd: (nome?: string) => void;\n"
    "  onPuxarComponentesDoCfVinculado: () => void;\n"
    "  puxandoComponentes?: boolean;\n",
    "props-r3",
)

# 2. bloco de botoes: remove "Adicionar componentes padrao", adiciona "Puxar componentes do CF vinculado"
src = replace_once(
    src,
    "              <p className=\"text-xs font-semibold\">Componentes da valvula</p>\n"
    "              <div className=\"flex gap-2\">\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-outline erp-btn-sm\"\n"
    "                  disabled={disabled}\n"
    "                  onClick={componentes.onAddPadrao}\n"
    "                >\n"
    "                  Adicionar componentes padrao\n"
    "                </button>\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-outline erp-btn-sm\"\n"
    "                  disabled={disabled}\n"
    "                  onClick={() => componentes.onAdd()}\n"
    "                >\n"
    "                  Adicionar componente\n"
    "                </button>\n"
    "              </div>\n",
    "              <p className=\"text-xs font-semibold\">Componentes da valvula</p>\n"
    "              <div className=\"flex flex-wrap gap-2\">\n"
    "                {it.certificado_fornecedor_origem_id &&\n"
    "                it.item_certificado_fornecedor_origem_id ? (\n"
    "                  <button\n"
    "                    type=\"button\"\n"
    "                    className=\"erp-btn-outline erp-btn-sm\"\n"
    "                    disabled={disabled || componentes.puxandoComponentes}\n"
    "                    title=\"Cria e preenche os componentes deste item com os dados do Certificado de Fornecedor vinculado.\"\n"
    "                    onClick={componentes.onPuxarComponentesDoCfVinculado}\n"
    "                  >\n"
    "                    {componentes.puxandoComponentes\n"
    "                      ? 'Puxando...'\n"
    "                      : 'Puxar componentes do CF vinculado'}\n"
    "                  </button>\n"
    "                ) : null}\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-outline erp-btn-sm\"\n"
    "                  disabled={disabled}\n"
    "                  onClick={() => componentes.onAdd()}\n"
    "                >\n"
    "                  Adicionar componente\n"
    "                </button>\n"
    "              </div>\n",
    "botoes-r3",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
