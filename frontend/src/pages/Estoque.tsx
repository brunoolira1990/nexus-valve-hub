import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { estoqueService } from '@/services/api/outros';
import type { EstoqueSaldoItem } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import type { ListQueryParams } from '@/lib/apiList';

function fmt(v?: string | null): string {
  if (v == null) return '—';
  const asNumber = Number(v);
  if (Number.isNaN(asNumber)) return '—';
  return asNumber.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function alertaParaStatus(alerta: string): string {
  const a = alerta.toLowerCase();
  if (a.includes('negativo')) return 'saldo_negativo';
  if (a.includes('baixo')) return 'baixo_estoque';
  if (a.includes('ncm')) return 'sem_ncm';
  if (a.includes('moviment')) return 'sem_movimentacao';
  return alerta;
}

function situacaoPrincipal(item: EstoqueSaldoItem): string {
  if (!item.alertas?.length) return 'normal';
  return alertaParaStatus(item.alertas[0]);
}

const fetchSaldosPage = (params: ListQueryParams) => estoqueService.listSaldosPaginated(params);

const Estoque = () => {
  const [searchParams] = useSearchParams();
  const filtroUrl = searchParams.get('filtro') || '';
  const initialFilters = useMemo(
    () => ({
      com_saldo: 'true',
      ...(filtroUrl === 'baixo_estoque' ? { com_alertas: 'true' } : {}),
    }),
    [filtroUrl],
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
    filters,
    setFilter,
    loading,
    error,
    reload,
  } = usePaginatedList<EstoqueSaldoItem>({
    fetchPage: fetchSaldosPage,
    initialFilters,
  });
  const [corrida, setCorrida] = useState('');
  const [tipoFisico, setTipoFisico] = useState('');

  useEffect(() => {
    if (filtroUrl === 'baixo_estoque') setFilter('com_alertas', 'true');
  }, [filtroUrl, setFilter]);

  useEffect(() => {
    setFilter('corrida', corrida.trim());
  }, [corrida, setFilter]);

  useEffect(() => {
    setFilter('tipo_fisico', tipoFisico.trim());
  }, [tipoFisico, setFilter]);

  const somenteDimensionais = filters.somente_dimensionais === 'true';
  const somenteComSaldo = filters.com_saldo !== 'false';
  const somenteComAlertas = filters.com_alertas === 'true';

  return (
    <div>
      <PageHeader
        title="Estoque / Saldos"
        description="Consulta de saldos, alertas e situação dos produtos em estoque."
        searchValue={search}
        onSearch={setSearch}
      />

      <NexusCard className="mb-4 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="erp-label">Corrida</label>
            <input className="erp-input mt-1" placeholder="Ex.: ABC123" value={corrida} onChange={(e) => setCorrida(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Tipo físico</label>
            <input className="erp-input mt-1" placeholder="Ex.: TUBO" value={tipoFisico} onChange={(e) => setTipoFisico(e.target.value)} />
          </div>
          <div className="flex flex-col justify-end gap-2 sm:col-span-2 lg:col-span-2">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={somenteDimensionais}
                onChange={(e) => setFilter('somente_dimensionais', e.target.checked ? 'true' : '')}
              />
              Somente produtos dimensionais
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={somenteComSaldo}
                onChange={(e) => setFilter('com_saldo', e.target.checked ? 'true' : 'false')}
              />
              Somente com saldo
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={somenteComAlertas}
                onChange={(e) => setFilter('com_alertas', e.target.checked ? 'true' : '')}
              />
              Somente com alertas
            </label>
          </div>
        </div>
      </NexusCard>

      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={6} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Código</th>
                <th>Produto</th>
                <th>Corrida</th>
                <th>Saldo principal</th>
                <th>Equivalentes</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <EmptyState message="Nenhum saldo encontrado para os filtros atuais." />
                  </td>
                </tr>
              ) : (
                items.map((e, i) => (
                  <tr key={`${e.produto_id}-${e.corrida || i}`}>
                    <td className="font-mono">{e.codigo || '—'}</td>
                    <td className="font-medium">{e.descricao}</td>
                    <td className="font-mono">{e.corrida || '—'}</td>
                    <td className="font-bold nexus-numeric">
                      {fmt(e.saldo_principal)} {e.unidade_principal || 'UN'}
                    </td>
                    <td>
                      {e.usa_conversao_dimensional ? (
                        <span className="text-sm">
                          Equiv.: {fmt(e.metros)} M | {fmt(e.barras)} BR | {fmt(e.toneladas)} TON
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="max-w-[320px]">
                      <div className="flex flex-wrap gap-1 items-center">
                        <StatusBadge status={situacaoPrincipal(e)} />
                        {e.alertas?.slice(1).map((a, idx) => (
                          <StatusBadge key={idx} status={alertaParaStatus(a)} />
                        ))}
                      </div>
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

export default Estoque;
