import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
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
import { apiErrorMessage } from '@/services/api/config';
import {
  certificadoFornecedorStatusBadge,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';
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

/**
 * Fase E.4 (Qualidade): o backend aplica permissões Django; o JWT não expõe codenames.
 * Não escondemos add/change/delete com base em suposições — só ocultamos «Novo» quando
 * o GET da lista retorna 403 (sem `view_*` para a coleção). Demais ações mostram
 * mensagem amigável via `apiErrorMessage` / 403. Evolução: endpoint tipo /me/permissions.
 */

const TEXTO_PADRAO =
  'Os certificados originais encontram-se em nosso poder, à sua disposição, certificamos que o(s) produto(s) supra está(ão) aprovado(s), de acordo com as especificações acima mencionadas. Documento impresso eletronicamente, dispensa assinatura.';

const COMPOSICAO_FIELDS = [
  'C', 'Mn', 'P', 'S', 'Si', 'Ni', 'Cr', 'Mo', 'Cu', 'V', 'Nb', 'Al', 'Ti', 'N', 'Zn', 'Fe', 'Sn', 'Pb', 'Ca', 'Ta', 'W', 'Li', 'Co',
] as const;
const TRACAO_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'limite_escoamento', label: 'Limite de escoamento / Flow Limit (MPa)' },
  { key: 'limite_resistencia', label: 'Limite de resistência / Resistance Limit (MPa)' },
  { key: 'alongamento', label: 'Alongamento / Stretching (%)' },
  { key: 'estriccao', label: 'Estricção / Strictness (%)' },
  { key: 'dureza', label: 'Dureza' },
  { key: 'tratamento_termico', label: 'Tratamento térmico / Heat Treatment' },
];
const IMPACTO_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'norma', label: 'Norma / Standard' },
  { key: 'corpo_prova', label: 'Corpo de prova / Specimen' },
  { key: 'direcao', label: 'Direção corpo / Specimen Direction' },
  { key: 'posicao', label: 'Posição corpo / Specimen Position' },
  { key: 'temperatura', label: 'Temperatura / Temperature' },
  { key: 'corpo_prova_a', label: 'Corpo de prova A / Specimen A' },
  { key: 'corpo_prova_b', label: 'Corpo de prova B / Specimen B' },
  { key: 'corpo_prova_c', label: 'Corpo de prova C / Specimen C' },
  { key: 'media', label: 'Média / Average' },
];
const COMPONENTES_PADRAO = ['Corpo', 'Tampa/Castelo', 'Esfera', 'Haste', 'Porca', 'Prisioneiro', 'Sede/Vedação'];
const MOTIVOS_NAO_INCLUSAO = [
  'Cliente não solicitou certificado',
  'Item sem certificado fornecedor',
  'Item comercial/acessório',
  'Certificado será enviado separado',
  'Outro',
] as const;

const CONFIRMAR_CANCELAMENTO_CERTIFICADO_QUALIDADE =
  'Cancelar este certificado de qualidade?\n\n'
  + 'O registro permanece no sistema para rastreabilidade. O PDF passará a exibir a marca CANCELADO e não deve ser usado como documento válido.\n\n'
  + 'Deseja continuar?';

const AVISO_SEM_CF_MANUAL =
  'Sem Certificado do Fornecedor vinculado. Os dados técnicos deste CQ foram informados manualmente.';

const LABEL_OBRIGATORIO_EMITIR = ' *';

const emptyForm = (): Omit<CertificadoQualidade, 'id' | 'criado_em' | 'atualizado_em' | 'numero_formatado'> => ({
  numero: '',
  serie: '',
  cliente: null,
  cliente_nome_snapshot: '',
  cliente_cnpj_snapshot: '',
  pedido_cliente: '',
  nota_fiscal_numero: '',
  nota_fiscal: null,
  nota_fiscal_historica: null,
  data_emissao: '',
  observacoes: '',
  texto_padrao: TEXTO_PADRAO,
  status: 'rascunho',
  tipo_certificado: 'PADRAO_POR_NFE',
  itens: [],
});

const ensureMap = (v: unknown): Record<string, string> => {
  if (!v || typeof v !== 'object') return {};
  return Object.entries(v as Record<string, unknown>).reduce<Record<string, string>>((acc, [k, val]) => {
    acc[k] = val == null ? '' : String(val);
    return acc;
  }, {});
};

/** Trim, colapsa espaços e maiúsculas — alinhado ao critério de busca no certificado fornecedor. */
const normalizeCorridaLoteBusca = (raw: string) => raw.trim().replace(/\s+/g, ' ').toUpperCase();

/** FK `produto` pode vir como número ou (em edge cases) objeto serializado. */
const coerceProdutoItemId = (produto: ItemCertificadoQualidade['produto']): number | null => {
  if (produto == null || produto === '') return null;
  if (typeof produto === 'object' && produto !== null && 'id' in produto) {
    const id = Number((produto as { id: unknown }).id);
    return Number.isFinite(id) && id > 0 ? id : null;
  }
  const n = Number(produto);
  return Number.isFinite(n) && n > 0 ? n : null;
};

/** Divide quantidade total em n partes (3 casas); última(s) linha(s) absorve(m) resto do arredondamento. */
const redistribuirQuantidadeIgual = (total: number, n: number): number[] => {
  if (n <= 0) return [];
  const totalMilli = Math.round(total * 1000);
  if (n === 1) return [totalMilli / 1000];
  const baseMilli = Math.floor(totalMilli / n);
  const restoMilli = totalMilli - baseMilli * n;
  const shares = Array.from({ length: n }, () => baseMilli);
  for (let i = 0; i < restoMilli; i += 1) {
    shares[n - 1 - i] += 1;
  }
  return shares.map((m) => m / 1000);
};

