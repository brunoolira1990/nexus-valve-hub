import { Fragment, useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { Pencil } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { formatApiErrors } from '@/lib/apiErrors';
import { certificadoFornecedorStatusBadge } from '@/lib/certificadoStatusUi';
import {
  AVISO_DADOS_HERDADOS_CORRIDA_CF,
  MSG_MULTIPLOS_CERTIFICADOS_COMPATIVEIS_CF,
  TEXTO_EXPLICATIVO_CORRIDAS_ADICIONAIS_CF,
  TITULO_CORRIDAS_ADICIONAIS_CF,
  avisosCorridasAdicionaisItemCf,
  errosCorridasAdicionaisItemCf,
  resumoQuantidadesCorridasItemCf,
} from '@/lib/cfCorridasAdicionaisUi';
import {
  certificadosFornecedorService,
  corridaLoteEfetivosResultadoFornecedor,
  mensagemPrincipalBuscaDadosTecnicosFornecedor,
} from '@/services/api/certificadosFornecedor';
import { apiErrorMessage } from '@/services/api/config';
import { nfeEntradasService } from '@/services/api/fiscal';
import { nfeEntradaHistoricaImportadaService, type NFeEntradaHistoricaList } from '@/services/api/nfeEntradaHistoricaImportada';
import type {
  CertificadoFornecedorEntrada,
  CertificadoFornecedorStatus,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoFornecedorCorrida,
  ItemCertificadoFornecedorEntrada,
  NFeEntrada,
} from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import type { ListQueryParams } from '@/lib/apiList';

/**
 * Fase E.4 (Qualidade): permissões só no backend; JWT sem codenames Django.
 * «Novo» some apenas se o GET da lista for 403. Erros de gravação usam `formatApiErrors`
 * (403 → mensagem de permissão). Evolução: /me/permissions ou claims no token.
 */

const COMPOSICAO_FIELDS = ['C', 'Mn', 'P', 'S', 'Si', 'Ni', 'Cr', 'Mo', 'Cu', 'V', 'Nb', 'Al', 'Ti', 'N', 'Zn', 'Fe', 'Sn', 'Pb', 'Ca', 'Ta', 'W', 'Li', 'Co'] as const;
const TRACAO_FIELDS = [
  { key: 'limite_escoamento', label: 'Limite de escoamento' },
  { key: 'limite_resistencia', label: 'Limite de resistência' },
  { key: 'alongamento', label: 'Alongamento' },
  { key: 'estriccao', label: 'Estricção' },
  { key: 'dureza', label: 'Dureza' },
  { key: 'tratamento_termico', label: 'Tratamento térmico' },
] as const;
const COMPONENTES_PADRAO_VALVULA = ['CORPO', 'ESFERA', 'HASTE', 'PORCA', 'PRISIONEIRO', 'TAMPA', 'SEDE', 'VEDAÇÃO', 'OUTROS'] as const;

const CONFIRMAR_CANCELAMENTO_CERTIFICADO_FORNECEDOR =
  'Cancelar este certificado de fornecedor?\n\n'
  + 'O registro permanece no sistema para rastreabilidade e consulta.\n\n'
  + 'Deseja continuar?';

type JsonFieldProps = {
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  idPrefix: string;
};

const ComposicaoQuimicaFields = ({ values, onChange, idPrefix }: JsonFieldProps) => (
  <div className="grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2">
    {COMPOSICAO_FIELDS.map((f) => (
      <div key={`${idPrefix}-cq-${f}`}>
        <label className="erp-label">{f}</label>
        <input
          className="erp-input mt-1"
          placeholder="***"
          value={values[f] || ''}
          onChange={(e) => onChange(f, e.target.value)}
        />
      </div>
    ))}
  </div>
);

const PropriedadesMecanicasFields = ({ values, onChange, idPrefix }: JsonFieldProps) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
    {TRACAO_FIELDS.map((f) => (
      <div key={`${idPrefix}-pm-${f.key}`}>
        <label className="erp-label">{f.label}</label>
        <input
          className="erp-input mt-1"
          value={values[f.key] || ''}
          onChange={(e) => onChange(f.key, e.target.value)}
        />
      </div>
    ))}
  </div>
);

type NFeResumo = {
  numero: string;
  serie?: string;
  fornecedor: string;
  fornecedorCnpj: string;
  emissao?: string;
  valorTotal?: number;
  chaveAcesso?: string;
};

