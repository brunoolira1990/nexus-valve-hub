import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, RefreshCw } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { apiErrorMessage } from '@/services/api/config';
import { cotacoesFornecedoresService, propostasService } from '@/services/api/comercial';
import {
  filtrarCotacoes,
  labelOrigemCotacao,
  labelStatusCotacao,
  type CotacaoOrigemFiltro,
} from '@/lib/cotacaoFornecedores';
import type { CotacaoFornecedor, CotacaoFornecedorStatus, Proposta } from '@/types';

type FiltrosCotacao = {
  busca: string;
  status: CotacaoFornecedorStatus | 'TODOS';
  origem: CotacaoOrigemFiltro;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatDateBr(value) || '—';
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export default function CotacoesFornecedores() {
  const navigate = useNavigate();
  const [cotacoes, setCotacoes] = useState<CotacaoFornecedor[]>([]);
  const [propostas, setPropostas] = useState<Proposta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filtros, setFiltros] = useState<FiltrosCotacao>({
    busca: '',
    status: 'TODOS',
    origem: 'TODAS',
  });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [cotacoesRows, propostasRows] = await Promise.all([
        cotacoesFornecedoresService.list({ limit: 200 }),
        propostasService.getAll({ limit: 200 }),
      ]);
      setCotacoes(cotacoesRows);
      setPropostas(propostasRows);
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar as cotações.' }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const propostaNumeroPorId = useMemo(() => {
    const map: Record<number, string> = {};
    for (const proposta of propostas) {
      map[proposta.id] = proposta.numero;
    }
    return map;
  }, [propostas]);

  const cotacoesFiltradas = useMemo(
    () => filtrarCotacoes(cotacoes, filtros, propostaNumeroPorId),
    [cotacoes, filtros, propostaNumeroPorId],
  );

  return (
    <div className="min-w-0">
      <PageHeader
        title="Cotações com Fornecedores"
        description="Listagem de cotações de compra criadas para consulta de mercado."
        breadcrumbs={[
          { label: 'Compras' },
          { label: 'Cotações com Fornecedores' },
        ]}
        actions={
          <button
            type="button"
            className="erp-btn-primary"
            onClick={() => navigate('/cotacoes-fornecedores/nova')}
          >
            <Plus className="mr-2 h-4 w-4" />
            Nova cotação
          </button>
        }
      />

      {error ? <div className="erp-alert erp-alert-error mb-4">{error}</div> : null}

      <div className="space-y-4">
        {/* Filtros */}
        <div className="flex flex-wrap gap-3">
          <input
            className="erp-input flex-1 min-w-[200px] max-w-md"
            placeholder="Buscar por número, Proposta ou responsável..."
            aria-label="Buscar cotação"
            value={filtros.busca}
            onChange={(event) =>
              setFiltros((prev) => ({ ...prev, busca: event.target.value }))
            }
          />

          <select
            className="erp-input min-w-[180px]"
            aria-label="Filtrar por status"
            value={filtros.status}
            onChange={(event) =>
              setFiltros((prev) => ({
                ...prev,
                status: event.target.value as CotacaoFornecedorStatus | 'TODOS',
              }))
            }
          >
            <option value="TODOS">Todos os status</option>
            <option value="RASCUNHO">Rascunho</option>
            <option value="EM_COTACAO">Em cotação</option>
            <option value="PARCIAL">Parcial</option>
            <option value="CONCLUIDA">Concluída</option>
            <option value="CANCELADA">Cancelada</option>
          </select>

          <select
            className="erp-input min-w-[180px]"
            aria-label="Filtrar por origem"
            value={filtros.origem}
            onChange={(event) =>
              setFiltros((prev) => ({
                ...prev,
                origem: event.target.value as CotacaoOrigemFiltro,
              }))
            }
          >
            <option value="TODAS">Todas as origens</option>
            <option value="MANUAL">Manual</option>
            <option value="PROPOSTA">Vinculada à Proposta</option>
          </select>

          <button
            type="button"
            className="erp-btn-outline"
            onClick={() => void load()}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar
          </button>
        </div>

        {/* Tabela */}
        <DataTableShell>
          {loading ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              Carregando cotações…
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={() => void load()} />
          ) : cotacoesFiltradas.length === 0 ? (
            <EmptyState
              message="Nenhuma cotação criada ainda."
              actionLabel="Criar primeira cotação"
              onAction={() => navigate('/cotacoes-fornecedores/nova')}
            />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <th>Número</th>
                  <th>Origem</th>
                  <th>Proposta</th>
                  <th>Itens</th>
                  <th>Fornecedores</th>
                  <th>Status</th>
                  <th>Atualização</th>
                  <th className="w-24">Ação</th>
                </tr>
              </thead>
              <tbody>
                {cotacoesFiltradas.map((cotacao) => (
                  <tr key={cotacao.id}>
                    <td className="font-medium">{cotacao.numero}</td>
                    <td>{labelOrigemCotacao(cotacao)}</td>
                    <td>
                      {cotacao.proposta_id == null ? (
                        '—'
                      ) : (
                        <Link
                          className="text-primary hover:underline"
                          to={`/propostas?proposta_id=${cotacao.proposta_id}`}
                        >
                          {propostaNumeroPorId[cotacao.proposta_id] ||
                            `#${cotacao.proposta_id}`}
                        </Link>
                      )}
                    </td>
                    <td>{cotacao.itens.length}</td>
                    <td>{cotacao.participantes.length}</td>
                    <td>
                      <StatusBadge
                        status={cotacao.status}
                        label={labelStatusCotacao(cotacao.status)}
                      />
                    </td>
                    <td className="text-sm">{formatDateTime(cotacao.atualizado_em)}</td>
                    <td>
                      <button
                        type="button"
                        className="erp-btn-ghost erp-btn-sm"
                        onClick={() => navigate(`/cotacoes-fornecedores/${cotacao.id}`)}
                      >
                        Abrir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataTableShell>
      </div>
    </div>
  );
}