/** Corrida/lote efetivos do CQ (campo manual + snapshots de rastreio); em válvula, complementa pelos componentes. */
const resolverCorridaLoteBuscaFornecedor = (item: ItemCertificadoQualidade) => {
  const corridaBruta = String(item.corrida || item.corrida_snapshot || '').trim();
  const loteBruto = String(item.lote || item.lote_snapshot || '').trim();
  let corrida = normalizeCorridaLoteBusca(corridaBruta);
  let lote = normalizeCorridaLoteBusca(loteBruto);
  if ((item.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES') {
    for (const comp of item.componentes || []) {
      if (!corrida) corrida = normalizeCorridaLoteBusca(String(comp.corrida || '').trim());
      if (!lote) lote = normalizeCorridaLoteBusca(String(comp.lote || '').trim());
      if (corrida && lote) break;
    }
  }
  return { corrida, lote };
};

const itemTemDadosTecnicosPreenchidos = (item: ItemCertificadoQualidade): boolean => {
  if ((item.norma || '').trim()) return true;
  if (Object.values(ensureMap(item.composicao_json)).some((v) => String(v || '').trim())) return true;
  if (Object.values(ensureMap(item.ensaio_tracao_json)).some((v) => String(v || '').trim())) return true;
  if (Object.values(ensureMap(item.ensaio_impacto_json)).some((v) => String(v || '').trim())) return true;
  if (item.certificado_fornecedor_origem_id) return true;
  return false;
};

const fornecedorResultadoSemProdutoVinculado = (src: DadosTecnicosFornecedorResultado) =>
  src.produto_match_tipo === 'sem_vinculo';

const normNumeric = (v: string) => v.replace(',', '.');
const parseBlockValues = (raw: string): string[] => {
  const line = (raw || '').trim();
  if (!line) return [];
  if (line.includes('\t')) return line.split('\t').map((x) => x.trim());
  if (line.includes(';')) return line.split(';').map((x) => x.trim());
  if (line.includes('|')) return line.split('|').map((x) => x.trim());
  return line.split(/\s+/).map((x) => x.trim());
};
const ensureComp = (raw: unknown, ordem = 1) => {
  const obj = (raw && typeof raw === 'object') ? (raw as Record<string, unknown>) : {};
  return {
    ordem: Number(obj.ordem || ordem),
    nome_componente: String(obj.nome_componente || ''),
    descricao_componente: String(obj.descricao_componente || ''),
    norma: String(obj.norma || ''),
    corrida: String(obj.corrida || ''),
    lote: String(obj.lote || ''),
    revisao_corrida: String(obj.revisao_corrida || ''),
    numero_certificado_fornecedor_componente: String(obj.numero_certificado_fornecedor_componente || ''),
    quantidade: obj.quantidade == null || obj.quantidade === '' ? null : Number(obj.quantidade),
    composicao_json: ensureMap(obj.composicao_json),
    ensaio_tracao_json: ensureMap(obj.ensaio_tracao_json),
    ensaio_impacto_json: ensureMap(obj.ensaio_impacto_json),
    observacoes: String(obj.observacoes || ''),
    ativo: obj.ativo !== false,
  };
};

const Certificados = () => {
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

  const itensComAvisoCfManual = useMemo(
    () => form.itens.filter(
      (it) => it.incluir_no_certificado !== false
        && (
          (it.rastreabilidade_avisos?.length ?? 0) > 0
          || it.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL')
          || (
            !it.tem_certificado_fornecedor
            && !it.certificado_fornecedor_origem_id
            && !it.item_certificado_fornecedor_origem_id
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
    setEditing(null);
    setForm(emptyForm());
    setNfeOpcaoSelecionada(null);
    setSaveError(null);
    setRastreabilidadeErros([]);
    setMensagens([]);
    setFornecedorBuscaItemMsg({});
    setModalOpen(true);
  };
  const openEdit = (c: CertificadoQualidade) => {
    setEditing(c);
    setForm({
      ...c,
      data_emissao: c.data_emissao || '',
      observacoes: c.observacoes || '',
      texto_padrao: c.texto_padrao || TEXTO_PADRAO,
      pedido_cliente: c.pedido_cliente || '',
      cliente_cnpj_snapshot: c.cliente_cnpj_snapshot || '',
      itens: (c.itens || []).map((it) => ({
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
    setNfeOpcaoSelecionada(null);
    if (c.nota_fiscal) {
      void certificadosQualidadeService.obterNfeOpcao(c.nota_fiscal).then((opt) => {
        if (opt) setNfeOpcaoSelecionada(opt);
        else {
          setNfeOpcaoSelecionada({
            id: c.nota_fiscal!,
            label_principal: c.nota_fiscal_numero
              ? `NF-e ${c.nota_fiscal_numero}`
              : `NF-e vinculada #${c.nota_fiscal}`,
            label_secundario: 'Documento legado — verifique elegibilidade',
            ambiente_badge: null,
            numero_nfe: '',
            serie_nfe: '',
            cliente_nome: c.cliente_nome_snapshot || '',
            data_emissao: c.data_emissao || null,
            status_emissao_sefaz: '',
            elegivel: false,
          });
        }
      });
    }
    setSaveError(null);
    setRastreabilidadeErros([]);
    setMensagens([]);
    setFornecedorBuscaItemMsg({});
    setModalOpen(true);
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
        setMensagens((m) => [
          ...m,
          'Nenhuma corrida/lote disponível encontrada para este produto cadastrado. Verifique entrada de estoque, conferência da NF-e de entrada ou certificado fornecedor.',
        ]);
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
    updateItem(idx, {
      corrida: source.corrida || item.corrida,
      lote: source.lote || item.lote || '',
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
      origem_observacoes: source.observacoes_origem || alertas.join(' | '),
    });
    if (alertas.length) {
      setMensagens((m) => [...m, ...alertas]);
    }
  };

  const valorSelecaoCorridaDisponivel = (c: CorridaDisponivelCertificadoQualidade) =>
    c.valor_selecao || `${c.corrida}||${c.lote || ''}`;

  const certificadoOrigemIdDeCorridaDisponivel = (c: CorridaDisponivelCertificadoQualidade) =>
    c.certificado_fornecedor_origem_id ?? c.certificado_fornecedor_id ?? null;

  const adicionarCorridaIrmaDesteCertificado = (idx: number) => {
    const item = formRef.current.itens[idx];
    const cfOrigemId = item.certificado_fornecedor_origem_id;
    if (!cfOrigemId) {
      setSaveError('Selecione uma corrida com certificado fornecedor vinculado antes de adicionar corridas irmãs.');
      return;
    }
    const produtoOrigemId = coerceProdutoItemId(item.produto);
    const pertenceAoGrupoProdutoCf = (it: ItemCertificadoQualidade) =>
      (it.certificado_fornecedor_origem_id ?? null) === cfOrigemId
      && coerceProdutoItemId(it.produto) === produtoOrigemId;
    setSaveError(null);
    const jaUsadas = new Set(
      formRef.current.itens
        .filter(pertenceAoGrupoProdutoCf)
        .map((it) => `${it.corrida || it.corrida_snapshot || ''}||${it.lote || it.lote_snapshot || ''}`),
    );
    const irmas = (corridasDisponiveisPorItem[idx] || []).filter(
      (c) => certificadoOrigemIdDeCorridaDisponivel(c) === cfOrigemId,
    );
    const disponiveis = irmas.filter((c) => !jaUsadas.has(valorSelecaoCorridaDisponivel(c)));
    if (!disponiveis.length) {
      setMensagens((m) => [...m, 'Não há outras corridas irmãs deste certificado para adicionar.']);
      return;
    }

    let escolhida = disponiveis[0];
    if (disponiveis.length > 1) {
      const opcoes = disponiveis
        .map((c, i) => `${i + 1}) ${c.corrida}${c.lote ? `/${c.lote}` : ''}`)
        .join('\n');
      const resp = window.prompt(`Escolha a corrida irmã para adicionar (número):\n${opcoes}`, '1');
      if (!resp) return;
      const pick = Number(resp) - 1;
      if (!Number.isFinite(pick) || pick < 0 || pick >= disponiveis.length) {
        setSaveError('Seleção inválida de corrida irmã.');
        return;
      }
      escolhida = disponiveis[pick];
    }

    const grupoIndicesAtuais = formRef.current.itens
      .map((it, i) => (pertenceAoGrupoProdutoCf(it) ? i : -1))
      .filter((i) => i >= 0);
    const somaGrupo = grupoIndicesAtuais.reduce(
      (acc, i) => acc + (Number(formRef.current.itens[i]?.quantidade) || 0),
      0,
    );
    const quantidadesRedistribuidas = redistribuirQuantidadeIgual(
      somaGrupo,
      grupoIndicesAtuais.length + 1,
    );

    const novoIdx = formRef.current.itens.length;
    const novoItem: ItemCertificadoQualidade = {
      ...item,
      id: undefined,
      ordem: novoIdx + 1,
      quantidade: quantidadesRedistribuidas[quantidadesRedistribuidas.length - 1] ?? 0,
      corrida: escolhida.corrida || '',
      lote: escolhida.lote || '',
      corrida_snapshot: escolhida.corrida || '',
      lote_snapshot: escolhida.lote || '',
      certificado_fornecedor_origem_id:
        escolhida.certificado_fornecedor_origem_id ?? escolhida.certificado_fornecedor_id ?? cfOrigemId,
      item_certificado_fornecedor_origem_id:
        escolhida.item_certificado_fornecedor_origem_id
        ?? escolhida.item_certificado_fornecedor_id
        ?? item.item_certificado_fornecedor_origem_id
        ?? null,
      numero_certificado_fornecedor_item_snapshot:
        escolhida.numero_certificado_fornecedor_item || escolhida.certificado_fornecedor || item.numero_certificado_fornecedor_item_snapshot || '',
      fornecedor_nome_snapshot: escolhida.fornecedor || item.fornecedor_nome_snapshot || '',
      nf_entrada_snapshot: escolhida.nf_entrada || item.nf_entrada_snapshot || '',
      origem_rastreabilidade_tipo: escolhida.origem || item.origem_rastreabilidade_tipo || 'certificado_fornecedor',
      origem_status_tecnico: escolhida.status_origem_tecnica || item.origem_status_tecnico || '',
      origem_observacoes: escolhida.observacoes_origem || item.origem_observacoes || '',
    };

    setForm((p) => {
      const itensAtualizados = [...p.itens, novoItem].map((it, i) => ({ ...it, ordem: i + 1 }));
      const grupoIndices = itensAtualizados
        .map((it, i) => (pertenceAoGrupoProdutoCf(it) ? i : -1))
        .filter((i) => i >= 0);
      grupoIndices.forEach((itemIdx, shareIdx) => {
        itensAtualizados[itemIdx] = {
          ...itensAtualizados[itemIdx],
          quantidade: quantidadesRedistribuidas[shareIdx] ?? itensAtualizados[itemIdx].quantidade,
        };
      });
      return { ...p, itens: itensAtualizados };
    });
    setCorridasDisponiveisPorItem((prev) => ({
      ...prev,
      [novoIdx]: prev[idx] || [],
    }));
    setMensagens((m) => [
      ...m,
      `Linha adicionada com corrida ${escolhida.corrida}${escolhida.lote ? `/${escolhida.lote}` : ''} do mesmo certificado fornecedor.`,
    ]);
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
      />
      {listError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {listLoading ? <TableSkeleton rows={6} cols={6} /> : null}
      {!listLoading && !listError ? (
        <DataTableShell>
        <DataTable className="text-sm">
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
                      <div className="flex flex-wrap justify-end gap-1">
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

      <Modal isOpen={modalOpen} onClose={closeCertModal} title={editing ? 'Editar certificado de qualidade' : 'Novo certificado de qualidade'} size="xl">
        {saveError ? <p className="text-sm text-destructive mb-2">{saveError}</p> : null}
        {rastreabilidadeErros.length > 0 ? (
          <div className="mb-3 rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <p className="font-medium mb-1">Pendências obrigatórias para emissão definitiva:</p>
            <ul className="list-disc pl-5 text-xs space-y-0.5">
              {rastreabilidadeErros.map((msg) => (
                <li key={msg}>{msg}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {form.status !== 'cancelado' && itensComAvisoCfManual.length > 0 ? (
          <div className="mb-3 rounded border border-sky-300/70 bg-sky-50/90 dark:border-sky-800 dark:bg-sky-950/25 px-3 py-2 text-sm text-sky-950 dark:text-sky-100">
            <p className="font-medium mb-1">Origem manual dos dados técnicos</p>
            <p className="text-xs">{AVISO_SEM_CF_MANUAL}</p>
          </div>
        ) : null}
        {mensagens.length ? (
          <div className="mb-2 text-xs text-amber-700 dark:text-amber-300">
            {mensagens.map((m) => <p key={m}>{m}</p>)}
          </div>
        ) : null}
        {editing?.status === 'cancelado' ? (
          <div className="mb-3 rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            Este certificado está cancelado. O registro permanece para rastreabilidade. Use ver ou baixar PDF para consulta — o documento exibe a marca CANCELADO.
          </div>
        ) : null}
        {editing?.status === 'emitido' ? (
          <div className="mb-3 rounded border border-amber-300/70 bg-amber-50/90 dark:bg-amber-950/25 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
            Certificado já emitido. Alterações podem divergir de cópias já enviadas ao cliente — revise com cuidado antes de salvar.
          </div>
        ) : null}
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
              <p className="text-xs text-muted-foreground mt-1">Número gerado automaticamente ao salvar.</p>
            ) : null}
          </div>
          <div><label className="erp-label">Série</label><input className="erp-input mt-1" value={form.serie} onChange={(e) => setF('serie', e.target.value)} /></div>
          <div><label className="erp-label">Data{LABEL_OBRIGATORIO_EMITIR}</label><input type="date" className="erp-input mt-1" value={form.data_emissao || ''} onChange={(e) => setF('data_emissao', e.target.value)} /></div>
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
            {editing?.status === 'cancelado' ? (
              <p className="text-xs text-muted-foreground mt-1">Status bloqueado após cancelamento.</p>
            ) : null}
          </div>
          <div className="md:col-span-2"><label className="erp-label">Cliente{LABEL_OBRIGATORIO_EMITIR}</label><input className="erp-input mt-1" value={form.cliente_nome_snapshot} onChange={(e) => setF('cliente_nome_snapshot', e.target.value)} /></div>
          <div><label className="erp-label">CNPJ Cliente</label><input className="erp-input mt-1" value={form.cliente_cnpj_snapshot || ''} onChange={(e) => setF('cliente_cnpj_snapshot', e.target.value)} /></div>
          <div><label className="erp-label">Pedido Cliente</label><input className="erp-input mt-1" value={form.pedido_cliente || ''} onChange={(e) => setF('pedido_cliente', e.target.value)} /></div>
        </div>

        <div className="mt-4 p-3 rounded border border-border bg-muted/20">
          <p className="text-sm font-medium">Carregar itens da NF-e de saída</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2">
            <div className="md:col-span-2">
              <label className="erp-label">NF-e de saída</label>
              <AsyncAutocomplete<NfeElegivelCqOpcao>
                value={form.nota_fiscal}
                selectedOption={nfeOpcaoSelecionada}
                placeholder="Buscar por número da NF-e ou cliente..."
                emptyMessage="Nenhuma NF-e autorizada encontrada."
                minChars={2}
                limit={20}
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
                onChange={selecionarNfeOperacional}
              />
              {nfeOpcaoSelecionada && !nfeOpcaoSelecionada.elegivel ? (
                <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                  Esta NF-e vinculada não está elegível pelas regras atuais (ex.: rascunho, cancelada ou sem
                  autorização fiscal). O registro legado é preservado; selecione uma NF-e autorizada para
                  alterar o vínculo.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground mt-1">
                  Somente NF-e de saída autorizadas (produção ou homologação) com número e série fiscais.
                </p>
              )}
            </div>
            <div>
              <label className="erp-label">NF-e saída histórica</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.nota_fiscal_historica || ''}
                onChange={(e) => {
                  const histId = e.target.value ? +e.target.value : null;
                  setNfeOpcaoSelecionada(null);
                  setF('nota_fiscal_historica', histId);
                  setF('nota_fiscal', null);
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
              <button type="button" className="erp-btn-outline w-full md:w-auto" onClick={() => void carregarPorNFe()}>
                Carregar itens da NF-e
              </button>
            </div>
          </div>
        </div>

        {form.status !== 'cancelado' ? (
          <div className="mt-4 rounded border border-border p-3 bg-muted/10">
            <p className="text-sm font-medium mb-2">Rastreabilidade técnica</p>
            {resumoRastreabilidade ? (
              <div className="flex flex-wrap gap-2 text-xs mb-2">
                <span className="erp-badge-success">Completa: {resumoRastreabilidade.completos}</span>
                <span className="erp-badge-warning">Parcial: {resumoRastreabilidade.parciais}</span>
                <span className="erp-badge-danger">Pendente: {resumoRastreabilidade.pendentes}</span>
                {resumoRastreabilidade.pode_emitir ? (
                  <span className="text-emerald-700 dark:text-emerald-400">Pronto para emissão definitiva</span>
                ) : (
                  <span className="text-amber-800 dark:text-amber-300">
                    A emissão definitiva exige rastreabilidade completa em todos os itens incluídos.
                  </span>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground mb-2">
                Salve o certificado para calcular o resumo de rastreabilidade no servidor.
              </p>
            )}
          </div>
        ) : null}

        <div className="mt-4">
          <p className="text-sm font-medium mb-2">Itens e dados técnicos (manual assistido)</p>
          <div className="mb-2 text-xs">
            <span className="text-muted-foreground">
              Itens: {totalItens} total | {incluidosCount} incluídos
              {naoIncluidosCount > 0 ? ` | ${naoIncluidosCount} não incluído${naoIncluidosCount > 1 ? 's' : ''}` : ''}
            </span>
            {incluidosCount === 0 && totalItens > 0 ? (
              <p className="mt-1 text-amber-700 dark:text-amber-300">
                Nenhum item incluído no certificado. Para emitir, inclua pelo menos um item.
              </p>
            ) : null}
          </div>
          <div className="space-y-3 max-h-[40vh] overflow-auto pr-1">
            {form.itens.map((it, idx) => (
              <details
                key={idx}
                className={`rounded border p-3 ${it.incluir_no_certificado === false ? 'border-amber-300 bg-amber-50/30 dark:border-amber-700 dark:bg-amber-900/10' : 'border-border'}`}
                open
              >
                <summary className="cursor-pointer text-sm font-medium">
                  <span className="inline-flex items-center gap-2">
                    <span>Item {it.ordem || idx + 1} - {it.codigo_produto || 'Sem código'} - {it.descricao_material || 'Sem descrição'}</span>
                    {it.incluir_no_certificado === false ? (
                      <span className="erp-badge-warning">Não incluído</span>
                    ) : (
                      <span className="erp-badge-success">Incluído</span>
                    )}
                    {it.incluir_no_certificado !== false && it.rastreabilidade_status ? (
                      <span className={`${rastreabilidadeCqBadge(it.rastreabilidade_status).className} text-[10px]`}>
                        {it.rastreabilidade_label || rastreabilidadeCqBadge(it.rastreabilidade_status).label}
                      </span>
                    ) : null}
                  </span>
                </summary>
                {it.incluir_no_certificado !== false && (it.rastreabilidade_avisos?.length ?? 0) > 0 ? (
                  <ul className="text-[11px] text-sky-800 dark:text-sky-300 mt-1 mb-2 list-disc pl-5">
                    {it.rastreabilidade_avisos!.map((msg) => (
                      <li key={msg}>{msg}</li>
                    ))}
                  </ul>
                ) : null}
                {it.incluir_no_certificado !== false && (it.rastreabilidade_mensagens?.length ?? 0) > 0 ? (
                  <ul className="text-[11px] text-amber-800 dark:text-amber-300 mt-1 mb-2 list-disc pl-5">
                    {it.rastreabilidade_mensagens!.map((msg) => (
                      <li key={msg}>{msg}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
                  <div><label className="erp-label">Ordem</label><input className="erp-input mt-1" value={it.ordem} onChange={(e) => updateItem(idx, { ordem: +e.target.value })} /></div>
                  <div><label className="erp-label">Código</label><input className="erp-input mt-1" value={it.codigo_produto} onChange={(e) => updateItem(idx, { codigo_produto: e.target.value })} /></div>
                  <div className="md:col-span-2"><label className="erp-label">Descrição{LABEL_OBRIGATORIO_EMITIR}</label><input className="erp-input mt-1" value={it.descricao_material} onChange={(e) => updateItem(idx, { descricao_material: e.target.value })} /></div>
                  <div><label className="erp-label">Qtd</label><input className="erp-input mt-1" value={it.quantidade} onChange={(e) => updateItem(idx, { quantidade: +e.target.value })} /></div>
                  <div><label className="erp-label">Un</label><input className="erp-input mt-1" value={it.unidade} onChange={(e) => updateItem(idx, { unidade: e.target.value })} /></div>
                  <div><label className="erp-label">Norma{LABEL_OBRIGATORIO_EMITIR}</label><input className="erp-input mt-1" value={it.norma} onChange={(e) => updateItem(idx, { norma: e.target.value })} /></div>
                  <div><label className="erp-label">Lote{LABEL_OBRIGATORIO_EMITIR}</label><input className="erp-input mt-1" value={it.lote || ''} onChange={(e) => updateItem(idx, { lote: e.target.value })} /></div>
                  <div><label className="erp-label">NCM</label><input className="erp-input mt-1" value={it.ncm || ''} onChange={(e) => updateItem(idx, { ncm: e.target.value })} /></div>
                  <div className="md:col-span-3">
                    <label className="erp-label">Tipo de dados técnicos</label>
                    <select
                      className="erp-select mt-1 w-full"
                      value={it.tipo_dados_tecnicos || 'PADRAO_ITEM'}
                      onChange={(e) => updateItem(idx, { tipo_dados_tecnicos: e.target.value as 'PADRAO_ITEM' | 'VALVULA_COMPONENTES' })}
                    >
                      <option value="PADRAO_ITEM">Dados por item</option>
                      <option value="VALVULA_COMPONENTES">Dados por componentes de válvula</option>
                    </select>
                  </div>
                  <div className="md:col-span-6 rounded border border-border p-2 bg-muted/10">
                    <p className="text-xs font-semibold mb-2">Rastreabilidade por produto cadastrado + Corrida/Lote</p>
                    {it.produto ? (
                      <div className="text-xs mb-2">
                        <p>
                          Produto cadastrado: {it.produto_codigo || '—'} - {it.produto_descricao || '—'}
                          {it.produto_ncm_efetivo ? ` | NCM efetivo: ${it.produto_ncm_efetivo}` : ''}
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-amber-700 dark:text-amber-300 mb-2">
                        Este item da NF-e ainda não está vinculado a um produto cadastrado. Vincule o produto para listar corridas disponíveis.
                      </p>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <div className="md:col-span-2">
                        <label className="erp-label">Selecionar produto cadastrado (autocomplete)</label>
                        <input
                          className="erp-input mt-1"
                          placeholder="Digite código ou descrição"
                          value={produtoBusca[idx] ?? (it.produto ? `${it.produto_codigo || ''} - ${it.produto_descricao || ''}` : '')}
                          onChange={(e) => void buscarProdutosParaItem(idx, e.target.value)}
                        />
                        {(produtoResultados[idx] || []).length > 0 ? (
                          <div className="mt-1 rounded border border-border max-h-32 overflow-auto bg-background">
                            {(produtoResultados[idx] || []).map((p) => (
                              <button
                                key={p.id}
                                type="button"
                                className="w-full text-left px-2 py-1 text-xs hover:bg-muted"
                                onClick={() => void vincularProdutoAoItem(idx, p)}
                              >
                                {p.codigo_completo} - {p.descricao}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex items-end">
                        <button type="button" className="erp-btn-outline w-full" disabled={!it.produto} onClick={() => void carregarCorridasDoItem(idx)}>
                          Listar corridas
                        </button>
                      </div>
                    </div>
                    <div className="mt-2">
                      <label className="erp-label">Corrida/Lote disponível</label>
                      <select
                        className="erp-select mt-1 w-full"
                        value={
                          (() => {
                            const list = corridasDisponiveisPorItem[idx] || [];
                            const corrEff = it.corrida || it.corrida_snapshot || '';
                            const loteEff = it.lote || it.lote_snapshot || '';
                            const match = list.find(
                              (c) => c.corrida === corrEff && (c.lote || '') === (loteEff || ''),
                            );
                            return match?.valor_selecao || `${corrEff}||${loteEff}`;
                          })()
                        }
                        onChange={(e) => {
                          const selected = e.target.value;
                          if (!selected) {
                            updateItem(idx, { corrida: '', lote: '' });
                            return;
                          }
                          const [cPart, lPart] = selected.split('||');
                          updateItem(idx, { corrida: cPart || '', lote: lPart || '' });
                          aplicarCorridaDisponivel(idx, selected);
                        }}
                        disabled={!coerceProdutoItemId(it.produto)}
                      >
                        <option value="">Selecione a corrida disponível...</option>
                        {(() => {
                          const list = corridasDisponiveisPorItem[idx] || [];
                          const corrEff = it.corrida || it.corrida_snapshot || '';
                          const loteEff = it.lote || it.lote_snapshot || '';
                          const manualVal = `${corrEff}||${loteEff}`;
                          const inList = list.some(
                            (c) => (c.valor_selecao || `${c.corrida}||${c.lote || ''}`) === manualVal,
                          );
                          const extra =
                            corrEff || loteEff
                              ? !inList && manualVal !== '||'
                                ? (
                                    <option key={`__manual_cq__-${idx}`} value={manualVal}>
                                      Corrida/lote manual: {corrEff}
                                      {loteEff ? ` / ${loteEff}` : ''}
                                    </option>
                                  )
                                : null
                              : null;
                          return (
                            <>
                              {extra}
                              {list.map((c) => (
                                <option
                                  key={c.valor_selecao || `${c.corrida}-${c.lote || ''}`}
                                  value={c.valor_selecao || `${c.corrida}||${c.lote || ''}`}
                                >
                                  {c.corrida}
                                  {c.lote ? `/${c.lote}` : ''}
                                  {c.saldo ? ` - Saldo: ${c.saldo} ${c.unidade || ''}` : ''}
                                  {c.fornecedor ? ` - ${c.fornecedor}` : ''}
                                  {c.nf_entrada ? ` - NF ${c.nf_entrada}` : ''}
                                  {c.certificado_fornecedor ? ` - Cert. Forn. ${c.certificado_fornecedor}` : ''}
                                  {c.status_certificado_fornecedor === 'rascunho' ? ' - Rascunho' : ''}
                                </option>
                              ))}
                            </>
                          );
                        })()}
                      </select>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={
                            !coerceProdutoItemId(it.produto)
                            || !it.certificado_fornecedor_origem_id
                            || editing?.status === 'cancelado'
                          }
                          title={
                            !it.certificado_fornecedor_origem_id
                              ? 'Selecione uma corrida vinculada a um certificado fornecedor.'
                              : 'Adiciona nova linha do item com outra corrida/lote do mesmo certificado fornecedor.'
                          }
                          onClick={() => adicionarCorridaIrmaDesteCertificado(idx)}
                        >
                          + Adicionar corrida deste certificado
                        </button>
                      </div>
                      {!coerceProdutoItemId(it.produto) ? null : (corridasDisponiveisPorItem[idx] || []).length === 0 ? (
                        <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                          Nenhuma corrida/lote disponível encontrada para este produto cadastrado.
                          Verifique entrada de estoque, conferência da NF-e de entrada ou certificado fornecedor.
                        </p>
                      ) : null}
                      <p className="text-xs text-muted-foreground mt-1">
                        Se necessário, informe corrida e lote manualmente (campos acima e abaixo). Use «Buscar dados do fornecedor» com produto + corrida/lote para carregar dados técnicos do certificado de fornecedor registrado. Se o item do fornecedor não tiver produto vinculado, será exibido aviso para conferência antes de aplicar. Não é obrigatório escolher na lista de corridas disponíveis.
                      </p>
                      <div className="flex flex-col sm:flex-row gap-2 mt-1 sm:items-end">
                        <div className="flex-1">
                          <label className="erp-label">Corrida manual{LABEL_OBRIGATORIO_EMITIR}</label>
                          <input
                            className="erp-input mt-1"
                            placeholder="Ex.: HEN-001"
                            value={it.corrida || it.corrida_snapshot || ''}
                            onChange={(e) => {
                              const v = e.target.value;
                              updateItem(idx, {
                                corrida: v,
                                origem_rastreabilidade_tipo: 'manual',
                                ...(v.trim() === '' ? { corrida_snapshot: '' } : {}),
                              });
                            }}
                          />
                        </div>
                        <button
                          type="button"
                          className="erp-btn-outline shrink-0"
                          disabled={fornecedorBuscaItemLoading === idx || editing?.status === 'cancelado'}
                          title={
                            editing?.status === 'cancelado'
                              ? 'Certificado cancelado: apenas consulta.'
                              : 'Busca por produto + corrida/lote (e código/descrição do item). Itens do fornecedor sem produto vinculado exigem confirmação antes de aplicar.'
                          }
                          onClick={() => void buscarDadosFornecedor(idx)}
                        >
                          {fornecedorBuscaItemLoading === idx ? 'Buscando…' : 'Buscar dados do fornecedor'}
                        </button>
                      </div>
                      {fornecedorBuscaItemMsg[idx] ? (
                        <p
                          className={
                            fornecedorBuscaItemMsg[idx].type === 'error'
                              ? 'text-sm text-destructive mt-2'
                              : 'text-sm text-amber-800 dark:text-amber-200 mt-2'
                          }
                          role={fornecedorBuscaItemMsg[idx].type === 'error' ? 'alert' : 'status'}
                        >
                          {fornecedorBuscaItemMsg[idx].text}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <div className="md:col-span-6 rounded border border-border p-2">
                    <label className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={it.incluir_no_certificado !== false}
                        onChange={(e) => updateItem(idx, { incluir_no_certificado: e.target.checked })}
                      />
                      Incluir no certificado
                    </label>
                    {it.incluir_no_certificado === false ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                        <div>
                          <label className="erp-label">Motivo da não inclusão</label>
                          <select
                            className="erp-select mt-1 w-full"
                            value={it.motivo_nao_inclusao || ''}
                            onChange={(e) => updateItem(idx, { motivo_nao_inclusao: e.target.value })}
                          >
                            <option value="">Selecione...</option>
                            {MOTIVOS_NAO_INCLUSAO.map((m) => <option key={m} value={m}>{m}</option>)}
                          </select>
                        </div>
                        <div>
                          <label className="erp-label">Observação interna</label>
                          <input
                            className="erp-input mt-1"
                            value={it.observacao_nao_inclusao || ''}
                            onChange={(e) => updateItem(idx, { observacao_nao_inclusao: e.target.value })}
                          />
                        </div>
                        <div className="md:col-span-2 text-xs text-amber-700 dark:text-amber-300">
                          Não incluído{it.motivo_nao_inclusao ? ` — Motivo: ${it.motivo_nao_inclusao}` : ''}.
                        </div>
                      </div>
                    ) : null}
                  </div>
                  {it.incluir_no_certificado !== false && it.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' && (
                    <div className="md:col-span-6 rounded border border-border p-2 bg-muted/10">
                      <p className="text-xs text-muted-foreground mb-2">
                        Para buscar componentes no certificado de fornecedor, informe corrida/lote no item (acima) ou corrida nos componentes e use «Buscar dados do fornecedor» na seção Rastreabilidade.
                      </p>
                      <div className="flex flex-wrap gap-2 items-center justify-between mb-2">
                        <p className="text-xs font-semibold">Componentes da válvula</p>
                        <div className="flex gap-2">
                          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => adicionarComponentesPadrao(idx)}>
                            Adicionar componentes padrão
                          </button>
                          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => addComponente(idx)}>
                            Adicionar componente
                          </button>
                        </div>
                      </div>
                      {(it.componentes || []).length === 0 ? (
                        <p className="text-xs text-amber-700 dark:text-amber-300">
                          Este item está marcado como válvula, mas ainda não possui componentes.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {(it.componentes || []).map((cp, cidx) => (
                            <details key={cidx} className="rounded border border-border p-2" open>
                              <summary className="cursor-pointer text-xs font-medium">
                                Componente {cp.ordem} - {cp.nome_componente || 'Sem nome'}
                              </summary>
                              <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mt-2">
                                <div><label className="erp-label">Ordem</label><input className="erp-input mt-1" value={cp.ordem} onChange={(e) => {
                                  const comps = [...(it.componentes || [])];
                                  comps[cidx] = { ...comps[cidx], ordem: +e.target.value };
                                  updateItem(idx, { componentes: comps });
                                }} /></div>
                                <div><label className="erp-label">Componente</label><input className="erp-input mt-1" value={cp.nome_componente} onChange={(e) => {
                                  const comps = [...(it.componentes || [])];
                                  comps[cidx] = { ...comps[cidx], nome_componente: e.target.value };
                                  updateItem(idx, { componentes: comps });
                                }} /></div>
                                <div className="md:col-span-2"><label className="erp-label">Descrição</label><input className="erp-input mt-1" value={cp.descricao_componente || ''} onChange={(e) => {
                                  const comps = [...(it.componentes || [])];
                                  comps[cidx] = { ...comps[cidx], descricao_componente: e.target.value };
                                  updateItem(idx, { componentes: comps });
                                }} /></div>
                                <div><label className="erp-label">Norma</label><input className="erp-input mt-1" value={cp.norma || ''} onChange={(e) => {
                                  const comps = [...(it.componentes || [])];
                                  comps[cidx] = { ...comps[cidx], norma: e.target.value };
                                  updateItem(idx, { componentes: comps });
                                }} /></div>
                                <div><label className="erp-label">Corrida</label><input className="erp-input mt-1" value={cp.corrida || ''} onChange={(e) => {
                                  const comps = [...(it.componentes || [])];
                                  comps[cidx] = { ...comps[cidx], corrida: e.target.value };
                                  updateItem(idx, { componentes: comps });
                                }} /></div>
                                <div className="md:col-span-6 flex flex-wrap gap-2">
                                  <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => copiarComponenteAnterior(idx, cidx)}>Copiar componente anterior</button>
                                  <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => duplicarComponente(idx, cidx)}>Duplicar componente</button>
                                  <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => removeComponente(idx, cidx)}>Remover componente</button>
                                </div>
                                <div className="md:col-span-6 rounded border border-border p-2">
                                  <p className="text-xs font-semibold mb-2">Composição química do componente</p>
                                  <div className="grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2">
                                    {COMPOSICAO_FIELDS.map((el) => (
                                      <div key={el}>
                                        <label className="erp-label">{el}</label>
                                        <input
                                          className="erp-input mt-1"
                                          placeholder="***"
                                          value={ensureMap(cp.composicao_json)[el] || ''}
                                          onChange={(e) => updateCompField(idx, cidx, 'composicao_json', el, normNumeric(e.target.value))}
                                        />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                                <div className="md:col-span-6 rounded border border-border p-2">
                                  <p className="text-xs font-semibold mb-2">Tração do componente</p>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {TRACAO_FIELDS.map((f) => (
                                      <div key={f.key}>
                                        <label className="erp-label">{f.label}</label>
                                        <input
                                          className="erp-input mt-1"
                                          value={ensureMap(cp.ensaio_tracao_json)[f.key] || ''}
                                          onChange={(e) => updateCompField(idx, cidx, 'ensaio_tracao_json', f.key, normNumeric(e.target.value))}
                                        />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </details>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {it.incluir_no_certificado !== false && it.tipo_dados_tecnicos !== 'VALVULA_COMPONENTES' && (
                    <>
                  <div className="md:col-span-6 flex flex-wrap gap-2 mt-1">
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => { setFornecedorTargetIdx(idx); const cq = formRef.current.itens[idx]; setFornecedorFiltro((p) => ({ ...p, corrida: cq?.corrida || cq?.corrida_snapshot || '' })); setFornecedorBuscaAvancadaOpen(true); }}>
                      Buscar dados técnicos avançado
                    </button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => copyTecnicoFromPrevious(idx)}>Copiar dados técnicos do item anterior</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => clearTecnico(idx)}>Limpar dados técnicos</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => clearComposicao(idx)}>Limpar composição</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => clearTracao(idx)}>Limpar tração</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => duplicateComposicaoToAll(idx)}>Duplicar composição para todos os itens</button>
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => duplicateTracaoToAll(idx)}>Duplicar tração para todos os itens</button>
                  </div>
                  <div className="md:col-span-6 rounded border border-border p-2">
                    <div className="flex items-center justify-between mb-2 gap-2">
                      <p className="text-xs font-semibold">Composição química{LABEL_OBRIGATORIO_EMITIR}</p>
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm"
                        onClick={() => {
                          setPasteCompIdx((cur) => (cur === idx ? null : idx));
                          setPasteCompText('');
                        }}
                      >
                        Colar composição em bloco
                      </button>
                    </div>
                    {pasteCompIdx === idx && (
                      <div className="mb-2 rounded border border-border p-2 bg-muted/20">
                        <p className="text-xs text-muted-foreground mb-1">
                          Cole uma linha (Excel/tabulado) na ordem:
                          {' '}
                          {COMPOSICAO_FIELDS.join(', ')}.
                        </p>
                        <textarea
                          className="erp-input h-16"
                          value={pasteCompText}
                          onChange={(e) => setPasteCompText(e.target.value)}
                        />
                        <div className="flex gap-2 mt-2">
                          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => applyCompositionBlock(idx)}>
                            Aplicar na grade
                          </button>
                          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => { setPasteCompIdx(null); setPasteCompText(''); }}>
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}
                    <div className="grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2">
                      {COMPOSICAO_FIELDS.map((el) => (
                        <div key={el}>
                          <label className="erp-label">{el}</label>
                          <input
                            className="erp-input mt-1"
                            placeholder="***"
                            value={ensureMap(it.composicao_json)[el] || ''}
                            onChange={(e) => updateJsonField(idx, 'composicao_json', el, normNumeric(e.target.value))}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="md:col-span-6 rounded border border-border p-2">
                    <p className="text-xs font-semibold mb-2">Teste de tração{LABEL_OBRIGATORIO_EMITIR}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {TRACAO_FIELDS.map((f) => (
                        <div key={f.key}>
                          <label className="erp-label">{f.label}</label>
                          <input
                            className="erp-input mt-1"
                            value={ensureMap(it.ensaio_tracao_json)[f.key] || ''}
                            onChange={(e) => updateJsonField(idx, 'ensaio_tracao_json', f.key, normNumeric(e.target.value))}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="md:col-span-6 rounded border border-border p-2">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-semibold">Teste de impacto</p>
                      <label className="text-xs flex items-center gap-1">
                        <input
                          type="checkbox"
                          checked={ensureMap(it.ensaio_impacto_json).informar_impacto === 'true'}
                          onChange={(e) => {
                            const map = ensureMap(form.itens[idx].ensaio_impacto_json);
                            map.informar_impacto = e.target.checked ? 'true' : '';
                            if (!e.target.checked) {
                              IMPACTO_FIELDS.forEach((f) => { map[f.key] = ''; });
                              map.nao_aplicavel = 'true';
                            } else {
                              map.nao_aplicavel = '';
                            }
                            updateItem(idx, { ensaio_impacto_json: map });
                          }}
                        />
                        Informar teste de impacto
                      </label>
                    </div>
                    {ensureMap(it.ensaio_impacto_json).informar_impacto !== 'true' ? (
                      <p className="text-xs text-muted-foreground">Impacto oculto por padrão (não aplicável no uso diário).</p>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {IMPACTO_FIELDS.map((f) => (
                          <div key={f.key}>
                            <label className="erp-label">{f.label}</label>
                            <input
                              className="erp-input mt-1"
                              value={ensureMap(it.ensaio_impacto_json)[f.key] || ''}
                              onChange={(e) => updateJsonField(idx, 'ensaio_impacto_json', f.key, normNumeric(e.target.value))}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                    </>
                  )}
                  <div className="md:col-span-3"><label className="erp-label">Observações item</label><input className="erp-input mt-1" value={it.observacoes_item || ''} onChange={(e) => updateItem(idx, { observacoes_item: e.target.value })} /></div>
                </div>
              </details>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <label className="erp-label">Observações</label>
          <textarea className="erp-input mt-1 h-20" value={form.observacoes || ''} onChange={(e) => setF('observacoes', e.target.value)} />
        </div>
        <div className="mt-2">
          <label className="erp-label">Texto padrão final</label>
          <textarea className="erp-input mt-1 h-20" value={form.texto_padrao || ''} onChange={(e) => setF('texto_padrao', e.target.value)} />
        </div>

        <div className="flex flex-wrap justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" className="erp-btn-outline" onClick={closeCertModal}>Fechar</button>
          <button
            type="button"
            className="erp-btn-outline"
            onClick={() => void salvar(false)}
            title={titleSalvarQualidadeSemEmitir()}
          >
            {labelSalvarQualidadeSemEmitir()}
          </button>
          <button
            type="button"
            className="erp-btn-outline"
            onClick={() => void visualizarPreviaPdf()}
            disabled={modalPdfBusy || editing?.status === 'cancelado'}
            title={
              editing?.status === 'cancelado'
                ? 'Prévia indisponível para certificado cancelado.'
                : 'Gera prévia a partir do rascunho atual (salva automaticamente antes). Prévia permitida mesmo com rastreabilidade pendente.'
            }
          >
            {modalPdfBusy ? 'Gerando prévia…' : 'Prévia PDF (rascunho)'}
          </button>
          {form.status !== 'cancelado' && resumoRastreabilidade && !resumoRastreabilidade.pode_emitir ? (
            <p className="w-full text-xs text-amber-800 dark:text-amber-300 text-right mt-1">
              Prévia permitida. A emissão definitiva exige rastreabilidade completa.
            </p>
          ) : null}
          {editing?.id ? (
            <button
              type="button"
              className="erp-btn-outline"
              onClick={() => void visualizarOuBaixarPdf(editing.id, form.status === 'rascunho', true, {
                numero: numeroArquivoAtual(),
                cliente: form.cliente_nome_snapshot,
                nf: form.nota_fiscal_numero,
              })}
              disabled={modalPdfBusy}
              title={
                form.status === 'cancelado'
                  ? 'Baixar PDF do certificado cancelado (marca CANCELADO).'
                  : 'Baixar PDF conforme o status atual.'
              }
            >
              Baixar PDF
            </button>
          ) : null}
          <button
            type="button"
            className="erp-btn-primary"
            disabled={form.status === 'cancelado' || modalPdfBusy}
            title={form.status === 'cancelado' ? 'Não é possível emitir um certificado cancelado.' : 'Valida itens incluídos e grava como emitido.'}
            onClick={() => {
              const itensIncluidos = form.itens.filter((it) => it.incluir_no_certificado !== false);
              if (!itensIncluidos.length) {
                setSaveError('Inclua ao menos um item no certificado antes de emitir.');
                return;
              }
              const existemNaoIncluidos = form.itens.some((it) => it.incluir_no_certificado === false);
              if (existemNaoIncluidos) {
                const okParcial = window.confirm(
                  `${naoIncluidosCount} de ${totalItens} item${totalItens > 1 ? 'ns' : ''} não será exibido no certificado. Deseja continuar?`,
                );
                if (!okParcial) return;
              }
              void salvar(true);
            }}
          >
            Emitir / finalizar
          </button>
        </div>
      </Modal>

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
        <div className="flex justify-end gap-2 mt-4">
          <button type="button" className="erp-btn-outline" onClick={() => setFornecedorBuscaAvancadaOpen(false)}>Cancelar</button>
          <button type="button" className="erp-btn-primary" onClick={() => void buscarDadosFornecedorAvancado()}>Buscar</button>
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
                  className="erp-btn-primary erp-btn-sm"
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
    </div>
  );
};

export default Certificados;