type OrigemRastreabilidadeResumo = {
  temVinculo: boolean;
  produtoNaConferencia: boolean;
  origemCompleta: boolean;
  nfNumero: string;
  nfSerie: string;
  itemNf: string;
  statusConferenciaLabel: string;
  corridaHerdada: string;
  loteHerdado: string;
  pedidoNumero: string;
  itemPedidoId: string;
  produtoPedidoCodigo: string;
  produtoPedidoDescricao: string;
  quantidadePedido: string;
  unidadePedido: string;
  mensagem: string;
  badgeClass: string;
  badgeText: string;
};

const LABEL_STATUS_CONFERENCIA: Record<string, string> = {
  PENDENTE_PRODUTO: 'Pendente produto',
  PRODUTO_VINCULADO: 'Produto vinculado',
  CONFERIDO: 'Conferido',
  DIVERGENTE: 'Divergente',
  IGNORADO: 'Ignorado',
};

function labelStatusConferencia(status: string | null | undefined): string {
  if (!status) return '—';
  return LABEL_STATUS_CONFERENCIA[status] || status;
}

function resumoOrigemItemCf(
  it: ItemCertificadoFornecedorEntrada,
  form: Pick<CertificadoFornecedorEntrada, 'numero_nf_entrada' | 'serie_nf_entrada'>,
): OrigemRastreabilidadeResumo {
  const temVinculo = Boolean(it.item_conferencia_id);
  const produtoNaConferencia = Boolean(it.origem_produto_vinculado);
  const nfNumero = it.origem_nfe_numero || form.numero_nf_entrada || '—';
  const nfSerie = it.origem_nfe_serie || form.serie_nf_entrada || '—';
  const itemNf = it.origem_nfe_item_numero != null ? String(it.origem_nfe_item_numero) : '—';
  const corridaHerdada = (it.corrida || '').trim();
  const loteHerdado = (it.lote || '').trim();
  const statusConferenciaLabel = labelStatusConferencia(it.origem_conferencia_status);
  const origemCompleta = Boolean(it.origem_rastreabilidade_completa);
  const pedidoNumero = it.pedido_compra_numero || it.item_pedido_resumo?.pedido_numero || '—';
  const itemPedidoId = it.item_pedido_compra_id != null ? String(it.item_pedido_compra_id) : '—';
  const produtoPedidoCodigo = it.produto_pedido_codigo || it.item_pedido_resumo?.codigo || '—';
  const produtoPedidoDescricao = it.produto_pedido_descricao || it.item_pedido_resumo?.descricao || '—';
  const quantidadePedido = it.quantidade_pedido || it.item_pedido_resumo?.quantidade || '—';
  const unidadePedido = it.unidade_pedido || it.item_pedido_resumo?.unidade || '—';

  const base = {
    nfNumero,
    nfSerie,
    itemNf,
    statusConferenciaLabel,
    corridaHerdada,
    loteHerdado,
    pedidoNumero,
    itemPedidoId,
    produtoPedidoCodigo,
    produtoPedidoDescricao,
    quantidadePedido,
    unidadePedido,
  };

  if (!temVinculo) {
    return {
      ...base,
      temVinculo: false,
      produtoNaConferencia: false,
      origemCompleta: false,
      statusConferenciaLabel: '—',
      mensagem: 'Item sem vínculo com linha da NF/conferência.',
      badgeClass: 'erp-badge-warning',
      badgeText: 'Sem rastreio NF',
    };
  }

  if (origemCompleta) {
    return {
      ...base,
      temVinculo: true,
      produtoNaConferencia,
      origemCompleta: true,
      mensagem: 'Rastreável pela conferência da NF e pelo Pedido de Compra.',
      badgeClass: 'erp-badge-success',
      badgeText: 'Rastreável NF + Pedido',
    };
  }

  if (!produtoNaConferencia) {
    return {
      ...base,
      temVinculo: true,
      produtoNaConferencia: false,
      origemCompleta: false,
      mensagem: 'Origem vinculada à NF, mas produto ainda não foi vinculado na conferência.',
      badgeClass: 'erp-badge-warning',
      badgeText: 'NF vinculada · sem produto',
    };
  }

  return {
    ...base,
    temVinculo: true,
    produtoNaConferencia: true,
    origemCompleta: false,
    mensagem: 'Origem vinculada à NF, mas sem item do pedido.',
    badgeClass: 'erp-badge-success',
    badgeText: 'Rastreável NF',
  };
}

