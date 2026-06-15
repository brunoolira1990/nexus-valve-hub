import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Pencil,
  Trash2,
  Plus,
  X,
  CheckCircle,
  ClipboardCheck,
  Loader2,
  FileCode,
  FileText,
  Copy,
  Eye,
  MoreHorizontal,
} from 'lucide-react';
import { NFeSaidaConferenciaModal } from '@/components/fiscal/NFeSaidaConferenciaModal';
import { NFeSaidaDetalheDrawer } from '@/components/fiscal/NFeSaidaDetalheDrawer';
import { NFeChecklistHomologacaoModal } from '@/components/fiscal/NFeChecklistHomologacaoModal';
import { NFeSaidaEfeitosPanel } from '@/components/fiscal/NFeSaidaEfeitosPanel';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import { apiErrorMessage } from '@/services/api/config';
import {
  nfeSaidasService,
  type NFeSaidaPreviewXmlResponse,
  type ValidacaoNFeSaidaResponse,
} from '@/services/api/fiscal';
import {
  atendimentoResumoBadgeClass,
  getNfeFiscalSummaryBadge,
  getNfeOperationalSummaryBadges,
} from '@/lib/nfeSaidaListagemCompacta';
import {
  formatDateBr,
  formatNfeSubtituloListagem,
  formatNfeTituloListagem,
  formatNfeValorListagem,
} from '@/lib/nfeSaidaApresentacaoFormat';
import {
  nfeClienteBloqueado,
  nfeDadosComplementaresEditaveis,
  nfeItensComerciaisEditaveis,
  nfeSalvarFormularioBloqueado,
} from '@/lib/nfeSaidaUi';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { transportadorasService } from '@/services/api/transportadoras';
import type { NFeSaida, NFeSaidaListItem, ItemNFe, Transportadora } from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';

type NFeSaidaFormState = {
  numero: string;
  cliente_id: number | null;
  cliente_nome: string;
  data: string;
  status: string;
  pedido_venda_id?: number;
  modo_atendimento_estoque: 'IMEDIATO' | 'ANTECIPADO';
  transportadora_id: number | null;
  modalidade_frete: string;
  valor_frete: number;
  quantidade_volumes: number;
  peso_bruto: number;
  peso_liquido: number;
  observacoes_nfe: string;
  informacoes_adicionais: string;
};

function buildFormFromNfe(nfe: NFeSaida | null): NFeSaidaFormState {
  const complementoVazio = {
    transportadora_id: null as number | null,
    modalidade_frete: '9',
    valor_frete: 0,
    quantidade_volumes: 0,
    peso_bruto: 0,
    peso_liquido: 0,
    observacoes_nfe: '',
    informacoes_adicionais: '',
  };
  if (!nfe) {
    return {
      numero: '',
      cliente_id: null,
      cliente_nome: '',
      data: '',
      status: 'RASCUNHO',
      pedido_venda_id: undefined,
      modo_atendimento_estoque: 'IMEDIATO',
      ...complementoVazio,
    };
  }
  return {
    numero: nfe.numero,
    cliente_id: nfe.cliente_id ?? null,
    cliente_nome: nfe.cliente_nome ?? '',
    data: nfe.data,
    status: nfe.status,
    pedido_venda_id: nfe.pedido_venda_id,
    modo_atendimento_estoque: nfe.modo_atendimento_estoque ?? 'IMEDIATO',
    transportadora_id: nfe.transportadora_id ?? null,
    modalidade_frete: nfe.modalidade_frete ?? '9',
    valor_frete: Number(nfe.valor_frete ?? 0),
    quantidade_volumes: Number(nfe.quantidade_volumes ?? 0),
    peso_bruto: Number(nfe.peso_bruto ?? 0),
    peso_liquido: Number(nfe.peso_liquido ?? 0),
    observacoes_nfe: nfe.observacoes_nfe ?? '',
    informacoes_adicionais: nfe.informacoes_adicionais ?? '',
  };
}

const GRUPO_VALIDACAO_LABELS: Record<string, string> = {
  cliente: 'Cliente',
  emitente: 'Emitente',
  itens: 'Itens',
  fiscal: 'Fiscal',
  valores: 'Valores',
  estoque: 'Estoque',
  transporte: 'Transporte',
  origem: 'Origem',
};

function isNfeRascunho(status: string | undefined): boolean {
  return (status || '').trim().toUpperCase() === 'RASCUNHO';
}

