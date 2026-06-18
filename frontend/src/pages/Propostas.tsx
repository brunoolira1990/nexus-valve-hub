import { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Download, ExternalLink, FileDown, MoreVertical, Pencil, RefreshCw, ShoppingCart, Trash2, Plus, X } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MSG_SALVE_ANTES_PDF } from '@/lib/commercialPdfDownload';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { HomologacaoFiscalPropostaPanel } from '@/components/HomologacaoFiscalPropostaPanel';
import { propostasService } from '@/services/api/comercial';
import { clientesService } from '@/services/api/clientes';
import { produtosService, ncmApiService } from '@/services/api/produtos';
import { empresasService } from '@/services/api/empresas';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import { cenariosFiscaisSaidaService } from '@/services/api/cenarios-fiscais-saida';
import { regrasFiscaisSaidaService } from '@/services/api/regras-fiscais-saida';
import type { CenarioFiscalSaida } from '@/types';
import { inferItemAvulso } from '@/lib/propostaApiPayload';
import {
  formatDecimal,
  formatMoneyBr,
  formatPercent,
  inputNumberValue,
  toNumber,
} from '@/lib/numberFormat';
import { apiErrorMessage } from '@/services/api/config';
import { buildDueDates, parsePaymentCondition } from '@/lib/paymentTerms';
import { previewCondicaoPagamento } from '@/lib/condicaoPagamento';
import { formatDateBr } from '@/lib/dateBr';
import { DateBrInput } from '@/components/comercial/DateBrInput';
import { GerarPedidoPropostaModal } from '@/components/comercial/GerarPedidoPropostaModal';
import { RecuperarPropostaModal } from '@/components/comercial/RecuperarPropostaModal';
import { CondicaoPagamentoResumo } from '@/components/comercial/CondicaoPagamentoResumo';
import { ClienteComercialField } from '@/components/comercial/ClienteComercialField';
import { ProdutoComercialField } from '@/components/comercial/ProdutoComercialField';
import { VendedorComercialField } from '@/components/comercial/VendedorComercialField';
import {
  clienteStubForDisplay,
  colaboradorStubForDisplay,
  produtoStubForDisplay,
  vendedorStubForDisplay,
} from '@/lib/comercialAutocomplete';
import { colaboradoresService } from '@/services/api/colaboradores';
import { vendedoresService } from '@/services/api/vendedores';
import { ItemComercialMetricasGrid } from '@/components/comercial/ItemComercialMetricasGrid';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import {
  normalizeNcm,
  ncmFiscalDigitsValid,
  recalcPropostaItem,
  computeIpiEntradaValor,
  percentualSaidaTotal,
  computeValorCargaSaida,
} from '@/lib/propostaPricing';
import { equivalentesPreco, labelPrecoPorUnidade, previewConversaoItem, todasUnidadesPadrao, unidadesNegociacaoProduto } from '@/lib/comercialDimensional';
import type {
  Proposta,
  ItemProposta,
  Cliente,
  Produto,
  Vendedor,
  Colaborador,
  Empresa,
  BuscaRegraFiscalSaida,
  OrigemRegraFiscalSaida,
  ComparativoFiscalSaida,
  HomologacaoFiscalStatusProposta,
  StatusComparativoFiscalSaida,
} from '@/types';
import { UFS } from '@/types';
import {
  CONDICAO_PAGAMENTO_PADRAO,
  MENSAGEM_COMERCIAL_PADRAO,
  STATUS_PROPOSTA_CONVERTIDA,
  STATUS_PROPOSTA_INICIAL,
  STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
  STATUS_PROPOSTA_REABERTA,
  VALIDADE_DIAS_PADRAO,
  dataHojeIso,
  diasValidadeEntreDatas,
  validadeIsoFromDias,
} from '@/lib/comercialFormDefaults';
import {
  propostaPodeGerarPedido,
  propostaRequerRecuperacao,
  propostaTemPedidoGerado,
  propostaTotalmenteConvertida,
  statusPropostaUi,
} from '@/lib/propostaStatus';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { toast } from 'sonner';
import {
  DiscountInput,
  IntegerInput,
  MoneyInput,
  QuantityInput,
  ReadonlyCalculatedField,
  UnitSelect,
} from '@/components/comercial/fields';

const USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS =
  import.meta.env.VITE_USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS === 'true';

const MSG_CONFIRMACAO_CONVERTER_PEDIDO =
  'Esta ação cria um Pedido de Venda a partir da proposta aprovada. O faturamento/NF-e será tratado em etapa posterior.\n\nDeseja continuar?';

function propostaUsaMotorCenario(
  form: { usar_cenario_fiscal_saida?: boolean },
  options?: { isNew?: boolean },
): boolean {
  if (USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS) return true;
  if (options?.isNew) return true;
  return Boolean(form.usar_cenario_fiscal_saida);
}

function labelOrigemRegraFiscal(origem?: OrigemRegraFiscalSaida): string {
  switch (origem) {
    case 'CENARIO_SAIDA':
      return 'Cenário fiscal de saída';
    case 'LEGADO':
      return 'Regra fiscal legada';
    case 'NAO_ENCONTRADA':
      return 'Não encontrada';
    default:
      return '';
  }
}

function labelStatusComparativo(status: StatusComparativoFiscalSaida): string {
  switch (status) {
    case 'IGUAL':
      return 'Igual';
    case 'DIVERGENTE':
      return 'Divergente';
    case 'CENARIO_NAO_ENCONTRADO':
      return 'Cenário não encontrado';
    case 'LEGADO_NAO_ENCONTRADO':
      return 'Legado não encontrado';
    case 'AMBOS_NAO_ENCONTRADOS':
      return 'Nenhum encontrado';
    default:
      return status;
  }
}

function classeStatusComparativo(status: StatusComparativoFiscalSaida): string {
  switch (status) {
    case 'IGUAL':
      return 'text-emerald-700 dark:text-emerald-400';
    case 'DIVERGENTE':
      return 'text-amber-700 dark:text-amber-400';
    case 'CENARIO_NAO_ENCONTRADO':
    case 'LEGADO_NAO_ENCONTRADO':
    case 'AMBOS_NAO_ENCONTRADOS':
      return 'text-muted-foreground';
    default:
      return 'text-muted-foreground';
  }
}

function itemFromBuscaRegra(row: ItemProposta, busca: BuscaRegraFiscalSaida): ItemProposta {
  if (busca.origem === 'NAO_ENCONTRADA') {
    return {
      ...row,
      icms_saida_percentual: 0,
      pis_saida_percentual: 0,
      cofins_saida_percentual: 0,
      ipi_saida_percentual: 0,
      regra_fiscal_id: null,
      regra_fiscal_saida_id: null,
      regra_fiscal_origem: 'NAO_ENCONTRADA',
    };
  }
  return {
    ...row,
    icms_saida_percentual: Number(busca.aliquota_icms) || 0,
    pis_saida_percentual: Number(busca.aliquota_pis) || 0,
    cofins_saida_percentual: Number(busca.aliquota_cofins) || 0,
    ipi_saida_percentual: Number(busca.aliquota_ipi) || 0,
    regra_fiscal_id: busca.regra_legada_id ?? null,
    regra_fiscal_saida_id: busca.regra_id ?? null,
    regra_fiscal_origem: busca.origem,
    deduzir_icms_base_pis: Boolean(busca.deduzir_icms_base_pis),
    deduzir_icms_base_cofins: Boolean(busca.deduzir_icms_base_cofins),
    pis_cofins_base_deduz_icms:
      busca.origem === 'CENARIO_SAIDA' &&
      Boolean(busca.deduzir_icms_base_pis || busca.deduzir_icms_base_cofins),
  };
}

