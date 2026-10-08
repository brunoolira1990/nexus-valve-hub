#!/usr/bin/env python3
"""Definitivo: esconde botao 'Carregar NF-e' em CQ existente + preserva componentes."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
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

# 1. Esconde o botao quando CQ existente JA tem itens carregados
src = replace_once(
    src,
    "          <div className=\"flex items-end md:col-span-3\">\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline w-full md:w-auto\"\n"
    "              onClick={() => void carregarPorNFe()}\n"
    "              disabled={\n"
    "                carregandoNfe ||\n"
    "                nfeBloqueada ||\n"
    "                (!form.nota_fiscal && !form.nota_fiscal_historica)\n"
    "              }\n"
    "            >\n"
    "              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}\n"
    "            </button>\n"
    "          </div>\n",
    "          {!(editing?.id && form.itens.length > 0) ? (\n"
    "          <div className=\"flex items-end md:col-span-3\">\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline w-full md:w-auto\"\n"
    "              onClick={() => void carregarPorNFe()}\n"
    "              disabled={\n"
    "                carregandoNfe ||\n"
    "                nfeBloqueada ||\n"
    "                (!form.nota_fiscal && !form.nota_fiscal_historica)\n"
    "              }\n"
    "            >\n"
    "              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}\n"
    "            </button>\n"
    "          </div>\n"
    "          ) : null}\n",
    "esconde-botao",
)

# 2. Preserva componentes do form quando backend nao manda
src = replace_once(
    src,
    "        itens: ((data.itens as ItemCertificadoQualidade[]) ?? []).map((it) => ({\n"
    "          ...it,\n"
    "          tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',\n"
    "          incluir_no_certificado: it.incluir_no_certificado !== false,\n"
    "          motivo_nao_inclusao: it.motivo_nao_inclusao || '',\n"
    "          observacao_nao_inclusao: it.observacao_nao_inclusao || '',\n"
    "          composicao_json: ensureMap(it.composicao_json),\n"
    "          ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),\n"
    "          ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),\n"
    "          componentes: (it.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),\n"
    "        })),\n",
    "        itens: ((data.itens as ItemCertificadoQualidade[]) ?? []).map((it, i) => {\n"
    "          const doBackend = (it.componentes || []).map((cp, j) => ensureComp(cp, j + 1));\n"
    "          const doForm = p.itens?.[i]?.componentes || [];\n"
    "          return {\n"
    "            ...it,\n"
    "            tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',\n"
    "            incluir_no_certificado: it.incluir_no_certificado !== false,\n"
    "            motivo_nao_inclusao: it.motivo_nao_inclusao || '',\n"
    "            observacao_nao_inclusao: it.observacao_nao_inclusao || '',\n"
    "            composicao_json: ensureMap(it.composicao_json),\n"
    "            ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),\n"
    "            ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),\n"
    "            componentes: doBackend.length > 0 ? doBackend : doForm,\n"
    "          };\n"
    "        }),\n",
    "preserva-comp",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} lines)")
