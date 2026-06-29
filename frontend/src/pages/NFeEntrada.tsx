import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, X, ExternalLink, FileUp, AlertCircle, Copy, FileSearch, Eye } from 'lucide-react';
import { toast } from 'sonner';
import { NexusButton } from '@/components/nexus';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NFeEntradaDetalheDrawer } from '@/components/fiscal/NFeEntradaDetalheDrawer';
import { NFeEntradaRevisaoDrawer } from '@/components/fiscal/NFeEntradaRevisaoDrawer';
import { nfeEntradasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeEntrada, ItemNFe, NFeEntradaPropriaImportResultado } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { labelStatusOperacionalNfeEntrada, labelTipoOrigemNfeEntrada, exibirAcaoRevisarDados } from '@/lib/nfeEntradaOperacionalLabels';
import {
  copiarTextoParaAreaDeTransferencia,
  montarTextoDiagnosticoNfeEntradaXml,
  normalizarFalhaImportacaoXml,
} from '@/utils/nfeXmlImportDiagnostico';

const BASE_NFE_ENTRADA_IMPORTADA_PATH = '/nfe-entrada-historica-importada';

const NFeEntrada = () => {
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
    loading,
    error,
    reload,
  } = usePaginatedList<NFeEntrada>({ fetchPage: nfeEntradasService.listPaginated });
  const [modalOpen, setModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [importErro, setImportErro] = useState<string | null>(null);
  const [importResultado, setImportResultado] = useState<NFeEntradaPropriaImportResultado | null>(null);
  const [diagCopiado, setDiagCopiado] = useState(false);
  const [editing, setEditing] = useState<NFeEntrada | null>(null);
  const [form, setForm] = useState({
    numero: '',
    fornecedor_id: 1,
    fornecedor_nome: 'Tupy S.A.',
    data: '',
    pedido_compra_id: undefined as number | undefined,
    cte_id: undefined as number | undefined,
  });
  const [itens, setItens] = useState<ItemNFe[]>([]);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [detalheOpen, setDetalheOpen] = useState(false);
  const [revisaoId, setRevisaoId] = useState<number | null>(null);
  const [revisaoOpen, setRevisaoOpen] = useState(false);

  const abrirDetalhe = (id: number) => {
    setDetalheId(id);
    setDetalheOpen(true);
  };

  const fecharDetalhe = () => {
    setDetalheOpen(false);
    setDetalheId(null);
  };

  const abrirRevisao = (id: number) => {
    setRevisaoId(id);
    setRevisaoOpen(true);
  };

  const fecharRevisao = () => {
    setRevisaoOpen(false);
    setRevisaoId(null);
  };

  const copiarChaveNfe = async (chave?: string | null) => {
    const texto = (chave || '').trim();
    if (!texto) {
      toast.error('Esta NF-e não possui chave de acesso.');
      return;
    }
    try {
      await copiarTextoParaAreaDeTransferencia(texto);
      toast.success('Chave NF-e copiada para a área de transferência.');
    } catch {
      toast.error('Não foi possível copiar a chave. Tente novamente.');
    }
  };

  const addItem = () =>
    setItens((p) => [...p, { id: Date.now(), produto_id: 1, produto_nome: '', quantidade: 1, valor: 0, corrida_id: undefined }]);
  const removeItem = (id: number) => setItens((p) => p.filter((i) => i.id !== id));
  const total = itens.reduce((s, i) => s + i.quantidade * i.valor, 0);

  const openEntradaPropria = () => {
    setEditing(null);
    setForm({ numero: '', fornecedor_id: 1, fornecedor_nome: '', data: '', pedido_compra_id: undefined, cte_id: undefined });
    setItens([]);
    setModalOpen(true);
  };

  const openImportEntradaPropria = () => {
    setImportErro(null);
    setImportResultado(null);
    setImportModalOpen(true);
  };

  const onImportFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setImportErro(null);
    setImportBusy(true);
    try {
      const res = await nfeEntradasService.importarEntradaPropriaEmitida(Array.from(files));
      setImportResultado(res);
      void reload();
    } catch (e) {
      setImportErro(apiErrorMessage(e));
    } finally {
      setImportBusy(false);
    }
  };

  const falhasImport = importResultado?.erros?.length
    ? importResultado.erros.map((raw) => normalizarFalhaImportacaoXml(raw))
    : [];

  const copiarDiagnostico = async () => {
    if (!importResultado) return;
    await copiarTextoParaAreaDeTransferencia(
      montarTextoDiagnosticoNfeEntradaXml({
        importadas: importResultado.importadas.map((i) => ({
          arquivo: i.arquivo,
          id: i.id,
          chave_acesso: i.chave_acesso,
          numero: i.numero,
          serie: i.serie,
        })),
        duplicadas: importResultado.duplicadas,
        erros: importResultado.erros,
        resumo: importResultado.resumo,
      }),
    );
    setDiagCopiado(true);
    window.setTimeout(() => setDiagCopiado(false), 2500);
  };

  const handleSave = async () => {
    const data = { ...form, itens, valor_total: total };
    if (editing) await nfeEntradasService.update(editing.id, data);
    else await nfeEntradasService.create(data as Omit<NFeEntrada, 'id'>);
    setModalOpen(false);
    void reload();
  };

  const emitenteLabel = (e: NFeEntrada) => {
    if (e.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA') {
      return e.destinatario_nome ? `${e.fornecedor_nome} → ${e.destinatario_nome}` : e.fornecedor_nome;
    }
    return e.fornecedor_nome;
  };

  return (
    <div>
      <PageHeader
        title="Entrada Própria"
        description="Entradas próprias emitidas ou importadas manualmente pela empresa (ex.: devolução). XMLs de fornecedor devem ser tratados no Inbox Fiscal."
        searchValue={search}
        onSearch={setSearch}
        actions={
          <>
            <NexusButton type="button" variant="outline" onClick={() => navigate(BASE_NFE_ENTRADA_IMPORTADA_PATH)}>
              <ExternalLink className="h-4 w-4" />
              Ir para Base NF-e Entrada Importada
            </NexusButton>
            <NexusButton type="button" variant="outline" onClick={openImportEntradaPropria}>
              <FileUp className="h-4 w-4" />
              Importar entrada própria já emitida
            </NexusButton>
            <NexusButton type="button" onClick={openEntradaPropria}>
              <Plus className="h-4 w-4" />
              Emitir entrada própria
            </NexusButton>
          </>
        }
      />
      {error ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={9} /> : null}
      {!loading && !error ? (
        <DataTableShell>
          <DataTable>
            <thead>
              <tr>
                <th>Emitente / Destinatário</th>
                <th>Tipo</th>
                <th>Número</th>
                <th>Série</th>
                <th>Chave</th>
                <th>Emissão</th>
                <th>Status</th>
                <th>Valor</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={9}>
                    <EmptyState
                      title="Nenhuma Entrada Própria encontrada."
                      message="Use o Inbox Fiscal para receber NF-e de fornecedores. Aqui, importe entrada própria já emitida (ex.: devolução) ou emita uma entrada própria manualmente."
                    />
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">{emitenteLabel(e)}</td>
                    <td>
                      <StatusBadge status={labelTipoOrigemNfeEntrada(e)} />
                    </td>
                    <td>{e.numero}</td>
                    <td>{e.serie || '—'}</td>
                    <td className="font-mono text-xs" title={e.chave_acesso || undefined}>
                      {chaveNfeResumida(e.chave_acesso)}
                    </td>
                    <td>{e.data ? formatDateBr(e.data) : '—'}</td>
                    <td>
                      <StatusBadge
                        status={labelStatusOperacionalNfeEntrada(e.status_operacional, e.status_operacional_label)}
                      />
                    </td>
                    <td className="nexus-numeric whitespace-nowrap">{formatMoneyBRL(e.valor_total)}</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {exibirAcaoRevisarDados(e) ? (
                          <button
                            type="button"
                            className="erp-btn-ghost erp-btn-sm text-xs"
                            title="Revisar dados importados (somente leitura)"
                            aria-label="Revisar dados da NF-e"
                            onClick={() => abrirRevisao(e.id)}
                          >
                            <FileSearch className="h-3.5 w-3.5 mr-0.5" />
                            Revisar dados
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-xs"
                          title="Copiar chave NF-e"
                          aria-label="Copiar chave NF-e"
                          onClick={() => void copiarChaveNfe(e.chave_acesso)}
                        >
                          <Copy className="h-3.5 w-3.5 mr-0.5" />
                          Copiar chave
                        </button>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-xs"
                          title="Ver detalhes da NF-e"
                          aria-label="Ver detalhes da NF-e"
                          onClick={() => abrirDetalhe(e.id)}
                        >
                          <Eye className="h-3.5 w-3.5 mr-0.5" />
                          Ver detalhes
                        </button>
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

      <Modal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        title="Importar entrada própria já emitida"
        size="lg"
      >
        <p className="text-sm text-muted-foreground mb-4">
          XML de NF-e de entrada própria já emitida pela empresa (ex.: devolução ou recusa de cliente). Não gera
          financeiro, estoque ou transmissão SEFAZ.
        </p>
        <label className="flex flex-col items-center justify-center gap-2 border border-dashed border-border rounded-lg p-8 cursor-pointer hover:bg-muted/40">
          <FileUp className="h-8 w-8 text-muted-foreground" />
          <span className="text-sm font-medium">Selecionar XMLs</span>
          <input
            type="file"
            accept=".xml,application/xml,text/xml"
            multiple
            className="hidden"
            disabled={importBusy}
            onChange={(ev) => void onImportFiles(ev.target.files)}
          />
        </label>
        {importBusy ? <p className="text-sm text-muted-foreground mt-3">Importando…</p> : null}
        {importErro ? (
          <p className="text-sm text-destructive mt-3 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {importErro}
          </p>
        ) : null}
        {importResultado ? (
          <div className="mt-4 space-y-3 text-sm">
            <p>
              <strong>{importResultado.resumo.importadas}</strong> importada(s),{' '}
              <strong>{importResultado.resumo.duplicadas}</strong> duplicada(s),{' '}
              <strong>{importResultado.resumo.erros}</strong> erro(s).
            </p>
            {importResultado.duplicadas.length > 0 ? (
              <ul className="list-disc pl-5 text-muted-foreground">
                {importResultado.duplicadas.map((d) => (
                  <li key={d.chave_acesso}>{d.arquivo}: {d.mensagem}</li>
                ))}
              </ul>
            ) : null}
            {falhasImport.length > 0 ? (
              <ul className="space-y-2">
                {falhasImport.map((f) => (
                  <li key={`${f.arquivo}-${f.chave}`} className="border border-border rounded p-2">
                    <p className="font-medium">{f.arquivo}</p>
                    <p className="text-destructive">{f.erroCurto}</p>
                    <p className="text-muted-foreground text-xs mt-1">{f.acaoSugerida}</p>
                  </li>
                ))}
              </ul>
            ) : null}
            <NexusButton type="button" variant="outline" size="sm" onClick={() => void copiarDiagnostico()}>
              <Copy className="h-4 w-4" />
              {diagCopiado ? 'Diagnóstico copiado' : 'Copiar diagnóstico'}
            </NexusButton>
          </div>
        ) : null}
      </Modal>

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar entrada própria' : 'Emitir entrada própria'}
        size="xl"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="erp-label">Número</label>
            <input className="erp-input mt-1" value={form.numero} onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Fornecedor</label>
            <select className="erp-select mt-1" value={form.fornecedor_id} onChange={(e) => setForm((p) => ({ ...p, fornecedor_id: +e.target.value }))}>
              <option value={1}>Tupy S.A.</option>
              <option value={2}>Vallourec</option>
            </select>
          </div>
          <div>
            <label className="erp-label">Data</label>
            <input type="date" className="erp-input mt-1" value={form.data} onChange={(e) => setForm((p) => ({ ...p, data: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Pedido Compra (opcional)</label>
            <input
              className="erp-input mt-1"
              placeholder="PC-001"
              value={form.pedido_compra_id ?? ''}
              onChange={(e) => setForm((p) => ({ ...p, pedido_compra_id: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div>
            <label className="erp-label">CT-e vinculado (opcional)</label>
            <input
              className="erp-input mt-1"
              placeholder="CTE-001"
              value={form.cte_id ?? ''}
              onChange={(e) => setForm((p) => ({ ...p, cte_id: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm">
              <Plus className="h-3 w-3" /> Item
            </button>
          </div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-5 gap-2 mb-2 items-end">
              <div>
                <label className="text-xs text-muted-foreground">Produto</label>
                <select
                  className="erp-input h-8 text-sm"
                  value={item.produto_id}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], produto_id: +e.target.value };
                    setItens(n);
                  }}
                >
                  <option value={1}>Válvula Gaveta 2&quot;</option>
                  <option value={2}>Válvula Esfera 4&quot;</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Qtd</label>
                <input
                  type="number"
                  className="erp-input h-8 text-sm"
                  value={item.quantidade}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], quantidade: +e.target.value };
                    setItens(n);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Valor</label>
                <input
                  type="number"
                  step="0.01"
                  className="erp-input h-8 text-sm"
                  value={item.valor}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], valor: +e.target.value };
                    setItens(n);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Corrida</label>
                <select
                  className="erp-input h-8 text-sm"
                  value={item.corrida_id ?? ''}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], corrida_id: +e.target.value || undefined };
                    setItens(n);
                  }}
                >
                  <option value="">Nova corrida</option>
                  <option value={1}>C-2024-001</option>
                  <option value={2}>C-2024-002</option>
                </select>
              </div>
              <button type="button" onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8">
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total: R$ {total.toFixed(2)}</div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
            Cancelar
          </button>
          <button type="button" onClick={() => void handleSave()} className="erp-btn-primary">
            Salvar
          </button>
        </div>
      </Modal>

      <NFeEntradaDetalheDrawer nfeId={detalheId} open={detalheOpen} onClose={fecharDetalhe} />
      <NFeEntradaRevisaoDrawer nfeId={revisaoId} open={revisaoOpen} onClose={fecharRevisao} />
    </div>
  );
};

export default NFeEntrada;
