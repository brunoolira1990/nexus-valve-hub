import { useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Download, ExternalLink, FileDown, MoreVertical, Pencil, ShoppingCart, Trash2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { PageHeader } from '@/components/PageHeader';
import { propostasService } from '@/services/api/comercial';
import type { Proposta } from '@/types';
import {
  STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
  STATUS_PROPOSTA_REABERTA,
} from '@/lib/comercialFormDefaults';
import {
  propostaPodeGerarPedido,
  propostaRequerRecuperacao,
  propostaTemPedidoGerado,
  propostaTotalmenteConvertida,
  statusPropostaUi,
} from '@/lib/propostaStatus';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBr } from '@/lib/numberFormat';
import { apiErrorMessage } from '@/services/api/config';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { toast } from 'sonner';

const MSG_SALVE_ANTES_PDF =
  'Salve a proposta antes de gerar ou visualizar o PDF. Se você já salvou, recarregue a lista.';

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
  const load = reloadList;

  const abrirPedidoPorId = useCallback((pedidoId: number) => {
    navigate(`/pedidos-venda?pedido=${pedidoId}`);
  }, [navigate]);

  const abrirPedidoDaProposta = useCallback(
    (proposta: Pick<Proposta, 'pedido_venda_id' | 'pedido_venda_numero'>) => {
      if (!proposta.pedido_venda_id) return;
      abrirPedidoPorId(proposta.pedido_venda_id);
    },
    [abrirPedidoPorId],
  );

  const openNew = useCallback(() => {
    navigate('/propostas/nova');
  }, [navigate]);

  const openEdit = useCallback((e: Proposta) => {
    navigate(`/propostas/${e.id}`);
  }, [navigate]);

  const handleDelete = useCallback(async (id: number) => {
    const nid = Number(id);
    if (!Number.isFinite(nid) || nid <= 0) {
      toast.error('Proposta inválida para exclusão. Recarregue a lista.');
      return;
    }
    if (confirm('Excluir?')) {
      await propostasService.delete(nid);
      void load();
    }
  }, [load]);

  const startWizard = useCallback(async (proposta: Proposta) => {
    if (propostaRequerRecuperacao(proposta)) {
      navigate(`/propostas/${proposta.id}`);
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
      navigate(`/propostas/${proposta.id}`);
      return;
    }
    navigate(`/propostas/${proposta.id}`);
  }, [abrirPedidoDaProposta, navigate]);

  const handleVisualizarPdf = useCallback(async (proposta: Proposta) => {
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
      toast.error(e instanceof Error ? e.message : apiErrorMessage(e, { fallback: 'Não foi possível visualizar o PDF da proposta.' }));
    }
  }, []);

  const handleBaixarPdf = useCallback(async (proposta: Proposta) => {
    const id = Number(proposta?.id);
    if (!Number.isFinite(id) || id <= 0) {
      alert(MSG_SALVE_ANTES_PDF);
      return;
    }
    try {
      await propostasService.baixarPdf(id, proposta.numero || String(id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : apiErrorMessage(e, { fallback: 'Não foi possível baixar o PDF da proposta.' }));
    }
  }, []);

  return (
    <div>
      <PageHeader
        title="Propostas"
        description="Gestão de propostas comerciais e acompanhamento até conversão em pedido."
        onAdd={openNew}
        addLabel="Nova Proposta"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Digite parte do número da proposta."
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
        <DataTable mobileMode="cards">
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
                        onClick={() => void startWizard(e)}
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
                          onSelect={() => void handleDelete(e.id)}
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
    </div>
  );
};

export default Propostas;
