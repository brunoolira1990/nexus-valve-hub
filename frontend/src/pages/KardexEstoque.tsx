import { useCallback, useEffect, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { estoqueService } from '@/services/api/outros';
import type { KardexEstoqueEvento, KardexEstoqueResumo } from '@/types';

const resumoVazio: KardexEstoqueResumo = {
  entradas: '0.000',
  saidas: '0.000',
  estornos: '0.000',
  saldo_final: '0.000',
  quantidade_eventos: 0,
};

function fmt(value?: string | null): string {
  if (value == null) return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return '—';
  return number.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function fmtDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function eventoClasses(natureza: KardexEstoqueEvento['natureza']): string {
  if (natureza === 'ENTRADA') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (natureza === 'ESTORNO') return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
}

function ResumoCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-bold ${tone}`}>{fmt(value)}</p>
    </div>
  );
}

const KardexEstoque = () => {
  const [search, setSearch] = useState('');
  const [produtoId, setProdutoId] = useState('');
  const [corridaId, setCorridaId] = useState('');
  const [natureza, setNatureza] = useState('');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');
  const [items, setItems] = useState<KardexEstoqueEvento[]>([]);
  const [resumo, setResumo] = useState<KardexEstoqueResumo>(resumoVazio);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [count, setCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await estoqueService.listKardexPaginated({
        page,
        page_size: pageSize,
        ...(search.trim() ? { search: search.trim() } : {}),
        ...(produtoId.trim() ? { produto_id: Number(produtoId) } : {}),
        ...(corridaId.trim() ? { corrida_id: Number(corridaId) } : {}),
        ...(natureza ? { natureza: natureza as KardexEstoqueEvento['natureza'] } : {}),
        ...(dataInicio ? { data_inicio: dataInicio } : {}),
        ...(dataFim ? { data_fim: dataFim } : {}),
      });
      setItems(response.results);
      setResumo(response.resumo || resumoVazio);
      setCount(response.count);
      setTotalPages(response.total_pages);
    } catch {
      setError(true);
      setItems([]);
      setResumo(resumoVazio);
    } finally {
      setLoading(false);
    }
  }, [corridaId, dataFim, dataInicio, natureza, page, pageSize, produtoId, search]);

  useEffect(() => {
    void load();
  }, [load]);

  const limparFiltros = () => {
    setSearch('');
    setProdutoId('');
    setCorridaId('');
    setNatureza('');
    setDataInicio('');
    setDataFim('');
    setPage(1);
  };

  return (
    <div>
      <PageHeader
        title="Kardex de Estoque"
        description="Extrato derivado dos efeitos físicos aplicados, por produto e corrida. Consulta somente leitura."
        searchValue={search}
        onSearch={(value) => {
          setSearch(value);
          setPage(1);
        }}
      />

      <NexusCard className="mb-4 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="erp-label" htmlFor="kardex-produto">Produto ID</label>
            <input id="kardex-produto" className="erp-input mt-1 w-full" inputMode="numeric" placeholder="Ex.: 123" value={produtoId} onChange={(event) => setProdutoId(event.target.value)} />
          </div>
          <div>
            <label className="erp-label" htmlFor="kardex-corrida">Corrida ID</label>
            <input id="kardex-corrida" className="erp-input mt-1 w-full" inputMode="numeric" placeholder="Ex.: 45" value={corridaId} onChange={(event) => setCorridaId(event.target.value)} />
          </div>
          <div>
            <label className="erp-label" htmlFor="kardex-natureza">Natureza</label>
            <select id="kardex-natureza" className="erp-input mt-1 w-full" value={natureza} onChange={(event) => { setNatureza(event.target.value); setPage(1); }}>
              <option value="">Todas</option>
              <option value="ENTRADA">Entradas físicas</option>
              <option value="SAIDA">Saídas físicas</option>
              <option value="ESTORNO">Estornos de saída</option>
            </select>
          </div>
          <div>
            <label className="erp-label" htmlFor="kardex-inicio">Data inicial</label>
            <input id="kardex-inicio" type="date" className="erp-input mt-1 w-full" value={dataInicio} onChange={(event) => { setDataInicio(event.target.value); setPage(1); }} />
          </div>
          <div>
            <label className="erp-label" htmlFor="kardex-fim">Data final</label>
            <input id="kardex-fim" type="date" className="erp-input mt-1 w-full" value={dataFim} onChange={(event) => { setDataFim(event.target.value); setPage(1); }} />
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <button type="button" className="erp-button-secondary w-full sm:w-auto" onClick={limparFiltros}>Limpar filtros</button>
          <button type="button" className="erp-button-primary w-full sm:w-auto" onClick={() => { setPage(1); void load(); }}>Atualizar extrato</button>
        </div>
      </NexusCard>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <ResumoCard label="Entradas físicas" value={resumo.entradas} tone="text-emerald-700" />
        <ResumoCard label="Saídas físicas" value={resumo.saidas} tone="text-rose-700" />
        <ResumoCard label="Estornos" value={resumo.estornos} tone="text-amber-700" />
        <ResumoCard label="Saldo do filtro" value={resumo.saldo_final} tone="text-sky-700" />
        <ResumoCard label="Eventos" value={String(resumo.quantidade_eventos)} tone="text-foreground" />
      </div>

      {error ? <ErrorState onRetry={() => void load()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
            <thead>
              <tr>
                <th>Data</th>
                <th>Natureza</th>
                <th>Produto</th>
                <th>Corrida</th>
                <th>Documento</th>
                <th>Quantidade</th>
                <th>Saldo acumulado</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={7}><EmptyState message="Nenhum evento físico encontrado para os filtros atuais." /></td></tr>
              ) : items.map((event) => (
                <tr key={event.id}>
                  <td className="whitespace-nowrap text-sm">{fmtDate(event.movimento_em)}</td>
                  <td>
                    <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${eventoClasses(event.natureza)}`}>{event.natureza_label}</span>
                  </td>
                  <td><div className="min-w-[180px]"><div className="font-mono text-xs">{event.codigo || '—'}</div><div className="font-medium">{event.descricao}</div></div></td>
                  <td className="font-mono">{event.corrida || '—'}</td>
                  <td><div className="min-w-[180px] text-sm">{event.documento}<div className="text-xs text-muted-foreground">{event.origem}</div></div></td>
                  <td className="whitespace-nowrap font-semibold nexus-numeric">{event.natureza === 'SAIDA' ? '-' : '+'}{fmt(event.quantidade)} {event.unidade}</td>
                  <td className="whitespace-nowrap font-bold nexus-numeric">{fmt(event.saldo_acumulado)} {event.unidade}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          {count > 0 ? <PaginationControls page={page} pageSize={pageSize} count={count} totalPages={totalPages} onPageChange={setPage} onPageSizeChange={(size) => { setPageSize(size); setPage(1); }} /> : null}
        </DataTableShell>
      ) : null}
    </div>
  );
};

export default KardexEstoque;
