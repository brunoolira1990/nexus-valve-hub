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
    empresa_emitente_id: undefined as number | undefined,
    cliente_destinatario_id: undefined as number | undefined,
    fornecedor_id: undefined as number | undefined,
    fornecedor_nome: '',
    data: '',
    fin_nfe: '4',
    nat_op: 'Devolução de mercadoria',
    chave_nfe_referenciada: '',
    ambiente_emissao: 'producao' as 'homologacao' | 'producao',
    pedido_compra_id: undefined as number | undefined,
    cte_id: undefined as number | undefined,
  });
  const [itens, setItens] = useState<ItemNFe[]>([]);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [detalheOpen, setDetalheOpen] = useState(false);
  const [revisaoId, setRevisaoId] = useState<number | null>(null);
  const [revisaoOpen, setRevisaoOpen] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);

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

  const impostosPadrao = () => ({
    icms: { cst: '41', orig: '0' },
    pis: { cst: '07' },
    cofins: { cst: '07' },
  });

  const addItem = () =>
    setItens((p) => [
      ...p,
      {
        id: Date.now(),
        produto_id: 0,
        produto_nome: '',
        quantidade: 1,
        valor: 0,
        ncm: '',
        cfop: '1202',
        unidade: 'UN',
        impostos_json: impostosPadrao(),
      },
    ]);
  const removeItem = (id: number) => setItens((p) => p.filter((i) => i.id !== id));
  const total = itens.reduce((s, i) => s + i.quantidade * i.valor, 0);

  const openEntradaPropria = () => {
    setEditing(null);
    setForm({
      numero: '',
      empresa_emitente_id: undefined,
      cliente_destinatario_id: undefined,
      fornecedor_id: undefined,
      fornecedor_nome: '',
      data: new Date().toISOString().slice(0, 10),
      fin_nfe: '4',
      nat_op: 'Devolução de mercadoria',
      chave_nfe_referenciada: '',
      ambiente_emissao: 'producao',
      pedido_compra_id: undefined,
      cte_id: undefined,
    });
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
    if (!form.empresa_emitente_id) {
      toast.error('Informe o ID da empresa emitente.');
      return;
    }
    if (!form.cliente_destinatario_id && !form.fornecedor_id) {
      toast.error('Informe cliente OU fornecedor como destinatário.');
      return;
    }
    if (form.cliente_destinatario_id && form.fornecedor_id) {
      toast.error('Destinatário deve ser cliente ou fornecedor — não ambos.');
      return;
    }
    if (!itens.length) {
      toast.error('Inclua ao menos um item com NCM, CFOP e unidade.');
      return;
    }
    setSaveBusy(true);
    try {
      const data = {
        numero: form.numero || `EP-${Date.now()}`,
        data: form.data,
        empresa_emitente_id: form.empresa_emitente_id,
        cliente_destinatario_id: form.cliente_destinatario_id ?? null,
        fornecedor_id: form.fornecedor_id ?? null,
        fin_nfe: form.fin_nfe,
        nat_op: form.nat_op,
        chave_nfe_referenciada: form.chave_nfe_referenciada,
        ambiente_emissao: form.ambiente_emissao,
        pedido_compra_id: form.pedido_compra_id,
        cte_id: form.cte_id,
        itens,
        valor_total: total,
        fornecedor_nome: '',
      };
      if (editing) {
        await nfeEntradasService.update(editing.id, data);
        toast.success('Rascunho atualizado.');
      } else {
        const criada = await nfeEntradasService.criarEntradaPropriaEmitida(data);
        toast.success('Rascunho criado — abra os detalhes para emitir na SEFAZ.');
        setModalOpen(false);
        void reload();
        abrirDetalhe(criada.id);
        return;
      }
      setModalOpen(false);
      void reload();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setSaveBusy(false);
    }
  };

  const emitenteLabel = (e: NFeEntrada) => {
    if (e.tipo_origem === 'ENTRADA_PROPRIA_IMPORTADA' || e.tipo_origem === 'ENTRADA_PROPRIA_EMITIDA') {
      return e.destinatario_nome ? `${e.fornecedor_nome || 'Empresa'} → ${e.destinatario_nome}` : e.fornecedor_nome;
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
        searchPlaceholder="Digite parte do número da NF-e de entrada."
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
        title={editing ? 'Editar entrada própria emitida' : 'Emitir entrada própria'}
        size="xl"
      >
        <p className="text-sm text-muted-foreground mb-4">
          Cria rascunho <strong>ENTRADA_PROPRIA_EMITIDA</strong> (sem estoque). Após salvar, use
          <strong> Ver detalhes</strong> para validar, numerar e transmitir à SEFAZ.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="erp-label">Número interno</label>
            <input
              className="erp-input mt-1"
              placeholder="Opcional — gerado se vazio"
              value={form.numero}
              onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Empresa emitente (ID)</label>
            <input
              type="number"
              className="erp-input mt-1"
              value={form.empresa_emitente_id ?? ''}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  empresa_emitente_id: e.target.value ? +e.target.value : undefined,
                }))
              }
            />
          </div>
          <div>
            <label className="erp-label">Data</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={form.data}
              onChange={(e) => setForm((p) => ({ ...p, data: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Cliente destinatário (ID)</label>
            <input
              type="number"
              className="erp-input mt-1"
              value={form.cliente_destinatario_id ?? ''}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  cliente_destinatario_id: e.target.value ? +e.target.value : undefined,
                  fornecedor_id: e.target.value ? undefined : p.fornecedor_id,
                }))
              }
            />
          </div>
          <div>
            <label className="erp-label">Ou fornecedor destinatário (ID)</label>
            <input
              type="number"
              className="erp-input mt-1"
              value={form.fornecedor_id ?? ''}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  fornecedor_id: e.target.value ? +e.target.value : undefined,
                  cliente_destinatario_id: e.target.value ? undefined : p.cliente_destinatario_id,
                }))
              }
            />
          </div>
          <div>
            <label className="erp-label">Ambiente</label>
            <select
              className="erp-select mt-1"
              value={form.ambiente_emissao}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  ambiente_emissao: e.target.value as 'homologacao' | 'producao',
                }))
              }
            >
              <option value="producao">Produção</option>
              <option value="homologacao">Homologação</option>
            </select>
          </div>
          <div>
            <label className="erp-label">finNFe</label>
            <select
              className="erp-select mt-1"
              value={form.fin_nfe}
              onChange={(e) => setForm((p) => ({ ...p, fin_nfe: e.target.value }))}
            >
              <option value="1">1 — Normal</option>
              <option value="2">2 — Complementar</option>
              <option value="3">3 — Ajuste</option>
              <option value="4">4 — Devolução</option>
            </select>
          </div>
          <div>
            <label className="erp-label">Natureza da operação</label>
            <input
              className="erp-input mt-1"
              value={form.nat_op}
              onChange={(e) => setForm((p) => ({ ...p, nat_op: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Chave NF-e referenciada</label>
            <input
              className="erp-input mt-1 font-mono text-xs"
              maxLength={44}
              placeholder="Obrigatória recomendada se finNFe=4"
              value={form.chave_nfe_referenciada}
              onChange={(e) => setForm((p) => ({ ...p, chave_nfe_referenciada: e.target.value }))}
            />
          </div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens fiscais</h3>
            <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm">
              <Plus className="h-3 w-3" /> Item
            </button>
          </div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3 items-end border-b border-border pb-3">
              <div>
                <label className="text-xs text-muted-foreground">Produto ID</label>
                <input
                  type="number"
                  className="erp-input h-8 text-sm"
                  value={item.produto_id || ''}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], produto_id: +e.target.value || 0 };
                    setItens(n);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">NCM</label>
                <input
                  className="erp-input h-8 text-sm"
                  value={item.ncm || ''}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], ncm: e.target.value };
                    setItens(n);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">CFOP</label>
                <input
                  className="erp-input h-8 text-sm"
                  value={item.cfop || ''}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], cfop: e.target.value };
                    setItens(n);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Unidade</label>
                <input
                  className="erp-input h-8 text-sm"
                  value={item.unidade || ''}
                  onChange={(e) => {
                    const n = [...itens];
                    n[idx] = { ...n[idx], unidade: e.target.value };
                    setItens(n);
                  }}
                />
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
              <div className="flex gap-1 items-end">
                <div className="flex-1">
                  <label className="text-xs text-muted-foreground">Valor unit.</label>
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
                <button
                  type="button"
                  onClick={() => removeItem(item.id)}
                  className="erp-btn-ghost erp-btn-sm text-destructive h-8"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
          <p className="text-xs text-muted-foreground mb-2">
            Impostos padrão NT (ICMS CST 41 / PIS-COFINS 07). Ajuste via API se necessário.
          </p>
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">
            Total: R$ {total.toFixed(2)}
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
            Cancelar
          </button>
          <button
            type="button"
            disabled={saveBusy}
            onClick={() => void handleSave()}
            className="erp-btn-primary"
          >
            {saveBusy ? 'Salvando…' : 'Salvar rascunho'}
          </button>
        </div>
      </Modal>

      <NFeEntradaDetalheDrawer
        nfeId={detalheId}
        open={detalheOpen}
        onClose={fecharDetalhe}
        onChanged={() => void reload()}
      />
      <NFeEntradaRevisaoDrawer nfeId={revisaoId} open={revisaoOpen} onClose={fecharRevisao} />
    </div>
  );
};

export default NFeEntrada;
