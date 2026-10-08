#!/usr/bin/env python3
"""Fase 1 — lista /certificados navega pro Workspace novo em vez de abrir modal."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/Certificados.tsx")
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

# 1. import useNavigate (se nao existir)
if "from 'react-router-dom'" in src:
    print("  skip: react-router-dom ja importado")
else:
    src = replace_once(
        src,
        "import { useEffect, useMemo, useRef, useState, useCallback } from 'react';\n",
        "import { useEffect, useMemo, useRef, useState, useCallback } from 'react';\n"
        "import { useNavigate } from 'react-router-dom';\n",
        "import-router",
    )

# 2. hook useNavigate (logo apos o inicio da function)
src = replace_once(
    src,
    "const Certificados = () => {\n",
    "const Certificados = () => {\n"
    "  const navigate = useNavigate();\n",
    "hook-navigate",
)

# 3. openNew -> navega
src = replace_once(
    src,
    "  const openNew = () => {\n"
    "    setEditing(null);\n"
    "    setForm(emptyForm());\n"
    "    setNfeOpcaoSelecionada(null);\n"
    "    setSaveError(null);\n"
    "    setRastreabilidadeErros([]);\n"
    "    setMensagens([]);\n"
    "    setFornecedorBuscaItemMsg({});\n"
    "    setModalOpen(true);\n"
    "  };\n",
    "  const openNew = () => {\n"
    "    navigate('/certificados-qualidade/novo');\n"
    "  };\n",
    "openNew-navega",
)

# 4. openEdit -> navega (todo o corpo antigo vira so navigate)
src = replace_once(
    src,
    "  const openEdit = (c: CertificadoQualidade) => {\n"
    "    setEditing(c);\n"
    "    setForm({\n"
    "      ...c,\n"
    "      data_emissao: c.data_emissao || '',\n"
    "      observacoes: c.observacoes || '',\n"
    "      texto_padrao: c.texto_padrao || TEXTO_PADRAO,\n"
    "      pedido_cliente: c.pedido_cliente || '',\n"
    "      cliente_cnpj_snapshot: c.cliente_cnpj_snapshot || '',\n"
    "      itens: (c.itens || []).map((it) => ({\n"
    "        ...it,\n"
    "        tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',\n"
    "        incluir_no_certificado: it.incluir_no_certificado !== false,\n"
    "        motivo_nao_inclusao: it.motivo_nao_inclusao || '',\n"
    "        observacao_nao_inclusao: it.observacao_nao_inclusao || '',\n"
    "        composicao_json: ensureMap(it.composicao_json),\n"
    "        ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),\n"
    "        ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),\n"
    "        componentes: (it.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),\n"
    "      })),\n"
    "    });\n"
    "    setNfeOpcaoSelecionada(null);\n"
    "    if (c.nota_fiscal) {\n"
    "      void certificadosQualidadeService.obterNfeOpcao(c.nota_fiscal).then((opt) => {\n"
    "        if (opt) setNfeOpcaoSelecionada(opt);\n"
    "        else {\n"
    "          setNfeOpcaoSelecionada({\n"
    "            id: c.nota_fiscal!,\n"
    "            label_principal: c.nota_fiscal_numero\n"
    "              ? `NF-e ${c.nota_fiscal_numero}`\n"
    "              : `NF-e vinculada #${c.nota_fiscal}`,\n"
    "            label_secundario: 'Documento legado — verifique elegibilidade',\n"
    "            ambiente_badge: null,\n"
    "            numero_nfe: '',\n"
    "            serie_nfe: '',\n"
    "            cliente_nome: c.cliente_nome_snapshot || '',\n"
    "            data_emissao: c.data_emissao || null,\n"
    "            status_emissao_sefaz: '',\n"
    "            elegivel: false,\n"
    "          });\n"
    "        }\n"
    "      });\n"
    "    }\n"
    "    setSaveError(null);\n"
    "    setRastreabilidadeErros([]);\n"
    "    setMensagens([]);\n"
    "    setFornecedorBuscaItemMsg({});\n"
    "    setModalOpen(true);\n"
    "  };\n",
    "  const openEdit = (c: CertificadoQualidade) => {\n"
    "    navigate(`/certificados-qualidade/${c.id}`);\n"
    "  };\n",
    "openEdit-navega",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
