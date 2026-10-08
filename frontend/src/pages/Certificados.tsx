import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { FileText, Pencil } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import {
  certificadosQualidadeService,
  type NfeElegivelCqOpcao,
} from '@/services/api/qualidade';
import {
  certificadosFornecedorService,
  corridaLoteEfetivosResultadoFornecedor,
  mensagemPrincipalBuscaDadosTecnicosFornecedor,
} from '@/services/api/certificadosFornecedor';
import { produtosService } from '@/services/api/produtos';
import { nfeHistoricaImportadaService, type NFeSaidaHistoricaList } from '@/services/api/nfeHistoricaImportada';
import { apiErrorMessage, getApiErrorStatus } from '@/services/api/config';
import {
  certificadoFornecedorStatusBadge,
  itemCqTemOrigemDocumental,
  origemFisicaCqBadge,
  origemFisicaCqDescricao,
  origemFisicaCqItem,
  origemFisicaCqResumo,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';
import { mesclarMensagensUnicas } from '@/lib/cqMensagensUi';
import {
  TITULO_MODAL_CORRIDAS_CF_CQ,
  aplicacaoSubstituiTecnicosDoItemAtual,
  aplicarDistribuicaoCorridasCfCq,
  quantidadeTotalDistribuicaoCorridasCfCq,
  selecoesExistentesCorridasCfCq,
  type CorridasCfParaCqResponse,
  type SelecaoCorridaCfCq,
  baseItemIrmao,
} from '@/lib/cqCorridasCfUi';
import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';
import type {
  CertificadoQualidade,
  CertificadoQualidadeStatus,
  CorridaDisponivelCertificadoQualidade,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoQualidade,
  Produto,
  ResumoRastreabilidadeCertificadoQualidade,
} from '@/types';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import type { ListQueryParams } from '@/lib/apiList';
import {
  TEXTO_PADRAO,
  COMPOSICAO_FIELDS,
  TRACAO_FIELDS,
  IMPACTO_FIELDS,
  COMPONENTES_PADRAO,
  MOTIVOS_NAO_INCLUSAO,
  CONFIRMAR_CANCELAMENTO_CERTIFICADO_QUALIDADE,
  AVISO_SEM_CF_MANUAL,
  LABEL_OBRIGATORIO_EMITIR,
  emptyForm,
  ensureMap,
  normalizeCorridaLoteBusca,
  coerceProdutoItemId,
  resolverCorridaLoteBuscaFornecedor,
  itemTemDadosTecnicosPreenchidos,
  fornecedorResultadoSemProdutoVinculado,
  normNumeric,
  parseBlockValues,
  ensureComp,
} from '@/lib/certificadoQualidadeConstants';

/**
 * Fase E.4 (Qualidade): o backend aplica permissões Django; o JWT não expõe codenames.
 * Não escondemos add/change/delete com base em suposições — só ocultamos «Novo» quando
 * o GET da lista retorna 403 (sem `view_*` para a coleção). Demais ações mostram
 * mensagem amigável via `apiErrorMessage` / 403. Evolução: endpoint tipo /me/permissions.
 */

const Certificados = () => {
  const navigate = useNavigate();
  const [listForbidden, setListForbidden] = useState(false);
  const fetchCertificadosPage = useCallback(async (params: ListQueryParams) => {
    try {
      const result = await certificadosQualidadeService.listPaginated(params);
      setListForbidden(false);
      return result;
    } catch (e) {
      if ((e as AxiosError).response?.status === 403) setListForbidden(true);
      throw e;
    }
  }, []);
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
    loading: listLoading,
    error: listError,
    reload: reloadList,
  } = usePaginatedList<CertificadoQualidade>({ fetchPage: fetchCertificadosPage });
  const [pdfBusy, setPdfBusy] = useState<PdfBusy>(null);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [previewPdfTitulo, setPreviewPdfTitulo] = useState('Prévia PDF');
  useEffect(() => {
    nfeHistoricaImportadaService.list().then((r) => setNfHistoricas(r)).catch(() => setNfHistoricas([]));
  }, []);

  const isRowPdfLoading = (id: number) => pdfBusy?.kind === 'table-row' && pdfBusy.id === id;
  const isRowPdfBlocked = (id: number) =>
    pdfBusy !== null && (pdfBusy.kind === 'modal' || (pdfBusy.kind === 'table-row' && pdfBusy.id !== id));
  const openNew = () => {
    navigate('/certificados-qualidade/novo');
  };
  const openEdit = (c: CertificadoQualidade) => {
    navigate(`/certificados-qualidade/${c.id}`);
  };

  const visualizarOuBaixarPdf = async (
    id: number,
    preview = false,
    forcarDownload = false,
    meta?: { numero?: string; cliente?: string; nf?: string },
    busy: PdfBusy = { kind: 'modal' },
  ) => {
    setPdfBusy(busy);
    setSaveError(null);
    try {
      if (forcarDownload) await certificadosQualidadeService.baixarPdf(id, preview, meta);
      else await certificadosQualidadeService.visualizarPdf(id, preview, meta);
    } catch (e) {
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível gerar o PDF. Verifique se o certificado foi salvo como rascunho.' }));
    } finally {
      setPdfBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Certificados de Qualidade"
        description="Emissão e acompanhamento de certificados de qualidade vinculados a produtos, lotes e clientes."
        onAdd={listForbidden ? undefined : openNew}
        addLabel="Novo certificado"
        searchValue={search}
        onSearch={setSearch}
        searchPlaceholder="Digite parte do número do certificado."
      />
      {listError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {listLoading ? <TableSkeleton rows={6} cols={6} /> : null}
      {!listLoading && !listError ? (
        <DataTableShell>
        <DataTable className="text-sm" mobileMode="cards">
          <thead>
            <tr>
              <th className="whitespace-nowrap">Número</th>
              <th>Cliente</th>
              <th className="whitespace-nowrap">NF</th>
              <th className="whitespace-nowrap">Data</th>
              <th className="whitespace-nowrap">Status</th>
              <th className="w-44 text-right whitespace-nowrap">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    message="Nenhum certificado de qualidade encontrado."
                    actionLabel={listForbidden ? undefined : 'Novo certificado'}
                    onAction={listForbidden ? undefined : openNew}
                  />
                </td>
              </tr>
            ) : (
              items.map((c) => {
                const pdfEhPrevia = c.status === 'rascunho';
                return (
                  <tr key={c.id}>
                    <td className="font-mono whitespace-nowrap">{c.numero_formatado}</td>
                    <td>{c.cliente_nome_snapshot || '—'}</td>
                    <td>{c.nota_fiscal_numero || '—'}</td>
                    <td>{c.data_emissao || '—'}</td>
                    <td>
                      <div className="flex flex-col gap-1 items-start">
                        <StatusBadge status={c.status || 'pendente'} />
                        {c.status !== 'cancelado' && c.rastreabilidade_resumo_label ? (
                          <span
                            className={`${rastreabilidadeCqBadge(
                              c.resumo_rastreabilidade?.pode_emitir
                                ? 'COMPLETA'
                                : (c.resumo_rastreabilidade?.pendentes ?? 0) > 0
                                  ? 'PENDENTE'
                                  : 'PARCIAL',
                            ).className} text-[10px]`}
                          >
                            {c.rastreabilidade_resumo_label}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-end gap-1">
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm"
                          onClick={() => openEdit(c)}
                          disabled={c.status === 'cancelado'}
                          title={c.status === 'cancelado' ? 'Certificado cancelado: use apenas visualizar ou baixar o PDF para consulta.' : 'Editar certificado'}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          onClick={() => void visualizarOuBaixarPdf(c.id, pdfEhPrevia, false, {
                            numero: c.numero_formatado || c.numero,
                            cliente: c.cliente_nome_snapshot,
                            nf: c.nota_fiscal_numero,
                          }, { kind: 'table-row', id: c.id })}
                          disabled={isRowPdfBlocked(c.id)}
                          title={
                            c.status === 'cancelado'
                              ? 'Abrir PDF do certificado cancelado (marca CANCELADO no documento).'
                              : pdfEhPrevia
                                ? 'Pré-visualizar PDF do rascunho.'
                                : 'Abrir PDF emitido.'
                          }
                        >
                          <FileText className="h-4 w-4 mr-1" />
                          {isRowPdfLoading(c.id) ? 'Gerando…' : c.status === 'cancelado' ? 'Ver PDF' : pdfEhPrevia ? 'Prévia' : 'Ver PDF'}
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          onClick={() => void visualizarOuBaixarPdf(c.id, pdfEhPrevia, true, {
                            numero: c.numero_formatado || c.numero,
                            cliente: c.cliente_nome_snapshot,
                            nf: c.nota_fiscal_numero,
                          }, { kind: 'table-row', id: c.id })}
                          disabled={isRowPdfBlocked(c.id)}
                          title={
                            c.status === 'cancelado'
                              ? 'Baixar PDF do certificado cancelado (marca CANCELADO).'
                              : 'Baixar PDF.'
                          }
                        >
                          {isRowPdfLoading(c.id) ? '…' : 'Baixar'}
                        </button>
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


      <Modal
        isOpen={Boolean(previewPdfUrl)}
        onClose={() => {
          if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
          setPreviewPdfUrl(null);
        }}
        title={previewPdfTitulo}
        size="xl"
      >
        {previewPdfUrl ? (
          <div className="h-[78vh]">
            <iframe title="Prévia PDF do certificado" src={previewPdfUrl} className="w-full h-full border border-border rounded" />
          </div>
        ) : null}
      </Modal>



    </div>
  );
};

export default Certificados;
