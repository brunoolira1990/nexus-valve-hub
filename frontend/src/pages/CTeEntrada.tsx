import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { cteEntradasService } from '@/services/api/fiscal';
import type { CTeEntrada } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { formatDateBr } from '@/lib/dateBr';
import {formatMoneyBRL} from '@/lib/numberFields';

const BASE_CTE_IMPORTADA_PATH = '/cte-historico-importado';

const fmtMoney = (v: unknown): string => {
  const n = Number(v ?? 0);
  return `formatMoneyBRL(n)`;
};

const CTeEntrada = () => {
  const navigate = useNavigate();
  const [detalheId, setDetalheId] = useState<number | null>(null);
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
  } = usePaginatedList<CTeEntrada>({ fetchPage: cteEntradasService.listPaginated });

  return (
    <div>
      <PageHeader
        title="CT-e Entrada"
        description="Conhecimentos conferidos para uso operacional (frete, impostos e NF-es). No detalhe: rateio assistido e geração explícita de Contas a Pagar — a conferência sozinha não gera financeiro."
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Digite parte do número do CT-e."
        actions={
          <NexusButton type="button" variant="outline" onClick={() => navigate(BASE_CTE_IMPORTADA_PATH)}>
            <ExternalLink className="h-4 w-4" />
            Ir para Base CT-e Importada
          </NexusButton>
        }
      />
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={9} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Número</th>
                <th>Transportadora</th>
                <th>Tomador</th>
                <th>Valor Frete</th>
                <th>ICMS</th>
                <th>NF-es</th>
                <th>Data</th>
                <th>Status</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={9}>
                    <div className="py-10 px-4 text-center">
                      <p className="text-sm font-medium text-foreground">Nenhum CT-e operacional encontrado.</p>
                      <p className="text-sm text-muted-foreground mt-2 max-w-xl mx-auto">
                        Importe XMLs na Base CT-e Importada e confira os documentos para uso operacional. A conferência
                        não gera contas a pagar, expedição ou rateio.
                      </p>
                      <NexusButton
                        type="button"
                        className="mt-4"
                        onClick={() => navigate(BASE_CTE_IMPORTADA_PATH)}
                      >
                        <ExternalLink className="h-4 w-4" />
                        Ir para Base CT-e Importada
                      </NexusButton>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">
                      {e.numero}
                      {e.serie ? `/${e.serie}` : ''}
                      {e.cfop ? (
                        <div className="text-xs text-muted-foreground font-normal">CFOP {e.cfop}</div>
                      ) : null}
                    </td>
                    <td>{e.transportadora_nome}</td>
                    <td>{e.tomador_nome}</td>
                    <td className="nexus-numeric">{fmtMoney(e.valor_frete)}</td>
                    <td className="text-xs tabular-nums whitespace-nowrap">
                      <div>{fmtMoney(e.impostos?.icms_valor)}</div>
                      {(e.impostos?.cbs_valor || e.impostos?.ibs_valor) ? (
                        <div className="text-muted-foreground">
                          CBS {fmtMoney(e.impostos?.cbs_valor)} · IBS {fmtMoney(e.impostos?.ibs_valor)}
                        </div>
                      ) : null}
                    </td>
                    <td className="tabular-nums">{e.qtd_nfe_referenciadas ?? 0}</td>
                    <td>{e.data ? formatDateBr(e.data) : '—'}</td>
                    <td>
                      <div className="flex flex-col gap-1 items-start">
                        {e.status_conferencia ? (
                          <StatusBadge status={e.status_conferencia.toLowerCase()} />
                        ) : (
                          <StatusBadge status="conferido" />
                        )}
                        <DfeClassificacaoBadges classificacao={e.classificacao_dfe} max={4} />
                      </div>
                    </td>
                    <td>
                      <NexusButton
                        type="button"
                        variant="outline"
                        className="erp-btn-sm"
                        onClick={() => setDetalheId(e.cte_historico_id ?? e.id)}
                      >
                        Detalhes
                      </NexusButton>
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

      <CTeHistoricoDetalheModal
        open={detalheId != null}
        cteId={detalheId}
        onClose={() => setDetalheId(null)}
        onConferenciaAtualizada={() => void reload()}
      />
    </div>
  );
};

export default CTeEntrada;
