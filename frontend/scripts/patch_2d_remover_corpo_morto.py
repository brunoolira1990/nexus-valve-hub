#!/usr/bin/env python3
"""Fase 2d — remove todos os handlers/states/helpers mortos do Certificados.tsx."""
import shutil, sys, pathlib, datetime, re

TARGET = pathlib.Path("src/pages/Certificados.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

# Nomes mortos (extraidos da analise; fetchCertificadosPage EXCLUIDO porque e vivo)
DEAD = {
    # states
    'nfHistoricas', 'nfeOpcaoSelecionada', 'modalOpen', 'editing', 'form',
    'saveError', 'rastreabilidadeErros', 'mensagens', 'pasteCompIdx', 'pasteCompText',
    'fornecedorMatchModalOpen', 'fornecedorMatches', 'fornecedorTargetIdx',
    'fornecedorBuscaAvancadaOpen', 'fornecedorBuscaItemLoading', 'fornecedorBuscaItemMsg',
    'produtoBusca', 'produtoResultados', 'corridasDisponiveisPorItem', 'dividindoCorridas',
    'corridasCfModal', 'fornecedorFiltro',
    # helpers / hooks internos
    'formRef', 'adicionarMensagensUnicas', 'componentePreenchido',
    'totalItens', 'incluidosCount', 'naoIncluidosCount',
    'resumoRastreabilidade', 'itensComAvisoCfManual', 'itensComOrigemVinculadaIncompleta',
    'origemFisicaResumo', 'temAvisoRastreabilidadeFisica', 'extrairErrosRastreabilidade',
    'buscaNfesElegiveis', 'itensComDadosTecnicos', 'selecionarNfeOperacional',
    'modalPdfBusy', 'labelSalvarQualidadeSemEmitir', 'titleSalvarQualidadeSemEmitir',
    'resolvePayloadStatus', 'closeCertModal', 'patchFornecedorBuscaItemMsg',
    'setF', 'hydrateFromSaved', 'numeroArquivoAtual', 'carregarPorNFe', 'salvar',
    'abrirPreviaModal', 'visualizarPreviaPdf', 'updateItem', 'buscarProdutosParaItem',
    'vincularProdutoAoItem', 'carregarCorridasDoItem', 'construirItemIrmaoDeCorrida',
    'aplicarCorridaDisponivel', 'addLinhaCorrida', 'removeLinhaCorrida', 'updateLinhaCorrida',
    'aplicarDistribuicaoCorridas', 'abrirModalCorridasCf', 'aplicarCorridasCfSelecionadas',
    'updateJsonField', 'copyTecnicoFromPrevious', 'clearTecnico', 'clearComposicao',
    'clearTracao', 'duplicateComposicaoToAll', 'duplicateTracaoToAll', 'applyCompositionBlock',
    'updateCompField', 'addComponente', 'removeComponente', 'duplicarComponente',
    'copiarComponenteAnterior', 'adicionarComponentesPadrao', 'aplicarDadosFornecedor',
    'buscarDadosFornecedor', 'buscarDadosFornecedorAvancado',
}

src = TARGET.read_text(encoding="utf-8")
orig = src
lines = src.split("\n")
return_idx = next(i for i, l in enumerate(lines) if l.strip() == 'return (')

# Encontra blocos (mesmo algoritmo da analise)
blocks = []  # (name, start, end)
i = 0
while i < return_idx:
    line = lines[i]
    m = re.match(r'^  const\s+(\w+|\[\s*\w+\s*,\s*\w+\s*\])', line)
    if m:
        raw = m.group(1)
        name_m = re.search(r'\w+', raw)
        name = name_m.group(0) if name_m else raw
        j = i + 1
        depth = line.count('{') - line.count('}') + line.count('(') - line.count(')') + line.count('[') - line.count(']')
        while j < return_idx:
            nl = lines[j]
            if re.match(r'^  (const|return|useEffect|useMemo|function)\b', nl) and depth <= 0:
                break
            depth += nl.count('{') - nl.count('}') + nl.count('(') - nl.count(')') + nl.count('[') - nl.count(']')
            j += 1
        blocks.append((name, i, j - 1))
        i = j
    else:
        i += 1

# Filtra mortos
to_remove = [b for b in blocks if b[0] in DEAD]
print(f"  removendo {len(to_remove)} blocos")
total_linhas = sum(e - s + 1 for _, s, e in to_remove)
print(f"  ~{total_linhas} linhas")

# Remove de tras pra frente
for name, s, e in sorted(to_remove, key=lambda x: -x[1]):
    del lines[s:e+1]

src = "\n".join(lines)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
