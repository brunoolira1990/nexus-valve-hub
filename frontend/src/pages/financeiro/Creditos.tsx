import { useCallback, useState } from 'react';
import { Eye } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { CreditoAplicarTituloModal } from '@/components/financeiro/CreditoAplicarTituloModal';
import { CreditoDetalheDrawer } from '@/components/financeiro/CreditoDetalheDrawer';
import { CreditoNovoModal } from '@/components/financeiro/CreditoNovoModal';
import { CreditoTipoEscolhaModal } from '@/components/financeiro/CreditoTipoEscolhaModal';
import { NexusButton } from '@/components/nexus';
import { SearchInput } from '@/components/nexus/inputs';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { formatDateBr } from '@/lib/dateBr';
import {
  CREDITO_STATUS_LABELS,
  CREDITO_TIPO_LABELS,
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CREDITO_MESSAGES,
  creditosTemFiltroAtivo,
  labelCreditoOrigem,
  labelCreditoStatus,
  labelCreditoTipo,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { financeiroService, type CreditoFinanceiro } from '@/services/api/financeiro';

export function CreditosPage() {
  const [tipoFiltro, setTipoFiltro] = useState('');
  const [statusFiltro, setStatusFiltro] = useState('');
  const [tipoEscolhaOpen, setTipoEscolhaOpen] = useState(false);
  const [novoTipo, setNovoTipo] = useState<'CLIENTE' | 'FORNECEDOR' | null>(null);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [aplicarCredito, setAplicarCredito] = useState<CreditoFinanceiro | null>(null);

  const fetchPage = useCallback(
    (params: Parameters<typeof financeiroService.listCreditos>[0]) =>
      financeiroService.listCreditos({
        ...params,
        ...(tipoFiltro ? { tipo: tipoFiltro } : {}),
        ...(statusFiltro ? { status: statusFiltro } : {}),
      }),
    [tipoFiltro, statusFiltro],
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
  } = usePaginatedList<CreditoFinanceiro>({ fetchPage });

  const filtroAtivo = creditosTemFiltroAtivo({ search, tipo: tipoFiltro, status: statusFiltro });
  const mostrarListagem = count > 0 || filtroAtivo;
  const estadoVazioLimpo = !loading && !error && count === 0 && !filtroAtivo;

  const abrirNovoCredito = () => setTipoEscolhaOpen(true);

  const limparFiltros = () => {
    setSearch('');
    setTipoFiltro('');
    setStatusFiltro('');
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        title="Créditos"
        description={
          estadoVazioLimpo
            ? 'Créditos de clientes e fornecedores para aplicar em títulos futuros, sem geração automática por NF-e.'
            : 'Créditos de cliente e fornecedor — aplicação manual em títulos, sem geração automática por NF-e.'
        }
        searchValue={mostrarListagem ? search : undefined}
        onSearch={mostrarListagem ? setSearch : undefined}
        actions={
          mostrarListagem ? (
            <>
              <SearchInput value={search} onChange={setSearch} />
              <select
                className="erp-select erp-select-sm"
                value={tipoFiltro}
                onChange={(e) => setTipoFiltro(e.target.value)}
                aria-label="Filtrar por tipo"
              >
                <option value="">Todos os tipos</option>
                {Object.entries(CREDITO_TIPO_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <select
                className="erp-select erp-select-sm"
                value={statusFiltro}
                onChange={(e) => setStatusFiltro(e.target.value)}
                aria-label="Filtrar por status"
              >
                <option value="">Todos os status</option>
                {Object.entries(CREDITO_STATUS_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <NexusButton type="button" onClick={abrirNovoCredito}>
                {FINANCEIRO_ACTION_LABELS.novoCredito}
              </NexusButton>
            </>
          ) : (
            <NexusButton type="button" onClick={abrirNovoCredito}>
              {FINANCEIRO_ACTION_LABELS.novoCredito}
            </NexusButton>
          )
        }
      />

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={estadoVazioLimpo ? 4 : 8} cols={10} /> : null}

      {estadoVazioLimpo ? (
        <EmptyState
          title="Nenhum crédito registrado ainda."
          message="Crie um crédito quando houver devolução, pagamento a maior ou ajuste manual."
          actionLabel={FINANCEIRO_ACTION_LABELS.novoCredito}
          onAction={abrirNovoCredito}
        />
      ) : null}

      {!loading && !error && mostrarListagem ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Cliente / Fornecedor</th>
                <th>Documento</th>
                <th>Origem</th>
                <th>Valor</th>
                <th>Utilizado</th>
                <th>Saldo</th>
                <th>Status</th>
                <th>Data</th>
                <th className="w-20">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={10}>
                    <EmptyState
                      message="Nenhum crédito encontrado com os filtros atuais."
                      actionLabel="Limpar filtros"
                      onAction={limparFiltros}
                    />
                  </td>
                </tr>
              ) : (
                items.map((c) => (
                  <tr key={c.id}>
                    <td>{labelCreditoTipo(c.tipo, c.tipo_label)}</td>
                    <td className="font-medium max-w-[200px] truncate" title={c.contraparte_nome}>
                      {c.contraparte_nome || '—'}
                    </td>
                    <td className="text-xs text-muted-foreground">{c.origem_numero || '—'}</td>
                    <td className="text-xs text-muted-foreground">
                      {labelCreditoOrigem(c.origem_tipo, c.origem_tipo_label)}
                    </td>
                    <td>{formatMoneyBRL(c.valor_original)}</td>
                    <td>{formatMoneyBRL(c.valor_utilizado)}</td>
                    <td>{formatMoneyBRL(c.saldo)}</td>
                    <td>
                      <StatusBadge status={labelCreditoStatus(c.status, c.status_label)} />
                    </td>
                    <td>{formatDateBr(c.data_credito)}</td>
                    <td>
                      <button
                        type="button"
                        className="erp-btn-ghost erp-btn-sm"
                        title="Ver detalhes"
                        onClick={() => setDetalheId(c.id)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </DataTable>
          {items.length > 0 ? (
            <PaginationControls
              page={page}
              pageSize={pageSize}
              totalPages={totalPages}
              count={count}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          ) : null}
        </DataTableShell>
      ) : null}

      <CreditoTipoEscolhaModal
        open={tipoEscolhaOpen}
        onClose={() => setTipoEscolhaOpen(false)}
        onEscolher={(tipo) => setNovoTipo(tipo)}
      />

      <CreditoNovoModal
        open={novoTipo === 'CLIENTE'}
        onClose={() => setNovoTipo(null)}
        tipo="CLIENTE"
        onCreated={() => {
          toast.success(FINANCEIRO_CREDITO_MESSAGES.creditoClienteSucesso);
          void reload();
        }}
      />
      <CreditoNovoModal
        open={novoTipo === 'FORNECEDOR'}
        onClose={() => setNovoTipo(null)}
        tipo="FORNECEDOR"
        onCreated={() => {
          toast.success(FINANCEIRO_CREDITO_MESSAGES.creditoFornecedorSucesso);
          void reload();
        }}
      />

      <CreditoDetalheDrawer
        creditoId={detalheId}
        open={detalheId != null}
        onClose={() => setDetalheId(null)}
        onUpdated={() => void reload()}
        onAplicar={(c) => setAplicarCredito(c)}
        onExcluido={() => {
          setDetalheId(null);
          void reload();
        }}
      />

      <CreditoAplicarTituloModal
        open={aplicarCredito != null}
        onClose={() => setAplicarCredito(null)}
        credito={aplicarCredito}
        onSuccess={(msg) => {
          toast.success(msg);
          setDetalheId(null);
          void reload();
        }}
      />
    </div>
  );
}

export default CreditosPage;
