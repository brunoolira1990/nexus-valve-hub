import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { FileText, Pencil } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import {
  certificadosQualidadeService,
  type NfeElegivelCqOpcao,
} from '@/services/api/qualidade';
import {
  certificadosFornecedorService,
  corridaLoteEfetivosResultadoFornecedor,
  mensagemPrincipalBuscaDadosTecnicosFornecedor,
} from '@/services/api/certificadosFornecedor';
import { produtosService } from '@/services/api/produtos';
import { nfeHistoricaImportadaService, type NFeSaidaHistoricaList } from '@/services/api/nfeHistoricaImportada';
import { apiErrorMessage, getApiErrorStatus } from '@/services/api/config';
import {
  certificadoFornecedorStatusBadge,
  itemCqTemOrigemDocumental,
  origemFisicaCqBadge,
  origemFisicaCqDescricao,
  origemFisicaCqItem,
  origemFisicaCqResumo,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';
import { mesclarMensagensUnicas } from '@/lib/cqMensagensUi';
import {
  TITULO_MODAL_CORRIDAS_CF_CQ,
  aplicacaoSubstituiTecnicosDoItemAtual,
  aplicarDistribuicaoCorridasCfCq,
  quantidadeTotalDistribuicaoCorridasCfCq,
  selecoesExistentesCorridasCfCq,
  type CorridasCfParaCqResponse,
  type SelecaoCorridaCfCq,
  baseItemIrmao,
} from '@/lib/cqCorridasCfUi';
import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';
import type {
  CertificadoQualidade,
  CertificadoQualidadeStatus,
  CorridaDisponivelCertificadoQualidade,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoQualidade,
  Produto,
  ResumoRastreabilidadeCertificadoQualidade,
} from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import type { ListQueryParams } from '@/lib/apiList';
import {
  TEXTO_PADRAO,
  COMPOSICAO_FIELDS,
  TRACAO_FIELDS,
  IMPACTO_FIELDS,
  COMPONENTES_PADRAO,
  MOTIVOS_NAO_INCLUSAO,
  CONFIRMAR_CANCELAMENTO_CERTIFICADO_QUALIDADE,
  AVISO_SEM_CF_MANUAL,
  LABEL_OBRIGATORIO_EMITIR,
  emptyForm,
  ensureMap,
  normalizeCorridaLoteBusca,
  coerceProdutoItemId,
  resolverCorridaLoteBuscaFornecedor,
  itemTemDadosTecnicosPreenchidos,
  fornecedorResultadoSemProdutoVinculado,
  normNumeric,
  parseBlockValues,
  ensureComp,
} from '@/lib/certificadoQualidadeConstants';

/**
 * Fase E.4 (Qualidade): o backend aplica permissões Django; o JWT não expõe codenames.
 * Não escondemos add/change/delete com base em suposições — só ocultamos «Novo» quando
 * o GET da lista retorna 403 (sem `view_*` para a coleção). Demais ações mostram
 * mensagem amigável via `apiErrorMessage` / 403. Evolução: endpoint tipo /me/permissions.
 */

const Certificados = () => {
  const navigate = useNavigate();
  const [listForbidden, setListForbidden] = useState(false);
  const fetchCertificadosPage = useCallback(async (params: ListQueryParams) => {
    try {
      const result = await certificadosQualidadeService.listPaginated(params);
      setListForbidden(false);
      return result;
    } catch (e) {
      if ((e as AxiosError).response?.status === 403) setListForbidden(true);
      throw e;
    }
  }, []);
  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    loading: listLoading,
    error: listError,
    reload: reloadList,
  } = usePaginatedList<CertificadoQualidade>({ fetchPage: fetchCertificadosPage });
  const [nfHistoricas, setNfHistoricas] = useState<NFeSaidaHistoricaList[]>([]);
  const [nfeOpcaoSelecionada, setNfeOpcaoSelecionada] = useState<NfeElegivelCqOpcao | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CertificadoQualidade | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saveError, setSaveError] = useState<string | null>(null);
  const [rastreabilidadeErros, setRastreabilidadeErros] = useState<string[]>([]);
  const [mensagens, setMensagens] = useState<string[]>([]);
  const [pasteCompIdx, setPasteCompIdx] = useState<number | null>(null);
  const [pasteCompText, setPasteCompText] = useState('');
  const [fornecedorMatchModalOpen, setFornecedorMatchModalOpen] = useState(false);
  const [fornecedorMatches, setFornecedorMatches] = useState<DadosTecnicosFornecedorResultado[]>([]);
  const [fornecedorTargetIdx, setFornecedorTargetIdx] = useState<number | null>(null);
  const [fornecedorBuscaAvancadaOpen, setFornecedorBuscaAvancadaOpen] = useState(false);
  /** Índice do item com busca técnica fornecedor em curso (loading local). */
  const [fornecedorBuscaItemLoading, setFornecedorBuscaItemLoading] = useState<number | null>(null);
  /** Feedback da busca por item (exibido junto à corrida — evita erro só no topo do modal). */
  const [fornecedorBuscaItemMsg, setFornecedorBuscaItemMsg] = useState<
    Record<number, { type: 'error' | 'info'; text: string }>
  >({});
  const [produtoBusca, setProdutoBusca] = useState<Record<number, string>>({});
  const [produtoResultados, setProdutoResultados] = useState<Record<number, Produto[]>>({});
  const [corridasDisponiveisPorItem, setCorridasDisponiveisPorItem] = useState<Record<number, CorridaDisponivelCertificadoQualidade[]>>({});
  /** Estado local para modo "dividir item em varias corridas". */
  const [dividindoCorridas, setDividindoCorridas] = useState<Record<number, Array<{corrida: string, lote: string, quantidade: string, valorSelecao: string}>>>({});
  /** Modal de corridas do CF exato vinculado ao item do CQ (hotfix múltiplas corridas). */
  const [corridasCfModal, setCorridasCfModal] = useState<
    | {
        itemIdx: number;
        dados: CorridasCfParaCqResponse | null;
        carregando: boolean;
        erro: string | null;
        quantidadeTotal: number;
        selecoesIniciais: SelecaoCorridaCfCq[];
      }
    | null
  >(null);
  type PdfBusy = null | { kind: 'modal' } | { kind: 'table-row'; id: number };
  const [pdfBusy, setPdfBusy] = useState<PdfBusy>(null);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [previewPdfTitulo, setPreviewPdfTitulo] = useState('Prévia PDF');
  const [fornecedorFiltro, setFornecedorFiltro] = useState({
    corrida: '',
    lote: '',
    fornecedor: '',
    nf_entrada: '',
    certificado_fornecedor: '',
    codigo_produto: '',
    descricao: '',
    status: 'registrado',
  });

  const formRef = useRef(form);
  formRef.current = form;

  /** Acrescenta mensagens sem duplicar as já exibidas (dedupe por conteúdo). */
  const adicionarMensagensUnicas = (novas: string | string[]) =>
    setMensagens((m) => mesclarMensagensUnicas(m, novas));

  const componentePreenchido = (comp: ReturnType<typeof ensureComp>) =>
    Boolean(
      (comp.nome_componente || '').trim()
      || (comp.corrida || '').trim()
      || (comp.norma || '').trim()
      || Object.values(ensureMap(comp.composicao_json)).some(Boolean)
      || Object.values(ensureMap(comp.ensaio_tracao_json)).some(Boolean),
    );

  const totalItens = form.itens.length;
  const incluidosCount = form.itens.filter((it) => it.incluir_no_certificado !== false).length;
  const naoIncluidosCount = totalItens - incluidosCount;

  const resumoRastreabilidade = useMemo((): ResumoRastreabilidadeCertificadoQualidade | null => {
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
  }, [form.resumo_rastreabilidade, form.itens]);

  /**
   * Banner «Origem manual» somente quando a origem é realmente manual:
   * sem vínculo documental (CF/IDs de origem) ou marcado pelo backend como
   * CF_NAO_VINCULADO_MANUAL. Avisos de rastreabilidade sozinhos não bastam.
   */
  const itensComAvisoCfManual = useMemo(
    () => form.itens.filter(
      (it) => it.incluir_no_certificado !== false
        && (
          it.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL')
          || !itemCqTemOrigemDocumental(it)
        ),
    ),
    [form.itens],
  );

  /** CF vinculado, porém sem corrida/lote identificado na origem — rastreabilidade incompleta, não «origem manual». */
  const itensComOrigemVinculadaIncompleta = useMemo(
    () => form.itens.filter(
      (it) => it.incluir_no_certificado !== false
        && itemCqTemOrigemDocumental(it)
        && !it.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL')
        && !(it.corrida_snapshot || '').trim()
        && !(it.lote_snapshot || '').trim(),
    ),
    [form.itens],
  );

  const origemFisicaResumo = useMemo(() => origemFisicaCqResumo(form.itens), [form.itens]);

  const temAvisoRastreabilidadeFisica = useMemo(
    () => form.itens.some(
      (it) => it.incluir_no_certificado !== false && (
        it.rastreabilidade_motivos?.includes('SEM_CORRIDA_LOTE')
        || it.rastreabilidade_motivos?.includes('ESTOQUE_NAO_APLICADO')
        || it.rastreabilidade_motivos?.includes('SEM_CONFERENCIA_ORIGEM')
        || it.rastreabilidade_motivos?.includes('RASTREABILIDADE_FISICA_OPCIONAL')
        || it.rastreabilidade_avisos?.some((a) => a.includes('não impede a emissão'))
        || (
          !it.tem_corrida_lote
          && !it.corrida
          && !it.lote
          && (it.rastreabilidade_status != null || form.itens.length > 0)
        )
      ),
    ),
    [form.itens],
  );

  const extrairErrosRastreabilidade = (e: unknown): string[] => {
    const data = (e as AxiosError<{ rastreabilidade?: string[] }>).response?.data;
    if (data?.rastreabilidade && Array.isArray(data.rastreabilidade)) return data.rastreabilidade;
    return [];
  };

  useEffect(() => {
    nfeHistoricaImportadaService.list().then((r) => setNfHistoricas(r)).catch(() => setNfHistoricas([]));
  }, []);

  const buscaNfesElegiveis = useCallback(
    (term: string, limit?: number) =>
      certificadosQualidadeService.buscarNfesElegiveis(term, limit ?? 20),
    [],
  );

  const itensComDadosTecnicos = useCallback((itens: ItemCertificadoQualidade[]) => {
    return itens.some(
      (it) =>
        Boolean(it.corrida?.trim()) ||
        Boolean(it.norma?.trim()) ||
        Boolean(it.lote?.trim()) ||
        (it.componentes && it.componentes.length > 0) ||
        Object.keys(it.composicao_json || {}).length > 0,
    );
  }, []);

  const selecionarNfeOperacional = useCallback(
    (id: number | string | null, option?: NfeElegivelCqOpcao | null) => {
      const nextId = id == null || id === '' ? null : Number(id);
      const trocando = nextId !== form.nota_fiscal;
      if (option && !option.elegivel && trocando) return;
      const temItensOuDados =
        form.itens.length > 0 || itensComDadosTecnicos(form.itens);
      if (trocando && temItensOuDados) {
        const ok = window.confirm(
          'Trocar a NF-e limpará os itens e dados técnicos já carregados desta nota. Continuar?',
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
      setCorridasDisponiveisPorItem({});
      setProdutoBusca({});
      setProdutoResultados({});
      setMensagens([]);
    },
    [form.itens, form.nota_fiscal, itensComDadosTecnicos],
  );

  const isRowPdfLoading = (id: number) => pdfBusy?.kind === 'table-row' && pdfBusy.id === id;
  const isRowPdfBlocked = (id: number) =>
    pdfBusy !== null && (pdfBusy.kind === 'modal' || (pdfBusy.kind === 'table-row' && pdfBusy.id !== id));
  const modalPdfBusy = pdfBusy?.kind === 'modal';

  const labelSalvarQualidadeSemEmitir = (): string => {
    if (form.status === 'cancelado') {
      return editing?.status === 'cancelado' ? 'Salvar cancelamento' : 'Confirmar cancelamento';
    }
    if (form.status === 'emitido') return 'Salvar como emitido';
    return 'Salvar rascunho';
  };

  const titleSalvarQualidadeSemEmitir = (): string => {
    if (form.status === 'cancelado') {
      return editing?.status === 'cancelado'
        ? 'Grava alterações no cadastro cancelado (o status permanece cancelado).'
        : 'Confirma o cancelamento: o registro permanece para rastreabilidade e o PDF passará a exibir CANCELADO.';
    }
    if (form.status === 'emitido') {
      return 'Grava alterações mantendo o status emitido. Use “Emitir / finalizar” para validar itens e concluir a emissão.';
    }
    return 'Grava o certificado como rascunho.';
  };

  const resolvePayloadStatus = (emitir: boolean): CertificadoQualidadeStatus => {
    if (emitir) return 'emitido';
    if (form.status === 'cancelado' || form.status === 'emitido' || form.status === 'rascunho') return form.status;
    return 'rascunho';
  };

  const closeCertModal = () => {
    setModalOpen(false);
    setFornecedorBuscaItemMsg({});
    setFornecedorBuscaItemLoading(null);
  };

  const openNew = () => {
    navigate('/certificados-qualidade/novo');
  };
  const openEdit = (c: CertificadoQualidade) => {
    navigate(`/certificados-qualidade/${c.id}`);
  };

  const patchFornecedorBuscaItemMsg = (idx: number, v: { type: 'error' | 'info'; text: string } | null) => {
    setFornecedorBuscaItemMsg((prev) => {
      const next = { ...prev };
      if (v == null) delete next[idx];
      else next[idx] = v;
      return next;
    });
  };

  const setF = (k: keyof typeof form, v: unknown) => setForm((p) => ({ ...p, [k]: v }));

  const hydrateFromSaved = (saved: CertificadoQualidade) => {
    setEditing(saved);
    setForm({
      ...saved,
      data_emissao: saved.data_emissao || '',
      observacoes: saved.observacoes || '',
      texto_padrao: saved.texto_padrao || TEXTO_PADRAO,
      pedido_cliente: saved.pedido_cliente || '',
      cliente_cnpj_snapshot: saved.cliente_cnpj_snapshot || '',
      itens: (saved.itens || []).map((it) => ({
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
    });
  };

  const numeroArquivoAtual = () =>
    form.numero?.trim() || editing?.numero_formatado || editing?.numero || 'sem_numero';

  const carregarPorNFe = async () => {
    setSaveError(null);
    setMensagens([]);
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
      setCorridasDisponiveisPorItem({});
      setProdutoBusca({});
      setProdutoResultados({});
      const itensResp = (data.itens as ItemCertificadoQualidade[]) ?? [];
      for (let i = 0; i < itensResp.length; i += 1) {
        const pit = itensResp[i];
        if (pit.produto) {
          certificadosQualidadeService
            .corridasDisponiveisPorProduto(pit.produto)
            .then((rows) => setCorridasDisponiveisPorItem((p) => ({ ...p, [i]: rows })))
            .catch(() => {});
        }
      }
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível carregar itens pela NF-e.' }));
    }
  };

  const salvar = async (emitir = false) => {
    setSaveError(null);
    setRastreabilidadeErros([]);
    if (emitir && form.status === 'cancelado') {
      setSaveError('Não é possível emitir um certificado cancelado.');
      return;
    }
    if (!emitir && form.status === 'cancelado') {
      const anterior = editing?.status;
      if (anterior !== 'cancelado') {
        const ok = window.confirm(CONFIRMAR_CANCELAMENTO_CERTIFICADO_QUALIDADE);
        if (!ok) return;
      }
    }
    const nextStatus = resolvePayloadStatus(emitir);
    const payload = {
      ...form,
      status: nextStatus,
      itens: (form.itens || []).map((it) => ({
        ...it,
        status_vinculo_produto: undefined,
        produto_codigo: undefined,
        produto_descricao: undefined,
        produto_ncm_efetivo: undefined,
      })),
    };
    try {
      let saved: CertificadoQualidade;
      if (editing) saved = await certificadosQualidadeService.update(editing.id, payload);
      else saved = await certificadosQualidadeService.create(payload);
      hydrateFromSaved(saved);
      setMensagens([
        emitir
          ? 'Certificado emitido com sucesso.'
          : nextStatus === 'cancelado'
            ? 'Cancelamento registrado com sucesso.'
            : 'Rascunho salvo com sucesso.',
      ]);
      void reloadList();
    } catch (e) {
      const errosRast = extrairErrosRastreabilidade(e);
      setRastreabilidadeErros(errosRast);
      setSaveError(
        apiErrorMessage(e, {
          fallback: emitir
            ? 'Não foi possível emitir o certificado. Verifique a rastreabilidade dos itens.'
            : 'Não foi possível salvar o certificado.',
        }),
      );
    }
  };

  const visualizarOuBaixarPdf = async (
    id: number,
    preview = false,
    forcarDownload = false,
    meta?: { numero?: string; cliente?: string; nf?: string },
    busy: PdfBusy = { kind: 'modal' },
  ) => {
    setPdfBusy(busy);
    setSaveError(null);
    try {
      if (forcarDownload) await certificadosQualidadeService.baixarPdf(id, preview, meta);
      else await certificadosQualidadeService.visualizarPdf(id, preview, meta);
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível gerar o PDF. Verifique se o certificado foi salvo como rascunho.' }));
    } finally {
      setPdfBusy(null);
    }
  };

  const abrirPreviaModal = async (id: number, meta?: { numero?: string; cliente?: string; nf?: string }) => {
    setSaveError(null);
    try {
      if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
      const blob = await certificadosQualidadeService.obterPdfBlob(id, true);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewPdfUrl(objectUrl);
      setPreviewPdfTitulo(`Prévia - ${certificadosQualidadeService.buildPdfFilename(meta || {}, true)}`);
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível gerar a prévia PDF.' }));
    }
  };

  const visualizarPreviaPdf = async () => {
    setSaveError(null);
    setPdfBusy({ kind: 'modal' });
    try {
      const payload = {
        ...form,
        status: (form.status === 'cancelado' ? 'cancelado' : 'rascunho') as CertificadoQualidadeStatus,
        itens: (form.itens || []).map((it) => ({
          ...it,
          status_vinculo_produto: undefined,
          produto_codigo: undefined,
          produto_descricao: undefined,
          produto_ncm_efetivo: undefined,
        })),
      };
      const saved = editing
        ? await certificadosQualidadeService.update(editing.id, payload)
        : await certificadosQualidadeService.create(payload);
      hydrateFromSaved(saved);
      setMensagens(['Rascunho salvo/atualizado automaticamente antes da prévia.']);
      void reloadList();
      await abrirPreviaModal(saved.id, {
        numero: saved.numero_formatado || saved.numero || numeroArquivoAtual(),
        cliente: saved.cliente_nome_snapshot || form.cliente_nome_snapshot,
        nf: saved.nota_fiscal_numero || form.nota_fiscal_numero,
      });
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível gerar a prévia PDF.' }));
    } finally {
      setPdfBusy(null);
    }
  };

  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>
    setForm((p) => {
      const next = [...p.itens];
      next[idx] = { ...next[idx], ...patch };
      return { ...p, itens: next };
    });

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
        adicionarMensagensUnicas(
          'Nenhuma corrida/lote disponível encontrada para este produto cadastrado. Verifique entrada de estoque, conferência da NF-e de entrada ou certificado fornecedor.',
        );
      }
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Falha ao carregar corridas disponíveis para o produto cadastrado.' }));
    }
  };

  const carregarCorridasDoItem = async (idx: number) => {
    const produtoId = coerceProdutoItemId(formRef.current.itens[idx]?.produto);
    if (!produtoId) return;
    try {
      const corridas = await certificadosQualidadeService.corridasDisponiveisPorProduto(produtoId);
      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: corridas }));
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Falha ao carregar corridas disponíveis para o item.' }));
    }
  };

  const construirItemIrmaoDeCorrida = (idx: number, source: CorridaDisponivelCertificadoQualidade, quantidade: string): ItemCertificadoQualidade => {
    const item = formRef.current.itens[idx];
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
      certificado_fornecedor_origem_id: source.certificado_fornecedor_origem_id ?? source.certificado_fornecedor_id ?? null,
      item_certificado_fornecedor_origem_id: source.item_certificado_fornecedor_origem_id ?? source.item_certificado_fornecedor_id ?? null,
      fornecedor_nome_snapshot: source.fornecedor || '',
      nf_entrada_snapshot: source.nf_entrada || '',
      numero_certificado_fornecedor_item_snapshot:
        source.numero_certificado_fornecedor_item || source.certificado_fornecedor || '',
      corrida_snapshot: source.corrida || '',
      lote_snapshot: source.lote || '',
      origem_rastreabilidade_tipo: source.origem || 'manual',
      origem_status_tecnico: source.status_origem_tecnica || (source.tem_dados_tecnicos ? 'dados_tecnicos' : 'sem_dados_tecnicos'),
      origem_observacoes: source.observacoes_origem || '',
    };
  };

  const aplicarCorridaDisponivel = (idx: number, valorSelecao: string) => {
    const item = formRef.current.itens[idx];
    const source = (corridasDisponiveisPorItem[idx] || []).find(
      (c) => (c.valor_selecao && c.valor_selecao === valorSelecao) || `${c.corrida}||${c.lote || ''}` === valorSelecao,
    );
    if (!source) return;
    if (source.status_certificado_fornecedor === 'rascunho') {
      const ok = window.confirm(
        'Dados técnicos encontrados em certificado fornecedor em rascunho. Use com confirmação ou registre o certificado fornecedor antes de emitir. Deseja aplicar estes dados?',
      );
      if (!ok) return;
    }
    const alertas = [...(source.alertas || [])];
    const existeDivergenciaNcm = Boolean(item.ncm && source.ncm && item.ncm !== source.ncm);
    if (existeDivergenciaNcm) {
      alertas.push('A corrida foi encontrada, mas há divergência entre descrição/NCM/norma da origem e do item de saída. Confira antes de aplicar.');
    }
    const quantidadeItem = item.quantidade || 0;
    updateItem(idx, construirItemIrmaoDeCorrida(idx, source, String(quantidadeItem)));
    if (alertas.length) {
      adicionarMensagensUnicas(alertas);
    }
  };

  /**
   * Adiciona uma linha vazia ao estado de divisão de corridas para o item idx.
   */
  const addLinhaCorrida = (idx: number) =>
    setDividindoCorridas((prev) => ({
      ...prev,
      [idx]: [...(prev[idx] || []), { corrida: '', lote: '', quantidade: '', valorSelecao: '' }],
    }));

  /**
   * Remove uma linha específica do estado de divisão de corridas.
   */
  const removeLinhaCorrida = (idx: number, linhaIdx: number) =>
    setDividindoCorridas((prev) => {
      const linhas = prev[idx] || [];
      const next = [...linhas];
      next.splice(linhaIdx, 1);
      return { ...prev, [idx]: next.length > 0 ? next : undefined };
    });

  /**
   * Atualiza um campo de uma linha específica do estado de divisão de corridas.
   */
  const updateLinhaCorrida = (idx: number, linhaIdx: number, patch: Partial<{ corrida: string; lote: string; quantidade: string; valorSelecao: string }>) =>
    setDividindoCorridas((prev) => {
      const linhas = prev[idx] || [];
      const next = [...linhas];
      next[linhaIdx] = { ...next[linhaIdx], ...patch };
      return { ...prev, [idx]: next };
    });

  /**
   * Aplica a distribuição de corridas: valida soma e quantidade, cria itens irmãos no array `itens`.
   */
  const aplicarDistribuicaoCorridas = (idx: number) => {
    const linhas = dividindoCorridas[idx] || [];
    if (!linhas.length) return;

    // Valida: todas as linhas têm corrida e quantidade > 0
    const linhasInvalidas = linhas.some((l) => !l.valorSelecao || !l.quantidade || parseFloat(l.quantidade) <= 0);
    if (linhasInvalidas) {
      adicionarMensagensUnicas(['Informe corrida e quantidade > 0 para todas as linhas.']);
      return;
    }

    // Valida: soma == quantidade do item original
    const quantidadeOriginal = formRef.current.itens[idx].quantidade || 0;
    const somaTotal = linhas.reduce((sum, l) => sum + parseFloat(l.quantidade), 0);
    if (Math.abs(somaTotal - quantidadeOriginal) > 0.001) {
      adicionarMensagensUnicas([
        `A soma das quantidades (${somaTotal}) deve ser equal à quantidade do item original (${quantidadeOriginal}).`,
      ]);
      return;
    }

    // Valida: sem corrida duplicada
    const chaves = new Set<string>();
    for (const l of linhas) {
      const chave = (l.valorSelecao || '').trim().toUpperCase();
      if (chaves.has(chave)) {
        adicionarMensagensUnicas(['A mesma corrida não pode ser adicionada duas vezes.']);
        return;
      }
      chaves.add(chave);
    }

    // Para cada linha selecionada, cria item irmão
    const novosItens: ItemCertificadoQualidade[] = [];

    for (const l of linhas) {
      const source = (corridasDisponiveisPorItem[idx] || []).find(
        (c) => (c.valor_selecao && c.valor_selecao === l.valorSelecao) || `${c.corrida}||${c.lote || ''}` === l.valorSelecao,
      );
      if (!source) continue;

      const itemIrmao = construirItemIrmaoDeCorrida(idx, source, l.quantidade);
      // Garantir que corrida e lote vêm da source selecionada
      itemIrmao.corrida = source.corrida || '';
      itemIrmao.lote = source.lote || '';
      itemIrmao.quantidade = parseFloat(l.quantidade);

      novosItens.push(itemIrmao);
    }

    // Substitui item original pelos irmaos no array itens
    const itemOriginal = formRef.current.itens[idx];
    const novosItensOrdenados = novosItens.map((it, i) => ({ ...it, ordem: (itemOriginal.ordem || idx + 1) + i }));

    setForm((p) => {
      const next = [...p.itens];
      next.splice(idx, 1, ...novosItensOrdenados);
      return { ...p, itens: next };
    });

    // Limpa estado do item
    setDividindoCorridas({});
    setCorridasDisponiveisPorItem({});
  };

  const abrirModalCorridasCf = async (idx: number) => {
    const item = formRef.current.itens[idx];
    const cfId = item.certificado_fornecedor_origem_id;
    const itemCfId = item.item_certificado_fornecedor_origem_id;
    if (!cfId || !itemCfId) {
      setSaveError(
        'Vincule este item a um Certificado de Fornecedor e ao item exato do CF (via corrida disponível ou busca de dados do fornecedor) antes de adicionar corridas.',
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
      const itensAtuais = formRef.current.itens;
      setCorridasCfModal({
        itemIdx: idx,
        dados,
        carregando: false,
        erro: null,
        quantidadeTotal: quantidadeTotalDistribuicaoCorridasCfCq(dados.linhas, itensAtuais, itensAtuais[idx]),
        selecoesIniciais: selecoesExistentesCorridasCfCq(dados.linhas, itensAtuais),
      });
    } catch (e) {
      // 401/403 permanecem nas mensagens padrão; 404 real (CF inexistente) usa o detail da API.
      const status = getApiErrorStatus(e);
      const detail = (e as AxiosError<{ detail?: string }>)?.response?.data?.detail;
      const erro = (
        (status === 401 || status === 403)
          ? apiErrorMessage(e, { fallback: 'Não foi possível carregar as corridas do Certificado de Fornecedor.' })
          : (typeof detail === 'string' && detail.trim()
            ? detail.trim()
            : apiErrorMessage(e, { fallback: 'Não foi possível carregar as corridas do Certificado de Fornecedor.' }))
      );
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
    const itemOriginal = formRef.current.itens[idx];
    if (
      aplicacaoSubstituiTecnicosDoItemAtual(itemOriginal, selecoes)
      && !window.confirm(
        'O item atual já possui dados técnicos preenchidos. Aplicar esta distribuição substituirá '
        + 'os dados técnicos da primeira origem selecionada. Deseja continuar?',
      )
    ) {
      return false;
    }
    setForm((p) => {
      const itens = aplicarDistribuicaoCorridasCfCq(p.itens, idx, dados.linhas, selecoes);
      return { ...p, itens };
    });
    setCorridasCfModal(null);
    adicionarMensagensUnicas([
      `Corridas aplicadas do Certificado de Fornecedor: ${selecoes
        .map((s) => `${s.linha.corrida}${s.linha.lote ? `/${s.linha.lote}` : ''} (${s.quantidade})`)
        .join(', ')}.`,
      corridasCfModal?.dados?.mensagem_origem_fisica || '',
    ].filter(Boolean));
    return true;
  };

  const updateJsonField = (
    idx: number,
    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',
    key: string,
    value: string,
  ) => {
    setForm((p) => {
      const next = [...p.itens];
      const current = ensureMap(next[idx][group]);
      current[key] = value;
      next[idx] = { ...next[idx], [group]: current };
      return { ...p, itens: next };
    });
  };

  const copyTecnicoFromPrevious = (idx: number) => {
    if (idx === 0) return;
    const prev = form.itens[idx - 1];
    updateItem(idx, {
      composicao_json: { ...ensureMap(prev.composicao_json) },
      ensaio_tracao_json: { ...ensureMap(prev.ensaio_tracao_json) },
      ensaio_impacto_json: { ...ensureMap(prev.ensaio_impacto_json) },
    });
  };

  const clearTecnico = (idx: number) => {
    updateItem(idx, {
      composicao_json: {},
      ensaio_tracao_json: {},
      ensaio_impacto_json: {},
    });
  };

  const clearComposicao = (idx: number) => {
    updateItem(idx, { composicao_json: {} });
  };

  const clearTracao = (idx: number) => {
    updateItem(idx, { ensaio_tracao_json: {} });
  };

  const duplicateComposicaoToAll = (idx: number) => {
    const source = { ...ensureMap(form.itens[idx].composicao_json) };
    setForm((p) => ({
      ...p,
      itens: p.itens.map((it) => ({ ...it, composicao_json: { ...source } })),
    }));
  };

  const duplicateTracaoToAll = (idx: number) => {
    const source = { ...ensureMap(form.itens[idx].ensaio_tracao_json) };
    setForm((p) => ({
      ...p,
      itens: p.itens.map((it) => ({ ...it, ensaio_tracao_json: { ...source } })),
    }));
  };

  const applyCompositionBlock = (idx: number) => {
    const values = parseBlockValues(pasteCompText);
    if (!values.length) return;
    const next = { ...ensureMap(form.itens[idx].composicao_json) };
    COMPOSICAO_FIELDS.forEach((field, i) => {
      if (values[i] != null) next[field] = normNumeric(values[i]);
    });
    updateItem(idx, { composicao_json: next });
    setPasteCompIdx(null);
    setPasteCompText('');
  };

  const updateCompField = (
    itemIdx: number,
    compIdx: number,
    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',
    key: string,
    value: string,
  ) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      const map = ensureMap(comps[compIdx][group]);
      map[key] = value;
      comps[compIdx] = { ...comps[compIdx], [group]: map };
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const addComponente = (itemIdx: number, nome = '') => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const removeComponente = (itemIdx: number, compIdx: number) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      comps.splice(compIdx, 1);
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps.map((c, i) => ({ ...c, ordem: i + 1 })) };
      return { ...p, itens: itemsNext };
    });
  };

  const duplicarComponente = (itemIdx: number, compIdx: number) => {
    const src = ensureComp(form.itens[itemIdx].componentes?.[compIdx], 1);
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      comps.push({ ...src, ordem: comps.length + 1 });
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const copiarComponenteAnterior = (itemIdx: number, compIdx: number) => {
    if (compIdx === 0) return;
    const prev = ensureComp(form.itens[itemIdx].componentes?.[compIdx - 1], compIdx);
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      comps[compIdx] = { ...comps[compIdx], ...prev, ordem: comps[compIdx].ordem };
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const adicionarComponentesPadrao = (itemIdx: number) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      COMPONENTES_PADRAO.forEach((nome) => {
        comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));
      });
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const aplicarDadosFornecedor = (idx: number, src: DadosTecnicosFornecedorResultado) => {
    if (src.status_certificado_fornecedor === 'rascunho') {
      const ok = window.confirm(
        'O certificado fornecedor encontrado ainda está em rascunho. Registre o certificado antes de usar os dados técnicos.\n\nDeseja aplicar os dados mesmo assim?',
      );
      if (!ok) return;
    }
    if (fornecedorResultadoSemProdutoVinculado(src)) {
      const ok = window.confirm(
        'Este dado técnico veio de um certificado fornecedor cujo item não está vinculado a produto cadastrado. Confira código, descrição e corrida antes de aplicar. Deseja continuar?',
      );
      if (!ok) return;
    }
    const item = formRef.current.itens[idx];
    const isValvula = (src.tipo_dados_tecnicos || item.tipo_dados_tecnicos) === 'VALVULA_COMPONENTES';
    const { corrida: crEf, lote: loEf } = corridaLoteEfetivosResultadoFornecedor(src);
    const novosComponentes = (src.componentes || []).map((cp, i) => ({
      ...ensureComp(cp, i + 1),
      numero_certificado_fornecedor_componente_snapshot:
        String(cp.numero_certificado_fornecedor_componente || '') || (src.numero_certificado_fornecedor_item || src.numero_certificado_fornecedor || ''),
    }));
    if (isValvula) {
      const existentes = (item.componentes || []).map((c, i) => ensureComp(c, i + 1));
      const existePreenchido = existentes.some(componentePreenchido);
      if (existePreenchido && novosComponentes.length) {
        const ok = window.confirm('Este item já possui componentes preenchidos. Deseja substituir pelos dados do certificado fornecedor?');
        if (!ok) return;
      }
      updateItem(idx, {
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        corrida: crEf || item.corrida,
        lote: loEf || item.lote,
        componentes: novosComponentes,
        certificado_fornecedor_origem_id: src.certificado_fornecedor_id || null,
        item_certificado_fornecedor_origem_id: src.id || null,
        fornecedor_nome_snapshot: src.fornecedor_nome || '',
        nf_entrada_snapshot: src.numero_nf_entrada || '',
        codigo_item_fornecedor_snapshot: src.codigo_produto || '',
        descricao_item_fornecedor_snapshot: src.descricao_material || '',
        numero_certificado_fornecedor_item_snapshot:
          src.numero_certificado_fornecedor_item || src.numero_certificado_fornecedor || '',
        corrida_snapshot: crEf || item.corrida_snapshot || '',
        lote_snapshot: loEf || item.lote_snapshot || '',
      });
    } else {
      if (itemTemDadosTecnicosPreenchidos(item)) {
        const ok = window.confirm(
          'Este item já possui dados técnicos preenchidos. Deseja substituir pelos dados do certificado de fornecedor selecionado?',
        );
        if (!ok) return;
      }
      updateItem(idx, {
        norma: src.norma || item.norma,
        corrida: crEf || item.corrida,
        lote: loEf || item.lote || '',
        composicao_json: ensureMap(src.composicao_json),
        ensaio_tracao_json: ensureMap(src.ensaio_tracao_json),
        ensaio_impacto_json: ensureMap(src.ensaio_impacto_json),
        tipo_dados_tecnicos: src.tipo_dados_tecnicos || item.tipo_dados_tecnicos,
        certificado_fornecedor_origem_id: src.certificado_fornecedor_id || null,
        item_certificado_fornecedor_origem_id: src.id || null,
        fornecedor_nome_snapshot: src.fornecedor_nome || '',
        nf_entrada_snapshot: src.numero_nf_entrada || '',
        codigo_item_fornecedor_snapshot: src.codigo_produto || '',
        descricao_item_fornecedor_snapshot: src.descricao_material || '',
        numero_certificado_fornecedor_item_snapshot:
          src.numero_certificado_fornecedor_item || src.numero_certificado_fornecedor || '',
        corrida_snapshot: crEf || item.corrida_snapshot || '',
        lote_snapshot: loEf || item.lote_snapshot || '',
        origem_rastreabilidade_tipo: 'certificado_fornecedor',
        origem_status_tecnico: src.status_certificado_fornecedor || '',
      });
    }
    const avisos: string[] = [];
    if (src.aviso_divergencia_codigo) avisos.push(src.aviso_divergencia_codigo);
    if (fornecedorResultadoSemProdutoVinculado(src)) {
      avisos.push(
        'Dados encontrados em certificado fornecedor sem produto vinculado. Confira código, descrição e corrida antes de aplicar.',
      );
    } else {
      avisos.push('Dados técnicos encontrados no certificado fornecedor.');
    }
    if (src.status_certificado_fornecedor === 'rascunho') {
      avisos.push('O certificado fornecedor encontrado ainda está em rascunho. Registre o certificado antes de usar os dados técnicos.');
    }
    if (src.aviso_sem_vinculo_produto && !fornecedorResultadoSemProdutoVinculado(src)) {
      avisos.push(src.aviso_sem_vinculo_produto);
    }
    setMensagens(avisos);
    patchFornecedorBuscaItemMsg(idx, null);
  };

  const buscarDadosFornecedor = async (idx: number) => {
    patchFornecedorBuscaItemMsg(idx, null);
    const item = formRef.current.itens[idx];
    if (!item) return;
    const produtoId = coerceProdutoItemId(item.produto);
    const isValvula = (item.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES';
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
      const debugBusca =
        typeof window !== 'undefined' &&
        new URLSearchParams(window.location.search).get('debug') === '1';
      const { resultados: encontrados, dicas_busca: dicasBusca } = await certificadosFornecedorService.buscarDadosTecnicos({
        ...(produtoId ? { produto: produtoId } : {}),
        corrida: corridaBusca || undefined,
        lote: loteBusca || undefined,
        codigo_produto: item.codigo_produto || undefined,
        descricao: item.descricao_material || undefined,
        tipo_dados_tecnicos: isValvula ? 'VALVULA_COMPONENTES' : 'PADRAO_ITEM',
        norma: item.norma || undefined,
        status: 'registrado',
        ...(debugBusca ? { debug: true } : {}),
      });
      if (!encontrados.length) {
        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);
        const text =
          dicaMsg
          || 'Nenhum certificado fornecedor registrado foi encontrado para esta corrida.';
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
        text: apiErrorMessage(e, { fallback: 'Falha ao buscar dados técnicos de entrada.' }),
      });
    } finally {
      setFornecedorBuscaItemLoading(null);
    }
  };

  const buscarDadosFornecedorAvancado = async () => {
    try {
      const debugBusca =
        typeof window !== 'undefined' &&
        new URLSearchParams(window.location.search).get('debug') === '1';
      const { resultados, dicas_busca: dicasBusca } = await certificadosFornecedorService.buscarDadosTecnicos({
        corrida: fornecedorFiltro.corrida || undefined,
        lote: fornecedorFiltro.lote || undefined,
        fornecedor: fornecedorFiltro.fornecedor ? Number(fornecedorFiltro.fornecedor) : undefined,
        nf_entrada: fornecedorFiltro.nf_entrada || undefined,
        certificado_fornecedor: fornecedorFiltro.certificado_fornecedor || undefined,
        codigo_produto: fornecedorFiltro.codigo_produto || undefined,
        descricao: fornecedorFiltro.descricao || undefined,
        status: fornecedorFiltro.status as 'rascunho' | 'registrado' | 'cancelado',
        include_rascunho: fornecedorFiltro.status === 'rascunho',
        ...(debugBusca ? { debug: true } : {}),
      });
      setFornecedorMatches(resultados);
      setFornecedorMatchModalOpen(true);
      setFornecedorBuscaAvancadaOpen(false);
      if (!resultados.length) {
        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);
        setSaveError(
          dicaMsg
            || 'Nenhum certificado de fornecedor registrado foi encontrado para esta corrida/lote. Verifique a corrida, o lote ou use a busca avançada por fornecedor/NF/descrição.',
        );
      }
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Falha ao buscar dados técnicos do fornecedor.' }));
    }
  };

  return (
    <div>
      <PageHeader
        title="Certificados de Qualidade"
        description="Emissão e acompanhamento de certificados de qualidade vinculados a produtos, lotes e clientes."
        onAdd={listForbidden ? undefined : openNew}
        addLabel="Novo certificado"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Digite parte do número do certificado."
      />
      {listError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {listLoading ? <TableSkeleton rows={6} cols={6} /> : null}
      {!listLoading && !listError ? (
        <DataTableShell>
        <DataTable className="text-sm" mobileMode="cards">
          <thead>
            <tr>
              <th className="whitespace-nowrap">Número</th>
              <th>Cliente</th>
              <th className="whitespace-nowrap">NF</th>
              <th className="whitespace-nowrap">Data</th>
              <th className="whitespace-nowrap">Status</th>
              <th className="w-44 text-right whitespace-nowrap">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    message="Nenhum certificado de qualidade encontrado."
                    actionLabel={listForbidden ? undefined : 'Novo certificado'}
                    onAction={listForbidden ? undefined : openNew}
                  />
                </td>
              </tr>
            ) : (
              items.map((c) => {
                const pdfEhPrevia = c.status === 'rascunho';
                return (
                  <tr key={c.id}>
                    <td className="font-mono whitespace-nowrap">{c.numero_formatado}</td>
                    <td>{c.cliente_nome_snapshot || '—'}</td>
                    <td>{c.nota_fiscal_numero || '—'}</td>
                    <td>{c.data_emissao || '—'}</td>
                    <td>
                      <div className="flex flex-col gap-1 items-start">
                        <StatusBadge status={c.status || 'pendente'} />
                        {c.status !== 'cancelado' && c.rastreabilidade_resumo_label ? (
                          <span
                            className={`${rastreabilidadeCqBadge(
                              c.resumo_rastreabilidade?.pode_emitir
                                ? 'COMPLETA'
                                : (c.resumo_rastreabilidade?.pendentes ?? 0) > 0
                                  ? 'PENDENTE'
                                  : 'PARCIAL',
                            ).className} text-[10px]`}
                          >
                            {c.rastreabilidade_resumo_label}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-end gap-1">
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm"
                          onClick={() => openEdit(c)}
                          disabled={c.status === 'cancelado'}
                          title={c.status === 'cancelado' ? 'Certificado cancelado: use apenas visualizar ou baixar o PDF para consulta.' : 'Editar certificado'}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          onClick={() => void visualizarOuBaixarPdf(c.id, pdfEhPrevia, false, {
                            numero: c.numero_formatado || c.numero,
                            cliente: c.cliente_nome_snapshot,
                            nf: c.nota_fiscal_numero,
                          }, { kind: 'table-row', id: c.id })}
                          disabled={isRowPdfBlocked(c.id)}
                          title={
                            c.status === 'cancelado'
                              ? 'Abrir PDF do certificado cancelado (marca CANCELADO no documento).'
                              : pdfEhPrevia
                                ? 'Pré-visualizar PDF do rascunho.'
                                : 'Abrir PDF emitido.'
                          }
                        >
                          <FileText className="h-4 w-4 mr-1" />
                          {isRowPdfLoading(c.id) ? 'Gerando…' : c.status === 'cancelado' ? 'Ver PDF' : pdfEhPrevia ? 'Prévia' : 'Ver PDF'}
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          onClick={() => void visualizarOuBaixarPdf(c.id, pdfEhPrevia, true, {
                            numero: c.numero_formatado || c.numero,
                            cliente: c.cliente_nome_snapshot,
                            nf: c.nota_fiscal_numero,
                          }, { kind: 'table-row', id: c.id })}
                          disabled={isRowPdfBlocked(c.id)}
                          title={
                            c.status === 'cancelado'
                              ? 'Baixar PDF do certificado cancelado (marca CANCELADO).'
                              : 'Baixar PDF.'
                          }
                        >
                          {isRowPdfLoading(c.id) ? '…' : 'Baixar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </DataTable>
          {count > 0 ? (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            count={count}
            totalPages={totalPages}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        ) : null}
        </DataTableShell>
      ) : null}


      <Modal
        isOpen={Boolean(previewPdfUrl)}
        onClose={() => {
          if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
          setPreviewPdfUrl(null);
        }}
        title={previewPdfTitulo}
        size="xl"
      >
        {previewPdfUrl ? (
          <div className="h-[78vh]">
            <iframe title="Prévia PDF do certificado" src={previewPdfUrl} className="w-full h-full border border-border rounded" />
          </div>
        ) : null}
      </Modal>

      <Modal isOpen={fornecedorBuscaAvancadaOpen} onClose={() => setFornecedorBuscaAvancadaOpen(false)} title="Busca avançada de certificado de fornecedor" size="lg">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="erp-label">Corrida</label><input className="erp-input mt-1" value={fornecedorFiltro.corrida} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, corrida: e.target.value }))} /></div>
          <div><label className="erp-label">Lote</label><input className="erp-input mt-1" value={fornecedorFiltro.lote} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, lote: e.target.value }))} /></div>
          <div><label className="erp-label">Fornecedor (id)</label><input className="erp-input mt-1" value={fornecedorFiltro.fornecedor} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, fornecedor: e.target.value }))} /></div>
          <div><label className="erp-label">NF entrada</label><input className="erp-input mt-1" value={fornecedorFiltro.nf_entrada} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, nf_entrada: e.target.value }))} /></div>
          <div><label className="erp-label">Certificado fornecedor</label><input className="erp-input mt-1" value={fornecedorFiltro.certificado_fornecedor} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, certificado_fornecedor: e.target.value }))} /></div>
          <div><label className="erp-label">Código item fornecedor</label><input className="erp-input mt-1" value={fornecedorFiltro.codigo_produto} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, codigo_produto: e.target.value }))} /></div>
          <div className="md:col-span-2"><label className="erp-label">Descrição</label><input className="erp-input mt-1" value={fornecedorFiltro.descricao} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, descricao: e.target.value }))} /></div>
          <div><label className="erp-label">Status</label><select className="erp-select mt-1 w-full" value={fornecedorFiltro.status} onChange={(e) => setFornecedorFiltro((p) => ({ ...p, status: e.target.value }))}><option value="registrado">Registrado</option><option value="rascunho">Rascunho</option><option value="cancelado">Cancelado</option></select></div>
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-4">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={() => setFornecedorBuscaAvancadaOpen(false)}>Cancelar</button>
          <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void buscarDadosFornecedorAvancado()}>Buscar</button>
        </div>
      </Modal>

      <Modal isOpen={fornecedorMatchModalOpen} onClose={() => setFornecedorMatchModalOpen(false)} title="Resultados de certificado de fornecedor" size="xl">
        <div className="space-y-2 max-h-[55vh] overflow-auto pr-1">
          {fornecedorMatches.map((r) => (
            <div key={`${r.certificado_fornecedor_id}-${r.id}`} className="rounded border border-border p-3">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {r.produto_match_tipo === 'sem_vinculo' ? (
                  <span className="erp-badge-warning text-xs">Item CF sem produto vinculado</span>
                ) : null}
                {r.produto_match_tipo === 'vinculado' ? (
                  <span className="erp-badge-success text-xs">Produto CF = produto CQ</span>
                ) : null}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-sm">
                <p><span className="font-medium">Fornecedor:</span> {r.fornecedor_nome || '—'}</p>
                <p><span className="font-medium">NF entrada:</span> {r.numero_nf_entrada || '—'}</p>
                <p><span className="font-medium">Certificado:</span> {r.numero_certificado_fornecedor || `#${r.certificado_fornecedor_id}`}</p>
                <p><span className="font-medium">Status (fornecedor):</span>{' '}
                  {(() => {
                    const sb = certificadoFornecedorStatusBadge(r.status_certificado_fornecedor);
                    return <span className={sb.className}>{sb.label}</span>;
                  })()}
                </p>
                <p><span className="font-medium">Código item fornecedor:</span> {r.codigo_produto || '—'}</p>
                <p><span className="font-medium">Descrição:</span> {r.descricao_material || '—'}</p>
                <p><span className="font-medium">Corrida:</span> {r.corrida || '—'}</p>
                <p><span className="font-medium">Lote:</span> {r.lote || '—'}</p>
                <p><span className="font-medium">Norma:</span> {r.norma || '—'}</p>
                <p><span className="font-medium">Tipo técnico:</span> {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Válvula por componentes' : 'Dados por item'}</p>
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
              {r.aviso_divergencia_codigo ? <p className="text-xs text-amber-700 dark:text-amber-300 mt-2">{r.aviso_divergencia_codigo}</p> : null}
              <div className="flex justify-end mt-2">
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm w-full sm:w-auto"
                  onClick={() => {
                    if (fornecedorTargetIdx == null) return;
                    aplicarDadosFornecedor(fornecedorTargetIdx, r);
                    setFornecedorMatchModalOpen(false);
                  }}
                >
                  {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Usar estes componentes' : 'Usar estes dados'}
                </button>
              </div>
            </div>
          ))}
          {!fornecedorMatches.length ? <p className="text-sm text-muted-foreground">Nenhum resultado.</p> : null}
        </div>
      </Modal>

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
    </div>
  );
};

export default Certificados;