function badgeProntidao(
  prontidao: ValidacaoNFeSaidaResponse['status_prontidao'] | undefined,
): { label: string; className: string } | null {
  if (!prontidao) return null;
  switch (prontidao) {
    case 'PRONTA':
      return { label: 'Pronta para emissão', className: 'erp-badge-success' };
    case 'COM_PENDENCIAS':
      return { label: 'Com pendências', className: 'erp-badge-danger' };
    case 'COM_ALERTAS':
      return { label: 'Com alertas', className: 'erp-badge-warning' };
    case 'BLOQUEADA':
      return { label: 'Bloqueada', className: 'erp-badge-danger' };
    default:
      return { label: prontidao, className: 'erp-badge-warning' };
  }
}

const NFeSaida = () => {
  const [searchParams] = useSearchParams();
  const statusEmissaoUrl = searchParams.get('status_emissao') || searchParams.get('status') || '';
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
    loading: listLoading,
    error: listError,
    reload: load,
  } = usePaginatedList<NFeSaidaListItem>({
    fetchPage: nfeSaidasService.listPaginated,
    initialFilters: statusEmissaoUrl ? { status_emissao: statusEmissaoUrl } : {},
  });
  const [detalheNfeId, setDetalheNfeId] = useState<number | null>(null);
  const [detalheOpen, setDetalheOpen] = useState(false);
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [checklistNfeId, setChecklistNfeId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<NFeSaida | null>(null);
  const [form, setForm] = useState<NFeSaidaFormState>(buildFormFromNfe(null));
  const [itens, setItens] = useState<ItemNFe[]>([]);
  const [emitida, setEmitida] = useState(false);
  const [titulosGerados, setTitulosGerados] = useState<NFeSaida['titulos_receber']>([]);
  const [validacao, setValidacao] = useState<ValidacaoNFeSaidaResponse | null>(null);
  const [validacaoLoading, setValidacaoLoading] = useState(false);
  const [validacaoError, setValidacaoError] = useState<string | null>(null);
  const [xmlModalOpen, setXmlModalOpen] = useState(false);
  const [xmlPreview, setXmlPreview] = useState<NFeSaidaPreviewXmlResponse | null>(null);
  const [xmlLoading, setXmlLoading] = useState(false);
  const [danfeLoading, setDanfeLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);

  useEffect(() => {
    if (statusEmissaoUrl) setFilter('status_emissao', statusEmissaoUrl);
  }, [statusEmissaoUrl, setFilter]);

  useEffect(() => {
    if (!modalOpen) return;
    void transportadorasService.getAll().then(setTransportadoras).catch(() => setTransportadoras([]));
  }, [modalOpen]);

  const nfeDeepLink = searchParams.get('nfe');
  useEffect(() => {
    if (!nfeDeepLink) return;
    const id = Number(nfeDeepLink);
    if (!id) return;
    const abrir = (e: NFeSaida) => {
      setEditing(e);
      setEmitida(false);
      setTitulosGerados(e.titulos_receber ?? []);
      setForm(buildFormFromNfe(e));
      setItens(e.itens ?? []);
      setValidacao(null);
      setValidacaoError(null);
      setModalOpen(true);
    };
    void nfeSaidasService.getById(id).then(abrir).catch(() => undefined);
  }, [nfeDeepLink]);

  const itensEditaveis = nfeItensComerciaisEditaveis(editing, form.status);
  const complementosEditaveis = nfeDadosComplementaresEditaveis(editing, form.status);
  const origemComercial = Boolean(
    editing?.origem_comercial_travada ?? editing?.faturamento_pedido_venda_id ?? editing?.pedido_venda_id,
  );

  const addItem = () => {
    if (!itensEditaveis) return;
    setItens((p) => [
      ...p,
      { id: Date.now(), produto_id: 0, produto_nome: '', quantidade: 1, valor: 0 },
    ]);
  };
  const removeItem = (id: number) => {
    if (!itensEditaveis) return;
    setItens((p) => p.filter((i) => i.id !== id));
  };
  const total = itens.reduce((s, i) => s + Number(i.quantidade) * Number(i.valor), 0);

  const openNew = () => {
    setEditing(null);
    setEmitida(false);
    setTitulosGerados([]);
    setValidacao(null);
    setValidacaoError(null);
    setXmlPreview(null);
    setPreviewError(null);
    setSaveError(null);
    setForm(buildFormFromNfe(null));
    setItens([]);
    setModalOpen(true);
  };
  const openEdit = async (row: NFeSaidaListItem | NFeSaida) => {
    const e = 'itens' in row && row.itens ? (row as NFeSaida) : await nfeSaidasService.getById(row.id);
    setEditing(e);
    setEmitida(false);
    setTitulosGerados(e.titulos_receber ?? []);
    setValidacao(null);
    setValidacaoError(null);
    setXmlPreview(null);
    setPreviewError(null);
    setSaveError(null);
    setForm(buildFormFromNfe(e));
    setItens(e.itens ?? []);
    setModalOpen(true);
  };

  const openDetalhe = (id: number) => {
    setDetalheNfeId(id);
    setDetalheOpen(true);
  };

  const openChecklist = (id: number) => {
    setChecklistNfeId(id);
    setChecklistOpen(true);
  };

  const previewDanfeLinha = async (row: NFeSaida) => {
    try {
      const sefaz = row.status_emissao_sefaz || row.resumo_emissao_sefaz?.status_emissao_sefaz;
      const autorizada =
        sefaz === 'AUTORIZADA_PRODUCAO' ||
        sefaz === 'AUTORIZADA_HOMOLOGACAO' ||
        row.status === 'AUTORIZADA_PRODUCAO' ||
        row.status === 'AUTORIZADA_HOMOLOGACAO';
      const blob = autorizada
        ? (await nfeSaidasService.danfeAutorizadoBlob(row.id)).blob
        : (await nfeSaidasService.previewDanfeBlob(row.id)).blob;
      openBlobInNewTab(blob);
    } catch (err) {
      alert(apiErrorMessage(err, { fallback: 'Não foi possível visualizar o DANFE.' }));
    }
  };

  const previewXmlLinha = async (id: number) => {
    try {
      const data = await nfeSaidasService.previewXmlPreliminar(id);
      const blob = new Blob([data.xml || ''], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nfe-${id}-preliminar.xml`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      alert(apiErrorMessage(err, { fallback: 'Não foi possível baixar o XML.' }));
    }
  };

  const handleValidarEmissao = async () => {
    if (!editing?.id) return;
    setValidacaoLoading(true);
    setValidacaoError(null);
    try {
      setValidacao(await nfeSaidasService.validarEmissao(editing.id));
    } catch (err) {
      setValidacao(null);
      setValidacaoError(apiErrorMessage(err));
    } finally {
      setValidacaoLoading(false);
    }
  };

  const handlePreviewXml = async () => {
    if (!editing?.id) return;
    setXmlLoading(true);
    setPreviewError(null);
    try {
      const data = await nfeSaidasService.previewXml(editing.id);
      setXmlPreview(data);
      setXmlModalOpen(true);
      if (data.status_prontidao === 'COM_PENDENCIAS') {
        setPreviewError('Prévia gerada com pendências. Corrija antes da emissão definitiva.');
      }
    } catch (err) {
      setPreviewError(apiErrorMessage(err));
    } finally {
      setXmlLoading(false);
    }
  };

  const handlePreviewDanfe = async () => {
    if (!editing?.id) return;
    setDanfeLoading(true);
    setPreviewError(null);
    try {
      const { blob } = await nfeSaidasService.previewDanfeBlob(editing.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setPreviewError(apiErrorMessage(err));
    } finally {
      setDanfeLoading(false);
    }
  };

  const copyXmlPreview = async () => {
    if (!xmlPreview?.xml) return;
    try {
      await navigator.clipboard.writeText(xmlPreview.xml);
    } catch {
      setPreviewError('Não foi possível copiar o XML para a área de transferência.');
    }
  };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await nfeSaidasService.delete(id); void load(); } };
  const handleSave = async () => {
    if (nfeSalvarFormularioBloqueado(form.status)) {
      setSaveError(
        'NF-e já autorizada ou cancelada. Use o painel de efeitos internos; alterações pelo formulário não são permitidas.',
      );
      return;
    }
    setSaveLoading(true);
    setSaveError(null);
    const statusSave = isNfeRascunho(form.status) ? 'RASCUNHO' : form.status;
    const incluirItens = itensEditaveis && isNfeRascunho(statusSave);
    const data: Partial<NFeSaida> = {
      numero: form.numero,
      data: form.data,
      status: statusSave,
      modo_atendimento_estoque: form.modo_atendimento_estoque,
    };
    if (incluirItens) {
      data.itens = itens;
      data.valor_total = total;
    }
    if (complementosEditaveis) {
      data.transportadora_id = form.transportadora_id;
      data.modalidade_frete = form.modalidade_frete;
      data.valor_frete = form.valor_frete;
      data.quantidade_volumes = form.quantidade_volumes;
      data.peso_bruto = form.peso_bruto;
      data.peso_liquido = form.peso_liquido;
      data.observacoes_nfe = form.observacoes_nfe;
      data.informacoes_adicionais = form.informacoes_adicionais;
    }
    if (!nfeClienteBloqueado(editing)) {
      if (form.cliente_id) data.cliente_id = form.cliente_id;
    }
    if (form.pedido_venda_id) data.pedido_venda_id = form.pedido_venda_id;
    try {
      const saved = editing
        ? await nfeSaidasService.update(editing.id, data)
        : await nfeSaidasService.create(data as Omit<NFeSaida, 'id'>);
      setTitulosGerados(saved.titulos_receber ?? []);
      setEmitida(true);
      setTimeout(() => {
        setModalOpen(false);
        load();
      }, 2000);
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setSaveLoading(false);
    }
  };

  if (modalOpen && editing?.id) {
    return (
      <div>
        <PageHeader
          title="NF-e Saída"
          description="Emissão, conferência e acompanhamento de notas fiscais de saída."
          onAdd={openNew}
          addLabel="Nova NF-e"
          searchValue={search}
          onSearch={setSearch}
        />
        <NFeSaidaConferenciaModal
          nfeId={editing.id}
          onClose={() => setModalOpen(false)}
          onSaved={() => {
          /* Lista atualizada apenas após validação/marcar pronta via aplicarRespostaProntidao */
        }}
        />
      </div>
    );
  }

  const clienteBloqueado = nfeClienteBloqueado(editing);
  const podeSalvarRascunho =
    !nfeSalvarFormularioBloqueado(form.status) &&
    (complementosEditaveis || itensEditaveis || !editing);

  return (
    <div>
      <PageHeader
        title="NF-e Saída"
        description="Emissão e gestão de NF-e de saída. Notas em homologação são teste, sem valor fiscal e fora da apuração."
        onAdd={openNew}
        addLabel="Nova NF-e"
        searchValue={search}
        onSearch={setSearch}
      />
      <FilterBar
        filters={[
          {
            key: 'ambiente',
            label: 'Ambiente',
            value: filters.ambiente || '',
            options: [
              { value: 'homologacao', label: 'Homologação' },
              { value: 'producao', label: 'Produção' },
            ],
          },
          {
            key: 'status_emissao',
            label: 'Status fiscal',
            value: filters.status_emissao || '',
            options: [
              { value: 'RASCUNHO', label: 'Rascunho' },
              { value: 'PRONTA_PARA_EMISSAO', label: 'Pronta' },
              { value: 'AUTORIZADA_HOMOLOGACAO', label: 'Autorizada homologação' },
              { value: 'REJEITADA_HOMOLOGACAO', label: 'Rejeitada homologação' },
              { value: 'ERRO_TRANSMISSAO', label: 'Erro transmissão' },
            ],
          },
          {
            key: 'tem_duplicatas',
            label: 'Duplicatas',
            value: filters.tem_duplicatas || '',
            options: [{ value: 'true', label: 'Com duplicatas' }],
          },
          {
            key: 'reforma_tributaria_status',
            label: 'Reforma Tributária',
            value: filters.reforma_tributaria_status || '',
            options: [
              { value: 'nao_aplicavel', label: 'Não aplicada' },
              { value: 'nao_preparada', label: 'Pesquisa/preparação' },
              { value: 'preparacao', label: 'Preparação' },
              { value: 'configurada_sem_xml', label: 'Configurada sem XML' },
              { value: 'homologacao', label: 'Homologação' },
              { value: 'bloqueada_producao', label: 'Produção bloqueada' },
            ],
          },
        ]}
        onChange={setFilter}
      />
      {listError ? <ErrorState onRetry={() => void load()} /> : null}
      <div className="erp-card overflow-x-auto">
        {listLoading ? <LoadingState /> : null}
        {!listLoading && !listError ? (
        <table className="erp-table">
          <thead>
            <tr>
              <th>NF-e</th>
              <th>Cliente</th>
              <th>Emissão</th>
              <th>Fiscal</th>
              <th>Atendimento</th>
              <th>Valor</th>
              <th className="w-36">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState message="Nenhuma NF-e encontrada." />
                </td>
              </tr>
            ) : (
              items.map((e) => {
                const resumo = e.listagem_resumo;
                const fiscal = getNfeFiscalSummaryBadge(resumo, e);
                const atend = getNfeOperationalSummaryBadges(resumo);
                const titulo = formatNfeTituloListagem(e);
                const subtitulo = formatNfeSubtituloListagem(e);
                return (
                  <tr key={e.id}>
                    <td className="font-medium max-w-[16rem]">
                      <div title={e.numero !== titulo ? e.numero : undefined}>{titulo}</div>
                      {subtitulo ? (
                        <p className="text-xs text-muted-foreground font-normal mt-0.5">{subtitulo}</p>
                      ) : null}
                    </td>
                    <td>{e.cliente_nome}</td>
                    <td className="whitespace-nowrap">{formatDateBr(e.data)}</td>
                    <td>
                      <div className="flex flex-col gap-0.5 items-start max-w-[14rem]">
                        {fiscal.hasData ? (
                          <>
                            <span className={fiscal.className}>{fiscal.label}</span>
                            {fiscal.subtexto ? (
                              <span className="text-xs text-muted-foreground leading-snug">{fiscal.subtexto}</span>
                            ) : null}
                          </>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1 items-center max-w-[12rem]">
                        {atend.badges.length === 0 ? (
                          <span className="text-xs text-muted-foreground">{atend.vazioLabel}</span>
                        ) : (
                          atend.badges.map((b) => (
                            <span
                              key={b.label}
                              className={`${atendimentoResumoBadgeClass(b.variant)} text-[10px] px-1.5 py-0`}
                            >
                              {b.label}
                            </span>
                          ))
                        )}
                        {atend.ocultos > 0 ? (
                          <span className="text-xs text-muted-foreground font-medium" title="Badges adicionais">
                            +{atend.ocultos}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="whitespace-nowrap">{formatNfeValorListagem(e.valor_total)}</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-xs"
                          onClick={() => openDetalhe(e.id)}
                          title="Ver detalhes da NF-e"
                          aria-label="Ver detalhes da NF-e"
                        >
                          <Eye className="h-3.5 w-3.5 mr-0.5" />
                          Detalhes
                        </button>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-xs"
                          onClick={() => openChecklist(e.id)}
                          title="Validar pré-homologação"
                          aria-label="Validar pré-homologação"
                        >
                          <ClipboardCheck className="h-3.5 w-3.5 mr-0.5" />
                          Validar
                        </button>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm p-1"
                          title="Visualizar DANFE"
                          aria-label="Visualizar DANFE"
                          onClick={() => void previewDanfeLinha(e)}
                        >
                          <FileText className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm p-1"
                          title="Baixar XML"
                          aria-label="Baixar XML"
                          onClick={() => void previewXmlLinha(e.id)}
                        >
                          <FileCode className="h-4 w-4" />
                        </button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="erp-btn-ghost erp-btn-sm p-1"
                              title="Mais ações"
                              aria-label="Mais ações"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem className="cursor-pointer" onSelect={() => void openEdit(e)}>
                              <Pencil className="h-3.5 w-3.5 mr-2" />
                              Abrir NF-e
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="cursor-pointer text-destructive focus:text-destructive"
                              onSelect={() => void handleDelete(e.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5 mr-2" />
                              Excluir
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
        </table>
        ) : null}
        {!listLoading && !listError && count > 0 ? (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            count={count}
            totalPages={totalPages}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        ) : null}
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar NF-e Saída' : 'Nova NF-e Saída'} size="xl">
        {emitida ? (
          <div className="text-center py-8">
            <CheckCircle className="h-16 w-16 text-success mx-auto mb-4" />
            <h3 className="text-xl font-bold text-foreground">NF-e emitida com sucesso!</h3>
            <p className="text-muted-foreground mt-2">Documento fiscal gerado.</p>
            {titulosGerados && titulosGerados.length > 0 && (
              <p className="text-sm text-muted-foreground mt-1">
                {titulosGerados.length} título(s) financeiro(s) gerado(s) para contas a receber.
              </p>
            )}
          </div>
        ) : (
          <>
            {editing?.pedido_venda_id || editing?.faturamento_pedido_venda_id ? (
              <div className="mb-4 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm">
                <span className="font-medium">Origem: </span>
                {editing.pedido_venda_numero || editing.pedido_venda_id ? (
                  <span>Pedido de venda {editing.pedido_venda_numero || `#${editing.pedido_venda_id}`}</span>
                ) : null}
                {editing.faturamento_pedido_venda_id ? (
                  <span className="text-muted-foreground">
                    {editing.pedido_venda_id ? ' · ' : ''}
                    Faturamento #{editing.faturamento_pedido_venda_id}
                  </span>
                ) : null}
                {editing.observacao_origem ? (
                  <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{editing.observacao_origem}</p>
                ) : null}
              </div>
            ) : null}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
              <div>
                <label className="erp-label">Cliente</label>
                {clienteBloqueado ? (
                  <>
                    <p className="erp-input mt-1 bg-muted/40 text-sm">{form.cliente_nome || '—'}</p>
                    <p className="text-xs text-muted-foreground mt-1">Cliente herdado do pedido/faturamento.</p>
                  </>
                ) : (
                  <input
                    type="number"
                    className="erp-input mt-1"
                    placeholder="ID do cliente cadastrado"
                    value={form.cliente_id ?? ''}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        cliente_id: e.target.value ? Number(e.target.value) : null,
                      }))
                    }
                  />
                )}
              </div>
              <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
              <div>
                <label className="erp-label">Pedido de Venda</label>
                <input
                  className="erp-input mt-1 bg-muted/30"
                  readOnly={clienteBloqueado}
                  placeholder="PV-001"
                  value={editing?.pedido_venda_numero ?? form.pedido_venda_id ?? ''}
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="erp-label">Modo de atendimento de estoque</label>
              <select
                className="erp-select mt-1 w-full max-w-xl"
                value={form.modo_atendimento_estoque}
                disabled={origemComercial}
                onChange={e => setForm(p => ({ ...p, modo_atendimento_estoque: e.target.value as 'IMEDIATO' | 'ANTECIPADO' }))}
              >
                <option value="IMEDIATO">Imediato — baixa estoque agora</option>
                <option value="ANTECIPADO">Antecipado — cria pendência sem baixar estoque</option>
              </select>
              {form.modo_atendimento_estoque === 'ANTECIPADO' && (
                <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
                  Neste modo, a NF será registrada sem baixa física de estoque. Será criado atendimento pendente.
                </p>
              )}
            </div>
            {origemComercial ? (
              <p className="text-sm text-amber-800 dark:text-amber-200 mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                Itens herdados do faturamento. Para corrigir produtos, quantidades ou valores, cancele/estorne a NF-e e
                gere novo faturamento.
              </p>
            ) : null}
            <div className="border border-border rounded-md p-3">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-medium text-sm">Itens</h3>
                {itensEditaveis ? (
                  <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm">
                    <Plus className="h-3 w-3" /> Item
                  </button>
                ) : null}
              </div>
              {itens.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">Nenhum item.</p>
              ) : (
                itens.map((item, idx) => (
                  <div key={item.id} className="grid grid-cols-5 gap-2 mb-2 items-end">
                    <div className="col-span-2">
                      <label className="text-xs text-muted-foreground">Produto</label>
                      <p className="erp-input h-8 text-sm flex items-center bg-muted/30 truncate">
                        {item.produto_nome || (item.produto_id ? `Produto #${item.produto_id}` : '—')}
                      </p>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Qtd</label>
                      <input
                        type="number"
                        className="erp-input h-8 text-sm"
                        readOnly={!itensEditaveis}
                        value={item.quantidade}
                        onChange={(e) => {
                          const n = [...itens];
                          n[idx] = { ...n[idx], quantidade: +e.target.value };
                          setItens(n);
                        }}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Valor un.</label>
                      <input
                        type="number"
                        step="0.01"
                        className="erp-input h-8 text-sm"
                        readOnly={!itensEditaveis}
                        value={item.valor}
                        onChange={(e) => {
                          const n = [...itens];
                          n[idx] = { ...n[idx], valor: +e.target.value };
                          setItens(n);
                        }}
                      />
                    </div>
                    <div className="flex items-end gap-1">
                      <div className="flex-1">
                        <label className="text-xs text-muted-foreground">Corrida</label>
                        <p className="erp-input h-8 text-sm bg-muted/30 truncate">
                          {item.corrida_numero || (item.corrida_id ? `#${item.corrida_id}` : '—')}
                        </p>
                      </div>
                      {itensEditaveis ? (
                        <button
                          type="button"
                          onClick={() => removeItem(item.id)}
                          className="erp-btn-ghost erp-btn-sm text-destructive h-8"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))
              )}
              <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total: R$ {total.toFixed(2)}</div>
            </div>
            {complementosEditaveis || editing?.transportadora_id || form.observacoes_nfe ? (
              <div className="mt-4 border border-border rounded-md p-3 space-y-3">
                <h3 className="font-medium text-sm">Transporte e dados complementares</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="erp-label">Modalidade do frete</label>
                    <select
                      className="erp-select mt-1 w-full"
                      disabled={!complementosEditaveis}
                      value={form.modalidade_frete}
                      onChange={(e) => setForm((p) => ({ ...p, modalidade_frete: e.target.value }))}
                    >
                      <option value="9">Sem frete</option>
                      <option value="0">Por conta do emitente (CIF)</option>
                      <option value="1">Por conta do destinatário (FOB)</option>
                      <option value="2">Por conta de terceiros</option>
                    </select>
                  </div>
                  <div>
                    <label className="erp-label">Transportadora</label>
                    <select
                      className="erp-select mt-1 w-full"
                      disabled={!complementosEditaveis}
                      value={form.transportadora_id ?? ''}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          transportadora_id: e.target.value ? Number(e.target.value) : null,
                        }))
                      }
                    >
                      <option value="">—</option>
                      {transportadoras.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.razao_social}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="erp-label">Valor do frete (R$)</label>
                    <input
                      type="number"
                      step="0.01"
                      className="erp-input mt-1"
                      readOnly={!complementosEditaveis}
                      value={form.valor_frete}
                      onChange={(e) => setForm((p) => ({ ...p, valor_frete: +e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="erp-label">Volumes</label>
                    <input
                      type="number"
                      className="erp-input mt-1"
                      readOnly={!complementosEditaveis}
                      value={form.quantidade_volumes}
                      onChange={(e) => setForm((p) => ({ ...p, quantidade_volumes: +e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="erp-label">Peso bruto (kg)</label>
                    <input
                      type="number"
                      step="0.001"
                      className="erp-input mt-1"
                      readOnly={!complementosEditaveis}
                      value={form.peso_bruto}
                      onChange={(e) => setForm((p) => ({ ...p, peso_bruto: +e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="erp-label">Peso líquido (kg)</label>
                    <input
                      type="number"
                      step="0.001"
                      className="erp-input mt-1"
                      readOnly={!complementosEditaveis}
                      value={form.peso_liquido}
                      onChange={(e) => setForm((p) => ({ ...p, peso_liquido: +e.target.value }))}
                    />
                  </div>
                </div>
                <div>
                  <label className="erp-label">Observações da NF-e</label>
                  <textarea
                    className="erp-input mt-1 min-h-[72px] w-full"
                    readOnly={!complementosEditaveis}
                    value={form.observacoes_nfe}
                    onChange={(e) => setForm((p) => ({ ...p, observacoes_nfe: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="erp-label">Informações adicionais</label>
                  <textarea
                    className="erp-input mt-1 min-h-[72px] w-full"
                    readOnly={!complementosEditaveis}
                    value={form.informacoes_adicionais}
                    onChange={(e) => setForm((p) => ({ ...p, informacoes_adicionais: e.target.value }))}
                  />
                </div>
              </div>
            ) : null}
            {editing?.id ? (
              <div className="mt-4 border border-border rounded-md p-3">
                <NFeSaidaEfeitosPanel
                  nfeSaidaId={editing.id}
                  nfeNumero={form.numero || editing.numero}
                  nfeStatus={form.status || editing.status}
                  autoLoad
                  onNfeAtualizada={async () => {
                    const atual = await nfeSaidasService.getById(editing.id);
                    setEditing(atual);
                    setForm((f) => ({ ...f, status: atual.status }));
                    await load();
                  }}
                />
              </div>
            ) : null}
            {editing?.id && isNfeRascunho(form.status) ? (
              <div className="mt-4 border border-border rounded-md p-3 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-medium text-sm">Checklist de emissão</h3>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={validacaoLoading}
                      onClick={() => void handleValidarEmissao()}
                    >
                      {validacaoLoading ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />
                      ) : (
                        <ClipboardCheck className="h-3 w-3 mr-1 inline" />
                      )}
                      Validar emissão
                    </button>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={xmlLoading}
                      onClick={() => void handlePreviewXml()}
                    >
                      {xmlLoading ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />
                      ) : (
                        <FileCode className="h-3 w-3 mr-1 inline" />
                      )}
                      Prévia XML
                    </button>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={danfeLoading}
                      onClick={() => void handlePreviewDanfe()}
                    >
                      {danfeLoading ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1 inline" />
                      ) : (
                        <FileText className="h-3 w-3 mr-1 inline" />
                      )}
                      Ver DANFE
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2 max-w-2xl">
                    Documento de conferência com layout DANFE modelo 55. Ainda sem autorização SEFAZ, sem chave
                    oficial e sem valor fiscal.
                  </p>
                </div>
                {previewError ? (
                  <p className="text-sm text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                    {previewError}
                  </p>
                ) : null}
                {validacaoError ? (
                  <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                    {validacaoError}
                  </p>
                ) : null}
                {validacao ? (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      {badgeProntidao(validacao.status_prontidao) ? (
                        <span className={badgeProntidao(validacao.status_prontidao)!.className}>
                          {badgeProntidao(validacao.status_prontidao)!.label}
                        </span>
                      ) : null}
                      <span className="text-xs text-muted-foreground">
                        {validacao.total_pendencias} pendência(s) · {validacao.total_alertas} alerta(s)
                      </span>
                    </div>
                    {validacao.mensagens.map((msg) => (
                      <p key={msg} className="text-sm text-muted-foreground">
                        {msg}
                      </p>
                    ))}
                    {validacao.status_prontidao === 'PRONTA' ? (
                      <p className="text-sm text-emerald-800 dark:text-emerald-200 rounded-md bg-emerald-600/10 px-3 py-2">
                        Esta NF-e rascunho não possui pendências bloqueantes. A transmissão será implementada em
                        etapa posterior.
                      </p>
                    ) : null}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {(['pendencias', 'alertas'] as const).map((bloco) => {
                        const tipoFiltro = bloco === 'pendencias' ? 'PENDENCIA' : 'ALERTA';
                        const titulo = bloco === 'pendencias' ? 'Pendências' : 'Alertas';
                        const itensBloco = Object.entries(validacao.grupos).flatMap(([grupo, lista]) =>
                          (lista ?? [])
                            .filter((x) => x.tipo === tipoFiltro)
                            .map((x) => ({ ...x, grupo })),
                        );
                        if (!itensBloco.length) return null;
                        return (
                          <div
                            key={bloco}
                            className={`rounded-md border p-3 ${
                              bloco === 'pendencias' ? 'border-destructive/30 bg-destructive/5' : 'border-amber-500/30 bg-amber-500/5'
                            }`}
                          >
                            <h4 className="text-xs font-semibold uppercase tracking-wide mb-2">{titulo}</h4>
                            <ul className="space-y-1.5 text-sm">
                              {itensBloco.map((item, i) => (
                                <li key={`${item.codigo}-${item.item_id ?? i}`}>
                                  <span className="text-muted-foreground text-xs">
                                    {GRUPO_VALIDACAO_LABELS[item.grupo] ?? item.grupo}:
                                  </span>{' '}
                                  {item.mensagem}
                                </li>
                              ))}
                            </ul>
                          </div>
                        );
                      })}
                    </div>
                    {Object.entries(validacao.grupos).some(([, lista]) =>
                      (lista ?? []).some((x) => x.tipo === 'INFO'),
                    ) ? (
                      <details className="text-xs text-muted-foreground">
                        <summary className="cursor-pointer">Informações operacionais</summary>
                        <ul className="mt-2 space-y-1 pl-2">
                          {Object.entries(validacao.grupos).flatMap(([grupo, lista]) =>
                            (lista ?? [])
                              .filter((x) => x.tipo === 'INFO')
                              .map((x, i) => (
                                <li key={`${x.codigo}-${i}`}>
                                  [{GRUPO_VALIDACAO_LABELS[grupo] ?? grupo}] {x.mensagem}
                                </li>
                              )),
                          )}
                        </ul>
                      </details>
                    ) : null}
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Execute a validação para ver pendências e alertas antes da futura transmissão à SEFAZ.
                  </p>
                )}
              </div>
            ) : null}
            {titulosGerados && titulosGerados.length > 0 && (
              <div className="mt-4 border border-border rounded-md p-3">
                <h3 className="font-medium text-sm mb-2">Títulos financeiros gerados</h3>
                <div className="overflow-x-auto">
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>Parcela</th>
                        <th>Dias</th>
                        <th>Vencimento</th>
                        <th>Valor</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {titulosGerados.map((t) => (
                        <tr key={`${t.parcela}-${t.vencimento}`}>
                          <td>{t.parcela}</td>
                          <td>{t.dias}</td>
                          <td>{t.vencimento}</td>
                          <td>R$ {Number(t.valor).toFixed(2)}</td>
                          <td>{t.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {saveError ? (
              <p className="text-sm text-destructive mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                {saveError}
              </p>
            ) : null}
            <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
              <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
              {podeSalvarRascunho ? (
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  className="erp-btn-primary"
                  disabled={saveLoading}
                >
                  {saveLoading ? 'Salvando…' : isNfeRascunho(form.status) ? 'Salvar rascunho' : 'Emitir NF-e'}
                </button>
              ) : null}
            </div>
          </>
        )}
      </Modal>

      <Modal
        isOpen={xmlModalOpen}
        onClose={() => setXmlModalOpen(false)}
        title="Prévia XML — NF-e Saída"
        size="xl"
      >
        <p className="text-sm text-amber-800 dark:text-amber-200 mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          XML de prévia, sem autorização SEFAZ. Rascunho não autorizado. Não transmitir / sem protocolo.
        </p>
        {xmlPreview?.recomendacoes_aplicadas?.length ? (
          <p className="text-xs text-muted-foreground mb-2">
            Recomendações: {xmlPreview.recomendacoes_aplicadas.join(' · ')}
          </p>
        ) : null}
        <div className="flex justify-end mb-2">
          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => void copyXmlPreview()}>
            <Copy className="h-3 w-3 mr-1 inline" />
            Copiar XML
          </button>
        </div>
        <pre className="max-h-[28rem] overflow-auto text-xs bg-muted/30 border border-border rounded-md p-3 whitespace-pre-wrap break-all">
          {xmlPreview?.xml ?? ''}
        </pre>
      </Modal>

      <NFeChecklistHomologacaoModal
        open={checklistOpen}
        onClose={() => {
          setChecklistOpen(false);
          setChecklistNfeId(null);
        }}
        nfeSaidaId={checklistNfeId}
      />

      <NFeSaidaDetalheDrawer
        nfeId={detalheNfeId}
        open={detalheOpen}
        onClose={() => {
          setDetalheOpen(false);
          setDetalheNfeId(null);
        }}
        onOpenConferencia={(nfe) => {
          setDetalheOpen(false);
          setEditing(nfe);
          setModalOpen(true);
        }}
      />
    </div>
  );
};

export default NFeSaida;
