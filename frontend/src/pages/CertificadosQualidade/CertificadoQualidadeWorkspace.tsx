/**
 * Workspace do Certificado de Qualidade (CQ).
 *
 * Fase 3a-Frontend — etapa 3a: cabecalho funcional.
 * Proximas etapas vao portar (do antigo Certificados.tsx):
 *  - Etapa 3b: busca de NF-e elegivel (AsyncAutocomplete)
 *  - Etapa 3c: prontidao tecnica + origem documental + avisos
 *  - Etapa 4:  tabela de itens
 *  - Etapa 5:  editor de item (componentes, composicao, ensaios)
 *  - Etapa 6:  modal de corridas CF
 *  - Etapa 7:  rastreabilidade + PDF
 *  - Etapa 8:  ajustar Certificados.tsx para navegar em vez de modal
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ItemEditor, type LinhaDivisaoCorrida } from './ItemEditor';
import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';
import { Modal } from '@/components/Modal';
import { produtosService } from '@/services/api/produtos';
import {
  certificadosFornecedorService,
  corridaLoteEfetivosResultadoFornecedor,
  mensagemPrincipalBuscaDadosTecnicosFornecedor,
} from '@/services/api/certificadosFornecedor';
import {
  COMPONENTES_PADRAO,
  ensureComp,
  ensureMap,
  fornecedorResultadoSemProdutoVinculado,
  resolverCorridaLoteBuscaFornecedor,
} from '@/lib/certificadoQualidadeConstants';
import {
  aplicacaoSubstituiTecnicosDoItemAtual,
  aplicarDistribuicaoCorridasCfCq,
  baseItemIrmao,
  quantidadeTotalDistribuicaoCorridasCfCq,
  selecoesExistentesCorridasCfCq,
  type CorridasCfParaCqResponse,
  type SelecaoCorridaCfCq,
} from '@/lib/cqCorridasCfUi';
import { mesclarMensagensUnicas } from '@/lib/cqMensagensUi';
import { coerceProdutoItemId } from '@/lib/certificadoQualidadeConstants';
import {
  origemFisicaCqBadge,
  origemFisicaCqDescricao,
  origemFisicaCqResumo,
} from '@/lib/certificadoStatusUi';
import {
  certificadosQualidadeService,
  type NfeElegivelCqOpcao,
} from '@/services/api/qualidade';
import {
  nfeHistoricaImportadaService,
  type NFeSaidaHistoricaList,
} from '@/services/api/nfeHistoricaImportada';
import { apiErrorMessage, getApiErrorStatus } from '@/services/api/config';
import {
  emptyForm,
  ensureComp,
  ensureMap,
  LABEL_OBRIGATORIO_EMITIR,
} from '@/lib/certificadoQualidadeConstants';
import type {
  CertificadoQualidade,
  CertificadoQualidadeStatus,
  CorridaDisponivelCertificadoQualidade,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoQualidade,
  ItemCertificadoQualidadeComponente,
  Produto,
  ResumoRastreabilidadeCertificadoQualidade,
} from '@/types';

type Props = {
  certificadoId: number | null;
  onSaved: () => void;
  onCancel: () => void;
};

type FormState = Omit<
  CertificadoQualidade,
  'id' | 'criado_em' | 'atualizado_em' | 'numero_formatado'
>;

export function CertificadoQualidadeWorkspace({ certificadoId, onSaved, onCancel }: Props) {
  const [editing, setEditing] = useState<CertificadoQualidade | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [nfeOpcaoSelecionada, setNfeOpcaoSelecionada] = useState<NfeElegivelCqOpcao | null>(null);
  const [mensagens, setMensagens] = useState<string[]>([]);
  const [carregandoNfe, setCarregandoNfe] = useState(false);
  const [nfHistoricas, setNfHistoricas] = useState<NFeSaidaHistoricaList[]>([]);
  const [abaAtiva, setAbaAtiva] = useState('dados');
  const [produtoBusca, setProdutoBusca] = useState<Record<number, string>>({});
  const [produtoResultados, setProdutoResultados] = useState<Record<number, Produto[]>>({});
  const [corridasDisponiveisPorItem, setCorridasDisponiveisPorItem] = useState<
    Record<number, CorridaDisponivelCertificadoQualidade[]>
  >({});
  const [dividindoCorridas, setDividindoCorridas] = useState<
    Record<number, LinhaDivisaoCorrida[]>
  >({});
  const [corridasCfModal, setCorridasCfModal] = useState<{
    itemIdx: number;
    dados: CorridasCfParaCqResponse | null;
    carregando: boolean;
    erro: string | null;
    quantidadeTotal: number;
    selecoesIniciais: SelecaoCorridaCfCq[];
  } | null>(null);
  const [fornecedorMatches, setFornecedorMatches] = useState<
    DadosTecnicosFornecedorResultado[]
  >([]);
  const [fornecedorTargetIdx, setFornecedorTargetIdx] = useState<number | null>(null);
  const [fornecedorMatchModalOpen, setFornecedorMatchModalOpen] = useState(false);
  const [fornecedorBuscaItemLoading, setFornecedorBuscaItemLoading] = useState<number | null>(
    null,
  );
  const [fornecedorBuscaItemMsg, setFornecedorBuscaItemMsg] = useState<
    Record<number, { type: 'error' | 'info'; text: string }>
  >({});
  const [fornecedorTargetCompIdx, setFornecedorTargetCompIdx] = useState<number | null>(
    null,
  );
  const [fornecedorBuscaCompLoading, setFornecedorBuscaCompLoading] = useState<
    number | null
  >(null);
  const [fornecedorBuscaCompMsg, setFornecedorBuscaCompMsg] = useState<
    Record<string, { type: 'error' | 'info'; text: string }>
  >({});
  const [puxandoComponentes, setPuxandoComponentes] = useState<number | null>(null);

  // Carrega CQ existente (ou reseta para novo)
  useEffect(() => {
    if (!certificadoId) {
      setEditing(null);
      setForm(emptyForm());
      setSaveError(null);
      setNfeOpcaoSelecionada(null);
      setMensagens([]);
      return;
    }
    setLoading(true);
    certificadosQualidadeService
      .getById(certificadoId)
      .then((row) => {
        setEditing(row);
        setForm({
          numero: row.numero || '',
          serie: row.serie || '',
          cliente: row.cliente ?? null,
          cliente_nome_snapshot: row.cliente_nome_snapshot || '',
          cliente_cnpj_snapshot: row.cliente_cnpj_snapshot || '',
          pedido_cliente: row.pedido_cliente || '',
          nota_fiscal_numero: row.nota_fiscal_numero || '',
          nota_fiscal: row.nota_fiscal ?? null,
          nota_fiscal_historica: row.nota_fiscal_historica ?? null,
          data_emissao: row.data_emissao || '',
          observacoes: row.observacoes || '',
          texto_padrao: row.texto_padrao || '',
          status: row.status || 'rascunho',
          tipo_certificado: row.tipo_certificado || 'PADRAO_POR_NFE',
          itens: row.itens || [],
        });
        setSaveError(null);
        setNfeOpcaoSelecionada(null);
        if (row.nota_fiscal) {
          void certificadosQualidadeService.obterNfeOpcao(row.nota_fiscal).then((opt) => {
            if (opt) setNfeOpcaoSelecionada(opt);
            else {
              setNfeOpcaoSelecionada({
                id: row.nota_fiscal!,
                label_principal: row.nota_fiscal_numero
                  ? `NF-e ${row.nota_fiscal_numero}`
                  : `NF-e vinculada #${row.nota_fiscal}`,
                label_secundario: 'Documento legado — verifique elegibilidade',
                ambiente_badge: null,
                numero_nfe: '',
                serie_nfe: '',
                cliente_nome: row.cliente_nome_snapshot || '',
                data_emissao: row.data_emissao || null,
                status_emissao_sefaz: '',
                elegivel: false,
              });
            }
          });
        }
      })
      .catch((e) => setSaveError(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [certificadoId]);

  // Carrega NF-e de saida historicas (uma vez no mount)
  useEffect(() => {
    nfeHistoricaImportadaService
      .list()
      .then((r) => setNfHistoricas(r))
      .catch(() => setNfHistoricas([]));
  }, []);

  const setF = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const buscaNfesElegiveis = useCallback(
    (term: string, limit?: number) =>
      certificadosQualidadeService.buscarNfesElegiveis(term, limit ?? 20),
    [],
  );

  const selecionarNfe = useCallback(
    (id: number | string | null, option?: NfeElegivelCqOpcao | null) => {
      const nextId = id == null || id === '' ? null : Number(id);
      const trocando = nextId !== form.nota_fiscal;
      if (option && !option.elegivel && trocando) return;
      const temItens = (form.itens?.length ?? 0) > 0;
      if (trocando && temItens) {
        const ok = window.confirm(
          'Trocar a NF-e limpara os itens e dados tecnicos ja carregados desta nota. Continuar?',
        );
        if (!ok) return;
      }
      setNfeOpcaoSelecionada(option ?? null);
      setForm((p) => ({
        ...p,
        nota_fiscal: nextId,
        nota_fiscal_historica: null,
        nota_fiscal_numero:
          option && option.numero_nfe
            ? `${option.numero_nfe}${option.serie_nfe ? `/${option.serie_nfe}` : ''}`
            : nextId
              ? p.nota_fiscal_numero
              : '',
        ...(trocando
          ? {
              itens: [],
              cliente: null,
              cliente_nome_snapshot: '',
              cliente_cnpj_snapshot: '',
              pedido_cliente: '',
              data_emissao: '',
            }
          : {}),
      }));
      setMensagens([]);
    },
    [form.nota_fiscal, form.itens],
  );

  const carregarPorNFe = async () => {
    setSaveError(null);
    setMensagens([]);
    setCarregandoNfe(true);
    try {
      const data = await certificadosQualidadeService.preencherPorNfe({
        nf_saida_id: form.nota_fiscal || undefined,
        nf_saida_historica_id: form.nota_fiscal_historica || undefined,
      });
      setForm((p) => ({
        ...p,
        cliente: data.cliente ?? p.cliente,
        cliente_nome_snapshot: data.cliente_nome_snapshot ?? p.cliente_nome_snapshot,
        cliente_cnpj_snapshot: data.cliente_cnpj_snapshot ?? p.cliente_cnpj_snapshot,
        pedido_cliente: data.pedido_cliente ?? p.pedido_cliente,
        nota_fiscal_numero: data.nota_fiscal_numero ?? p.nota_fiscal_numero,
        nota_fiscal: data.nota_fiscal ?? p.nota_fiscal,
        nota_fiscal_historica: data.nota_fiscal_historica ?? p.nota_fiscal_historica,
        data_emissao: data.data_emissao ?? p.data_emissao,
        itens: ((data.itens as ItemCertificadoQualidade[]) ?? []).map((it) => ({
          ...it,
          tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',
          incluir_no_certificado: it.incluir_no_certificado !== false,
          motivo_nao_inclusao: it.motivo_nao_inclusao || '',
          observacao_nao_inclusao: it.observacao_nao_inclusao || '',
          composicao_json: ensureMap(it.composicao_json),
          ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),
          ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),
          componentes: (it.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),
        })),
      }));
      if (data.nota_fiscal) {
        void certificadosQualidadeService.obterNfeOpcao(data.nota_fiscal).then((opt) => {
          if (opt) setNfeOpcaoSelecionada(opt);
        });
      }
      setMensagens(data.mensagens || []);
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    } finally {
      setCarregandoNfe(false);
    }
  };

  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');
  const incluidosCount = form.itens.filter((it) => it.incluir_no_certificado !== false).length;
  const naoIncluidosCount = form.itens.length - incluidosCount;

  const resumoRastreabilidade = useMemo(
    (): ResumoRastreabilidadeCertificadoQualidade | null => {
      if (form.resumo_rastreabilidade) return form.resumo_rastreabilidade;
      const incl = form.itens.filter((it) => it.incluir_no_certificado !== false);
      if (!incl.some((it) => it.rastreabilidade_status)) return null;
      let completos = 0;
      let parciais = 0;
      let pendentes = 0;
      incl.forEach((it) => {
        if (it.rastreabilidade_status === 'COMPLETA') completos += 1;
        else if (it.rastreabilidade_status === 'PARCIAL') parciais += 1;
        else pendentes += 1;
      });
      return {
        completos,
        parciais,
        pendentes,
        pode_emitir: incl.length > 0 && parciais === 0 && pendentes === 0,
      };
    },
    [form.resumo_rastreabilidade, form.itens],
  );

  const origemFisicaResumo = useMemo(
    () => origemFisicaCqResumo(form.itens),
    [form.itens],
  );

  const temAvisoRastreabilidadeFisica = useMemo(
    () =>
      form.itens.some(
        (it) =>
          it.incluir_no_certificado !== false &&
          (it.rastreabilidade_motivos?.includes('SEM_CORRIDA_LOTE') ||
            it.rastreabilidade_motivos?.includes('ESTOQUE_NAO_APLICADO') ||
            it.rastreabilidade_motivos?.includes('SEM_CONFERENCIA_ORIGEM') ||
            it.rastreabilidade_motivos?.includes('RASTREABILIDADE_FISICA_OPCIONAL') ||
            it.rastreabilidade_avisos?.some((a) => a.includes('nao impede a emissao')) ||
            (!it.tem_corrida_lote &&
              !it.corrida &&
              !it.lote &&
              (it.rastreabilidade_status != null || form.itens.length > 0))),
      ),
    [form.itens],
  );

  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>
    setForm((p) => ({
      ...p,
      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    }));

  const adicionarMensagensUnicas = (novas: string | string[]) =>
    setMensagens((m) => mesclarMensagensUnicas(m, novas));

  const buscarProdutosParaItem = async (idx: number, termo: string) => {
    setProdutoBusca((p) => ({ ...p, [idx]: termo }));
    const query = termo.trim();
    if (query.length < 2) {
      setProdutoResultados((p) => ({ ...p, [idx]: [] }));
      return;
    }
    try {
      const encontrados = await produtosService.search(query, 20);
      setProdutoResultados((p) => ({ ...p, [idx]: encontrados }));
    } catch {
      setProdutoResultados((p) => ({ ...p, [idx]: [] }));
    }
  };

  const vincularProdutoAoItem = async (idx: number, produto: Produto) => {
    updateItem(idx, {
      produto: produto.id,
      produto_codigo: produto.codigo_completo,
      produto_descricao: produto.descricao,
      produto_ncm_efetivo: produto.ncm_efetivo?.codigo || produto.ncm || '',
      status_vinculo_produto: 'VINCULADO',
      origem_observacoes: '',
    });
    setProdutoBusca((p) => ({ ...p, [idx]: `${produto.codigo_completo} - ${produto.descricao}` }));
    setProdutoResultados((p) => ({ ...p, [idx]: [] }));
    try {
      const corridas = await certificadosQualidadeService.corridasDisponiveisPorProduto(produto.id);
      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: corridas }));
      if (!corridas.length) {
        adicionarMensagensUnicas('Nenhuma corrida/lote disponivel para este produto.');
      }
    } catch {
      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: [] }));
    }
  };

  const carregarCorridasDoItem = async (idx: number) => {
    const produtoId = coerceProdutoItemId(form.itens[idx]?.produto);
    if (!produtoId) return;
    try {
      const corridas = await certificadosQualidadeService.corridasDisponiveisPorProduto(produtoId);
      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: corridas }));
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    }
  };

  const construirItemIrmaoDeCorrida = (
    idx: number,
    source: CorridaDisponivelCertificadoQualidade,
    quantidade: string,
  ): ItemCertificadoQualidade => {
    const item = form.itens[idx];
    return {
      ...baseItemIrmao(item),
      corrida: source.corrida || item.corrida,
      lote: source.lote || item.lote || '',
      quantidade: parseFloat(quantidade) || 0,
      norma: source.norma || item.norma,
      ncm: source.ncm || item.ncm || '',
      composicao_json: ensureMap(source.composicao_json),
      ensaio_tracao_json: ensureMap(source.ensaio_tracao_json),
      ensaio_impacto_json: ensureMap(source.ensaio_impacto_json),
      certificado_fornecedor_origem_id:
        source.certificado_fornecedor_origem_id ?? source.certificado_fornecedor_id ?? null,
      item_certificado_fornecedor_origem_id:
        source.item_certificado_fornecedor_origem_id ?? source.item_certificado_fornecedor_id ?? null,
      fornecedor_nome_snapshot: source.fornecedor || '',
      nf_entrada_snapshot: source.nf_entrada || '',
      numero_certificado_fornecedor_item_snapshot:
        source.numero_certificado_fornecedor_item || source.certificado_fornecedor || '',
      corrida_snapshot: source.corrida || '',
      lote_snapshot: source.lote || '',
      origem_rastreabilidade_tipo: source.origem || 'manual',
      origem_status_tecnico:
        source.status_origem_tecnica ||
        (source.tem_dados_tecnicos ? 'dados_tecnicos' : 'sem_dados_tecnicos'),
      origem_observacoes: source.observacoes_origem || '',
    };
  };

  const aplicarCorridaDisponivel = (idx: number, valorSelecao: string) => {
    const item = form.itens[idx];
    const source = (corridasDisponiveisPorItem[idx] || []).find(
      (c) =>
        (c.valor_selecao && c.valor_selecao === valorSelecao) ||
        `${c.corrida}||${c.lote || ''}` === valorSelecao,
    );
    if (!source) return;
    if (source.status_certificado_fornecedor === 'rascunho') {
      const ok = window.confirm(
        'Dados tecnicos encontrados em certificado fornecedor em rascunho. Use com confirmacao ou registre o certificado fornecedor antes de emitir. Deseja aplicar estes dados?',
      );
      if (!ok) return;
    }
    const alertas = [...(source.alertas || [])];
    const existeDivergenciaNcm = Boolean(item.ncm && source.ncm && item.ncm !== source.ncm);
    if (existeDivergenciaNcm) {
      alertas.push(
        'A corrida foi encontrada, mas ha divergencia entre descricao/NCM/norma da origem e do item de saida. Confira antes de aplicar.',
      );
    }
    const quantidadeItem = item.quantidade || 0;
    updateItem(idx, construirItemIrmaoDeCorrida(idx, source, String(quantidadeItem)));
    if (alertas.length) {
      adicionarMensagensUnicas(alertas);
    }
  };

  const addLinhaCorrida = (idx: number) =>
    setDividindoCorridas((prev) => ({
      ...prev,
      [idx]: [
        ...(prev[idx] || []),
        { corrida: '', lote: '', quantidade: '', valorSelecao: '' },
      ],
    }));

  const removeLinhaCorrida = (idx: number, linhaIdx: number) =>
    setDividindoCorridas((prev) => {
      const linhas = prev[idx] || [];
      const next = [...linhas];
      next.splice(linhaIdx, 1);
      const out: Record<number, LinhaDivisaoCorrida[]> = { ...prev };
      if (next.length > 0) out[idx] = next;
      else delete out[idx];
      return out;
    });

  const updateLinhaCorrida = (
    idx: number,
    linhaIdx: number,
    patch: Partial<LinhaDivisaoCorrida>,
  ) =>
    setDividindoCorridas((prev) => {
      const linhas = prev[idx] || [];
      const next = [...linhas];
      next[linhaIdx] = { ...next[linhaIdx], ...patch };
      return { ...prev, [idx]: next };
    });

  const hasCorridaDuplicada = (idx: number): boolean => {
    const linhas = dividindoCorridas[idx] || [];
    const chaves = new Set<string>();
    for (const l of linhas) {
      const chave = (l.valorSelecao || '').trim().toUpperCase();
      if (!chave) continue;
      if (chaves.has(chave)) return true;
      chaves.add(chave);
    }
    return false;
  };

  const aplicarDistribuicaoCorridas = (idx: number) => {
    const linhas = dividindoCorridas[idx] || [];
    if (!linhas.length) return;

    const linhasInvalidas = linhas.some(
      (l) => !l.valorSelecao || !l.quantidade || parseFloat(l.quantidade) <= 0,
    );
    if (linhasInvalidas) {
      adicionarMensagensUnicas(['Informe corrida e quantidade > 0 para todas as linhas.']);
      return;
    }

    const quantidadeOriginal = form.itens[idx].quantidade || 0;
    const somaTotal = linhas.reduce((sum, l) => sum + parseFloat(l.quantidade), 0);
    if (Math.abs(somaTotal - quantidadeOriginal) > 0.001) {
      adicionarMensagensUnicas([
        `A soma das quantidades (${somaTotal}) deve ser igual a quantidade do item original (${quantidadeOriginal}).`,
      ]);
      return;
    }

    const chaves = new Set<string>();
    for (const l of linhas) {
      const chave = (l.valorSelecao || '').trim().toUpperCase();
      if (chaves.has(chave)) {
        adicionarMensagensUnicas(['A mesma corrida nao pode ser adicionada duas vezes.']);
        return;
      }
      chaves.add(chave);
    }

    const novosItens: ItemCertificadoQualidade[] = [];
    for (const l of linhas) {
      const source = (corridasDisponiveisPorItem[idx] || []).find(
        (c) =>
          (c.valor_selecao && c.valor_selecao === l.valorSelecao) ||
          `${c.corrida}||${c.lote || ''}` === l.valorSelecao,
      );
      if (!source) continue;
      const itemIrmao = construirItemIrmaoDeCorrida(idx, source, l.quantidade);
      itemIrmao.corrida = source.corrida || '';
      itemIrmao.lote = source.lote || '';
      itemIrmao.quantidade = parseFloat(l.quantidade);
      novosItens.push(itemIrmao);
    }

    const itemOriginal = form.itens[idx];
    const novosItensOrdenados = novosItens.map((it, i) => ({
      ...it,
      ordem: (itemOriginal.ordem || idx + 1) + i,
    }));

    setForm((p) => {
      const next = [...p.itens];
      next.splice(idx, 1, ...novosItensOrdenados);
      return { ...p, itens: next };
    });

    setDividindoCorridas({});
    setCorridasDisponiveisPorItem({});
    setProdutoBusca({});
    setProdutoResultados({});
  };

  const updateComponente = (
    idx: number,
    compIdx: number,
    patch: Partial<ItemCertificadoQualidadeComponente>,
  ) =>
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      comps[compIdx] = { ...comps[compIdx], ...patch };
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });

  const updateCompJson = (
    idx: number,
    compIdx: number,
    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',
    key: string,
    value: string,
  ) =>
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      const map = ensureMap(comps[compIdx][group]);
      map[key] = value;
      comps[compIdx] = { ...comps[compIdx], [group]: map };
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });

  const addComponente = (idx: number, nome = '') =>
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });

  const removeComponente = (idx: number, compIdx: number) =>
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      comps.splice(compIdx, 1);
      next[idx] = {
        ...next[idx],
        componentes: comps.map((c, i) => ({ ...c, ordem: i + 1 })),
      };
      return { ...p, itens: next };
    });

  const duplicarComponente = (idx: number, compIdx: number) => {
    const srcComp = ensureComp(form.itens[idx].componentes?.[compIdx], 1);
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      comps.push({ ...srcComp, ordem: comps.length + 1 });
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });
  };

  const copiarComponenteAnterior = (idx: number, compIdx: number) => {
    if (compIdx === 0) return;
    const prev = ensureComp(form.itens[idx].componentes?.[compIdx - 1], compIdx);
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      comps[compIdx] = { ...comps[compIdx], ...prev, ordem: comps[compIdx].ordem };
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });
  };

  const adicionarComponentesPadrao = (idx: number) =>
    setForm((p) => {
      const next = [...p.itens];
      const comps = [...(next[idx].componentes || [])];
      COMPONENTES_PADRAO.forEach((nome) => {
        comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));
      });
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });

  const abrirModalCorridasCf = async (idx: number) => {
    const item = form.itens[idx];
    const cfId = item.certificado_fornecedor_origem_id;
    const itemCfId = item.item_certificado_fornecedor_origem_id;
    if (!cfId || !itemCfId) {
      setSaveError(
        'Vincule este item a um Certificado de Fornecedor e ao item exato do CF (via corrida disponivel ou busca de dados do fornecedor) antes de adicionar corridas.',
      );
      return;
    }
    setSaveError(null);
    setCorridasCfModal({
      itemIdx: idx,
      dados: null,
      carregando: true,
      erro: null,
      quantidadeTotal: Number(item.quantidade) || 0,
      selecoesIniciais: [],
    });
    try {
      const dados = await certificadosQualidadeService.corridasCertificadoFornecedor(cfId, itemCfId);
      const itensAtuais = form.itens;
      setCorridasCfModal({
        itemIdx: idx,
        dados,
        carregando: false,
        erro: null,
        quantidadeTotal: quantidadeTotalDistribuicaoCorridasCfCq(
          dados.linhas,
          itensAtuais,
          itensAtuais[idx],
        ),
        selecoesIniciais: selecoesExistentesCorridasCfCq(dados.linhas, itensAtuais),
      });
    } catch (e) {
      const status = getApiErrorStatus(e);
      const detail = (e as AxiosError<{ detail?: string }>)?.response?.data?.detail;
      const erro =
        status === 401 || status === 403
          ? apiErrorMessage(e, {
              fallback:
                'Nao foi possivel carregar as corridas do Certificado de Fornecedor.',
            })
          : typeof detail === 'string' && detail.trim()
            ? detail.trim()
            : apiErrorMessage(e, {
                fallback:
                  'Nao foi possivel carregar as corridas do Certificado de Fornecedor.',
              });
      setCorridasCfModal({
        itemIdx: idx,
        dados: null,
        carregando: false,
        erro,
        quantidadeTotal: Number(item.quantidade) || 0,
        selecoesIniciais: [],
      });
    }
  };

  const aplicarCorridasCfSelecionadas = (selecoes: SelecaoCorridaCfCq[]) => {
    const idx = corridasCfModal?.itemIdx;
    const dados = corridasCfModal?.dados;
    if (idx == null || !dados) return false;
    const itemOriginal = form.itens[idx];
    if (
      aplicacaoSubstituiTecnicosDoItemAtual(itemOriginal, selecoes) &&
      !window.confirm(
        'O item atual ja possui dados tecnicos preenchidos. Aplicar esta distribuicao substituira os dados tecnicos da primeira origem selecionada. Deseja continuar?',
      )
    ) {
      return false;
    }
    setForm((p) => {
      const itens = aplicarDistribuicaoCorridasCfCq(p.itens, idx, dados.linhas, selecoes);
      return { ...p, itens };
    });
    setCorridasCfModal(null);
    adicionarMensagensUnicas(
      [
        `Corridas aplicadas do Certificado de Fornecedor: ${selecoes
          .map(
            (s) =>
              `${s.linha.corrida}${s.linha.lote ? `/${s.linha.lote}` : ''} (${s.quantidade})`,
          )
          .join(', ')}.`,
        dados.mensagem_origem_fisica || '',
      ].filter(Boolean),
    );
    return true;
  };

  const patchFornecedorBuscaItemMsg = (
    idx: number,
    v: { type: 'error' | 'info'; text: string } | null,
  ) =>
    setFornecedorBuscaItemMsg((prev) => {
      const next = { ...prev };
      if (v == null) delete next[idx];
      else next[idx] = v;
      return next;
    });

  const componentePreenchido = (comp: ReturnType<typeof ensureComp>) =>
    Boolean(
      (comp.nome_componente || '').trim() ||
        (comp.corrida || '').trim() ||
        (comp.norma || '').trim() ||
        Object.values(ensureMap(comp.composicao_json)).some(Boolean) ||
        Object.values(ensureMap(comp.ensaio_tracao_json)).some(Boolean),
    );

  const aplicarDadosFornecedor = (idx: number, srcData: DadosTecnicosFornecedorResultado) => {
    if (srcData.status_certificado_fornecedor === 'rascunho') {
      const ok = window.confirm(
        'O certificado fornecedor encontrado ainda esta em rascunho. Registre o certificado antes de usar os dados tecnicos. Deseja aplicar mesmo assim?',
      );
      if (!ok) return;
    }
    if (fornecedorResultadoSemProdutoVinculado(srcData)) {
      const ok = window.confirm(
        'Este dado tecnico veio de um certificado fornecedor cujo item nao esta vinculado a produto cadastrado. Confira codigo, descricao e corrida antes de aplicar. Deseja continuar?',
      );
      if (!ok) return;
    }
    const item = form.itens[idx];
    const isValvula =
      (srcData.tipo_dados_tecnicos || item.tipo_dados_tecnicos) === 'VALVULA_COMPONENTES';
    const { corrida: crEf, lote: loEf } = corridaLoteEfetivosResultadoFornecedor(srcData);
    const novosComponentes = (srcData.componentes || []).map((cp, i) => ({
      ...ensureComp(cp, i + 1),
      numero_certificado_fornecedor_componente_snapshot:
        String(cp.numero_certificado_fornecedor_componente || '') ||
        (srcData.numero_certificado_fornecedor_item ||
          srcData.numero_certificado_fornecedor ||
          ''),
    }));
    if (isValvula) {
      const existentes = (item.componentes || []).map((c, i) => ensureComp(c, i + 1));
      const existePreenchido = existentes.some(componentePreenchido);
      if (existePreenchido && novosComponentes.length) {
        const ok = window.confirm(
          'Este item ja possui componentes preenchidos. Deseja substituir pelos dados do certificado fornecedor?',
        );
        if (!ok) return;
      }
      updateItem(idx, {
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        corrida: crEf || item.corrida,
        lote: loEf || item.lote,
        componentes: novosComponentes,
        certificado_fornecedor_origem_id: srcData.certificado_fornecedor_id || null,
        item_certificado_fornecedor_origem_id: srcData.id || null,
        fornecedor_nome_snapshot: srcData.fornecedor_nome || '',
        nf_entrada_snapshot: srcData.numero_nf_entrada || '',
        codigo_item_fornecedor_snapshot: srcData.codigo_produto || '',
        descricao_item_fornecedor_snapshot: srcData.descricao_material || '',
        numero_certificado_fornecedor_item_snapshot:
          srcData.numero_certificado_fornecedor_item ||
          srcData.numero_certificado_fornecedor ||
          '',
        corrida_snapshot: crEf || item.corrida_snapshot || '',
        lote_snapshot: loEf || item.lote_snapshot || '',
        origem_rastreabilidade_tipo: 'certificado_fornecedor',
        origem_status_tecnico: srcData.status_certificado_fornecedor || '',
      });
    } else {
      updateItem(idx, {
        norma: srcData.norma || item.norma,
        corrida: crEf || item.corrida,
        lote: loEf || item.lote || '',
        composicao_json: ensureMap(srcData.composicao_json),
        ensaio_tracao_json: ensureMap(srcData.ensaio_tracao_json),
        ensaio_impacto_json: ensureMap(srcData.ensaio_impacto_json),
        tipo_dados_tecnicos: srcData.tipo_dados_tecnicos || item.tipo_dados_tecnicos,
        certificado_fornecedor_origem_id: srcData.certificado_fornecedor_id || null,
        item_certificado_fornecedor_origem_id: srcData.id || null,
        fornecedor_nome_snapshot: srcData.fornecedor_nome || '',
        nf_entrada_snapshot: srcData.numero_nf_entrada || '',
        codigo_item_fornecedor_snapshot: srcData.codigo_produto || '',
        descricao_item_fornecedor_snapshot: srcData.descricao_material || '',
        numero_certificado_fornecedor_item_snapshot:
          srcData.numero_certificado_fornecedor_item ||
          srcData.numero_certificado_fornecedor ||
          '',
        corrida_snapshot: crEf || item.corrida_snapshot || '',
        lote_snapshot: loEf || item.lote_snapshot || '',
        origem_rastreabilidade_tipo: 'certificado_fornecedor',
        origem_status_tecnico: srcData.status_certificado_fornecedor || '',
      });
    }
    const avisos: string[] = [];
    if (srcData.aviso_divergencia_codigo) avisos.push(srcData.aviso_divergencia_codigo);
    if (fornecedorResultadoSemProdutoVinculado(srcData)) {
      avisos.push(
        'Dados encontrados em certificado fornecedor sem produto vinculado. Confira codigo, descricao e corrida antes de aplicar.',
      );
    } else {
      avisos.push('Dados tecnicos encontrados no certificado fornecedor.');
    }
    if (srcData.status_certificado_fornecedor === 'rascunho') {
      avisos.push(
        'O certificado fornecedor encontrado ainda esta em rascunho. Registre o certificado antes de usar os dados tecnicos.',
      );
    }
    if (
      srcData.aviso_sem_vinculo_produto &&
      !fornecedorResultadoSemProdutoVinculado(srcData)
    ) {
      avisos.push(srcData.aviso_sem_vinculo_produto);
    }
    adicionarMensagensUnicas(avisos);
    patchFornecedorBuscaItemMsg(idx, null);
  };

  const aplicarDadosFornecedorComponente = (
    idx: number,
    compIdx: number,
    srcData: DadosTecnicosFornecedorResultado,
  ) => {
    const item = form.itens[idx];
    const comps = [...(item.componentes || [])];
    if (!comps[compIdx]) return;
    const compAlvo = ensureComp(comps[compIdx], compIdx + 1);
    const corridaAlvo = (compAlvo.corrida || '').trim().toUpperCase();
    const loteAlvo = (compAlvo.lote || '').trim().toUpperCase();
    const listaSrc = srcData.componentes || [];
    const match =
      listaSrc.find((c) => {
        const cCorrida = String(c.corrida || '').trim().toUpperCase();
        const cLote = String(c.lote || '').trim().toUpperCase();
        return cCorrida === corridaAlvo && cLote === loteAlvo;
      }) || listaSrc[0];
    if (!match) {
      setFornecedorBuscaCompMsg((p) => ({
        ...p,
        [`${idx}:${compIdx}`]: {
          type: 'error',
          text: 'Nenhum componente compativel foi retornado pelo CF.',
        },
      }));
      return;
    }
    comps[compIdx] = {
      ...compAlvo,
      corrida: String(match.corrida || compAlvo.corrida || ''),
      lote: String(match.lote || compAlvo.lote || ''),
      norma: String(match.norma || compAlvo.norma || ''),
      descricao_componente:
        String(match.descricao_componente || compAlvo.descricao_componente || ''),
      numero_certificado_fornecedor_componente_snapshot:
        String(match.numero_certificado_fornecedor_componente || '') ||
        srcData.numero_certificado_fornecedor_item ||
        srcData.numero_certificado_fornecedor ||
        '',
      composicao_json: ensureMap(match.composicao_json),
      ensaio_tracao_json: ensureMap(match.ensaio_tracao_json),
      ensaio_impacto_json: ensureMap(match.ensaio_impacto_json),
    };
    setForm((p) => {
      const next = [...p.itens];
      next[idx] = { ...next[idx], componentes: comps };
      return { ...p, itens: next };
    });
    updateItem(idx, {
      certificado_fornecedor_origem_id:
        item.certificado_fornecedor_origem_id || srcData.certificado_fornecedor_id || null,
      item_certificado_fornecedor_origem_id:
        item.item_certificado_fornecedor_origem_id || srcData.id || null,
    });
    adicionarMensagensUnicas([
      `Componente ${compAlvo.nome_componente || compIdx + 1}: dados do CF aplicados.`,
    ]);
    setFornecedorBuscaCompMsg((p) => {
      const next = { ...p };
      delete next[`${idx}:${compIdx}`];
      return next;
    });
  };

  const buscarDadosCorridaComponente = async (idx: number, compIdx: number) => {
    const chave = `${idx}:${compIdx}`;
    setFornecedorBuscaCompMsg((p) => {
      const next = { ...p };
      delete next[chave];
      return next;
    });
    const item = form.itens[idx];
    const comp = ensureComp(item.componentes?.[compIdx], compIdx + 1);
    const corrida = (comp.corrida || '').trim();
    const lote = (comp.lote || '').trim();
    if (!corrida && !lote) {
      setFornecedorBuscaCompMsg((p) => ({
        ...p,
        [chave]: {
          type: 'error',
          text: 'Informe a corrida ou o lote deste componente antes de buscar.',
        },
      }));
      return;
    }
    setFornecedorBuscaCompLoading(compIdx);
    try {
      const { resultados: encontrados, dicas_busca: dicasBusca } =
        await certificadosFornecedorService.buscarDadosTecnicos({
          corrida: corrida || undefined,
          lote: lote || undefined,
          codigo_produto: item.codigo_produto || undefined,
          descricao: comp.nome_componente || item.descricao_material || undefined,
          norma: comp.norma || item.norma || undefined,
          tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
          status: 'registrado',
        });
      if (!encontrados.length) {
        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);
        setFornecedorBuscaCompMsg((p) => ({
          ...p,
          [chave]: {
            type: 'error',
            text:
              dicaMsg ||
              'Nenhum dado tecnico encontrado para esta corrida do componente.',
          },
        }));
        return;
      }
      if (encontrados.length === 1) {
        aplicarDadosFornecedorComponente(idx, compIdx, encontrados[0]);
        return;
      }
      setFornecedorTargetIdx(idx);
      setFornecedorTargetCompIdx(compIdx);
      setFornecedorMatches(encontrados);
      setFornecedorMatchModalOpen(true);
    } catch (e) {
      setFornecedorBuscaCompMsg((p) => ({
        ...p,
        [chave]: {
          type: 'error',
          text: apiErrorMessage(e, {
            fallback: 'Falha ao buscar dados tecnicos da corrida.',
          }),
        },
      }));
    } finally {
      setFornecedorBuscaCompLoading(null);
    }
  };

  const puxarComponentesDoCfVinculado = async (idx: number) => {
    const item = form.itens[idx];
    const cfId = item.certificado_fornecedor_origem_id;
    const itemCfId = item.item_certificado_fornecedor_origem_id;
    if (!cfId || !itemCfId) {
      adicionarMensagensUnicas([
        'Vincule o item a um CF antes de puxar componentes.',
      ]);
      return;
    }
    setPuxandoComponentes(idx);
    try {
      const cf = await certificadosFornecedorService.getById(cfId);
      const itemCf = (cf.itens || []).find((it) => it.id === itemCfId);
      if (!itemCf) {
        adicionarMensagensUnicas([
          'Item vinculado nao foi encontrado no certificado fornecedor.',
        ]);
        return;
      }
      const componentesCf = itemCf.componentes || [];
      if (!componentesCf.length) {
        adicionarMensagensUnicas([
          'O CF vinculado nao possui componentes cadastrados para este item.',
        ]);
        return;
      }
      const existentes = (item.componentes || []).map((c, i) => ensureComp(c, i + 1));
      const existePreenchido = existentes.some((c) =>
        Boolean(
          (c.nome_componente || '').trim() ||
            (c.corrida || '').trim() ||
            Object.values(ensureMap(c.composicao_json)).some(Boolean),
        ),
      );
      if (existePreenchido) {
        const ok = window.confirm(
          'Este item ja possui componentes preenchidos. Deseja substituir pelos componentes do CF vinculado?',
        );
        if (!ok) return;
      }
      const novosComponentes = componentesCf.map((cp, i) => ({
        ...ensureComp(cp, i + 1),
        numero_certificado_fornecedor_componente_snapshot:
          String(cp.numero_certificado_fornecedor_componente || '') ||
          itemCf.numero_certificado_fornecedor_item ||
          cf.numero_certificado_fornecedor ||
          '',
      }));
      updateItem(idx, {
        componentes: novosComponentes,
        fornecedor_nome_snapshot: item.fornecedor_nome_snapshot || cf.fornecedor_nome_snapshot || '',
      });
      adicionarMensagensUnicas([
        `${novosComponentes.length} componente(s) puxado(s) do CF vinculado.`,
      ]);
    } catch (e) {
      adicionarMensagensUnicas([
        apiErrorMessage(e, { fallback: 'Falha ao puxar componentes do CF.' }),
      ]);
    } finally {
      setPuxandoComponentes(null);
    }
  };

  const buscarDadosFornecedor = async (idx: number) => {
    patchFornecedorBuscaItemMsg(idx, null);
    const item = form.itens[idx];
    if (!item) return;

    // Se o item ja tem vinculo com CF/item exatos, puxa direto pelo getById
    // (nao exige corrida — os componentes vem preenchidos pelo vinculo).
    const cfIdVinculado = item.certificado_fornecedor_origem_id;
    const itemCfIdVinculado = item.item_certificado_fornecedor_origem_id;
    if (cfIdVinculado && itemCfIdVinculado) {
      setFornecedorBuscaItemLoading(idx);
      try {
        const cf = await certificadosFornecedorService.getById(cfIdVinculado);
        const itemCf = (cf.itens || []).find((it) => it.id === itemCfIdVinculado);
        if (!itemCf) {
          patchFornecedorBuscaItemMsg(idx, {
            type: 'error',
            text: 'Item vinculado nao foi encontrado no certificado fornecedor.',
          });
          return;
        }
        const resultado: DadosTecnicosFornecedorResultado = {
          id: itemCf.id!,
          certificado_fornecedor_id: cf.id,
          fornecedor: cf.fornecedor ?? null,
          fornecedor_nome: cf.fornecedor_nome_snapshot || '',
          numero_nf_entrada: cf.numero_nf_entrada || '',
          data_nf_entrada: cf.data_nf_entrada ?? undefined,
          numero_certificado_fornecedor: cf.numero_certificado_fornecedor || '',
          numero_certificado_fornecedor_item:
            itemCf.numero_certificado_fornecedor_item || '',
          status_certificado_fornecedor: cf.status,
          produto: itemCf.produto ?? null,
          codigo_produto: itemCf.codigo_produto || '',
          descricao_material: itemCf.descricao_material || '',
          norma: itemCf.norma || '',
          corrida: itemCf.corrida || '',
          lote: itemCf.lote || '',
          tipo_dados_tecnicos:
            (itemCf.tipo_dados_tecnicos as
              | 'PADRAO_ITEM'
              | 'VALVULA_COMPONENTES') || 'PADRAO_ITEM',
          composicao_json: (
            itemCf as unknown as { composicao_json?: Record<string, unknown> }
          ).composicao_json,
          ensaio_tracao_json: (
            itemCf as unknown as { ensaio_tracao_json?: Record<string, unknown> }
          ).ensaio_tracao_json,
          ensaio_impacto_json: (
            itemCf as unknown as { ensaio_impacto_json?: Record<string, unknown> }
          ).ensaio_impacto_json,
          componentes: itemCf.componentes || [],
        };
        aplicarDadosFornecedor(idx, resultado);
      } catch (e) {
        patchFornecedorBuscaItemMsg(idx, {
          type: 'error',
          text: apiErrorMessage(e, {
            fallback: 'Falha ao carregar dados do CF vinculado.',
          }),
        });
      } finally {
        setFornecedorBuscaItemLoading(null);
      }
      return;
    }

    const produtoId = coerceProdutoItemId(item.produto);
    const isValvula =
      (item.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES';
    const { corrida: corridaBusca, lote: loteBusca } = resolverCorridaLoteBuscaFornecedor(item);
    if (!corridaBusca && !loteBusca) {
      patchFornecedorBuscaItemMsg(idx, {
        type: 'error',
        text: 'Informe a corrida ou o lote antes de buscar dados do certificado fornecedor.',
      });
      return;
    }
    setFornecedorBuscaItemLoading(idx);
    try {
      const { resultados: encontrados, dicas_busca: dicasBusca } =
        await certificadosFornecedorService.buscarDadosTecnicos({
          ...(produtoId ? { produto: produtoId } : {}),
          corrida: corridaBusca || undefined,
          lote: loteBusca || undefined,
          codigo_produto: item.codigo_produto || undefined,
          descricao: item.descricao_material || undefined,
          tipo_dados_tecnicos: isValvula ? 'VALVULA_COMPONENTES' : 'PADRAO_ITEM',
          norma: item.norma || undefined,
          status: 'registrado',
        });
      if (!encontrados.length) {
        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);
        const text =
          dicaMsg ||
          'Nenhum certificado fornecedor registrado foi encontrado para esta corrida.';
        patchFornecedorBuscaItemMsg(idx, { type: 'error', text });
        return;
      }
      if (encontrados.length === 1) {
        aplicarDadosFornecedor(idx, encontrados[0]);
        return;
      }
      patchFornecedorBuscaItemMsg(idx, null);
      setFornecedorTargetIdx(idx);
      setFornecedorMatches(encontrados);
      setFornecedorMatchModalOpen(true);
    } catch (e) {
      patchFornecedorBuscaItemMsg(idx, {
        type: 'error',
        text: apiErrorMessage(e, {
          fallback: 'Falha ao buscar dados tecnicos de entrada.',
        }),
      });
    } finally {
      setFornecedorBuscaItemLoading(null);
    }
  };

  const salvar = async (novoStatus?: CertificadoQualidadeStatus) => {
    setSaving(true);
    setSaveError(null);
    try {
      const payload: FormState = {
        ...form,
        status: novoStatus ?? form.status,
      };
      if (editing) {
        const updated = await certificadosQualidadeService.update(editing.id, payload);
        setEditing(updated);
        setForm((prev) => ({ ...prev, status: updated.status }));
      } else {
        const created = await certificadosQualidadeService.create(payload);
        setEditing(created);
        setForm((prev) => ({ ...prev, numero: created.numero || prev.numero }));
      }
      onSaved();
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-muted-foreground">Carregando certificado...</div>
    );
  }

  return (
    <div className="space-y-4">
      {saveError ? (
        <p className="text-sm text-destructive">{saveError}</p>
      ) : null}

      <Tabs value={abaAtiva} onValueChange={setAbaAtiva}>
        <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
          <TabsTrigger value="dados">Dados</TabsTrigger>
          <TabsTrigger value="itens">Itens</TabsTrigger>
          <TabsTrigger value="observacoes">Observações</TabsTrigger>
        </TabsList>

        <TabsContent value="dados" className="mt-0 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="erp-label">Número</label>
          <input
            className="erp-input mt-1 bg-muted/40 read-only:cursor-default"
            readOnly
            value={form.numero || editing?.numero_formatado || ''}
            placeholder="Número gerado automaticamente ao salvar."
          />
          {!editing ? (
            <p className="text-xs text-muted-foreground mt-1">
              Número gerado automaticamente ao salvar.
            </p>
          ) : null}
        </div>
        <div>
          <label className="erp-label">Série</label>
          <input
            className="erp-input mt-1"
            value={form.serie}
            onChange={(e) => setF('serie', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Data{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            type="date"
            className="erp-input mt-1"
            value={form.data_emissao || ''}
            onChange={(e) => setF('data_emissao', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Status</label>
          <select
            className="erp-select mt-1 w-full"
            value={form.status}
            disabled={editing?.status === 'cancelado'}
            onChange={(e) => setF('status', e.target.value as CertificadoQualidadeStatus)}
          >
            <option value="rascunho">Rascunho</option>
            <option value="emitido">Emitido</option>
            <option value="cancelado">Cancelado</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="erp-label">Cliente{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={form.cliente_nome_snapshot}
            onChange={(e) => setF('cliente_nome_snapshot', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">CNPJ Cliente</label>
          <input
            className="erp-input mt-1"
            value={form.cliente_cnpj_snapshot || ''}
            onChange={(e) => setF('cliente_cnpj_snapshot', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Pedido Cliente</label>
          <input
            className="erp-input mt-1"
            value={form.pedido_cliente || ''}
            onChange={(e) => setF('pedido_cliente', e.target.value)}
          />
        </div>
        <div className="md:col-span-4">
          <label className="erp-label">Texto padrão</label>
          <textarea
            className="erp-input mt-1 min-h-[80px]"
            value={form.texto_padrao || ''}
            onChange={(e) => setF('texto_padrao', e.target.value)}
          />
        </div>
      </div>

      <div className="rounded border border-border bg-muted/20 p-3">
        <p className="text-sm font-medium mb-2">NF-e de saída vinculada</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="erp-label">NF-e de saída</label>
            <AsyncAutocomplete<NfeElegivelCqOpcao>
              value={form.nota_fiscal}
              selectedOption={nfeOpcaoSelecionada}
              placeholder="Buscar por número da NF-e ou cliente..."
              emptyMessage="Nenhuma NF-e autorizada encontrada."
              minChars={2}
              limit={20}
              disabled={nfeBloqueada}
              search={buscaNfesElegiveis}
              getOptionValue={(o) => o.id}
              getOptionLabel={(o) => o.label_principal}
              renderOption={(o) => (
                <div className="flex flex-col gap-0.5 py-0.5">
                  <span className="font-medium text-sm">{o.label_principal}</span>
                  <span className="text-xs text-muted-foreground flex flex-wrap items-center gap-1">
                    {o.label_secundario}
                    {o.ambiente_badge ? (
                      <span
                        className={
                          o.ambiente_badge === 'Produção'
                            ? 'erp-badge-success text-[10px]'
                            : 'erp-badge-warning text-[10px]'
                        }
                      >
                        {o.ambiente_badge}
                      </span>
                    ) : null}
                  </span>
                </div>
              )}
              onChange={selecionarNfe}
            />
            {nfeOpcaoSelecionada && !nfeOpcaoSelecionada.elegivel ? (
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                {nfeOpcaoSelecionada.ambiente_badge === 'Homologação'
                  ? 'Esta NF-e vinculada foi autorizada em homologação e não pode ser usada em novo CQ de saída. O registro legado é preservado; selecione uma NF-e autorizada em produção para alterar o vínculo.'
                  : 'Esta NF-e vinculada não está elegível pelas regras atuais (ex.: rascunho, cancelada ou sem autorização fiscal em produção). O registro legado é preservado; selecione uma NF-e autorizada em produção para alterar o vínculo.'}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-1">
                Somente NF-e de saída autorizadas em produção, com número e série fiscais.
              </p>
            )}
          </div>
          <div>
            <label className="erp-label">NF-e saída histórica</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.nota_fiscal_historica || ''}
              disabled={nfeBloqueada}
              onChange={(e) => {
                const histId = e.target.value ? +e.target.value : null;
                setNfeOpcaoSelecionada(null);
                setF('nota_fiscal_historica', histId);
                setF('nota_fiscal', null);
                setMensagens([]);
              }}
            >
              <option value="">Selecione...</option>
              {nfHistoricas.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.numero}/{n.serie} - {n.cliente_nome} - {n.dh_emissao.slice(0, 10)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end md:col-span-3">
            <button
              type="button"
              className="erp-btn-outline w-full md:w-auto"
              onClick={() => void carregarPorNFe()}
              disabled={
                carregandoNfe ||
                nfeBloqueada ||
                (!form.nota_fiscal && !form.nota_fiscal_historica)
              }
            >
              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}
            </button>
          </div>
        </div>

        {mensagens.length > 0 ? (
          <ul className="mt-2 space-y-1">
            {mensagens.map((m, i) => (
              <li key={i} className="text-xs text-muted-foreground">
                {m}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
        </TabsContent>

        <TabsContent value="itens" className="mt-0 space-y-4">
          {form.status !== 'cancelado' ? (
            <div className="rounded border border-border p-3 bg-muted/10">
              <p className="text-sm font-medium mb-2">Prontidão técnica</p>
              {resumoRastreabilidade ? (
                <div className="flex flex-wrap gap-2 text-xs mb-2">
                  <span className="erp-badge-success">
                    Completa: {resumoRastreabilidade.completos}
                  </span>
                  <span className="erp-badge-warning">
                    Parcial: {resumoRastreabilidade.parciais}
                  </span>
                  <span className="erp-badge-danger">
                    Pendente: {resumoRastreabilidade.pendentes}
                  </span>
                  {resumoRastreabilidade.pode_emitir ? (
                    <span className="text-emerald-700 dark:text-emerald-400">
                      Pronto para emissão definitiva
                    </span>
                  ) : (
                    <span className="text-amber-800 dark:text-amber-300">
                      Pendências de produto/descrição ou dados técnicos ainda impedem a emissão definitiva.
                    </span>
                  )}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground mb-2">
                  Salve o certificado para calcular o resumo de rastreabilidade no servidor.
                </p>
              )}
              <p className="text-[11px] text-muted-foreground mb-3">
                A prontidão técnica indica apenas os dados exigidos para emissão do CQ; ela não comprova a origem física do material.
              </p>
              <p className="text-sm font-medium mb-2">Origem documental</p>
              <div className="flex flex-wrap items-center gap-2 text-xs mb-1">
                <span className={origemFisicaCqBadge(origemFisicaResumo).className}>
                  {origemFisicaCqBadge(origemFisicaResumo).label}
                </span>
                <span className="text-muted-foreground">
                  {origemFisicaCqDescricao(origemFisicaResumo)}
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground mb-1">
                Este indicador confirma o vínculo documental com o Certificado de Fornecedor e os dados de corrida/lote registrados. Ele não comprova, nesta fase, a origem física da quantidade consumida no estoque ou na alocação da venda.
              </p>
              {temAvisoRastreabilidadeFisica ? (
                <p className="text-xs text-sky-800 dark:text-sky-300">
                  Rastreabilidade física não vinculada. Isso não impede a emissão do certificado.
                </p>
              ) : null}
            </div>
          ) : null}
      <div className="rounded border border-border bg-muted/10 p-3">
        <p className="text-sm font-medium mb-2">Itens do certificado</p>
        {form.itens.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Nenhum item carregado. Vincule uma NF-e acima e clique em «Carregar dados da NF-e».
          </p>
        ) : (
          <>
            <div className="mb-2 text-xs">
              <span className="text-muted-foreground">
                Itens: {form.itens.length} total | {incluidosCount} incluídos
                {naoIncluidosCount > 0
                  ? ` | ${naoIncluidosCount} não incluído${naoIncluidosCount > 1 ? 's' : ''}`
                  : ''}
              </span>
              {incluidosCount === 0 ? (
                <p className="mt-1 text-amber-700 dark:text-amber-300">
                  Nenhum item incluído no certificado. Para emitir, inclua pelo menos um item.
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              {form.itens.map((it, idx) => (
                <ItemEditor
                  key={it.id ?? idx}
                  item={it}
                  idx={idx}
                  disabled={nfeBloqueada || saving}
                  onChange={(patch) => updateItem(idx, patch)}
                  corridas={{
                    produtoBusca: produtoBusca[idx],
                    produtoResultados: produtoResultados[idx] || [],
                    corridasDisponiveis: corridasDisponiveisPorItem[idx] || [],
                    onBuscarProdutos: (term) => void buscarProdutosParaItem(idx, term),
                    onVincularProduto: (p) => void vincularProdutoAoItem(idx, p),
                    onCarregarCorridas: () => void carregarCorridasDoItem(idx),
                    onAplicarCorrida: (v) => aplicarCorridaDisponivel(idx, v),
                    dividindo: dividindoCorridas[idx] || [],
                    temCorridaDuplicada: hasCorridaDuplicada(idx),
                    onAddLinha: () => addLinhaCorrida(idx),
                    onRemoveLinha: (linhaIdx) => removeLinhaCorrida(idx, linhaIdx),
                    onUpdateLinha: (linhaIdx, patch) => updateLinhaCorrida(idx, linhaIdx, patch),
                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),
                    onAbrirModalCorridasCf: () => void abrirModalCorridasCf(idx),
                    onBuscarDadosFornecedor: () => void buscarDadosFornecedor(idx),
                    fornecedorBuscaLoading: fornecedorBuscaItemLoading === idx,
                    fornecedorBuscaMsg: fornecedorBuscaItemMsg[idx],
                  }}
                  componentes={{
                    lista: it.componentes || [],
                    onAdd: (nome?: string) => addComponente(idx, nome),
                    onPuxarComponentesDoCfVinculado: () =>
                      void puxarComponentesDoCfVinculado(idx),
                    puxandoComponentes: puxandoComponentes === idx,
                    onRemove: (compIdx: number) => removeComponente(idx, compIdx),
                    onDuplicar: (compIdx: number) => duplicarComponente(idx, compIdx),
                    onCopiarAnterior: (compIdx: number) =>
                      copiarComponenteAnterior(idx, compIdx),
                    onUpdate: (compIdx, patch) => updateComponente(idx, compIdx, patch),
                    onUpdateJson: (compIdx, group, key, value) =>
                      updateCompJson(idx, compIdx, group, key, value),
                    onBuscarDadosCorrida: (compIdx) =>
                      void buscarDadosCorridaComponente(idx, compIdx),
                    fornecedorBuscaCompLoading,
                    fornecedorBuscaCompMsg: Object.keys(fornecedorBuscaCompMsg)
                      .filter((k) => k.startsWith(`${idx}:`))
                      .map((k) => fornecedorBuscaCompMsg[k])
                      .find(Boolean) || null,
                  }}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Corrida/lote, composição, componentes, corridas CF e rastreabilidade/PDF serão portados nas próximas etapas</p>
        <p>Etapa 3c-2: prontidão/origem · Etapa 5b-2/3/4: corrida/composição/componentes · Etapa 6: corridas CF · Etapa 7: rastreabilidade/PDF</p>
      </div>
        </TabsContent>

        <TabsContent value="observacoes" className="mt-0 space-y-4">
          <div>
            <label className="erp-label">Observações</label>
            <textarea
              className="erp-input mt-1 min-h-[120px]"
              value={form.observacoes || ''}
              onChange={(e) => setF('observacoes', e.target.value)}
            />
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="erp-btn-outline"
          onClick={onCancel}
          disabled={saving}
        >
          Voltar
        </button>
        <button
          type="button"
          className="erp-btn-outline"
          onClick={() => void salvar('emitido')}
          disabled={saving}
        >
          Salvar e emitir
        </button>
        <button
          type="button"
          className="erp-btn"
          onClick={() => void salvar()}
          disabled={saving}
        >
          {saving ? 'Salvando...' : 'Salvar'}
        </button>
      </div>

      <ModalCorridasCertificadoFornecedor
        isOpen={corridasCfModal != null}
        onClose={() => setCorridasCfModal(null)}
        dados={corridasCfModal?.dados ?? null}
        carregando={corridasCfModal?.carregando ?? false}
        erroCarregamento={corridasCfModal?.erro ?? null}
        quantidadeTotalItem={corridasCfModal?.quantidadeTotal ?? 0}
        selecoesIniciais={corridasCfModal?.selecoesIniciais ?? []}
        contextoChave={
          corridasCfModal
            ? [
                corridasCfModal.itemIdx,
                form.itens[corridasCfModal.itemIdx]?.certificado_fornecedor_origem_id ?? '',
                form.itens[corridasCfModal.itemIdx]?.item_certificado_fornecedor_origem_id ?? '',
                form.itens[corridasCfModal.itemIdx]?.produto ?? '',
              ].join(':')
            : ''
        }
        onAplicar={aplicarCorridasCfSelecionadas}
      />

      <Modal
        isOpen={fornecedorMatchModalOpen}
        onClose={() => setFornecedorMatchModalOpen(false)}
        title="Resultados de certificado de fornecedor"
        size="xl"
      >
        <div className="space-y-2 max-h-[55vh] overflow-auto pr-1">
          {fornecedorMatches.map((r) => (
            <div
              key={`${r.certificado_fornecedor_id}-${r.id}`}
              className="rounded border border-border p-3"
            >
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {r.produto_match_tipo === 'sem_vinculo' ? (
                  <span className="erp-badge-warning text-xs">
                    Item CF sem produto vinculado
                  </span>
                ) : null}
                {r.produto_match_tipo === 'vinculado' ? (
                  <span className="erp-badge-success text-xs">
                    Produto CF = produto CQ
                  </span>
                ) : null}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-sm">
                <p><span className="font-medium">Fornecedor:</span> {r.fornecedor_nome || '\u2014'}</p>
                <p><span className="font-medium">NF entrada:</span> {r.numero_nf_entrada || '\u2014'}</p>
                <p><span className="font-medium">Certificado:</span> {r.numero_certificado_fornecedor || `#${r.certificado_fornecedor_id}`}</p>
                <p><span className="font-medium">Status (fornecedor):</span> {r.status_certificado_fornecedor || '\u2014'}</p>
                <p><span className="font-medium">Codigo item fornecedor:</span> {r.codigo_produto || '\u2014'}</p>
                <p><span className="font-medium">Descricao:</span> {r.descricao_material || '\u2014'}</p>
                <p><span className="font-medium">Corrida:</span> {r.corrida || '\u2014'}</p>
                <p><span className="font-medium">Lote:</span> {r.lote || '\u2014'}</p>
                <p><span className="font-medium">Norma:</span> {r.norma || '\u2014'}</p>
                <p><span className="font-medium">Tipo tecnico:</span> {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Valvula por componentes' : 'Dados por item'}</p>
                {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? (
                  <p className="md:col-span-2">
                    <span className="font-medium">Componentes:</span> {(r.componentes || []).length}
                    {(r.componentes || []).length
                      ? ` (${(r.componentes || []).slice(0, 6).map((c) => c.nome_componente || 'Componente').join(', ')})`
                      : ''}
                  </p>
                ) : null}
              </div>
              {r.aviso_sem_vinculo_produto ? (
                <p className="text-xs text-amber-800 dark:text-amber-200 mt-2">{r.aviso_sem_vinculo_produto}</p>
              ) : null}
              {r.aviso_divergencia_codigo ? (
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-2">{r.aviso_divergencia_codigo}</p>
              ) : null}
              <div className="flex justify-end mt-2">
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm w-full sm:w-auto"
                  onClick={() => {
                    if (fornecedorTargetIdx == null) return;
                    if (fornecedorTargetCompIdx != null) {
                      aplicarDadosFornecedorComponente(
                        fornecedorTargetIdx,
                        fornecedorTargetCompIdx,
                        r,
                      );
                    } else {
                      aplicarDadosFornecedor(fornecedorTargetIdx, r);
                    }
                    setFornecedorMatchModalOpen(false);
                    setFornecedorTargetCompIdx(null);
                  }}
                >
                  {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Usar estes componentes' : 'Usar estes dados'}
                </button>
              </div>
            </div>
          ))}
          {!fornecedorMatches.length ? (
            <p className="text-sm text-muted-foreground">Nenhum resultado.</p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}