const Propostas = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const statusUrl = searchParams.get('status') || '';
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
    filters,
    setFilter,
    loading: loadingList,
    error: loadError,
    reload: reloadList,
  } = usePaginatedList<Proposta>({
    fetchPage: propostasService.listPaginated,
    initialFilters: statusUrl ? { status: statusUrl } : {},
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Proposta | null>(null);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const itensRef = useRef<ItemProposta[]>([]);
  const produtosRef = useRef<Produto[]>([]);
  const empresasRef = useRef<Empresa[]>([]);
  const [form, setForm] = useState({
    numero: '',
    cliente_id: null as number | null,
    cliente_avulso_nome: '',
    empresa_emitente_id: null as number | null,
    data: '',
    validade_dias: VALIDADE_DIAS_PADRAO,
    frete_texto: '',
    mensagem_comercial: '',
    observacoes_proposta: '',
    referencia_cliente: '',
    vendedor_id: null as number | null,
    status: STATUS_PROPOSTA_INICIAL,
    condicao_pagamento_texto: CONDICAO_PAGAMENTO_PADRAO,
    prazo_entrega_texto: '',
    uf_destino_avulso: '',
    usar_cenario_fiscal_saida: false,
    cenario_fiscal_saida_id: null as number | null,
  });
  const [cenariosSaida, setCenariosSaida] = useState<CenarioFiscalSaida[]>([]);
  const [homologacaoStatus, setHomologacaoStatus] = useState<HomologacaoFiscalStatusProposta>('NAO_INICIADA');
  const [homologacaoObservacao, setHomologacaoObservacao] = useState('');
  const [homologacaoEm, setHomologacaoEm] = useState<string | null>(null);
  const [clienteAvulso, setClienteAvulso] = useState(false);
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);
  const [selectedVendedor, setSelectedVendedor] = useState<Vendedor | null>(null);
  const [selectedColaboradorVendedor, setSelectedColaboradorVendedor] = useState<Colaborador | null>(null);
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(() => new Map());
  const [itens, setItens] = useState<ItemProposta[]>([]);
  const [comparativoFiscal, setComparativoFiscal] = useState<
    Record<string, ComparativoFiscalSaida | 'loading' | 'error'>
  >({});
  const [referenciaFrete, setReferenciaFrete] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      frete_medio_observado: number | null;
      peso_frete_sobre_faturamento: number | null;
      valor_total_fretes_periodo: number;
      quantidade_ctes_validos: number;
      transportadora_referencia: { transportadora_id: number; transportadora_nome: string } | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);
  const [referenciaCustoCompra, setReferenciaCustoCompra] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      custo_medio_observado: number | null;
      ultimo_custo_observado: number | null;
      quantidade_notas_base: number;
      quantidade_itens_base: number;
      fornecedor_referencia: string | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);
  const [custoCompraRefLoading, setCustoCompraRefLoading] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [wizardError, setWizardError] = useState<string | null>(null);
  const [wizardLoading, setWizardLoading] = useState(false);
  const [gerarPedidoOpen, setGerarPedidoOpen] = useState(false);
  const [gerarPedidoLoading, setGerarPedidoLoading] = useState(false);
  const [recuperarOpen, setRecuperarOpen] = useState(false);
  const [recuperarLoading, setRecuperarLoading] = useState(false);
  const [wizardProposta, setWizardProposta] = useState<Proposta | null>(null);
  const [wizardClienteId, setWizardClienteId] = useState<number | null>(null);
  const [novoClienteNome, setNovoClienteNome] = useState('');
  const [novoClienteCnpj, setNovoClienteCnpj] = useState('');
  const [itemLinks, setItemLinks] = useState<Record<number, number | null>>({});
  const [novoProdutoDescricao, setNovoProdutoDescricao] = useState<Record<number, string>>({});
  const numericClass =
    'erp-input h-8 text-sm text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none';

  const normalizeItem = (item: Partial<ItemProposta>): ItemProposta => {
    const itemAvulso = item.item_avulso ?? inferItemAvulso(item);
    const base: ItemProposta = {
      id: item.id ?? Date.now(),
      item_avulso: itemAvulso,
      produto_id: itemAvulso ? null : (item.produto_id ?? null),
      produto_nome: item.produto_nome ?? '',
      descricao_avulsa: item.descricao_avulsa ?? '',
      ncm_avulso: item.ncm_avulso ?? '',
      quantidade: toNumber(item.quantidade, 1),
      unidade_negociada: item.unidade_negociada ?? '',
      quantidade_negociada: toNumber(item.quantidade_negociada ?? item.quantidade, 1),
      unidade_estoque_calculada: item.unidade_estoque_calculada ?? '',
      quantidade_estoque_calculada: toNumber(item.quantidade_estoque_calculada),
      peso_total_kg: toNumber(item.peso_total_kg),
      metros_total: toNumber(item.metros_total),
      barras_total: toNumber(item.barras_total),
      valor_unitario: toNumber(item.valor_unitario),
      preco_por_unidade_negociada: toNumber(item.preco_por_unidade_negociada ?? item.valor_unitario),
      preco_por_kg: toNumber(item.preco_por_kg),
      preco_por_metro: toNumber(item.preco_por_metro),
      fator_conversao: toNumber(item.fator_conversao),
      desconto: toNumber(item.desconto),
      custo_utilizado: toNumber(item.custo_utilizado),
      frete: toNumber(item.frete),
      despesas: toNumber(item.despesas),
      ipi_entrada_percentual: toNumber(item.ipi_entrada_percentual),
      ipi_custo: toNumber(item.ipi_custo),
      st_custo: toNumber(item.st_custo),
      outros_impostos_custo: toNumber(item.outros_impostos_custo),
      custo_final: toNumber(item.custo_final),
      icms_saida_percentual: toNumber(item.icms_saida_percentual),
      pis_saida_percentual: toNumber(item.pis_saida_percentual),
      cofins_saida_percentual: toNumber(item.cofins_saida_percentual),
      ipi_saida_percentual: toNumber(item.ipi_saida_percentual),
      regra_fiscal_id: item.regra_fiscal_id ?? null,
      regra_fiscal_origem: item.origem_regra_fiscal_saida ?? item.regra_fiscal_origem,
      regra_fiscal_saida_id: item.regra_fiscal_saida_id ?? null,
      deduzir_icms_base_pis: item.deduzir_icms_base_pis ?? false,
      deduzir_icms_base_cofins: item.deduzir_icms_base_cofins ?? false,
      pis_cofins_base_deduz_icms: item.pis_cofins_base_deduz_icms ?? false,
      irpj_estimado_percentual: toNumber(item.irpj_estimado_percentual),
      csll_estimada_percentual: toNumber(item.csll_estimada_percentual),
      comissao_percentual: toNumber(item.comissao_percentual),
      frete_saida: toNumber(item.frete_saida),
      outras_despesas_saida: toNumber(item.outras_despesas_saida),
      modo_preco: item.modo_preco === 'manual' ? 'manual' : 'sugerido',
      preco_sugerido: toNumber(item.preco_sugerido),
      preco_final: toNumber(item.preco_final ?? item.valor_unitario),
      margem_resultante: toNumber(item.margem_resultante),
      lucro_resultante: toNumber(item.lucro_resultante),
    };
    base.quantidade = base.quantidade_negociada ?? base.quantidade;
    base.valor_unitario = base.preco_por_unidade_negociada ?? base.valor_unitario;
    return recalcPropostaItem(base);
  };

  const load = reloadList;

  useEffect(() => {
    if (statusUrl) setFilter('status', statusUrl);
  }, [statusUrl, setFilter]);

  const hydrateCliente = useCallback((clienteId: number | null, nomeFallback?: string) => {
    if (!clienteId) {
      setSelectedCliente(null);
      return;
    }
    void clientesService
      .getById(clienteId)
      .then(setSelectedCliente)
      .catch(() => setSelectedCliente(clienteStubForDisplay(clienteId, nomeFallback || '—')));
  }, []);

  const hydrateVendedor = useCallback((vendedorId: number | null, nomeFallback?: string) => {
    if (!vendedorId) {
      setSelectedVendedor(null);
      setSelectedColaboradorVendedor(null);
      return;
    }
    void vendedoresService
      .getById(vendedorId)
      .then((v) => {
        setSelectedVendedor(v);
        setSelectedColaboradorVendedor(
          colaboradorStubForDisplay(v.id, v.nome, v.codigo, v.id),
        );
      })
      .catch(() => {
        const stub = vendedorStubForDisplay(vendedorId, nomeFallback || '—');
        setSelectedVendedor(stub);
        setSelectedColaboradorVendedor(
          colaboradorStubForDisplay(vendedorId, nomeFallback || '—', '', vendedorId),
        );
      });
  }, []);

  const mergeProdutoCache = useCallback((p: Produto) => {
    setProdutoCache((prev) => new Map(prev).set(p.id, p));
  }, []);

  const hydrateProdutosItens = useCallback((lista: ItemProposta[]) => {
    const stubs = new Map<number, Produto>();
    for (const it of lista) {
      if (!it.produto_id) continue;
      stubs.set(
        it.produto_id,
        produtoStubForDisplay(it.produto_id, '', it.produto_nome || it.descricao_avulsa || ''),
      );
    }
    setProdutoCache(stubs);
    for (const it of lista) {
      if (!it.produto_id) continue;
      void produtosService.getById(it.produto_id).then(mergeProdutoCache).catch(() => undefined);
    }
  }, [mergeProdutoCache]);

  useEffect(() => {
    empresasService
      .getAll()
      .then((list) => setEmpresas(list))
      .catch(() => setEmpresas([]));
  }, []);

  itensRef.current = itens;
  produtosRef.current = Array.from(produtoCache.values());
  empresasRef.current = empresas;

  const resolveUfDestino = useCallback((): string => {
    if (!clienteAvulso && form.cliente_id && selectedCliente?.id === form.cliente_id) {
      return (selectedCliente.uf || '').toUpperCase().slice(0, 2);
    }
    return (form.uf_destino_avulso || '').toUpperCase().slice(0, 2);
  }, [clienteAvulso, form.cliente_id, form.uf_destino_avulso, selectedCliente]);

  const validadeCalculadaIso = useMemo(() => {
    if (!form.data || !form.validade_dias) return '';
    return validadeIsoFromDias(form.data, form.validade_dias);
  }, [form.data, form.validade_dias]);

  const resolveUfOrigemEmitente = useCallback((): string => {
    const list = empresasRef.current;
    const id = form.empresa_emitente_id ?? list[0]?.id;
    const emp = list.find((x) => x.id === id) ?? list[0];
    return (emp?.uf || '').toUpperCase().slice(0, 2);
  }, [form.empresa_emitente_id]);

  const mergeRowWithFiscal = useCallback(
    async (row: ItemProposta): Promise<ItemProposta> => {
      const ufOrigem = resolveUfOrigemEmitente();
      const ufDestino = resolveUfDestino();
      const operacao = 'Saída';
      let ncm = '';
      if (row.produto_id) {
        const prod = produtosRef.current.find((p) => p.id === row.produto_id);
        ncm = normalizeNcm(prod?.ncm || '');
      } else {
        ncm = normalizeNcm(row.ncm_avulso || '');
      }
      if (!ncm || ufOrigem.length !== 2 || ufDestino.length !== 2) {
        return {
          ...row,
          icms_saida_percentual: 0,
          pis_saida_percentual: 0,
          cofins_saida_percentual: 0,
          ipi_saida_percentual: 0,
          regra_fiscal_id: null,
          regra_fiscal_saida_id: null,
          regra_fiscal_origem: 'NAO_ENCONTRADA',
        };
      }
      if (propostaUsaMotorCenario(form)) {
        const busca = await regrasFiscaisSaidaService.buscar({
          ncm,
          produto_id: row.produto_id ?? undefined,
          uf_origem: ufOrigem,
          uf_destino: ufDestino,
          tipo_operacao: 'VENDA',
          cenario_id: form.cenario_fiscal_saida_id ?? undefined,
        });
        if (!busca) {
          return itemFromBuscaRegra(row, {
            origem: 'NAO_ENCONTRADA',
            regra_id: null,
            regra_legada_id: null,
            cfop: '',
            cfop_st: '',
            cst_icms: '',
            aliquota_icms: '0',
            cst_ipi: '',
            aliquota_ipi: '0',
            cst_pis: '',
            aliquota_pis: '0',
            cst_cofins: '',
            aliquota_cofins: '0',
            movimenta_estoque: true,
            gera_financeiro: true,
            mensagens: [],
          });
        }
        return itemFromBuscaRegra(row, busca);
      }
      const regra = await regrasFiscaisService.buscar({
        ncm,
        uf_origem: ufOrigem,
        uf_destino: ufDestino,
        operacao,
      });
      if (!regra) {
        return {
          ...row,
          icms_saida_percentual: 0,
          pis_saida_percentual: 0,
          cofins_saida_percentual: 0,
          ipi_saida_percentual: 0,
          regra_fiscal_id: null,
          regra_fiscal_origem: 'NAO_ENCONTRADA',
        };
      }
      return {
        ...row,
        icms_saida_percentual: regra.aliquota_icms,
        pis_saida_percentual: regra.aliquota_pis,
        cofins_saida_percentual: regra.aliquota_cofins,
        ipi_saida_percentual: regra.aliquota_ipi,
        regra_fiscal_id: regra.id,
        regra_fiscal_origem: 'LEGADO',
      };
    },
    [resolveUfOrigemEmitente, resolveUfDestino, form.usar_cenario_fiscal_saida, form.cenario_fiscal_saida_id],
  );

  const runComparativoFiscal = useCallback(
    async (item: ItemProposta) => {
      const key = String(item.id);
      const ufOrigem = resolveUfOrigemEmitente();
      const ufDestino = resolveUfDestino();
      let ncm = '';
      if (item.produto_id) {
        const prod = produtosRef.current.find((p) => p.id === item.produto_id);
        ncm = normalizeNcm(prod?.ncm || '');
      } else {
        ncm = normalizeNcm(item.ncm_avulso || '');
      }
      if (!ncm || ufOrigem.length !== 2 || ufDestino.length !== 2) {
        return;
      }
      setComparativoFiscal((prev) => ({ ...prev, [key]: 'loading' }));
      try {
        const resultado = await regrasFiscaisSaidaService.comparar({
          ncm,
          produto_id: item.produto_id ?? undefined,
          uf_origem: ufOrigem,
          uf_destino: ufDestino,
          tipo_operacao: 'VENDA',
        });
        setComparativoFiscal((prev) => ({ ...prev, [key]: resultado }));
      } catch {
        setComparativoFiscal((prev) => ({ ...prev, [key]: 'error' }));
      }
    },
    [resolveUfOrigemEmitente, resolveUfDestino],
  );

  const fiscalTriggerKey = useMemo(
    () =>
      [
        form.usar_cenario_fiscal_saida ? '1' : '0',
        form.cenario_fiscal_saida_id ?? '',
        itens.map((i) => `${i.id}:${i.produto_id ?? ''}:${normalizeNcm(i.ncm_avulso || '')}`).join('|'),
      ].join('|'),
    [itens, form.usar_cenario_fiscal_saida, form.cenario_fiscal_saida_id],
  );

  const itemRefCusto = useMemo(
    () => itens.find((i) => i.produto_id || ncmFiscalDigitsValid(i.ncm_avulso || '')),
    [itens],
  );

  useLayoutEffect(() => {
    if (!modalOpen) return;
    const podeCusto =
      itemRefCusto &&
      (itemRefCusto.produto_id != null || ncmFiscalDigitsValid(itemRefCusto.ncm_avulso || ''));
    if (podeCusto) setCustoCompraRefLoading(true);
  }, [modalOpen, itemRefCusto]);

  useEffect(() => {
    if (!modalOpen || itens.length === 0) return;
    let cancelled = false;
    const t = setTimeout(() => {
      void (async () => {
        const cur = itensRef.current;
        const merged = await Promise.all(cur.map((r) => mergeRowWithFiscal(r)));
        if (!cancelled) setItens(merged.map((r) => recalcPropostaItem(r)));
      })();
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [
    modalOpen,
    form.empresa_emitente_id,
    form.uf_destino_avulso,
    form.cliente_id,
    clienteAvulso,
    mergeRowWithFiscal,
    itens.length,
    fiscalTriggerKey,
  ]);

  useEffect(() => {
    if (!modalOpen || empresas.length !== 1) return;
    setForm((f) => ({ ...f, empresa_emitente_id: empresas[0].id }));
  }, [modalOpen, empresas]);

  useEffect(() => {
    if (!modalOpen) {
      setReferenciaCustoCompra(null);
      setCustoCompraRefLoading(false);
      return;
    }
    const qs = new URLSearchParams();
    if (form.data) {
      const ym = form.data.slice(0, 7);
      if (ym.length === 7) qs.set('mes', ym);
    }
    if (form.empresa_emitente_id) qs.set('empresa_id', String(form.empresa_emitente_id));
    void propostasService.referenciaComercialFrete(qs).then((data) => {
      if (data && typeof data === 'object') setReferenciaFrete(data);
      else setReferenciaFrete(null);
    });

    const podeCusto =
      itemRefCusto &&
      (itemRefCusto.produto_id != null || ncmFiscalDigitsValid(itemRefCusto.ncm_avulso || ''));
    if (!podeCusto) {
      setReferenciaCustoCompra(null);
      setCustoCompraRefLoading(false);
      return;
    }
    const qsCusto = new URLSearchParams(qs.toString());
    if (itemRefCusto.produto_id) qsCusto.set('produto_id', String(itemRefCusto.produto_id));
    else if (itemRefCusto.ncm_avulso) qsCusto.set('ncm', itemRefCusto.ncm_avulso);
    setCustoCompraRefLoading(true);
    void propostasService
      .referenciaComercialCustoCompra(qsCusto)
      .then((data) => {
        if (data && typeof data === 'object') setReferenciaCustoCompra(data);
        else setReferenciaCustoCompra(null);
      })
      .finally(() => setCustoCompraRefLoading(false));
  }, [modalOpen, form.data, form.empresa_emitente_id, itemRefCusto]);

  const addItem = () => {
    setItens((p) => [
      ...p,
      normalizeItem({
        id: Date.now(),
        item_avulso: false,
        produto_id: null,
        produto_nome: '',
        descricao_avulsa: '',
      }),
    ]);
  };
  const removeItem = (id: number) => setItens(p => p.filter(i => i.id !== id));
  const total = itens.reduce(
    (s, i) => s + (i.quantidade_negociada ?? i.quantidade) * (i.preco_por_unidade_negociada ?? i.preco_final) - i.desconto,
    0,
  );
  const custoTotal = itens.reduce((s, i) => s + i.quantidade * i.custo_final, 0);
  const receitaTotal = total;
  const lucroTotal = receitaTotal - custoTotal;
  const margemMedia = receitaTotal > 0 ? (lucroTotal / receitaTotal) * 100 : 0;
  const quantidadeTotalItens = itens.reduce((s, i) => s + (i.quantidade_negociada ?? i.quantidade), 0);
  const existeAvulsoSemNcm = itens.some(
    (i) => (i.item_avulso ?? inferItemAvulso(i)) && !ncmFiscalDigitsValid(i.ncm_avulso || ''),
  );

  const openNew = () => {
    const hoje = dataHojeIso();
    setEditing(null);
    setClienteAvulso(false);
    setSelectedCliente(null);
    setSelectedVendedor(null);
    setSelectedColaboradorVendedor(null);
    setProdutoCache(new Map());
    setForm({
      numero: '',
      cliente_id: null,
      cliente_avulso_nome: '',
      empresa_emitente_id: empresas.length === 1 ? empresas[0]?.id ?? null : null,
      data: hoje,
      validade_dias: VALIDADE_DIAS_PADRAO,
      frete_texto: '',
      mensagem_comercial: MENSAGEM_COMERCIAL_PADRAO,
      observacoes_proposta: '',
      referencia_cliente: '',
      vendedor_id: null,
      status: STATUS_PROPOSTA_INICIAL,
      condicao_pagamento_texto: CONDICAO_PAGAMENTO_PADRAO,
      prazo_entrega_texto: '',
      uf_destino_avulso: '',
      usar_cenario_fiscal_saida: true,
      cenario_fiscal_saida_id: null,
    });
    void propostasService.sugestaoNova(null).then((s) => {
      setForm((p) => ({
        ...p,
        mensagem_comercial: (s.mensagem_comercial || '').trim() || MENSAGEM_COMERCIAL_PADRAO,
      }));
    });
    setItens([]);
    setHomologacaoStatus('NAO_INICIADA');
    setHomologacaoObservacao('');
    setHomologacaoEm(null);
    setModalOpen(true);
    void colaboradoresService.getVinculado().then((c) => {
      if (c?.vendedor_id) {
        setSelectedColaboradorVendedor(c);
        setSelectedVendedor({ id: c.vendedor_id, nome: c.nome, codigo: c.codigo, ativo: true });
        setForm((p) => ({ ...p, vendedor_id: c.vendedor_id! }));
        void propostasService.sugestaoNova(c.vendedor_id).then((s) => {
          setForm((p) => ({
            ...p,
            mensagem_comercial: (s.mensagem_comercial || '').trim() || MENSAGEM_COMERCIAL_PADRAO,
          }));
        });
        return;
      }
      void vendedoresService.getVinculado().then((v) => {
        if (!v) return;
        setSelectedVendedor(v);
        setSelectedColaboradorVendedor(colaboradorStubForDisplay(v.id, v.nome, v.codigo, v.id));
        setForm((p) => ({ ...p, vendedor_id: v.id }));
        void propostasService.sugestaoNova(v.id).then((s) => {
          setForm((p) => ({
            ...p,
            mensagem_comercial: (s.mensagem_comercial || '').trim() || MENSAGEM_COMERCIAL_PADRAO,
          }));
        });
      });
    });
  };
  const openEdit = (e: Proposta) => {
    setEditing(e);
    setClienteAvulso(!e.cliente_id);
    hydrateCliente(e.cliente_id ?? null, e.cliente_nome);
    hydrateVendedor(e.vendedor_id ?? null, e.vendedor_nome || e.vendedor);
    hydrateProdutosItens(e.itens);
    setForm({
      numero: e.numero,
      cliente_id: e.cliente_id ?? null,
      cliente_avulso_nome: e.cliente_avulso_nome ?? '',
      empresa_emitente_id: e.empresa_emitente_id ?? (empresas.length === 1 ? empresas[0]?.id ?? null : null),
      data: e.data,
      validade_dias: e.validade_dias ?? diasValidadeEntreDatas(e.data, e.validade) ?? VALIDADE_DIAS_PADRAO,
      frete_texto: e.frete_texto ?? '',
      mensagem_comercial: e.mensagem_comercial ?? '',
      observacoes_proposta: e.observacoes_proposta ?? '',
      referencia_cliente: e.referencia_cliente ?? '',
      vendedor_id: e.vendedor_id ?? null,
      status: e.status,
      condicao_pagamento_texto: e.condicao_pagamento_texto,
      prazo_entrega_texto: e.prazo_entrega_texto ?? '',
      uf_destino_avulso: e.uf_destino_avulso ?? '',
      usar_cenario_fiscal_saida: Boolean(e.usar_cenario_fiscal_saida),
      cenario_fiscal_saida_id: e.cenario_fiscal_saida_id ?? null,
    });
    setItens(e.itens.map((it) => normalizeItem(it)));
    setHomologacaoStatus(e.homologacao_fiscal_status ?? 'NAO_INICIADA');
    setHomologacaoObservacao(e.homologacao_fiscal_observacao ?? '');
    setHomologacaoEm(e.homologacao_fiscal_em ?? null);
    setModalOpen(true);
  };

  const refreshItensAposHomologacao = useCallback(async () => {
    if (!editing?.id) return;
    try {
      const p = await propostasService.getById(editing.id);
      setEditing(p);
      setItens(p.itens.map((it) => normalizeItem(it)));
      setForm((prev) => ({
        ...prev,
        usar_cenario_fiscal_saida: Boolean(p.usar_cenario_fiscal_saida),
        cenario_fiscal_saida_id: p.cenario_fiscal_saida_id ?? null,
      }));
      setHomologacaoStatus(p.homologacao_fiscal_status ?? 'NAO_INICIADA');
      setHomologacaoObservacao(p.homologacao_fiscal_observacao ?? '');
      setHomologacaoEm(p.homologacao_fiscal_em ?? null);
    } catch {
      /* mantém estado local se falhar refresh */
    }
  }, [editing?.id]);

  useEffect(() => {
    if (!modalOpen) return;
    void cenariosFiscaisSaidaService
      .getAll()
      .then(setCenariosSaida)
      .catch(() => setCenariosSaida([]));
  }, [modalOpen]);
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await propostasService.delete(id); load(); } };
  const handleSave = async () => {
    if (!clienteAvulso && !form.cliente_id) {
      toast.error('Selecione um cliente cadastrado ou marque cliente avulso.');
      return;
    }
    if (empresas.length > 1 && !form.empresa_emitente_id) {
      toast.error('Selecione a empresa emitente (matriz ou filial).');
      return;
    }
    if (clienteAvulso && !form.uf_destino_avulso) {
      toast.error('Informe a UF destino para contexto fiscal da proposta.');
      return;
    }
    if (!form.validade_dias || form.validade_dias < 1) {
      toast.error('Informe a validade da proposta em dias (mínimo 1).');
      return;
    }
    const condPreview = previewCondicaoPagamento(form.condicao_pagamento_texto, form.data);
    if (condPreview.erro) {
      toast.error(condPreview.erro);
      return;
    }
    const dias = condPreview.prazos ?? [];
    const vencimentos = buildDueDates(form.data, dias);
    const payloadForm = {
      ...form,
      validade: validadeCalculadaIso || validadeIsoFromDias(form.data, form.validade_dias),
      usar_cenario_fiscal_saida: editing ? form.usar_cenario_fiscal_saida : true,
      cliente_id: clienteAvulso ? null : form.cliente_id,
      cliente_avulso_nome: clienteAvulso ? form.cliente_avulso_nome : '',
      uf_destino_avulso: clienteAvulso ? form.uf_destino_avulso : '',
    };
    const data = {
      ...payloadForm,
      itens,
      valor_total: total,
    };
    const payload = { ...data, dias_parcelas: dias, quantidade_parcelas: dias.length, vencimentos_previstos: vencimentos };
    if (!editing && !form.numero?.trim()) {
      delete (payload as { numero?: string }).numero;
    }
    try {
      if (editing) await propostasService.update(editing.id, payload);
      else await propostasService.create(payload as Omit<Proposta, 'id'>);
      setModalOpen(false);
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível salvar a proposta.' }));
    }
  };
  const refreshProposta = async (id: number) => {
    const updated = await propostasService.getById(id);
    setWizardProposta(updated);
    return updated;
  };

  const abrirPedidoPorId = (pedidoId: number) => {
    navigate(`/pedidos-venda?pedido=${pedidoId}`);
  };

  const abrirPedidoDaProposta = (proposta: Pick<Proposta, 'pedido_venda_id' | 'pedido_venda_numero'>) => {
    if (!proposta.pedido_venda_id) return;
    abrirPedidoPorId(proposta.pedido_venda_id);
  };

  const abrirGerarPedidoModal = (proposta: Proposta) => {
    setEditing(proposta);
    setGerarPedidoOpen(true);
  };

  const confirmarGerarPedido = async (payload: {
    itens: { proposta_item_id: number }[];
    acao_itens_nao_selecionados: 'MANTER_PENDENTE' | 'CANCELAR';
    observacao: string;
  }) => {
    if (!editing?.id) return;
    setGerarPedidoLoading(true);
    try {
      const r = await propostasService.gerarPedido(editing.id, payload);
      setGerarPedidoOpen(false);
      const p = await propostasService.getById(editing.id);
      setEditing(p);
      await load();
      const abrir = window.confirm(`Pedido de Venda nº ${r.numero} gerado com sucesso.\n\nDeseja abrir o pedido agora?`);
      if (abrir) abrirPedidoPorId(r.pedido_id);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível gerar o pedido de venda.' }));
    } finally {
      setGerarPedidoLoading(false);
    }
  };

  const confirmarRecuperarProposta = async (motivo: string) => {
    if (!editing?.id) return;
    setRecuperarLoading(true);
    try {
      const r = await propostasService.recuperar(editing.id, { motivo });
      const p = await propostasService.getById(editing.id);
      setEditing(p);
      setRecuperarOpen(false);
      await load();
      alert(r.mensagem);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível recuperar a proposta.' }));
    } finally {
      setRecuperarLoading(false);
    }
  };

  const startWizard = async (proposta: Proposta) => {
    if (propostaRequerRecuperacao(proposta)) {
      setEditing(proposta);
      setRecuperarOpen(true);
      return;
    }
    if (propostaTotalmenteConvertida(proposta)) {
      if (proposta.pedido_venda_id) {
        abrirPedidoDaProposta(proposta);
        return;
      }
      alert('Esta proposta já foi convertida integralmente em pedido de venda.');
      return;
    }
    if (propostaPodeGerarPedido(proposta)) {
      abrirGerarPedidoModal(proposta);
      return;
    }
    setWizardOpen(true);
    setWizardStep(1);
    setWizardError(null);
    setWizardLoading(true);
    try {
      const current = await propostasService.getById(proposta.id);
      setWizardProposta(current);
      setWizardClienteId(current.cliente_id ?? null);
      setNovoClienteNome(current.cliente_avulso_nome ?? '');
      setNovoClienteCnpj('');
      const nextLinks: Record<number, number | null> = {};
      const nextDescricoes: Record<number, string> = {};
      current.itens.forEach((it) => {
        nextLinks[it.id] = it.produto_id ?? null;
        nextDescricoes[it.id] = it.descricao_avulsa ?? it.produto_nome ?? '';
      });
      setItemLinks(nextLinks);
      setNovoProdutoDescricao(nextDescricoes);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível iniciar o wizard de conversão.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const vincularClienteExistente = async () => {
    if (!wizardProposta || !wizardClienteId) return;
    setWizardLoading(true);
    setWizardError(null);
    try {
      await propostasService.update(wizardProposta.id, { cliente_id: wizardClienteId, cliente_avulso_nome: '' });
      await refreshProposta(wizardProposta.id);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível vincular o cliente.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const criarClienteDaProposta = async () => {
    if (!wizardProposta) return;
    const nome = (novoClienteNome || wizardProposta.cliente_avulso_nome || '').trim();
    const cnpj = novoClienteCnpj.replace(/\D/g, '');
    if (!nome) {
      setWizardError('Informe a razão social para criar o cliente.');
      return;
    }
    if (cnpj.length !== 14) {
      setWizardError('Informe um CNPJ válido com 14 dígitos para criar o cliente.');
      return;
    }
    setWizardLoading(true);
    setWizardError(null);
    try {
      const cliente = await clientesService.create({
        razao_social: nome,
        nome_fantasia: nome,
        cnpj,
        ie: '',
        logradouro: '',
        numero: '',
        complemento: '',
        bairro: '',
        cidade: '',
        uf: '',
        cep: '',
        telefone: '',
        email: '',
        contato_responsavel: '',
        observacoes: '',
        inscricao_municipal: '',
        suframa: '',
        email_nf: '',
        telefone_alternativo: '',
        celular: '',
        limite_credito: 0,
        condicao_pagamento_texto: '0',
        dias_parcelas: [0],
        quantidade_parcelas: 1,
        transportadora_padrao_id: null,
        vendedor_padrao: '',
        bloqueado: false,
        ativo: true,
        ddd: '',
        banco: '',
        agencia: '',
        conta: '',
        tipo_conta: '',
        cnae: '',
        regime_tributario: '',
        integracao_texto: '',
      });
      await propostasService.update(wizardProposta.id, { cliente_id: cliente.id, cliente_avulso_nome: '' });
      await refreshProposta(wizardProposta.id);
      hydrateCliente(cliente.id, cliente.razao_social);
      setWizardClienteId(cliente.id);
      setWizardStep(2);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível criar o cliente cadastrado.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const vincularItemExistente = async (itemId: number) => {
    if (!wizardProposta) return;
    const produtoId = itemLinks[itemId];
    if (!produtoId) {
      setWizardError('Selecione um produto para vincular o item avulso.');
      return;
    }
    const itensAtualizados = wizardProposta.itens.map((it) =>
      it.id === itemId ? { ...it, produto_id: produtoId, descricao_avulsa: '' } : it,
    );
    setWizardLoading(true);
    setWizardError(null);
    try {
      await propostasService.update(wizardProposta.id, { itens: itensAtualizados });
      await refreshProposta(wizardProposta.id);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível vincular o item ao produto.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const criarProdutoParaItem = async (itemId: number) => {
    if (!wizardProposta) return;
    const descricao = (novoProdutoDescricao[itemId] || '').trim();
    if (!descricao) {
      setWizardError('Informe a descrição do novo produto.');
      return;
    }
    setWizardLoading(true);
    setWizardError(null);
    try {
      const produto = await produtosService.create({
        figura: 'AV',
        sufixo: 'LIVRE',
        schedule: 'STD',
        polegada_principal: '1/2"',
        polegada_secundaria: '',
        descricao,
        material: '',
        tipo_peca: '',
        pressao_nominal: '',
        norma: '',
        conexao: '',
        ncm: '',
        preco_custo: 0,
        preco_venda: 0,
        estoque_minimo: 0,
        codigo_completo: '',
      });
      const itensAtualizados = wizardProposta.itens.map((it) =>
        it.id === itemId ? { ...it, produto_id: produto.id, descricao_avulsa: '' } : it,
      );
      await propostasService.update(wizardProposta.id, { itens: itensAtualizados });
      mergeProdutoCache(produto);
      await refreshProposta(wizardProposta.id);
      setItemLinks((prev) => ({ ...prev, [itemId]: produto.id }));
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível criar o produto para o item.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const clienteResolvido = Boolean(wizardProposta?.cliente_id);
  const itensPendentes = wizardProposta?.itens.filter((it) => !it.produto_id) ?? [];
  const itensResolvidos = (wizardProposta?.itens.length ?? 0) - itensPendentes.length;
  const podeConverter = Boolean(
    wizardProposta &&
      !propostaTotalmenteConvertida(wizardProposta) &&
      !propostaRequerRecuperacao(wizardProposta) &&
      clienteResolvido &&
      itensPendentes.length === 0,
  );

  const concluirConversao = async () => {
    if (!wizardProposta || !podeConverter) return;
    if (!confirm(MSG_CONFIRMACAO_CONVERTER_PEDIDO)) return;
    setWizardLoading(true);
    setWizardError(null);
    try {
      const ids = wizardProposta.itens
        .filter((it) => it.pode_selecionar_para_pedido !== false && it.status_comercial !== 'CONVERTIDO_EM_PEDIDO')
        .map((it) => it.id);
      const r = await propostasService.gerarPedido(wizardProposta.id, {
        itens: ids.map((id) => ({ proposta_item_id: id })),
        acao_itens_nao_selecionados: 'MANTER_PENDENTE',
      });
      setWizardOpen(false);
      await load();
      alert(`Pedido de venda ${r.numero} criado com sucesso (${r.itens_criados} itens).`);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível converter a proposta em pedido.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const handleVisualizarPdf = async (proposta: Proposta) => {
    const id = Number(proposta?.id);
    if (!Number.isFinite(id) || id <= 0) {
      alert(MSG_SALVE_ANTES_PDF);
      return;
    }
    const previewTab = window.open('about:blank', '_blank');
    if (!previewTab) {
      alert('Não foi possível abrir uma nova aba (pop-up bloqueado). Permita pop-ups e tente novamente.');
      return;
    }
    try {
      await propostasService.visualizarPdf(id, proposta.numero || String(id), previewTab);
    } catch (e) {
      previewTab.close();
      alert(e instanceof Error ? e.message : 'Não foi possível visualizar o PDF da proposta.');
    }
  };

  const handleBaixarPdf = async (proposta: Proposta) => {
    const id = Number(proposta?.id);
    if (!Number.isFinite(id) || id <= 0) {
      alert(MSG_SALVE_ANTES_PDF);
      return;
    }
    try {
      await propostasService.baixarPdf(id, proposta.numero || String(id));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Não foi possível baixar o PDF da proposta.');
    }
  };

  const condicaoPreview = previewCondicaoPagamento(form.condicao_pagamento_texto, form.data);
  const isNovaProposta = !editing;
  const usaCenarioUi = propostaUsaMotorCenario(form, { isNew: isNovaProposta });
  const propostaLegadoFiscal = Boolean(editing && !editing.usar_cenario_fiscal_saida);
  const statusOpcoesProposta = [
    { value: 'PENDENTE', label: 'Pendente' },
    { value: 'Aprovada', label: 'Aprovada' },
    { value: 'Rejeitada', label: 'Rejeitada' },
  ];
  if (editing && propostaTotalmenteConvertida(editing)) {
    statusOpcoesProposta.unshift({ value: STATUS_PROPOSTA_CONVERTIDA, label: 'Convertida' });
  } else if (editing && propostaTemPedidoGerado(editing)) {
    statusOpcoesProposta.unshift({ value: STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA, label: 'Parcialmente convertida' });
  }
  if (editing && (editing.status || '').toUpperCase() === STATUS_PROPOSTA_REABERTA) {
    statusOpcoesProposta.unshift({ value: STATUS_PROPOSTA_REABERTA, label: 'Reaberta' });
  }
  if (editing && ['Pendente', 'pendente'].includes(editing.status)) {
    statusOpcoesProposta.push({ value: 'Pendente', label: 'Pendente (legado)' });
  }
  const propostaConvertidaNoModal = Boolean(editing && propostaTotalmenteConvertida(editing));
  const cenarioSelecionado =
    cenariosSaida.find((c) => c.id === form.cenario_fiscal_saida_id) ??
    cenariosSaida.find((c) => c.padrao) ??
    null;
  const margemBadgeClass =
    margemMedia >= 20
      ? 'erp-badge-success'
      : margemMedia >= 10
        ? 'erp-badge-warning'
        : 'erp-badge-danger';

  const updateItem = (idx: number, patch: Partial<ItemProposta>) => {
    let snapshot: ItemProposta | null = null;
    setItens((prev) => {
      const merged = { ...prev[idx], ...patch };
      if (Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada')) {
        merged.quantidade = Number(merged.quantidade_negociada ?? merged.quantidade ?? 0);
      }
      if (Object.prototype.hasOwnProperty.call(patch, 'preco_por_unidade_negociada')) {
        const p = Number(merged.preco_por_unidade_negociada ?? merged.preco_final ?? 0);
        merged.preco_final = p;
        merged.valor_unitario = p;
      }
      snapshot = merged;
      const next = [...prev];
      next[idx] = recalcPropostaItem(merged);
      return next;
    });
    if (
      snapshot &&
      (Object.prototype.hasOwnProperty.call(patch, 'produto_id') ||
        Object.prototype.hasOwnProperty.call(patch, 'ncm_avulso') ||
        Object.prototype.hasOwnProperty.call(patch, 'quantidade') ||
        Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada') ||
        Object.prototype.hasOwnProperty.call(patch, 'unidade_negociada'))
    ) {
      void mergeRowWithFiscal(snapshot).then((f) => {
        setItens((prev) => {
          const n = [...prev];
          if (!n[idx]) return prev;
          n[idx] = recalcPropostaItem({ ...n[idx], ...f });
          return n;
        });
      });
      void (async () => {
        const row = snapshot;
        if (!row?.produto_id) return;
        const produto = produtosRef.current.find((p) => p.id === row.produto_id);
        const unidadeNegociada = (row.unidade_negociada || produto?.unidade_venda_efetiva || produto?.unidade || 'PC').toUpperCase();
        const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
        const unidadeEstoque = (produto?.unidade_estoque_efetiva || produto?.unidade_estoque || produto?.unidade || 'PC').toUpperCase();
        if (!produto?.usa_conversao_dimensional_efetivo || unidadeNegociada === unidadeEstoque) {
          setItens((prev) => {
            const n = [...prev];
            if (!n[idx]) return prev;
            n[idx] = recalcPropostaItem({
              ...n[idx],
              unidade_negociada: unidadeNegociada,
              quantidade_negociada: quantidadeNegociada,
              unidade_estoque_calculada: unidadeEstoque,
              quantidade_estoque_calculada: quantidadeNegociada,
              fator_conversao: 1,
            });
            return n;
          });
          return;
        }
        try {
          const conv = await produtosService.converterMedida({
            produto_id: row.produto_id,
            quantidade: quantidadeNegociada,
            unidade_origem: unidadeNegociada,
            unidade_destino: unidadeEstoque,
          });
          const qtdOrig = Number(conv.quantidade_origem || quantidadeNegociada);
          const qtdDest = Number(conv.quantidade_destino || quantidadeNegociada);
          setItens((prev) => {
            const n = [...prev];
            if (!n[idx]) return prev;
            n[idx] = recalcPropostaItem({
              ...n[idx],
              unidade_negociada: unidadeNegociada,
              quantidade_negociada: qtdOrig,
              quantidade: qtdOrig,
              unidade_estoque_calculada: conv.unidade_estoque || unidadeEstoque,
              quantidade_estoque_calculada: qtdDest,
              peso_total_kg: Number(conv.peso_kg || 0),
              metros_total: Number(conv.metros || 0),
              barras_total: Number(conv.barras || 0),
              fator_conversao: qtdOrig ? qtdDest / qtdOrig : 0,
            });
            return n;
          });
        } catch {
          // Sem bloqueio na fase 1: mantém fluxo comercial atual.
        }
      })();
    }
  };

  return (
    <div>
      <PageHeader
        title="Propostas"
        description="Gestão de propostas comerciais e acompanhamento até conversão em pedido."
        onAdd={openNew}
        addLabel="Nova Proposta"
        searchValue={search}
        onSearch={setSearch}
      />
      <FilterBar
        filters={[
          {
            key: 'status',
            label: 'Status',
            value: filters.status || '',
            options: [
              { value: 'PENDENTE', label: 'Pendente' },
              { value: 'Aprovada', label: 'Aprovada' },
              { value: 'Rejeitada', label: 'Rejeitada' },
              { value: 'CONVERTIDA', label: 'Convertida' },
              { value: STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA, label: 'Parcialmente convertida' },
              { value: STATUS_PROPOSTA_REABERTA, label: 'Reaberta' },
            ],
          },
        ]}
        onChange={setFilter}
      />
      {loadError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {loadingList ? <TableSkeleton rows={6} cols={8} /> : null}
      {!loadingList && !loadError ? (
        <DataTableShell>
        <DataTable>
          <thead><tr><th>Número</th><th>Cliente</th><th>Data</th><th>Validade</th><th>Vendedor</th><th>Status</th><th>Valor Total</th><th className="w-36 text-right">Ações</th></tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <EmptyState
                    message="Nenhuma proposta encontrada para os filtros atuais."
                    actionLabel="Nova proposta"
                    onAction={openNew}
                  />
                </td>
              </tr>
            ) : (
            items.map(e => {
              const statusUi = statusPropostaUi(e);
              const temPedido = propostaTemPedidoGerado(e);
              const podeGerar = propostaPodeGerarPedido(e);
              return (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.cliente_nome || e.cliente_avulso_nome || 'Cliente avulso'}</td><td>{formatDateBr(e.data)}</td><td>{formatDateBr(e.validade)}</td><td>{e.vendedor_nome || e.vendedor || '—'}</td>
                <td><StatusBadge status={statusUi.label} /></td>
                <td>{formatMoneyBr(e.valor_total)}</td>
                <td className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    {temPedido && !podeGerar ? (
                      <button
                        type="button"
                        onClick={() => abrirPedidoDaProposta(e)}
                        className="erp-btn-ghost erp-btn-sm"
                        title="Abrir pedido de venda"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => startWizard(e)}
                        className="erp-btn-ghost erp-btn-sm"
                        title={podeGerar ? 'Gerar pedido de venda' : 'Converter em pedido'}
                      >
                        <ShoppingCart className="h-4 w-4" />
                      </button>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button type="button" className="erp-btn-ghost erp-btn-sm" aria-label="Ações da proposta">
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-52" onOpenAutoFocus={(ev) => ev.preventDefault()}>
                        <DropdownMenuItem className="cursor-pointer" onSelect={() => openEdit(e)}>
                          <span className="flex items-center gap-2">
                            <Pencil className="h-4 w-4" />
                            Editar
                          </span>
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleVisualizarPdf(e)}>
                          <span className="flex items-center gap-2">
                            <FileDown className="h-4 w-4" />
                            Visualizar PDF
                          </span>
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleBaixarPdf(e)}>
                          <span className="flex items-center gap-2">
                            <Download className="h-4 w-4" />
                            Baixar PDF
                          </span>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="cursor-pointer text-destructive focus:text-destructive"
                          onSelect={() => handleDelete(e.id)}
                        >
                          <span className="flex items-center gap-2">
                            <Trash2 className="h-4 w-4" />
                            Excluir
                          </span>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Proposta' : 'Nova Proposta'} size="xl">
        <div className="space-y-4 mb-4">
          <ComercialModalSection title="Cabeçalho" description="Dados principais da proposta comercial.">
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="erp-label">Número</label>
                  <input
                    className="erp-input mt-1"
                    placeholder="Gerado automaticamente no padrão comercial"
                    value={form.numero}
                    onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))}
                  />
                  {!editing ? (
                    <p className="text-[10px] text-muted-foreground mt-1">
                      Deixe em branco para gerar ao salvar (ex.: PROP-AAAAMMDD-NNNN).
                    </p>
                  ) : null}
                </div>
                <DateBrInput
                  label="Data"
                  valueIso={form.data}
                  onChangeIso={(iso) =>
                    setForm((p) => ({
                      ...p,
                      data: iso,
                    }))
                  }
                />
                <div>
                  <label className="erp-label">Validade da proposta (dias)</label>
                  <IntegerInput
                    value={form.validade_dias}
                    min={1}
                    className="erp-input mt-1"
                    onChange={(value) => setForm((p) => ({ ...p, validade_dias: value || VALIDADE_DIAS_PADRAO }))}
                  />
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Válida até {formatDateBr(validadeCalculadaIso) || '—'}
                  </p>
                </div>
                <div>
                  <label className="erp-label">Status</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={form.status}
                    disabled={propostaConvertidaNoModal}
                    onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                  >
                    {statusOpcoesProposta.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 min-w-0">
                  <label className="erp-label">Cliente</label>
                  <div className="mt-1 space-y-2">
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={clienteAvulso}
                        onChange={(e) => {
                          const avulso = e.target.checked;
                          setClienteAvulso(avulso);
                          if (avulso) {
                            setForm((p) => ({ ...p, cliente_id: null }));
                            setSelectedCliente(null);
                          }
                        }}
                      />
                      Cliente avulso (sem cadastro)
                    </label>
                    {clienteAvulso ? (
                      <div className="space-y-2">
                        <input
                          className="erp-input w-full"
                          placeholder="Nome do cliente avulso"
                          value={form.cliente_avulso_nome}
                          onChange={(e) => setForm((p) => ({ ...p, cliente_avulso_nome: e.target.value }))}
                        />
                        <div>
                          <label className="text-xs text-muted-foreground">UF destino</label>
                          <p className="text-[10px] text-muted-foreground">
                            Informe a UF destino para contexto fiscal da proposta.
                          </p>
                          <select
                            className="erp-select mt-1 w-full"
                            value={form.uf_destino_avulso}
                            onChange={(e) => setForm((p) => ({ ...p, uf_destino_avulso: e.target.value }))}
                          >
                            <option value="">Selecione</option>
                            {UFS.map((u) => (
                              <option key={u} value={u}>
                                {u}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ) : (
                      <ClienteComercialField
                        valueId={form.cliente_id}
                        selectedCliente={selectedCliente}
                        onSelect={(c) => {
                          setForm((p) => ({ ...p, cliente_id: c.id }));
                          setSelectedCliente(c);
                        }}
                        onClear={() => {
                          setForm((p) => ({ ...p, cliente_id: null }));
                          setSelectedCliente(null);
                        }}
                      />
                    )}
                  </div>
                </div>
                <div className="min-w-0 lg:max-w-xs">
                  <label className="erp-label">Vendedor</label>
                  <VendedorComercialField
                    valueId={form.vendedor_id}
                    selectedVendedor={selectedVendedor}
                    selectedColaborador={selectedColaboradorVendedor}
                    onSelect={(vendedorId, colab) => {
                      setForm((p) => ({ ...p, vendedor_id: vendedorId }));
                      setSelectedColaboradorVendedor(colab);
                      setSelectedVendedor({ id: vendedorId, nome: colab.nome, codigo: colab.codigo, ativo: true });
                    }}
                    onClear={() => {
                      setForm((p) => ({ ...p, vendedor_id: null }));
                      setSelectedVendedor(null);
                      setSelectedColaboradorVendedor(null);
                    }}
                  />
                </div>
              </div>

              {empresas.length > 1 ? (
                <div>
                  <label className="erp-label">Empresa emitente</label>
                  <select
                    className="erp-select mt-1 w-full max-w-xl"
                    value={form.empresa_emitente_id ?? ''}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, empresa_emitente_id: e.target.value ? Number(e.target.value) : null }))
                    }
                  >
                    <option value="">Selecione matriz ou filial</option>
                    {empresas.map((em) => (
                      <option key={em.id} value={em.id}>
                        {em.razao_social}
                        {em.uf ? ` (${em.uf})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              ) : empresas.length === 1 ? (
                <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground max-w-xl">
                  Emitente: <span className="font-medium text-foreground">{empresas[0].razao_social}</span>
                  {empresas[0].uf ? ` · UF origem ${empresas[0].uf}` : ''}
                </div>
              ) : null}
            </div>
          </ComercialModalSection>

          <ComercialModalSection
            title="Condições comerciais"
            description="Condição de pagamento em texto comercial livre (ex.: 30 DDL, 30/45 DDL, À vista, A combinar)."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="erp-label">Condição de pagamento</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Ex.: 30 DDL, 30/45 DDL, À vista, A combinar"
                  value={form.condicao_pagamento_texto}
                  onChange={(e) => setForm((p) => ({ ...p, condicao_pagamento_texto: e.target.value }))}
                />
              </div>
              <div>
                <label className="erp-label">Resumo de parcelas</label>
                <div className="erp-input mt-1 min-h-10 h-auto py-2 flex items-center">
                  {condicaoPreview.erro ? '—' : condicaoPreview.resumo}
                </div>
              </div>
              <div>
                <label className="erp-label">Nº da requisição / cotação do cliente</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Opcional"
                  value={form.referencia_cliente}
                  onChange={(e) => setForm((p) => ({ ...p, referencia_cliente: e.target.value }))}
                />
              </div>
              <div>
                <label className="erp-label">Frete / condição de frete</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Ex.: FOB – POSTO / SP, CIF, RETIRA, A COMBINAR"
                  value={form.frete_texto}
                  onChange={(e) => setForm((p) => ({ ...p, frete_texto: e.target.value }))}
                />
              </div>
              <div className="md:col-span-2">
                <label className="erp-label">Mensagem comercial</label>
                <textarea
                  className="erp-input mt-1 min-h-[72px]"
                  rows={3}
                  value={form.mensagem_comercial}
                  onChange={(e) => setForm((p) => ({ ...p, mensagem_comercial: e.target.value }))}
                />
              </div>
              <div className="md:col-span-2">
                <label className="erp-label">Observações da proposta</label>
                <textarea
                  className="erp-input mt-1 min-h-[72px]"
                  rows={3}
                  value={form.observacoes_proposta}
                  onChange={(e) => setForm((p) => ({ ...p, observacoes_proposta: e.target.value }))}
                />
              </div>
              <div>
                <label className="erp-label">Prazo de entrega</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Ex.: 30 dias após aprovação do pedido"
                  value={form.prazo_entrega_texto}
                  onChange={(e) => setForm((p) => ({ ...p, prazo_entrega_texto: e.target.value }))}
                />
              </div>
              <div className="md:col-span-2">
                <label className="erp-label">Vencimentos previstos</label>
                <div className="mt-1 rounded-md border border-border bg-muted/10 p-3">
                  <CondicaoPagamentoResumo condicao={form.condicao_pagamento_texto} dataBaseIso={form.data} />
                </div>
              </div>
              <p className="md:col-span-2 text-xs text-muted-foreground">
                Validade: {form.validade_dias} dia(s) · Válida até {formatDateBr(validadeCalculadaIso) || '—'} · Prazo de entrega:{' '}
                {(form.prazo_entrega_texto || '').trim() || '—'}
              </p>
            </div>
          </ComercialModalSection>

          <ComercialModalSection title="Fiscal" description="Fonte fiscal operacional da proposta.">
            <div className="space-y-3">
              <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
                <p className="text-xs font-semibold text-foreground">Fonte fiscal</p>
                <p className="text-sm font-medium mt-1">Cenário Fiscal de Saída</p>
                <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
                  Esta proposta usa o Cenário Fiscal de Saída. Regras legadas permanecem apenas para compatibilidade
                  histórica no backend.
                </p>
              </div>
              {propostaLegadoFiscal ? (
                <p className="text-[11px] text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                  Esta proposta foi criada usando regra fiscal legada. O cálculo histórico é preservado; novas edições
                  seguem o cenário quando salvas pelo fluxo atual.
                </p>
              ) : null}
              {usaCenarioUi && cenariosSaida.length > 0 ? (
                <div>
                  <label className="text-xs text-muted-foreground">Cenário aplicado</label>
                  <select
                    className="erp-select mt-1 w-full max-w-md"
                    value={form.cenario_fiscal_saida_id ?? ''}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        cenario_fiscal_saida_id: e.target.value ? Number(e.target.value) : null,
                      }))
                    }
                  >
                    <option value="">Cenário padrão de saída</option>
                    {cenariosSaida.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                        {c.padrao ? ' (padrão)' : ''}
                      </option>
                    ))}
                  </select>
                  {cenarioSelecionado ? (
                    <p className="text-[10px] text-muted-foreground mt-1">Selecionado: {cenarioSelecionado.nome}</p>
                  ) : (
                    <p className="text-[10px] text-muted-foreground mt-1">Será usado o cenário padrão do sistema.</p>
                  )}
                </div>
              ) : null}
              {resolveUfOrigemEmitente() && resolveUfDestino() ? (
                <p className="text-[11px] text-muted-foreground">
                  UF origem {resolveUfOrigemEmitente()} → UF destino {resolveUfDestino()} · Operação: saída
                </p>
              ) : (
                <p className="text-[11px] text-muted-foreground">Defina emitente e cliente (ou UF avulsa) para o contexto fiscal.</p>
              )}
            </div>
          </ComercialModalSection>

          {editing?.id && usaCenarioUi && !USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS ? (
            <HomologacaoFiscalPropostaPanel
              propostaId={editing.id}
              homologacaoStatus={homologacaoStatus}
              homologacaoObservacao={homologacaoObservacao}
              homologacaoEm={homologacaoEm}
              cenariosSaida={cenariosSaida}
              onPropostaFiscalAtualizada={(patch) => {
                setHomologacaoStatus(patch.homologacao_fiscal_status);
                setHomologacaoObservacao(patch.homologacao_fiscal_observacao ?? '');
                setHomologacaoEm(patch.homologacao_fiscal_em ?? null);
                setForm((p) => ({
                  ...p,
                  usar_cenario_fiscal_saida: patch.usar_cenario_fiscal_saida,
                  cenario_fiscal_saida_id: patch.cenario_fiscal_saida_id,
                }));
              }}
              onItensRecalculados={refreshItensAposHomologacao}
            />
          ) : null}
        </div>

        <ComercialModalSection title="Itens" className="mb-4">
        <div className="border border-border rounded-md p-3 -mx-0">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button onClick={addItem} className="erp-btn-outline erp-btn-sm"><Plus className="h-3 w-3" /> Adicionar Item</button>
          </div>
          {existeAvulsoSemNcm ? (
            <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
              Há item(ns) avulso(s) sem NCM válido (8 dígitos): a proposta segue como <strong>simulação comercial</strong> para tributos de
              saída. Para converter em pedido ou faturar, informe o NCM em cada item avulso e depois vincule um produto cadastrado.
            </div>
          ) : null}
          {itens.map((item, idx) => {
            const pctSaida = percentualSaidaTotal(item);
            const precoRef = item.modo_preco === 'manual' ? item.preco_final : item.preco_sugerido;
            const valCarga = computeValorCargaSaida(precoRef, pctSaida);
            const ipiEntradaVal = computeIpiEntradaValor(
              item.custo_utilizado,
              item.ipi_entrada_percentual ?? 0,
              item.ipi_custo ?? 0,
            );
            const margemBadge =
              item.margem_resultante >= 15 ? 'erp-badge-success' : item.margem_resultante >= 8 ? 'erp-badge-warning' : 'erp-badge-danger';
            const ufO = resolveUfOrigemEmitente();
            const ufD = resolveUfDestino();
            const produtoCached = item.produto_id ? produtoCache.get(item.produto_id) : undefined;
            const ncmBusca = item.produto_id
              ? normalizeNcm(produtoCached?.ncm || '')
              : normalizeNcm(item.ncm_avulso || '');
            const cmpKey = String(item.id);
            const cmp = comparativoFiscal[cmpKey];
            const podeComparar =
              ncmFiscalDigitsValid(ncmBusca) && ufO.length === 2 && ufD.length === 2;
            let msgRegra = '';
            const itemAvulso = item.item_avulso ?? inferItemAvulso(item);
            if (itemAvulso && !ncmFiscalDigitsValid(item.ncm_avulso || '')) {
              msgRegra =
                'Item avulso sem NCM (8 dígitos): tributos de saída zerados. Informe o NCM para buscar a Regra Fiscal ou vincule um produto cadastrado.';
            } else if (ufO.length !== 2 || ufD.length !== 2) {
              msgRegra = 'Defina empresa emitente com UF, cliente com UF ou UF destino (cliente avulso) para localizar a regra fiscal.';
            } else if (item.regra_fiscal_origem === 'NAO_ENCONTRADA' || (!item.regra_fiscal_id && !item.regra_fiscal_saida_id)) {
              msgRegra =
                'Não encontramos regra fiscal para este NCM com UF origem/destino e operação saída. Cadastre a regra em Regras fiscais ou revise o NCM.';
            } else {
              const origemLabel = labelOrigemRegraFiscal(item.regra_fiscal_origem);
              const idRef =
                item.regra_fiscal_origem === 'CENARIO_SAIDA'
                  ? item.regra_fiscal_saida_id
                  : item.regra_fiscal_id;
              msgRegra = origemLabel
                ? `${origemLabel}${idRef != null ? ` (id ${idRef})` : ''}.`
                : `Regra fiscal aplicada (id ${item.regra_fiscal_id ?? item.regra_fiscal_saida_id}).`;
            }
            return (
              <div key={item.id} className="mb-4 rounded-md border border-border p-3 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 md:col-span-2">
                    <label className="text-xs text-muted-foreground">Produto / item</label>
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={itemAvulso}
                        onChange={(e) =>
                          updateItem(
                            idx,
                            e.target.checked
                              ? {
                                  item_avulso: true,
                                  produto_id: null,
                                  produto_nome: '',
                                }
                              : {
                                  item_avulso: false,
                                  descricao_avulsa: '',
                                  ncm_avulso: '',
                                },
                          )
                        }
                      />
                      Item avulso
                    </label>
                  </div>
                  <button type="button" onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                {itemAvulso ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-3xl">
                    <div>
                      <label className="text-xs text-muted-foreground">Descrição (item avulso)</label>
                      <input
                        className="erp-input h-8 text-sm mt-1"
                        placeholder="Descrição comercial"
                        value={item.descricao_avulsa ?? ''}
                        onChange={(e) => updateItem(idx, { descricao_avulsa: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">NCM (busca na base — regra fiscal)</label>
                      <NcmAutocomplete
                        value={
                          item.ncm_avulso
                            ? ({
                                id: -(item.id as number),
                                codigo: normalizeNcm(item.ncm_avulso),
                                descricao: '',
                              } satisfies NcmOption)
                            : null
                        }
                        searchNcm={(term, limit) => ncmApiService.search(term, limit)}
                        onChange={(opt) =>
                          updateItem(idx, { ncm_avulso: opt ? normalizeNcm(opt.codigo) : '' })
                        }
                      />
                    </div>
                  </div>
                ) : (
                  <div className="w-full min-w-0">
                    <ProdutoComercialField
                      compact
                      valueId={item.produto_id}
                      selectedProduto={produtoCached ?? null}
                      onSelect={(pr) => {
                        mergeProdutoCache(pr);
                        const unidades = unidadesNegociacaoProduto(pr);
                        updateItem(idx, {
                          produto_id: pr.id,
                          produto_nome: pr.descricao,
                          descricao_avulsa: '',
                          ncm_avulso: '',
                          unidade_negociada: unidades[0] || item.unidade_negociada,
                        });
                      }}
                      onClear={() => {
                        updateItem(idx, { produto_id: null, produto_nome: '', descricao_avulsa: '', ncm_avulso: '' });
                      }}
                    />
                  </div>
                )}

                <ItemComercialMetricasGrid>
                  <div>
                    <label className="text-xs text-muted-foreground">Unidade negociada</label>
                    <UnitSelect
                      value={item.unidade_negociada || ''}
                      className="erp-input h-9 text-sm w-full min-w-[160px] text-left leading-normal py-1.5"
                      options={(() => {
                        const p = item.produto_id ? produtoCache.get(item.produto_id) : undefined;
                        return p ? unidadesNegociacaoProduto(p) : todasUnidadesPadrao();
                      })()}
                      onChange={(value) => updateItem(idx, { unidade_negociada: value })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Quantidade negociada</label>
                    <QuantityInput
                      value={Number(inputNumberValue(item.quantidade_negociada ?? item.quantidade, 1))}
                      className={numericClass}
                      onChange={(value) => updateItem(idx, { quantidade_negociada: value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">{labelPrecoPorUnidade(item.unidade_negociada)}</label>
                    <MoneyInput
                      value={Number(inputNumberValue(item.preco_por_unidade_negociada ?? item.preco_final))}
                      className={numericClass}
                      step="0.0001"
                      onChange={(value) => updateItem(idx, { preco_por_unidade_negociada: value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Desconto (R$)</label>
                    <DiscountInput
                      value={Number(inputNumberValue(item.desconto))}
                      className={numericClass}
                      onChange={(value) => updateItem(idx, { desconto: value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Valor total</label>
                    <ReadonlyCalculatedField
                      className={`${numericClass} flex items-center justify-end`}
                      value={formatMoneyBr(
                        toNumber(item.quantidade_negociada ?? item.quantidade) *
                          toNumber(item.preco_por_unidade_negociada ?? item.preco_final),
                      )}
                    />
                  </div>
                </ItemComercialMetricasGrid>
                <p className="text-xs text-muted-foreground">{previewConversaoItem(item)}</p>
                {equivalentesPreco(item).length ? (
                  <p className="text-xs text-muted-foreground">{equivalentesPreco(item).join(' | ')}</p>
                ) : null}

                <details className="rounded-md border border-border bg-muted/10 group">
                  <summary className="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground select-none">
                    Custos e rentabilidade
                  </summary>
                  <div className="p-3 pt-0 space-y-3">
                <div className="space-y-2">
                  <p className="text-[11px] font-medium text-muted-foreground">Custo de entrada</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">Custo do produto</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.custo_utilizado)}
                        onChange={(e) => updateItem(idx, { custo_utilizado: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI entrada %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.ipi_entrada_percentual)}
                        onChange={(e) => updateItem(idx, { ipi_entrada_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">ST (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.st_custo)}
                        onChange={(e) => updateItem(idx, { st_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Frete entrada</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.frete)}
                        onChange={(e) => updateItem(idx, { frete: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Despesas entrada</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.despesas)}
                        onChange={(e) => updateItem(idx, { despesas: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Outros (entrada)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.outros_impostos_custo)}
                        onChange={(e) => updateItem(idx, { outros_impostos_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI entrada (R$ legado)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        title="Compatível com propostas antigas: usado só se IPI % = 0"
                        value={inputNumberValue(item.ipi_custo)}
                        onChange={(e) => updateItem(idx, { ipi_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs text-muted-foreground">IPI entrada calculado (R$)</label>
                      <div className="erp-input h-8 text-sm flex items-center">{formatMoneyBr(ipiEntradaVal)}</div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs text-muted-foreground font-medium">Custo carregado</label>
                      <div className="erp-input h-8 text-sm flex items-center font-medium">{formatMoneyBr(item.custo_final)}</div>
                    </div>
                  </div>
                </div>

                <details className="rounded-md border border-border bg-muted/10 group">
                  <summary className="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground select-none">
                    Fiscal aplicado
                  </summary>
                  <div className="p-3 pt-0 space-y-2">
                  <p className="text-[11px] font-medium text-muted-foreground">Tributos e despesas da venda</p>
                  <p className="text-[11px] font-medium text-muted-foreground">Da Regra Fiscal (automático)</p>
                  <p className="text-[11px] text-muted-foreground">
                    ICMS, PIS, COFINS e IPI de saída vêm da regra cadastrada (NCM {ncmBusca || '—'} + UF origem {ufO || '—'} + UF destino{' '}
                    {ufD || '—'} + saída). Campos somente leitura.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                    <div>
                      <label className="text-xs text-muted-foreground">ICMS saída %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{formatPercent(item.icms_saida_percentual)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">PIS %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{formatPercent(item.pis_saida_percentual)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">COFINS %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{formatPercent(item.cofins_saida_percentual)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI saída %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{formatPercent(item.ipi_saida_percentual)}</div>
                    </div>
                    <div className="md:col-span-2 text-[11px] text-muted-foreground flex flex-col justify-end leading-snug gap-0.5">
                      <span>{msgRegra}</span>
                      {item.regra_fiscal_origem === 'CENARIO_SAIDA' && item.pis_cofins_base_deduz_icms ? (
                        <span className="text-[10px] text-amber-700 dark:text-amber-400">
                          PIS/COFINS com base deduzida do ICMS
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="md:col-span-6 space-y-2 border-t border-border/60 pt-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="erp-btn-ghost erp-btn-sm h-7 text-xs"
                        disabled={!podeComparar || cmp === 'loading'}
                        onClick={() => void runComparativoFiscal(item)}
                      >
                        {cmp === 'loading' ? 'Comparando…' : 'Comparar fiscal'}
                      </button>
                      <span className="text-[10px] text-muted-foreground">
                        Comparativo legado × cenário (homologação — não altera o cálculo da proposta)
                      </span>
                    </div>
                    {cmp === 'error' ? (
                      <p className="text-[11px] text-muted-foreground">
                        Não foi possível comparar regras fiscais agora.
                      </p>
                    ) : null}
                    {cmp && cmp !== 'loading' && cmp !== 'error' ? (
                      <div className="rounded border border-border/80 bg-background/80 p-2 space-y-1.5 text-[11px]">
                        <p className={`font-semibold ${classeStatusComparativo(cmp.status)}`}>
                          Legado × Cenário: {labelStatusComparativo(cmp.status)}
                        </p>
                        {cmp.status === 'CENARIO_NAO_ENCONTRADO' ? (
                          <p className="text-muted-foreground leading-snug">
                            Cenário fiscal de saída ainda não possui regra para este item. A proposta continua usando a
                            regra legada.
                          </p>
                        ) : null}
                        {cmp.legado.encontrado ? (
                          <p className="text-muted-foreground">
                            Legado: regra #{cmp.legado.regra_id}
                            {cmp.legado.cfop ? ` · CFOP ${cmp.legado.cfop}` : ''}
                            {cmp.legado.aliquota_icms ? ` · ICMS ${cmp.legado.aliquota_icms}%` : ''}
                          </p>
                        ) : (
                          <p className="text-muted-foreground">Legado: não encontrado</p>
                        )}
                        {cmp.cenario.encontrado ? (
                          <p className="text-muted-foreground">
                            Cenário: regra #{cmp.cenario.regra_id}
                            {cmp.cenario.cfop ? ` · CFOP ${cmp.cenario.cfop}` : ''}
                            {cmp.cenario.aliquota_icms ? ` · ICMS ${cmp.cenario.aliquota_icms}%` : ''}
                          </p>
                        ) : (
                          <p className="text-muted-foreground">Cenário: não encontrado</p>
                        )}
                        {cmp.divergencias.length > 0 ? (
                          <ul className="list-disc pl-4 space-y-0.5 text-muted-foreground">
                            {cmp.divergencias.map((d) => (
                              <li key={d.campo}>
                                {d.label}: legado {d.legado} · cenário {d.cenario}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        {cmp.mensagens.length > 0 ? (
                          <p className="text-[10px] text-muted-foreground/90">{cmp.mensagens.join(' ')}</p>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  </div>
                </details>

                  <p className="text-[11px] font-medium text-muted-foreground pt-1">Camada gerencial (estimativa de margem — não vem da Regra Fiscal)</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">IRPJ estimado %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.irpj_estimado_percentual)}
                        onChange={(e) => updateItem(idx, { irpj_estimado_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">CSLL estimada %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.csll_estimada_percentual)}
                        onChange={(e) => updateItem(idx, { csll_estimada_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Comissão %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.comissao_percentual)}
                        onChange={(e) => updateItem(idx, { comissao_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Frete saída (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.frete_saida)}
                        onChange={(e) => updateItem(idx, { frete_saida: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Outras despesas saída (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={inputNumberValue(item.outras_despesas_saida)}
                        onChange={(e) => updateItem(idx, { outras_despesas_saida: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">% carga tributária + gerencial</label>
                      <div className="erp-input h-8 text-sm flex items-center">{formatPercent(pctSaida)}</div>
                    </div>
                  </div>

                <div className="space-y-2">
                  <p className="text-[11px] font-medium text-muted-foreground">Resultado do item</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">Preço base (custo ÷ 0,60)</label>
                      <div className="erp-input h-8 text-sm flex items-center font-medium">{formatMoneyBr(item.preco_sugerido)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Modo preço</label>
                      <select
                        className="erp-input h-8 text-sm"
                        value={item.modo_preco}
                        onChange={(e) => updateItem(idx, { modo_preco: e.target.value as 'sugerido' | 'manual' })}
                      >
                        <option value="sugerido">Automático (preço base)</option>
                        <option value="manual">Manual</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Preço final / unitário</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        disabled={item.modo_preco !== 'manual'}
                        className={numericClass}
                        value={inputNumberValue(item.preco_final)}
                        onChange={(e) => updateItem(idx, { preco_final: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Carga da venda (R$)</label>
                      <div className="erp-input h-8 text-sm flex items-center">{formatMoneyBr(valCarga)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Lucro líquido estimado</label>
                      <div className="erp-input h-8 text-sm flex items-center">{formatMoneyBr(item.lucro_resultante)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Margem líquida estimada</label>
                      <div className="erp-input h-8 text-sm flex items-center gap-2">
                        <span>{formatPercent(item.margem_resultante)}</span>
                        <span className={margemBadge}>
                          {item.margem_resultante >= 15 ? 'OK' : item.margem_resultante >= 8 ? 'Atenção' : 'Risco'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
                  </div>
                </details>
              </div>
            );
          })}
        </div>
        </ComercialModalSection>

        <ComercialModalSection title="Totais" className="mb-4">
          <div className="text-right text-2xl font-bold text-foreground">Total da proposta: {formatMoneyBr(total)}</div>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Custo total</p>
              <p className="text-lg font-semibold">{formatMoneyBr(custoTotal)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Receita total</p>
              <p className="text-lg font-semibold">{formatMoneyBr(receitaTotal)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Lucro total</p>
              <p className="text-lg font-semibold">{formatMoneyBr(lucroTotal)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Margem média</p>
              <div className="mt-1">
                <span className={margemBadgeClass}>{formatPercent(margemMedia)}</span>
              </div>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Quantidade total</p>
              <p className="text-lg font-semibold">{formatDecimal(quantidadeTotalItens, 3)}</p>
            </div>
          </div>
        </ComercialModalSection>

        {referenciaFrete && (
          <div className="mt-4 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Referência comercial de frete (apoio gerencial)</p>
            <p className="text-xs text-muted-foreground mt-1">{referenciaFrete.mensagem || '—'}</p>
            {referenciaFrete.tem_base_historica === false && (
              <p className="text-xs text-amber-800 dark:text-amber-200 mt-1">
                Sem base histórica de frete no período selecionado. Os indicadores abaixo podem aparecer vazios.
              </p>
            )}
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Frete médio observado</div>
                <div className="font-medium">
                  {referenciaFrete.referencia_historica?.frete_medio_observado == null
                    ? '—'
                    : formatMoneyBr(referenciaFrete.referencia_historica.frete_medio_observado)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Peso médio do frete</div>
                <div className="font-medium">
                  {referenciaFrete.referencia_historica?.peso_frete_sobre_faturamento == null
                    ? '—'
                    : formatPercent(referenciaFrete.referencia_historica.peso_frete_sobre_faturamento)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">CT-es válidos</div>
                <div className="font-medium">{referenciaFrete.referencia_historica?.quantidade_ctes_validos ?? '—'}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Período da referência</div>
                <div className="font-medium">
                  {(referenciaFrete.periodo_utilizado?.data_inicio || '—')} a {(referenciaFrete.periodo_utilizado?.data_fim || '—')}
                </div>
              </div>
            </div>
            {referenciaFrete.referencia_historica?.transportadora_referencia && (
              <p className="mt-2 text-xs text-muted-foreground">
                Referência da transportadora selecionada:{' '}
                {referenciaFrete.referencia_historica.transportadora_referencia.transportadora_nome ?? '—'}.
              </p>
            )}
          </div>
        )}

        <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Referência comercial de custo de compra (apoio gerencial)
          </p>
          {!itemRefCusto && (
            <p className="text-xs text-muted-foreground mt-1">
              Selecione um produto (ou informe NCM fiscal válido) no item da proposta para consultar a referência histórica de custo.
            </p>
          )}
          {itemRefCusto && custoCompraRefLoading && (
            <p className="text-xs text-muted-foreground mt-1">Carregando referência de custo…</p>
          )}
          {itemRefCusto && !custoCompraRefLoading && !referenciaCustoCompra && (
            <p className="text-xs text-muted-foreground mt-1">
              Não foi possível carregar a referência de custo. A proposta segue com o fluxo comercial normal; tente de novo se precisar da referência.
            </p>
          )}
          {itemRefCusto && referenciaCustoCompra && (
            <>
              <p className="text-xs text-muted-foreground mt-1">{referenciaCustoCompra.mensagem || '—'}</p>
              {referenciaCustoCompra.tem_base_historica === false && (
                <p className="text-xs text-amber-800 dark:text-amber-200 mt-1">
                  Não há base histórica fiscal suficiente no período para este produto ou NCM. Use apenas como orientação gerencial.
                </p>
              )}
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Custo médio observado</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.custo_medio_observado == null
                      ? '—'
                      : formatMoneyBr(referenciaCustoCompra.referencia_historica.custo_medio_observado)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Última compra observada</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.ultimo_custo_observado == null
                      ? '—'
                      : formatMoneyBr(referenciaCustoCompra.referencia_historica.ultimo_custo_observado)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Fornecedor de referência</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.fornecedor_referencia || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Período da referência</div>
                  <div className="font-medium">
                    {(referenciaCustoCompra.periodo_utilizado?.data_inicio || '—')} a{' '}
                    {(referenciaCustoCompra.periodo_utilizado?.data_fim || '—')}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {editing?.id ? (
          <div className="mt-6 rounded-md border border-border bg-muted/30 p-4">
            <p className="text-sm font-medium">Pedido de venda</p>
            {propostaRequerRecuperacao(editing) ? (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-amber-800 dark:text-amber-200">
                  Esta proposta está cancelada/perdida. Para gerar Pedido de Venda, recupere a proposta primeiro.
                </p>
                <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setRecuperarOpen(true)}>
                  Recuperar proposta
                </button>
              </div>
            ) : propostaTotalmenteConvertida(editing) ? (
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span className="erp-badge-success">Convertida integralmente</span>
                {(editing.pedidos_gerados_resumo?.length ? editing.pedidos_gerados_resumo : editing.pedido_venda_id ? [{ id: editing.pedido_venda_id, numero: editing.pedido_venda_numero || '', status: '' }] : []).map((pv) => (
                  <button
                    key={pv.id}
                    type="button"
                    className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                    onClick={() => abrirPedidoPorId(pv.id)}
                  >
                    <ExternalLink className="h-4 w-4" />
                    {pv.numero || `PV #${pv.id}`}
                  </button>
                ))}
              </div>
            ) : (
              <div className="mt-2 space-y-3">
                {propostaTemPedidoGerado(editing) ? (
                  <div className="flex flex-wrap gap-2">
                    <span className="erp-badge-warning">Parcialmente convertida</span>
                    {(editing.pedidos_gerados_resumo || []).map((pv) => (
                      <button
                        key={pv.id}
                        type="button"
                        className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                        onClick={() => abrirPedidoPorId(pv.id)}
                      >
                        <ExternalLink className="h-4 w-4" />
                        {pv.numero}
                      </button>
                    ))}
                  </div>
                ) : null}
                {propostaPodeGerarPedido(editing) ? (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Gere um pedido com todos ou parte dos itens. Itens restantes podem ficar pendentes ou ser
                      cancelados/perdidos.
                    </p>
                    <button
                      type="button"
                      className="erp-btn-primary inline-flex items-center gap-2"
                      onClick={() => setGerarPedidoOpen(true)}
                    >
                      <ShoppingCart className="h-4 w-4" />
                      Gerar Pedido de Venda
                    </button>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Vincule cliente cadastrado e produtos em todos os itens pendentes para habilitar a geração de pedido.
                  </p>
                )}
              </div>
            )}
          </div>
        ) : null}

        <div className="flex flex-wrap justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          {editing?.id ? (
            <>
              <button
                type="button"
                className="erp-btn-outline inline-flex items-center gap-1"
                onClick={() => void handleVisualizarPdf(editing)}
              >
                <FileDown className="h-4 w-4" />
                Visualizar PDF
              </button>
              <button
                type="button"
                className="erp-btn-outline inline-flex items-center gap-1"
                onClick={() => void handleBaixarPdf(editing)}
              >
                <Download className="h-4 w-4" />
                Baixar PDF
              </button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground self-center mr-2">{MSG_SALVE_ANTES_PDF}</span>
          )}
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>

      <Modal
        isOpen={wizardOpen}
        onClose={() => setWizardOpen(false)}
        title={wizardProposta ? `Converter Proposta ${wizardProposta.numero}` : 'Converter proposta'}
        size="xl"
      >
        {wizardLoading && !wizardProposta ? <p className="text-sm text-muted-foreground">Carregando dados da proposta...</p> : null}
        {wizardProposta ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {[1, 2, 3].map((step) => (
                <button
                  key={step}
                  type="button"
                  disabled={wizardLoading}
                  onClick={() => setWizardStep(step as 1 | 2 | 3)}
                  className={`rounded-md border px-3 py-2 text-sm ${wizardStep === step ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground'}`}
                >
                  {step === 1 ? '1. Cliente' : step === 2 ? '2. Itens' : '3. Validação final'}
                </button>
              ))}
            </div>

            {wizardError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{wizardError}</div>
            ) : null}

            {wizardStep === 1 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3">
                  <p className="text-sm">
                    <span className="font-medium">Cliente atual:</span>{' '}
                    {wizardProposta.cliente_nome || wizardProposta.cliente_avulso_nome || 'Não definido'}
                  </p>
                  {clienteResolvido ? (
                    <p className="mt-2 inline-flex items-center gap-1 text-xs text-success"><CheckCircle2 className="h-4 w-4" /> Cliente cadastrado já vinculado.</p>
                  ) : (
                    <p className="mt-2 text-xs text-warning">Cliente avulso detectado. Vincule ou crie cadastro antes da conversão.</p>
                  )}
                </div>

                {!clienteResolvido ? (
                  <>
                    <div className="rounded-md border border-border p-3 space-y-2">
                      <p className="text-sm font-medium">Vincular cliente existente</p>
                      <ClienteComercialField
                        valueId={wizardClienteId}
                        selectedCliente={
                          wizardClienteId && selectedCliente?.id === wizardClienteId
                            ? selectedCliente
                            : wizardClienteId
                              ? clienteStubForDisplay(wizardClienteId, wizardProposta?.cliente_nome || '')
                              : null
                        }
                        disabled={wizardLoading}
                        onSelect={(c) => setWizardClienteId(c.id)}
                        onClear={() => setWizardClienteId(null)}
                      />
                      <button type="button" className="erp-btn-outline" disabled={!wizardClienteId || wizardLoading} onClick={vincularClienteExistente}>
                        Vincular
                      </button>
                    </div>

                    <div className="rounded-md border border-border p-3">
                      <p className="mb-2 text-sm font-medium">Criar novo cliente a partir da proposta</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <input
                          className="erp-input"
                          placeholder="Razão social"
                          value={novoClienteNome}
                          onChange={(e) => setNovoClienteNome(e.target.value)}
                        />
                        <input
                          className="erp-input"
                          placeholder="CNPJ (somente números)"
                          value={novoClienteCnpj}
                          onChange={(e) => setNovoClienteCnpj(e.target.value)}
                        />
                      </div>
                      <button type="button" className="erp-btn-outline mt-2" disabled={wizardLoading} onClick={criarClienteDaProposta}>
                        Criar cliente e vincular
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            {wizardStep === 2 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3 text-sm">
                  Itens vinculados: <span className="font-semibold">{itensResolvidos}</span> / {wizardProposta.itens.length}
                </div>
                <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground leading-relaxed">
                  Itens avulsos usam NCM informado na proposta para a Regra Fiscal. A conversão em pedido exige <strong>NCM válido (8 dígitos)</strong> e{' '}
                  <strong>produto cadastrado</strong> em cada linha — o pedido e o faturamento seguem o cadastro de produtos.
                </div>
                {wizardProposta.itens.map((item) => (
                  <div key={item.id} className="rounded-md border border-border p-3 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium">{item.produto_nome || item.descricao_avulsa || `Item #${item.id}`}</p>
                      <div className="flex flex-wrap items-center gap-1">
                        {!item.produto_id && !ncmFiscalDigitsValid(item.ncm_avulso || '') ? (
                          <span className="erp-badge-danger text-xs">Sem NCM (8 dígitos)</span>
                        ) : null}
                        {item.produto_id ? (
                          <span className="erp-badge-success">Vinculado</span>
                        ) : (
                          <span className="erp-badge-warning">Pendente produto</span>
                        )}
                      </div>
                    </div>
                    {!item.produto_id ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <div className="md:col-span-2">
                          <ProdutoComercialField
                            compact
                            valueId={itemLinks[item.id] ?? null}
                            selectedProduto={
                              itemLinks[item.id] ? produtoCache.get(itemLinks[item.id]!) ?? null : null
                            }
                            disabled={wizardLoading}
                            onSelect={(pr) => {
                              mergeProdutoCache(pr);
                              setItemLinks((prev) => ({ ...prev, [item.id]: pr.id }));
                            }}
                            onClear={() => setItemLinks((prev) => ({ ...prev, [item.id]: null }))}
                          />
                        </div>
                        <button type="button" className="erp-btn-outline" disabled={!itemLinks[item.id] || wizardLoading} onClick={() => vincularItemExistente(item.id)}>
                          Vincular produto
                        </button>
                        <input
                          className="erp-input md:col-span-2"
                          placeholder="Descrição para novo produto"
                          value={novoProdutoDescricao[item.id] ?? ''}
                          onChange={(e) => setNovoProdutoDescricao((prev) => ({ ...prev, [item.id]: e.target.value }))}
                        />
                        <button type="button" className="erp-btn-outline" disabled={wizardLoading} onClick={() => criarProdutoParaItem(item.id)}>
                          Criar produto
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}

            {wizardStep === 3 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3">
                  <p className="text-sm"><span className="font-medium">Cliente cadastrado:</span> {clienteResolvido ? 'OK' : 'Pendente'}</p>
                  <p className="text-sm"><span className="font-medium">Itens vinculados:</span> {itensPendentes.length === 0 ? 'OK' : `${itensPendentes.length} pendente(s)`}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    A conversão cria um Pedido de Venda com os itens pendentes. É possível gerar pedidos parciais
                    adicionais depois, enquanto houver itens pendentes na proposta.
                  </p>
                </div>
              </div>
            ) : null}

            <div className="flex justify-between border-t border-border pt-4">
              <button type="button" className="erp-btn-outline" onClick={() => setWizardOpen(false)} disabled={wizardLoading}>
                Fechar
              </button>
              <div className="flex gap-2">
                <button type="button" className="erp-btn-outline" disabled={wizardStep === 1 || wizardLoading} onClick={() => setWizardStep((s) => (s > 1 ? (s - 1) as 1 | 2 | 3 : s))}>
                  Voltar
                </button>
                {wizardStep < 3 ? (
                  <button
                    type="button"
                    className="erp-btn-primary"
                    disabled={wizardLoading || (wizardStep === 1 && !clienteResolvido) || (wizardStep === 2 && itensPendentes.length > 0)}
                    onClick={() => setWizardStep((s) => (s < 3 ? (s + 1) as 1 | 2 | 3 : s))}
                  >
                    Próximo
                  </button>
                ) : (
                  <button type="button" className="erp-btn-primary" disabled={!podeConverter || wizardLoading} onClick={concluirConversao}>
                    Converter em pedido
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <GerarPedidoPropostaModal
        open={gerarPedidoOpen}
        proposta={editing}
        loading={gerarPedidoLoading}
        onClose={() => setGerarPedidoOpen(false)}
        onConfirm={confirmarGerarPedido}
      />
      <RecuperarPropostaModal
        open={recuperarOpen}
        loading={recuperarLoading}
        onClose={() => setRecuperarOpen(false)}
        onConfirm={confirmarRecuperarProposta}
      />
    </div>
  );
};

export default Propostas;
