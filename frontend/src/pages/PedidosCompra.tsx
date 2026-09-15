import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2, MoreVertical, FileDown, Download } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { pedidosCompraService } from '@/services/api/comercial';
import type { PedidoCompra } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { toast } from 'sonner';
import { formatMoneyBRL } from '@/lib/numberFields';

function numSeguro(v: unknown): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : 0;
}

const PedidosCompra = () => {
  const navigate = useNavigate();
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
    loading: loadingList,
    error: loadError,
    reload: reloadList,
  } = usePaginatedList<PedidoCompra>({ fetchPage: pedidosCompraService.listPaginated });

  const handleNovo = useCallback(() => {
    navigate('/pedidos-compra/novo');
  }, [navigate]);

  const handleEditar = useCallback((pedidoId: number | string) => {
    const pid = Number(pedidoId);
    if (!Number.isFinite(pid) || pid <= 0) {
      toast.error('Pedido sem identificador válido. Recarregue a lista ou entre em contato com o suporte.');
      return;
    }
    navigate(`/pedidos-compra/${pid}`);
  }, [navigate]);

  const handleDelete = useCallback(async (id: number) => {
    const nid = Number(id);
    if (!Number.isFinite(nid) || nid <= 0) {
      toast.error('Pedido inválido para exclusão. Recarregue a lista.');
      return;
    }
    if (confirm('Excluir?')) {
      await pedidosCompraService.delete(nid);
      void reloadList();
    }
  }, [reloadList]);

  const handleVisualizarPdf = useCallback(async (pedido: PedidoCompra) => {
    const rawId = pedido?.id;
    const id = Number(rawId);
    if (!Number.isFinite(id) || id <= 0) {
      console.error('[PedidosCompra] Visualizar PDF: id ausente ou inválido na linha da tabela', pedido);
      toast.error(
        'Não foi possível identificar o pedido para gerar o PDF (id inválido). Recarregue a lista ou contate o suporte.',
      );
      return;
    }
    const previewTab = window.open('about:blank', '_blank');
    if (!previewTab) {
      toast.error(
        'Não foi possível abrir uma nova aba (pop-up bloqueado). Permita pop-ups para este site e tente novamente.',
      );
      return;
    }
    try {
      await pedidosCompraService.visualizarPdf(id, pedido.numero || String(id), previewTab);
    } catch (e) {
      previewTab.close();
      toast.error(e instanceof Error ? e.message : 'Não foi possível gerar o PDF do pedido de compra.');
    }
  }, []);

  const handleBaixarPdf = useCallback(async (pedido: PedidoCompra) => {
    const rawId = pedido?.id;
    const id = Number(rawId);
    if (!Number.isFinite(id) || id <= 0) {
      toast.error(
        'Não foi possível identificar o pedido para baixar o PDF (id inválido). Recarregue a lista ou contate o suporte.',
      );
      return;
    }
    try {
      await pedidosCompraService.baixarPdf(id, pedido.numero || String(id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Não foi possível baixar o PDF do pedido de compra.');
    }
  }, []);

  return (
    <div>
      <PageHeader
        title="Pedidos de Compra"
        description="Controle de compras, fornecedores e acompanhamento de recebimento."
        onAdd={handleNovo}
        addLabel="Novo Pedido"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Digite parte do número do pedido de compra."
      />
      {loadError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {loadingList ? <TableSkeleton rows={6} cols={6} /> : null}
      {!loadingList && !loadError ? (
        <DataTableShell>
        <DataTable mobileMode="cards">
          <thead>
            <tr>
              <th>Número</th>
              <th>Fornecedor</th>
              <th>Data</th>
              <th>Status</th>
              <th>Valor Total</th>
              <th className="w-36 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    message="Nenhum pedido de compra encontrado."
                    actionLabel="Novo pedido"
                    onAction={handleNovo}
                  />
                </td>
              </tr>
            ) : (
            items.map((pedido) => (
              <tr key={pedido.id}>
                <td data-label="Número" className="font-medium">{pedido.numero ?? '—'}</td>
                <td data-label="Fornecedor">{pedido.fornecedor_nome ?? '—'}</td>
                <td data-label="Data">{pedido.data ?? ''}</td>
                <td data-label="Status">
                  <StatusBadge status={pedido.status ?? ''} />
                </td>
                <td data-label="Valor total">{formatMoneyBRL(numSeguro(pedido.valor_total))}</td>
                <td data-label="Ações" className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button" className="erp-btn-ghost erp-btn-sm" aria-label="Ações do pedido">
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      className="w-52"
                      onOpenAutoFocus={(ev) => ev.preventDefault()}
                    >
                      <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleEditar(pedido.id)}>
                        <span className="flex items-center gap-2">
                          <Pencil className="h-4 w-4" />
                          Editar
                        </span>
                      </DropdownMenuItem>
                      <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleVisualizarPdf(pedido)}>
                        <span className="flex items-center gap-2">
                          <FileDown className="h-4 w-4" />
                          Visualizar PDF
                        </span>
                      </DropdownMenuItem>
                      <DropdownMenuItem className="cursor-pointer" onSelect={() => void handleBaixarPdf(pedido)}>
                        <span className="flex items-center gap-2">
                          <Download className="h-4 w-4" />
                          Baixar PDF
                        </span>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="cursor-pointer text-destructive focus:text-destructive"
                        onSelect={() => void handleDelete(pedido.id)}
                      >
                        <span className="flex items-center gap-2">
                          <Trash2 className="h-4 w-4" />
                          Excluir
                        </span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
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

export default PedidosCompra;
