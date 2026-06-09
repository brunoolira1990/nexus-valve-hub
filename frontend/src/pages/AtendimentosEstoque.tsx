import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Pencil } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { AtendimentoOperacionalBadge } from '@/components/comercial/AtendimentoOperacionalBadge';
import { AtendimentoOperacionalEditModal } from '@/components/comercial/AtendimentoOperacionalEditModal';
import { ClienteComercialField } from '@/components/comercial/ClienteComercialField';
import { ProdutoComercialField } from '@/components/comercial/ProdutoComercialField';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { atendimentosOperacionaisService } from '@/services/api/atendimentosOperacionais';
import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';
import type { AtendimentoOperacionalItem, AtendimentosOperacionaisKpis } from '@/types/atendimentosOperacionais';
import type { OpcaoFornecedor } from '@/types/alocacaoAtendimentoOpcoes';
import { STATUS_ENTRADA_FISCAL, TIPOS_ATENDIMENTO } from '@/types/alocacaoAtendimento';
import type { Cliente, Produto } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { ErrorState } from '@/components/list/ListStates';
import { EmptyState } from '@/components/nexus/EmptyState';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';

function fmtQty(v?: string | null): string {
  if (v == null) return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

const KPI_CARDS: {
  key: keyof AtendimentosOperacionaisKpis;
  label: string;
  filter?: Record<string, string>;
}[] = [
  { key: 'total', label: 'Total de atendimentos' },
  { key: 'entradas_pendentes', label: 'Entradas pendentes', filter: { status_entrada_fiscal: 'PENDENTE' } },
  { key: 'entradas_conciliadas', label: 'Entradas conciliadas', filter: { status_entrada_fiscal: 'CONCILIADA' } },
  {
    key: 'retiradas_fornecedor',
    label: 'Retiradas fornecedor',
    filter: { tipo_atendimento: 'RETIRADA_FORNECEDOR' },
  },
  {
    key: 'entregas_diretas',
    label: 'Entregas diretas',
    filter: { tipo_atendimento: 'ENTREGA_DIRETA_FORNECEDOR_CLIENTE' },
  },
  { key: 'sem_compra_vinculada', label: 'Sem compra vinculada', filter: { somente_sem_compra: 'true' } },
  { key: 'com_cte_conferido', label: 'Com CT-e conferido', filter: { tem_cte_vinculado: 'true' } },
];

const AtendimentosEstoque = () => {
  const [kpis, setKpis] = useState<AtendimentosOperacionaisKpis | null>(null);
  const [selCliente, setSelCliente] = useState<Cliente | null>(null);
  const [selProduto, setSelProduto] = useState<Produto | null>(null);
  const [selFornecedor, setSelFornecedor] = useState<OpcaoFornecedor | null>(null);
  const [editId, setEditId] = useState<number | null>(null);

  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    setPage,
    setPageSize,
    filters,
    setFilter,
    setFilters,
    loading,
    error,
    reload: reloadList,
  } = usePaginatedList<AtendimentoOperacionalItem>({
    fetchPage: async (params) => {
      const data = await atendimentosOperacionaisService.listPaginated(params);
      if (data.kpis) setKpis(data.kpis);
      return data;
    },
    initialFilters: { somente_pendentes: 'true' },
  });

  const reload = useCallback(() => {
    void reloadList();
  }, [reloadList]);

  const applyKpiFilter = (filter?: Record<string, string>) => {
    if (!filter) {
      setFilters({ somente_pendentes: '' });
      return;
    }
    setFilters({
      somente_pendentes: '',
      tipo_atendimento: '',
      status_entrada_fiscal: '',
      somente_sem_compra: '',
      tem_nfe_entrada_vinculada: '',
      tem_cte_vinculado: '',
      ...filter,
    });
  };

  const buscarFornecedor = useCallback(
    (term: string, limit?: number) => alocacaoAtendimentoService.opcoesFornecedores(term, { limit: limit ?? 25 }),
    [],
  );

  const filterParams = useMemo(
    () => ({
      search: filters.search || '',
      tipo_atendimento: filters.tipo_atendimento || '',
      status_entrada_fiscal: filters.status_entrada_fiscal || '',
      cliente_id: filters.cliente_id || '',
      produto_id: filters.produto_id || '',
      fornecedor_id: filters.fornecedor_id || '',
      somente_pendentes: filters.somente_pendentes || '',
      somente_sem_compra: filters.somente_sem_compra || '',
      tem_nfe_entrada_vinculada: filters.tem_nfe_entrada_vinculada || '',
      tem_cte_vinculado: filters.tem_cte_vinculado || '',
      data_inicio: filters.data_inicio || '',
      data_fim: filters.data_fim || '',
    }),
    [filters],
  );

  const limparFiltros = () => {
    setSelCliente(null);
    setSelProduto(null);
    setSelFornecedor(null);
    setFilters({});
  };

  return (
    <div>
      <PageHeader
        title="Atendimentos Operacionais"
        description="Atendimento operacional de itens por pedido, faturamento e NF-e. Acompanhe retiradas no fornecedor, entregas diretas, entradas pendentes, entradas conciliadas e vínculos com compras, NF-e entrada e CT-e. Esta tela não movimenta estoque nem gera financeiro automaticamente."
      />

      {kpis ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
          {KPI_CARDS.map((card) => (
            <button
              key={card.key}
              type="button"
              className="text-left rounded-lg border border-border bg-card px-3 py-2 hover:bg-muted/50 transition-colors"
              onClick={() => applyKpiFilter(card.filter)}
            >
              <div className="text-2xl font-semibold tabular-nums">{kpis[card.key]}</div>
              <div className="text-xs text-muted-foreground leading-snug">{card.label}</div>
            </button>
          ))}
        </div>
      ) : null}

      <NexusCard className="p-4 mb-4 space-y-4">
        <div>
          <label className="erp-label">Busca</label>
          <input
            className="erp-input mt-1 w-full"
            placeholder="Buscar por PV, cliente, produto, fornecedor, NF-e, FAT ou PC..."
            value={filterParams.search}
            onChange={(e) => setFilter('search', e.target.value)}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="erp-label">Tipo de atendimento</label>
            <select
              className="erp-select mt-1 w-full"
              value={filterParams.tipo_atendimento}
              onChange={(e) => setFilter('tipo_atendimento', e.target.value)}
            >
              <option value="">Todos</option>
              {TIPOS_ATENDIMENTO.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Entrada fiscal</label>
            <select
              className="erp-select mt-1 w-full"
              value={filterParams.status_entrada_fiscal}
              onChange={(e) => setFilter('status_entrada_fiscal', e.target.value)}
            >
              <option value="">Todos</option>
              {STATUS_ENTRADA_FISCAL.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Data inicial</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={filterParams.data_inicio}
              onChange={(e) => setFilter('data_inicio', e.target.value)}
            />
          </div>
          <div>
            <label className="erp-label">Data final</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={filterParams.data_fim}
              onChange={(e) => setFilter('data_fim', e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="erp-label">Cliente</label>
            <ClienteComercialField
              valueId={selCliente?.id ?? null}
              selectedCliente={selCliente}
              onSelect={(c) => {
                setSelCliente(c);
                setFilter('cliente_id', String(c.id));
              }}
              onClear={() => {
                setSelCliente(null);
                setFilter('cliente_id', '');
              }}
            />
          </div>
          <div>
            <label className="erp-label">Produto</label>
            <ProdutoComercialField
              valueId={selProduto?.id ?? null}
              selectedProduto={selProduto}
              onSelect={(p) => {
                setSelProduto(p);
                setFilter('produto_id', String(p.id));
              }}
              onClear={() => {
                setSelProduto(null);
                setFilter('produto_id', '');
              }}
            />
          </div>
          <div>
            <label className="erp-label">Fornecedor</label>
            <AsyncAutocomplete<OpcaoFornecedor>
              wrapClassName="w-full"
              value={selFornecedor?.id ?? null}
              selectedOption={selFornecedor}
              placeholder="Buscar fornecedor..."
              minChars={2}
              limit={25}
              search={buscarFornecedor}
              getOptionValue={(f) => f.id}
              getOptionLabel={(f) => f.label}
              renderOption={(f) => <span>{f.label}</span>}
              onSelect={(f) => {
                setSelFornecedor(f);
                setFilter('fornecedor_id', String(f.id));
              }}
              onClear={() => {
                setSelFornecedor(null);
                setFilter('fornecedor_id', '');
              }}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filterParams.somente_pendentes === 'true'}
              onChange={(e) => setFilter('somente_pendentes', e.target.checked ? 'true' : '')}
            />
            Somente pendentes
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filterParams.somente_sem_compra === 'true'}
              onChange={(e) => setFilter('somente_sem_compra', e.target.checked ? 'true' : '')}
            />
            Sem compra vinculada
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filterParams.tem_nfe_entrada_vinculada === 'true'}
              onChange={(e) => setFilter('tem_nfe_entrada_vinculada', e.target.checked ? 'true' : '')}
            />
            Com NF-e entrada
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filterParams.tem_cte_vinculado === 'true'}
              onChange={(e) => setFilter('tem_cte_vinculado', e.target.checked ? 'true' : '')}
            />
            Com CT-e conferido
          </label>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={8} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Documento</th>
                <th>Cliente</th>
                <th>Produto</th>
                <th>Quantidades</th>
                <th>Atendimento</th>
                <th>Vínculos</th>
                <th>Alertas</th>
                <th className="w-36">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <EmptyState
                      title="Nenhum atendimento operacional encontrado."
                      message="Crie alocações de atendimento a partir de um Pedido de Venda, Faturamento ou NF-e Saída para acompanhar retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada."
                      actionLabel="Limpar filtros"
                      onAction={limparFiltros}
                    />
                    <div className="text-center -mt-6 pb-6">
                      <Link to="/pedidos-venda" className="erp-btn-outline erp-btn-sm inline-flex">
                        Ir para Pedidos de Venda
                      </Link>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr key={row.id}>
                    <td className="text-sm">
                      {row.pedido_venda ? (
                        <div className="font-medium">{row.pedido_venda.numero}</div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                      {(row.faturamento?.numero_faturamento || row.nfe_saida?.titulo) && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {[row.faturamento?.numero_faturamento, row.nfe_saida?.titulo].filter(Boolean).join(' · ')}
                        </div>
                      )}
                    </td>
                    <td>{row.cliente?.nome || '—'}</td>
                    <td>
                      <div className="font-medium">{row.produto.codigo}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-[200px]" title={row.produto.descricao}>
                        {row.produto.descricao}
                      </div>
                    </td>
                    <td className="text-xs tabular-nums whitespace-nowrap">
                      <div>Nec.: {fmtQty(row.quantidade_necessaria)}</div>
                      <div>Atend.: {fmtQty(row.quantidade_atendida)}</div>
                      <div>Pend.: {fmtQty(row.quantidade_pendente)}</div>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {(row.badges ?? []).slice(0, 4).map((b) => (
                          <AtendimentoOperacionalBadge key={`${row.id}-${b.status}`} badge={b} />
                        ))}
                      </div>
                    </td>
                    <td className="text-xs text-muted-foreground space-y-0.5">
                      {row.fornecedor?.nome ? <div>Forn.: {row.fornecedor.nome}</div> : null}
                      {row.pedido_compra?.numero ? <div>PC: {row.pedido_compra.numero}</div> : null}
                      {row.nfe_entrada?.numero ? (
                        <div>
                          NF-e Ent.: {row.nfe_entrada.numero}
                          {row.nfe_entrada.status_conferencia
                            ? ` (${row.nfe_entrada.status_conferencia})`
                            : ''}
                        </div>
                      ) : null}
                      {row.cte?.numero ? (
                        <div>
                          CT-e: {row.cte.numero}
                          {row.cte.status_conferencia ? ` (${row.cte.status_conferencia})` : ''}
                        </div>
                      ) : null}
                      {!row.fornecedor && !row.pedido_compra && !row.nfe_entrada && !row.cte ? '—' : null}
                    </td>
                    <td>
                      {(row.alertas ?? []).length > 0 ? (
                        <span
                          className="inline-flex items-center rounded-full bg-amber-500/15 text-amber-900 dark:text-amber-100 px-2 py-0.5 text-[10px] font-medium"
                          title={(row.alertas ?? []).join('\n')}
                        >
                          {(row.alertas ?? []).length} alerta(s)
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <div className="flex flex-col gap-1">
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                          onClick={() => setEditId(row.id)}
                        >
                          <Pencil className="h-3 w-3" />
                          Editar
                        </button>
                        {row.pedido_venda ? (
                          <Link
                            to="/pedidos-venda"
                            className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1 justify-center"
                          >
                            <ExternalLink className="h-3 w-3" />
                            PV
                          </Link>
                        ) : null}
                        {row.nfe_saida ? (
                          <Link
                            to="/nfe-saida"
                            className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1 justify-center"
                          >
                            <ExternalLink className="h-3 w-3" />
                            NF-e
                          </Link>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </DataTable>
          {!loading && !error && count > 0 ? (
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

      <AtendimentoOperacionalEditModal
        open={editId != null}
        alocacaoId={editId}
        onClose={() => setEditId(null)}
        onSaved={() => void reload()}
      />
    </div>
  );
};

export default AtendimentosEstoque;
