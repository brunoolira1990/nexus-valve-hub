import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Eye, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { TituloFinanceiroBaixaModal } from '@/components/financeiro/TituloFinanceiroBaixaModal';
import { AplicarCreditoModal } from '@/components/financeiro/AplicarCreditoModal';
import { AbaterDevolucaoModal } from '@/components/financeiro/AbaterDevolucaoModal';
import { TituloFinanceiroDetalheDrawer } from '@/components/financeiro/TituloFinanceiroDetalheDrawer';
import { ContaPagarDespesaModal } from '@/components/financeiro/ContaPagarDespesaModal';
import { ContaPagarTributoModal } from '@/components/financeiro/ContaPagarTributoModal';
import { TituloFinanceiroNovoModal } from '@/components/financeiro/TituloFinanceiroNovoModal';
import {
  TituloFinanceiroFiltrosPanel,
  tituloFiltrosFromSearchParams,
  tituloFiltrosToQuery,
  type TituloFiltrosState,
} from '@/components/financeiro/TituloFinanceiroFiltrosPanel';
import { NexusButton } from '@/components/nexus';
import { SearchInput } from '@/components/nexus/inputs';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { formatDateBr } from '@/lib/dateBr';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_FORNECEDOR_MESSAGES,
  labelTipoLancamentoPagar,
  statusBadgeFinanceiro,
  tituloModoConfig,
  type TituloModo,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { financeiroService, type TituloFinanceiro } from '@/services/api/financeiro';

type Props = { modo: TituloModo };