const ensureMap = (v: unknown): Record<string, string> => {
  if (!v || typeof v !== 'object') return {};
  return Object.entries(v as Record<string, unknown>).reduce<Record<string, string>>((acc, [k, val]) => {
    acc[k] = val == null ? '' : String(val);
    return acc;
  }, {});
};

const ensureCorridaAdicional = (raw: unknown, ordem = 1): ItemCertificadoFornecedorCorrida => {
  const obj = (raw && typeof raw === 'object') ? (raw as Record<string, unknown>) : {};
  return {
    ...(obj.id != null ? { id: Number(obj.id) } : {}),
    ordem: Number(obj.ordem || ordem),
    corrida: String(obj.corrida || ''),
    lote: String(obj.lote || ''),
    quantidade: obj.quantidade == null || obj.quantidade === '' ? null : Number(obj.quantidade),
    composicao_json: obj.composicao_json || {},
    ensaio_tracao_json: obj.ensaio_tracao_json || {},
    ensaio_impacto_json: obj.ensaio_impacto_json || {},
    ...(obj.criado_em ? { criado_em: String(obj.criado_em) } : {}),
  };
};

const mergeCorridasAdicionais = (
  existentesRaw: ItemCertificadoFornecedorCorrida[] | undefined,
  novasRaw: ItemCertificadoFornecedorCorrida[] | undefined,
): ItemCertificadoFornecedorCorrida[] => {
  const existentes = (existentesRaw || []).map((ca, i) => ensureCorridaAdicional(ca, i + 1));
  const novas = (novasRaw || []).map((ca, i) => ensureCorridaAdicional(ca, i + 1));
  if (!existentes.length && !novas.length) return [];

  const chave = (c: ItemCertificadoFornecedorCorrida) => {
    const corrida = (c.corrida || '').trim().toUpperCase();
    const lote = (c.lote || '').trim().toUpperCase();
    return `${corrida}||${lote}`;
  };

  const usados = new Set(existentes.map(chave));
  const resultado: ItemCertificadoFornecedorCorrida[] = [...existentes];

  for (const nova of novas) {
    const k = chave(nova);
    if (!k || usados.has(k)) continue;
    usados.add(k);
    resultado.push({
      ...nova,
      id: nova.id,
    });
  }

  return resultado.map((c, idx) => ({
    ...c,
    ordem: idx + 1,
  }));
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

const emptyForm = (): Omit<CertificadoFornecedorEntrada, 'id' | 'criado_em' | 'atualizado_em'> => ({
  numero_certificado_fornecedor: '',
  fornecedor: null,
  fornecedor_nome_snapshot: '',
  fornecedor_cnpj_snapshot: '',
  nf_entrada_historica: null,
  nf_entrada_operacional: null,
  numero_nf_entrada: '',
  serie_nf_entrada: '',
  data_nf_entrada: '',
  empresa_destinataria: null,
  status: 'rascunho',
  observacoes: '',
  arquivo_original: null,
  itens: [],
});

const CertificadosFornecedor = () => {
  const [listForbidden, setListForbidden] = useState(false);
  const fetchCertificadosPage = useCallback(async (params: ListQueryParams) => {
    try {
      const result = await certificadosFornecedorService.listPaginated(params);
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
  } = usePaginatedList<CertificadoFornecedorEntrada>({ fetchPage: fetchCertificadosPage });
  const [nfEntradas, setNfEntradas] = useState<NFeEntrada[]>([]);
  const [nfHistoricas, setNfHistoricas] = useState<NFeEntradaHistoricaList[]>([]);
  const [nfOperacionalCache, setNfOperacionalCache] = useState<NFeEntrada | null>(null);
  const [nfHistoricaCache, setNfHistoricaCache] = useState<NFeEntradaHistoricaList | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CertificadoFornecedorEntrada | null>(null);
  const [form, setForm] = useState(emptyForm());
  const navigate = useNavigate();
  const [saveErrors, setSaveErrors] = useState<string[]>([]);
  const [buscaNfOperacional, setBuscaNfOperacional] = useState('');
  const [buscaNfHistorica, setBuscaNfHistorica] = useState('');
  const [nfeSelecionadaResumo, setNfeSelecionadaResumo] = useState<NFeResumo | null>(null);
  const [fornecedorMatches, setFornecedorMatches] = useState<DadosTecnicosFornecedorResultado[]>([]);
  const [fornecedorMatchModalOpen, setFornecedorMatchModalOpen] = useState(false);
  const [fornecedorTargetIdx, setFornecedorTargetIdx] = useState<number | null>(null);
  const [fornecedorTargetCompIdx, setFornecedorTargetCompIdx] = useState<number | null>(null);
  const [fornecedorComparacaoVisible, setFornecedorComparacaoVisible] = useState<Record<string, boolean>>({});
  const [includeRascunhoBusca, setIncludeRascunhoBusca] = useState(false);
  const [mensagemInfo, setMensagemInfo] = useState<string | null>(null);

  // Busca no servidor (lista paginada ~100 itens não contém todas as NF-e).
  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      const q = buscaNfOperacional.trim();
      nfeEntradasService
        .getAll({ search: q || undefined, limit: 50 })
        .then((rows) => {
          if (!cancelled) setNfEntradas(rows);
        })
        .catch(() => {
          if (!cancelled) setNfEntradas([]);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [buscaNfOperacional]);

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      const q = buscaNfHistorica.trim();
      nfeEntradaHistoricaImportadaService
        .list({ search: q || undefined, limit: 50 })
        .then((rows) => {
          if (!cancelled) setNfHistoricas(rows);
        })
        .catch(() => {
          if (!cancelled) setNfHistoricas([]);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [buscaNfHistorica]);

  const labelSalvarFornecedorSemRegistrar = (): string => {
    if (form.status === 'cancelado') {
      return editing?.status === 'cancelado' ? 'Salvar cancelamento' : 'Confirmar cancelamento';
    }
    if (form.status === 'registrado') return 'Salvar como registrado';
    return 'Salvar rascunho';
  };

  const titleSalvarFornecedorSemRegistrar = (): string => {
    if (form.status === 'cancelado') {
      return editing?.status === 'cancelado'
        ? 'Grava alterações no cadastro cancelado (o status permanece cancelado).'
        : 'Confirma o cancelamento: o registro permanece para rastreabilidade e consulta.';
    }
    if (form.status === 'registrado') {
      return 'Grava alterações mantendo o status registrado. Use “Registrar certificado” para validar itens e formalizar o registro.';
    }
    return 'Grava sem registrar formalmente (permanece em rascunho).';
  };

  const formatDate = (iso?: string) => {
    if (!iso) return '—';
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return iso.slice(0, 10);
    return dt.toLocaleDateString('pt-BR');
  };

  const formatCurrency = (value?: number) =>
    typeof value === 'number'
      ? value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
      : '—';

  const keyCompact = (key?: string) => {
    if (!key) return '—';
    if (key.length <= 12) return key;
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  const labelNfCompleta = (nf: NFeResumo) =>
    `NF ${nf.numero || '—'} / Série ${nf.serie || '—'} — ${nf.fornecedor || '—'} — ${nf.fornecedorCnpj || '—'} — ${formatDate(nf.emissao)} — ${formatCurrency(nf.valorTotal)} — Chave ${keyCompact(nf.chaveAcesso)}`;

  const labelNfCompacta = (nf: NFeResumo) =>
    `${nf.numero || '—'}/${nf.serie || '—'} — ${(nf.fornecedor || '—').slice(0, 24)} — ${formatDate(nf.emissao)} — ${formatCurrency(nf.valorTotal)}`;

  const toResumoOperacional = (n: NFeEntrada): NFeResumo => ({
    numero: n.numero,
    serie: n.serie || '',
    fornecedor: n.fornecedor_nome || '',
    fornecedorCnpj: n.fornecedor_cnpj || '',
    emissao: n.data,
    valorTotal: n.valor_total,
    chaveAcesso: n.chave_acesso || '',
  });

  const toResumoHistorica = (n: NFeEntradaHistoricaList): NFeResumo => ({
    numero: n.numero,
    serie: n.serie,
    fornecedor: n.fornecedor_nome || '',
    fornecedorCnpj: n.fornecedor_cnpj || '',
    emissao: n.dh_emissao,
    valorTotal: n.valor_total_nf,
    chaveAcesso: n.chave_acesso || '',
  });

  /** Mantém a NF já escolhida na lista mesmo se a busca atual não a trouxer. */
  const nfOperacionaisOpcoes = useMemo(() => {
    const id = form.nf_entrada_operacional;
    if (!id || !nfOperacionalCache || nfOperacionalCache.id !== id) return nfEntradas;
    if (nfEntradas.some((n) => n.id === id)) return nfEntradas;
    return [nfOperacionalCache, ...nfEntradas];
  }, [nfEntradas, form.nf_entrada_operacional, nfOperacionalCache]);

  const nfHistoricasOpcoes = useMemo(() => {
    const id = form.nf_entrada_historica;
    if (!id || !nfHistoricaCache || nfHistoricaCache.id !== id) return nfHistoricas;
    if (nfHistoricas.some((n) => n.id === id)) return nfHistoricas;
    return [nfHistoricaCache, ...nfHistoricas];
  }, [nfHistoricas, form.nf_entrada_historica, nfHistoricaCache]);

  const openNew = () => navigate('/certificados-fornecedor/novo');

  const openEdit = (row: CertificadoFornecedorEntrada) => navigate(`/certificados-fornecedor/${row.id}`);

  const setF = (k: keyof typeof form, v: unknown) => setForm((p) => ({ ...p, [k]: v }));
  const norm = (v: string) => v.replace(',', '.');
  const numeroCabecalho = (form.numero_certificado_fornecedor || '').trim();

  const numeroEfetivoItem = (item: ItemCertificadoFornecedorEntrada) => {
    const numeroItem = (item.numero_certificado_fornecedor_item || '').trim();
    if (numeroItem) return { numero: numeroItem, origem: 'item' as const };
    if (numeroCabecalho) return { numero: numeroCabecalho, origem: 'cabeçalho' as const };
    return { numero: '', origem: 'nenhum' as const };
  };

  const numeroEfetivoComponente = (
    item: ItemCertificadoFornecedorEntrada,
    comp?: { numero_certificado_fornecedor_componente?: string },
  ) => {
    const numeroComp = (comp?.numero_certificado_fornecedor_componente || '').trim();
    if (numeroComp) return { numero: numeroComp, origem: 'componente' as const };
    const itemEfetivo = numeroEfetivoItem(item);
    if (itemEfetivo.numero) return itemEfetivo;
    return { numero: '', origem: 'nenhum' as const };
  };

  const componenteStatus = (item: ItemCertificadoFornecedorEntrada, comp: ReturnType<typeof ensureComp>) => {
    const hasNumero = Boolean(numeroEfetivoComponente(item, comp).numero);
    const hasCorrida = Boolean((comp.corrida || '').trim() || (comp.lote || '').trim());
    const hasNorma = Boolean((comp.norma || '').trim());
    const hasCompTec = Object.keys(ensureMap(comp.composicao_json)).some((k) => ensureMap(comp.composicao_json)[k]);
    const hasMec = Object.keys(ensureMap(comp.ensaio_tracao_json)).some((k) => ensureMap(comp.ensaio_tracao_json)[k]);
    if (!hasNumero) return 'Sem número';
    if (!hasCorrida) return 'Sem corrida';
    if (hasNorma && (hasCompTec || hasMec)) return 'Completo';
    return 'Incompleto';
  };

  const carregarItens = async () => {
    setSaveErrors([]);
    setMensagemInfo(null);
    try {
      const data = await certificadosFornecedorService.preencherPorNfeEntrada({
        nf_entrada_operacional_id: form.nf_entrada_operacional || undefined,
        nf_entrada_historica_id: form.nf_entrada_historica || undefined,
      });
      setForm((p) => ({
        ...p,
        ...data,
        itens: ((data.itens as ItemCertificadoFornecedorEntrada[]) || []).map((it) => {
          const anterioresPorConferencia = new Map<number, ItemCertificadoFornecedorEntrada>();
          (p.itens || []).forEach((oldIt) => {
            if (oldIt.item_conferencia_id != null) {
              anterioresPorConferencia.set(oldIt.item_conferencia_id, oldIt);
            }
          });
          const existente = it.item_conferencia_id != null
            ? anterioresPorConferencia.get(it.item_conferencia_id)
            : undefined;
          const corridasExistentes = existente?.corridas_adicionais || [];
          const corridasNovas = (it.corridas_adicionais || []).map((ca, i) => ensureCorridaAdicional(ca, i + 1));

          return {
            ...it,
            tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',
            numero_certificado_fornecedor_item: it.numero_certificado_fornecedor_item || '',
            data_certificado_fornecedor_item: it.data_certificado_fornecedor_item || '',
            pagina_certificado_fornecedor: it.pagina_certificado_fornecedor || '',
            observacao_origem_certificado: it.observacao_origem_certificado || '',
            composicao_json: ensureMap(it.composicao_json),
            ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),
            ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),
            componentes: (it.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),
            corridas_adicionais: mergeCorridasAdicionais(corridasExistentes, corridasNovas),
          };
        }),
      }));
      setNfeSelecionadaResumo((prev) => ({
        numero: String(data.numero_nf_entrada || prev?.numero || form.numero_nf_entrada || ''),
        serie: String(data.serie_nf_entrada || prev?.serie || form.serie_nf_entrada || ''),
        fornecedor: String(data.fornecedor_nome_snapshot || prev?.fornecedor || form.fornecedor_nome_snapshot || ''),
        fornecedorCnpj: String(data.fornecedor_cnpj_snapshot || prev?.fornecedorCnpj || form.fornecedor_cnpj_snapshot || ''),
        emissao: String(data.data_nf_entrada || prev?.emissao || form.data_nf_entrada || ''),
        valorTotal: prev?.valorTotal,
        chaveAcesso: prev?.chaveAcesso || '',
      }));
    } catch (e) {
      setSaveErrors(formatApiErrors(e));
    }
  };

  const salvar = async (registrar = false) => {
    setSaveErrors([]);
    setMensagemInfo(null);
    if (registrar && form.status === 'cancelado') {
      setSaveErrors(['Não é possível registrar no status cancelado. Altere o status no campo Status antes de registrar.']);
      return;
    }
    if (!registrar && form.status === 'cancelado') {
      const anterior = editing?.status;
      if (anterior !== 'cancelado') {
        const ok = window.confirm(CONFIRMAR_CANCELAMENTO_CERTIFICADO_FORNECEDOR);
        if (!ok) return;
      }
    }
    const errosCorridasAdicionais: string[] = [];
    form.itens.forEach((it, idx) => {
      errosCorridasAdicionaisItemCf(it).forEach((msg) => {
        errosCorridasAdicionais.push(`Item ${idx + 1}: ${msg}`);
      });
    });
    if (errosCorridasAdicionais.length) {
      setSaveErrors(errosCorridasAdicionais);
      return;
    }
    if (registrar) {
      const errosFrontend: string[] = [];
      form.itens.forEach((it, idx) => {
        if ((it.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES' && (it.componentes || []).length === 0) {
          errosFrontend.push(`Item ${idx + 1}: informe ao menos um componente para válvula por componentes.`);
        }
      });
      if (errosFrontend.length) {
        setSaveErrors(errosFrontend);
        return;
      }
    }
    try {
      const payload = { ...form, status: registrar ? 'registrado' : form.status };
      if (editing) await certificadosFornecedorService.update(editing.id, payload);
      else await certificadosFornecedorService.create(payload);
      setModalOpen(false);
      void reloadList();
    } catch (e) {
      setSaveErrors(formatApiErrors(e));
    }
  };

  const updateItem = (idx: number, patch: Partial<ItemCertificadoFornecedorEntrada>) =>
    setForm((p) => {
      const next = [...p.itens];
      next[idx] = { ...next[idx], ...patch };
      return { ...p, itens: next };
    });

  const updateComponente = (
    itemIdx: number,
    compIdx: number,
    patch: Partial<NonNullable<ItemCertificadoFornecedorEntrada['componentes']>[number]>,
  ) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      comps[compIdx] = { ...comps[compIdx], ...patch };
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

  const updateCorridaAdicional = (
    itemIdx: number,
    corridaIdx: number,
    patch: Partial<ItemCertificadoFornecedorCorrida>,
  ) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const corridas = [...(itemsNext[itemIdx].corridas_adicionais || [])];
      corridas[corridaIdx] = { ...corridas[corridaIdx], ...patch };
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], corridas_adicionais: corridas };
      return { ...p, itens: itemsNext };
    });
  };

  const addCorridaAdicional = (itemIdx: number) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const item = itemsNext[itemIdx];
      const corridas = [...(item.corridas_adicionais || [])];
      // Nova corrida herda dados tecnicos do item principal (evita bloqueio de validacao
      // e replica o comportamento historico do badge "Dados herdados")
      const nova = ensureCorridaAdicional({}, corridas.length + 1);
      nova.composicao_json = { ...(item.composicao_json || {}) };
      nova.ensaio_tracao_json = { ...(item.ensaio_tracao_json || {}) };
      nova.ensaio_impacto_json = { ...(item.ensaio_impacto_json || {}) };
      corridas.push(nova);
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], corridas_adicionais: corridas };
      return { ...p, itens: itemsNext };
    });
  };

  const removeCorridaAdicional = (itemIdx: number, corridaIdx: number) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const corridas = [...(itemsNext[itemIdx].corridas_adicionais || [])];
      corridas.splice(corridaIdx, 1);
      itemsNext[itemIdx] = {
        ...itemsNext[itemIdx],
        corridas_adicionais: corridas.map((c, i) => ({ ...c, ordem: i + 1 })),
      };
      return { ...p, itens: itemsNext };
    });
  };

  const adicionarComponentesPadraoValvula = (itemIdx: number) => {
    setForm((p) => {
      const itemsNext = [...p.itens];
      const comps = [...(itemsNext[itemIdx].componentes || [])];
      const nomesExistentes = new Set(comps.map((c) => (c.nome_componente || '').trim().toUpperCase()));
      COMPONENTES_PADRAO_VALVULA.forEach((nome) => {
        if (!nomesExistentes.has(nome)) {
          comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));
          nomesExistentes.add(nome);
        }
      });
      itemsNext[itemIdx] = { ...itemsNext[itemIdx], componentes: comps };
      return { ...p, itens: itemsNext };
    });
  };

  const aplicarNumeroCabecalhoEmTodosOsItens = () => {
    const numeroCabecalho = (form.numero_certificado_fornecedor || '').trim();
    if (!numeroCabecalho) {
      setMensagemInfo('Preencha o número do certificado no cabeçalho para copiar.');
      return;
    }
    setForm((p) => ({
      ...p,
      itens: p.itens.map((it) => ({
        ...it,
        numero_certificado_fornecedor_item: numeroCabecalho,
      })),
    }));
    setMensagemInfo('Número do cabeçalho aplicado em todos os itens.');
  };

  const aplicarDadosTecnicosExistentes = (idx: number, src: DadosTecnicosFornecedorResultado, compIdx?: number) => {
    const item = form.itens[idx];
    const { corrida: crEf, lote: loEf } = corridaLoteEfetivosResultadoFornecedor(src);
    if (compIdx != null) {
      const compAtual = ensureComp(item.componentes?.[compIdx], compIdx + 1);
      updateComponente(idx, compIdx, {
        norma: src.norma || compAtual.norma,
        corrida: crEf || compAtual.corrida,
        lote: loEf || compAtual.lote,
        composicao_json: ensureMap(src.composicao_json),
        ensaio_tracao_json: ensureMap(src.ensaio_tracao_json),
        ensaio_impacto_json: ensureMap(src.ensaio_impacto_json),
        numero_certificado_fornecedor_componente:
          src.numero_certificado_fornecedor_item || src.numero_certificado_fornecedor || compAtual.numero_certificado_fornecedor_componente,
      });
      setMensagemInfo(`Dados técnicos reutilizados no componente ${compAtual.nome_componente || compIdx + 1}.`);
      return;
    }
    updateItem(idx, {
      norma: src.norma || item.norma,
      corrida: crEf || item.corrida,
      lote: loEf || item.lote,
      numero_certificado_fornecedor_item:
        src.numero_certificado_fornecedor_item || src.numero_certificado_fornecedor || item.numero_certificado_fornecedor_item,
      tipo_dados_tecnicos: src.tipo_dados_tecnicos || item.tipo_dados_tecnicos,
      composicao_json: ensureMap(src.composicao_json),
      ensaio_tracao_json: ensureMap(src.ensaio_tracao_json),
      ensaio_impacto_json: ensureMap(src.ensaio_impacto_json),
      componentes: (src.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),
      observacoes_item: item.observacoes_item || '',
    });
    setMensagemInfo(
      `Dados técnicos reutilizados do certificado #${src.certificado_fornecedor_id} (${src.numero_nf_entrada || 'NF sem número'}).`,
    );
  };

  const buscarDadosCorridaExistente = async (idx: number, auto = false) => {
    setSaveErrors([]);
    setMensagemInfo(null);
    const item = form.itens[idx];
    const corrida = (item.corrida || '').trim();
    const lote = (item.lote || '').trim();
    const fornecedor = form.fornecedor || undefined;
    if (!corrida && !lote) return;
    try {
      const debugBusca =
        typeof window !== 'undefined' &&
        new URLSearchParams(window.location.search).get('debug') === '1';
      const { resultados: found, dicas_busca } = await certificadosFornecedorService.buscarDadosTecnicos({
        corrida,
        lote,
        fornecedor,
        produto: item.produto || undefined,
        codigo_produto: item.codigo_produto || '',
        descricao: item.descricao_material || '',
        norma: item.norma || '',
        tipo_dados_tecnicos: item.tipo_dados_tecnicos || 'PADRAO_ITEM',
        status: 'registrado',
        include_rascunho: includeRascunhoBusca,
        ...(debugBusca ? { debug: true } : {}),
      });
      if (!found.length) {
        if (!auto) {
          const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicas_busca);
          setMensagemInfo(dicaMsg || 'Nenhum dado técnico existente encontrado para essa corrida/lote.');
        }
        return;
      }
      setFornecedorTargetIdx(idx);
      setFornecedorTargetCompIdx(null);
      setFornecedorMatches(found);
      setFornecedorMatchModalOpen(true);
    } catch (e) {
      setSaveErrors(formatApiErrors(e));
    }
  };

  const buscarDadosCorridaComponente = async (itemIdx: number, compIdx: number) => {
    setSaveErrors([]);
    setMensagemInfo(null);
    const item = form.itens[itemIdx];
    const comp = ensureComp(item.componentes?.[compIdx], compIdx + 1);
    const fornecedor = form.fornecedor || undefined;
    const corrida = (comp.corrida || '').trim();
    const lote = (comp.lote || '').trim();
    if (!corrida && !lote) {
      setSaveErrors([`Item ${itemIdx + 1} > Componente ${comp.nome_componente || compIdx + 1}: informe corrida/lote para buscar dados.`]);
      return;
    }
    try {
      const debugBusca =
        typeof window !== 'undefined' &&
        new URLSearchParams(window.location.search).get('debug') === '1';
      const { resultados: found, dicas_busca } = await certificadosFornecedorService.buscarDadosTecnicos({
        corrida,
        lote,
        fornecedor,
        codigo_produto: item.codigo_produto || '',
        descricao: comp.nome_componente || item.descricao_material || '',
        norma: comp.norma || item.norma || '',
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        certificado_fornecedor: comp.numero_certificado_fornecedor_componente || item.numero_certificado_fornecedor_item || form.numero_certificado_fornecedor || '',
        status: 'registrado',
        ...(debugBusca ? { debug: true } : {}),
      });
      if (!found.length) {
        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicas_busca);
        setMensagemInfo(dicaMsg || 'Nenhum dado técnico encontrado para a corrida do componente.');
        return;
      }
      setFornecedorTargetIdx(itemIdx);
      setFornecedorTargetCompIdx(compIdx);
      setFornecedorMatches(found);
      setFornecedorMatchModalOpen(true);
    } catch (e) {
      setSaveErrors(formatApiErrors(e));
    }
  };

  return (
    <div>
      <PageHeader
        title="Certificados de Fornecedor"
        description="Controle de certificados recebidos de fornecedores e vínculos com produtos, lotes e entradas."
        onAdd={listForbidden ? undefined : openNew}
        addLabel="Novo certificado"
        searchValue={search}
        onSearch={setSearch}
      />
      {listError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {listLoading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!listLoading && !listError ? (
        <DataTableShell>
        <DataTable className="text-sm" mobileMode="cards">
          <thead>
            <tr>
              <th>Fornecedor</th>
              <th className="whitespace-nowrap">NF entrada</th>
              <th className="whitespace-nowrap">Data</th>
              <th>Certificado</th>
              <th className="whitespace-nowrap text-right">Itens</th>
              <th className="whitespace-nowrap">Status</th>
              <th className="w-20 text-right whitespace-nowrap">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState
                    message="Nenhum certificado de fornecedor encontrado."
                    actionLabel={listForbidden ? undefined : 'Novo certificado'}
                    onAction={listForbidden ? undefined : openNew}
                  />
                </td>
              </tr>
            ) : (
              items.map((c) => (
                  <tr key={c.id}>
                    <td>{c.fornecedor_nome_snapshot || '—'}</td>
                    <td>{c.numero_nf_entrada || '—'}</td>
                    <td>{c.data_nf_entrada || '—'}</td>
                    <td className="font-mono text-xs">{c.numero_certificado_fornecedor || '—'}</td>
                    <td className="text-right tabular-nums">{c.quantidade_itens ?? c.itens.length}</td>
                    <td>
                      <StatusBadge status={c.status || 'pendente'} />
                    </td>
                    <td className="text-right">
                      <button
                        type="button"
                        className="erp-btn-ghost erp-btn-sm"
                        onClick={() => openEdit(c)}
                        title="Abrir cadastro do certificado de fornecedor"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
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

    </div>
  );
};

export default CertificadosFornecedor;