export function TitulosFinanceirosPage({ modo }: Props) {
  const cfg = tituloModoConfig(modo);
  const [searchParams, setSearchParams] = useSearchParams();
  const filtrosIniciais = useMemo(() => tituloFiltrosFromSearchParams(searchParams), []);
  const fetchPage = useCallback(
    (params: Parameters<typeof financeiroService.listContasReceber>[0]) =>
      modo === 'RECEBER'
        ? financeiroService.listContasReceber(params)
        : financeiroService.listContasPagar(params),
    [modo],
  );

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
    loading,
    error,
    reload,
    filters,
    setFilters,
  } = usePaginatedList<TituloFinanceiro>({ fetchPage, initialFilters: tituloFiltrosToQuery(filtrosIniciais) });

  const [filtrosUi, setFiltrosUi] = useState<TituloFiltrosState>(filtrosIniciais);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [centros, setCentros] = useState<{ id: number; nome: string }[]>([]);
  const [contasOpts, setContasOpts] = useState<{ id: number; nome: string }[]>([]);

  useEffect(() => {
    void Promise.all([
      financeiroService.listCategorias({ limit: 200 }),
      financeiroService.listCentrosCusto({ limit: 200 }),
      financeiroService.listContasAtivas(),
    ]).then(([cat, cc, contas]) => {
      setCategorias((cat.results ?? []).filter((c) => c.ativo).map((c) => ({ id: c.id, nome: c.nome })));
      setCentros((cc.results ?? []).filter((c) => c.ativo).map((c) => ({ id: c.id, nome: c.nome })));
      setContasOpts(contas.map((c) => ({ id: c.id, nome: c.nome })));
    });
  }, []);

  const aplicarFiltrosUi = (next: TituloFiltrosState) => {
    setFiltrosUi(next);
    setFilters(tituloFiltrosToQuery(next));
    const sp = new URLSearchParams(tituloFiltrosToQuery(next));
    setSearchParams(sp, { replace: true });
  };

  const [novoOpen, setNovoOpen] = useState(false);
  const [despesaOpen, setDespesaOpen] = useState(false);
  const [tributoOpen, setTributoOpen] = useState(false);
  const [fornecedorOpen, setFornecedorOpen] = useState(false);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [baixaTitulo, setBaixaTitulo] = useState<TituloFinanceiro | null>(null);
  const [aplicarCreditoTitulo, setAplicarCreditoTitulo] = useState<TituloFinanceiro | null>(null);
  const [abaterTitulo, setAbaterTitulo] = useState<TituloFinanceiro | null>(null);
  const [drawerRefresh, setDrawerRefresh] = useState(0);

  useEffect(() => {
    const tituloParam = searchParams.get('titulo');
    if (!tituloParam) return;
    const id = Number(tituloParam);
    if (Number.isFinite(id) && id > 0) {
      setDetalheId(id);
      const next = new URLSearchParams(searchParams);
      next.delete('titulo');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const linhaPrincipal = (t: TituloFinanceiro) => {
    if (modo === 'RECEBER') return t.cliente_nome || '—';
    if (t.descricao?.trim()) return t.descricao.trim();
    if (t.fornecedor_nome?.trim()) return t.fornecedor_nome.trim();
    if (t.tipo_lancamento === 'DESPESA_OPERACIONAL' || t.tipo_lancamento === 'SERVICO') {
      return t.titulo_resumo || FINANCEIRO_FORNECEDOR_MESSAGES.semFornecedor;
    }
    return t.titulo_resumo || '—';
  };

  const headerActions =
    modo === 'PAGAR' ? (
      <>
        <SearchInput value={search} onChange={setSearch} />
        <NexusButton type="button" variant="outline" onClick={() => setDespesaOpen(true)}>
          {FINANCEIRO_ACTION_LABELS.novaDespesa}
        </NexusButton>
        <NexusButton type="button" variant="outline" onClick={() => setTributoOpen(true)}>
          {FINANCEIRO_ACTION_LABELS.novoTributo}
        </NexusButton>
        <NexusButton type="button" onClick={() => setFornecedorOpen(true)}>
          {FINANCEIRO_ACTION_LABELS.novaContaPagar}
        </NexusButton>
      </>
    ) : undefined;

  return (
    <div>
      <PageHeader
        title={cfg.tituloPagina}
        description={cfg.descricao}
        onAdd={modo === 'RECEBER' ? () => setNovoOpen(true) : undefined}
        addLabel={cfg.novoLabel}
        searchValue={search}
        onSearch={modo === 'RECEBER' ? setSearch : undefined}
        actions={headerActions}
      />

      <TituloFinanceiroFiltrosPanel
        modo={modo}
        filtros={filtrosUi}
        onChange={aplicarFiltrosUi}
        categorias={categorias}
        centros={centros}
        contas={contasOpts}
      />

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={8} cols={8} /> : null}

      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Vencimento</th>
                <th>{modo === 'PAGAR' ? 'Descrição / Fornecedor' : cfg.contraparteLabel}</th>
                {modo === 'PAGAR' ? <th>Tipo</th> : null}
                <th>Número</th>
                <th>Valor</th>
                <th>Saldo</th>
                <th>Status</th>
                <th>Origem</th>
                <th className="w-28">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={modo === 'PAGAR' ? 9 : 8}>
                    <EmptyState
                      message="Nenhum título encontrado."
                      actionLabel={modo === 'PAGAR' ? FINANCEIRO_ACTION_LABELS.novaDespesa : cfg.novoLabel}
                      onAction={() => (modo === 'PAGAR' ? setDespesaOpen(true) : setNovoOpen(true))}
                    />
                  </td>
                </tr>
              ) : (
                items.map((t) => (
                  <tr key={t.id}>
                    <td>{formatDateBr(t.data_vencimento)}</td>
                    <td className="font-medium max-w-[200px] truncate" title={linhaPrincipal(t)}>
                      {linhaPrincipal(t)}
                    </td>
                    {modo === 'PAGAR' ? (
                      <td className="text-xs text-muted-foreground">
                        {labelTipoLancamentoPagar(t.tipo_lancamento, t.tipo_lancamento_label)}
                      </td>
                    ) : null}
                    <td>{t.numero}</td>
                    <td>{formatMoneyBRL(t.valor_original)}</td>
                    <td>{formatMoneyBRL(t.valor_aberto)}</td>
                    <td>
                      <div className="flex flex-col gap-1 items-start">
                        <StatusBadge status={statusBadgeFinanceiro(t)} />
                        {t.alerta_origem_cancelada ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100">
                            Origem cancelada
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="text-xs text-muted-foreground max-w-[160px] truncate" title={t.origem_exibicao}>
                      {t.origem_descricao || t.origem_numero || 'Manual'}
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm"
                          title={FINANCEIRO_ACTION_LABELS.verDetalhes}
                          onClick={() => setDetalheId(t.id)}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        {t.pode_baixar ? (
                          <button
                            type="button"
                            className="erp-btn-ghost erp-btn-sm"
                            title={cfg.baixarLabel}
                            onClick={() => setBaixaTitulo(t)}
                          >
                            <Wallet className="h-3.5 w-3.5" />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </DataTable>
          <PaginationControls
            page={page}
            pageSize={pageSize}
            totalPages={totalPages}
            count={count}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        </DataTableShell>
      ) : null}

      {modo === 'RECEBER' ? (
        <TituloFinanceiroNovoModal
          open={novoOpen}
          onClose={() => setNovoOpen(false)}
          modo={modo}
          onCreated={() => {
            toast.success('Título criado com sucesso.');
            void reload();
          }}
        />
      ) : (
        <>
          <ContaPagarDespesaModal
            open={despesaOpen}
            onClose={() => setDespesaOpen(false)}
            tipoLancamento="DESPESA_OPERACIONAL"
            onCreated={() => {
              toast.success('Despesa registrada com sucesso.');
              void reload();
            }}
          />
          <ContaPagarTributoModal
            open={tributoOpen}
            onClose={() => setTributoOpen(false)}
            onCreated={() => {
              toast.success('Tributo a pagar registrado com sucesso.');
              void reload();
            }}
          />
          <ContaPagarDespesaModal
            open={fornecedorOpen}
            onClose={() => setFornecedorOpen(false)}
            tipoLancamento="FORNECEDOR"
            tituloModal={FINANCEIRO_ACTION_LABELS.novaContaPagar}
            onCreated={() => {
              toast.success('Conta a pagar criada com sucesso.');
              void reload();
            }}
          />
        </>
      )}

      <TituloFinanceiroDetalheDrawer
        tituloId={detalheId}
        modo={modo}
        open={detalheId != null}
        onClose={() => setDetalheId(null)}
        refreshToken={drawerRefresh}
        onBaixar={(t) => {
          setDetalheId(null);
          setBaixaTitulo(t);
        }}
        onAplicarCredito={(t) => setAplicarCreditoTitulo(t)}
        onAbaterDevolucao={(t) => setAbaterTitulo(t)}
        onUpdated={() => {
          setDrawerRefresh((n) => n + 1);
          void reload();
        }}
        onExcluido={() => {
          setDetalheId(null);
          void reload();
        }}
      />

      <AplicarCreditoModal
        open={aplicarCreditoTitulo != null}
        onClose={() => setAplicarCreditoTitulo(null)}
        modo={modo}
        titulo={aplicarCreditoTitulo}
        onSuccess={(msg) => {
          toast.success(msg);
          setAplicarCreditoTitulo(null);
          setDrawerRefresh((n) => n + 1);
          void reload();
        }}
      />

      <AbaterDevolucaoModal
        open={abaterTitulo != null}
        onClose={() => setAbaterTitulo(null)}
        modo={modo}
        titulo={abaterTitulo}
        onSuccess={(msg) => {
          toast.success(msg);
          setAbaterTitulo(null);
          setDrawerRefresh((n) => n + 1);
          void reload();
        }}
      />

      <TituloFinanceiroBaixaModal
        open={baixaTitulo != null}
        onClose={() => setBaixaTitulo(null)}
        modo={modo}
        titulo={baixaTitulo}
        onSuccess={(msg) => {
          toast.success(msg);
          void reload();
        }}
      />
    </div>
  );
}

export default TitulosFinanceirosPage;
