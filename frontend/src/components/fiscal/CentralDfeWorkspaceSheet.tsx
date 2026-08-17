import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { ManifestacaoEventoForm } from '@/components/fiscal/ManifestacaoDestinatarioModals';
import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { NFeEntradaFinanceiroAcoes } from '@/components/fiscal/NFeEntradaFinanceiroAcoes';
import { GerarContasPagarNfeEntradaModal } from '@/components/fiscal/GerarContasPagarNfeEntradaModal';
import { NFeEntradaReabrirModal } from '@/components/fiscal/NFeEntradaReabrirModal';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import {
  abaInicialCteWorkspace,
  resolverConteudoWorkspace,
  resolverCteHistoricoId,
  resolverNfHistoricaId,
} from '@/lib/centralDfeWorkspaceUi';
import {
  badgeStatusEstadoConsolidado,
  resolverEstadoConsolidadoExibicao,
  textosAlertaEstadoConsolidado,
} from '@/lib/inboxFiscalUi';
import {
  LABEL_IMPORTAR_XML_NFE,
  TOOLTIP_IMPORTAR_XML_NFE,
  isCteTransportadora,
  isNfeFornecedor,
  labelAbrirBaseImportada,
  rotaAbrirBaseImportada,
} from '@/lib/centralDfeUi';
import {
  statusManifestacaoExibicao,
  statusXmlExibicao,
} from '@/lib/manifestacaoDestinatarioUi';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import type {
  EventoManifestacaoDestinatario,
  NFeDestinadaDocumento,
} from '@/services/api/manifestacaoDestinatario';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import {formatMoneyBRL} from '@/lib/numberFields';
import {
  labelStatusConferenciaCabecalho,
  labelStatusEntradaNfeConferenciaFinalizada,
} from '@/lib/conferenciaNfeLabels';

const fmtData = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = v.slice(0, 10);
  const [y, m, day] = d.split('-');
  if (!y || !m || !day) return v;
  return `${day}/${m}/${y}`;
};

const fmtMoney = (v: string | number | null | undefined): string => {
  const n = Number(String(v ?? '0').replace(',', '.'));
  return `formatMoneyBRL(n)`;
};

const fmtCnpj = (cnpj: string): string => {
  const d = (cnpj || '').replace(/\D/g, '');
  if (d.length !== 14) return cnpj || '—';
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

export type CentralDfeWorkspaceSheetProps = {
  open: boolean;
  row: CentralDfeDocumento | null;
  manifestacao: NFeDestinadaDocumento | null;
  somenteResumo: boolean;
  loadingAcao: boolean;
  onClose: () => void;
  onUpdated: () => Promise<void>;
  onPrepararManifestacao: () => Promise<NFeDestinadaDocumento | null>;
  onExecutarManifestacao: (
    evento: EventoManifestacaoDestinatario,
    justificativa: string,
  ) => Promise<void>;
  onIniciarArmazenarXmlNfe: () => void;
  onIniciarArmazenarXmlCte: () => void;
};

export function CentralDfeWorkspaceSheet({
  open,
  row,
  manifestacao,
  somenteResumo,
  loadingAcao,
  onClose,
  onUpdated,
  onPrepararManifestacao,
  onExecutarManifestacao,
  onIniciarArmazenarXmlNfe,
  onIniciarArmazenarXmlCte,
}: CentralDfeWorkspaceSheetProps) {
  const [manifestDoc, setManifestDoc] = useState<NFeDestinadaDocumento | null>(null);
  const [preparandoManifest, setPreparandoManifest] = useState(false);
  const [forcarConferencia, setForcarConferencia] = useState(false);
  const [resumoConferencia, setResumoConferencia] = useState<{
    status: string;
    estoque_aplicado_em: string | null;
    financeiro?: {
      financeiro_gerado?: boolean;
      pode_gerar_contas_pagar?: boolean;
      contas_pagar_vinculadas?: Array<{ id: number; numero: string }>;
    };
  } | null>(null);
  const [carregandoResumo, setCarregandoResumo] = useState(false);
  const [gerarCpOpen, setGerarCpOpen] = useState(false);
  const [reabrirOpen, setReabrirOpen] = useState(false);

  const estadoInbox = useMemo(
    () => (row ? resolverEstadoConsolidadoExibicao(row, manifestacao) : null),
    [row, manifestacao],
  );

  const alertasEstado = useMemo(
    () => (estadoInbox ? textosAlertaEstadoConsolidado(estadoInbox) : []),
    [estadoInbox],
  );

  const nfHistoricaId = row ? resolverNfHistoricaId(row, manifestacao) : null;
  const cteHistoricoId = row ? resolverCteHistoricoId(row) : null;

  const conteudo = useMemo(() => {
    if (!row || !estadoInbox) return 'recebido' as const;
    return resolverConteudoWorkspace(row, estadoInbox.estado, forcarConferencia);
  }, [row, estadoInbox, forcarConferencia]);

  useEffect(() => {
    if (!open) {
      setManifestDoc(null);
      setForcarConferencia(false);
      setResumoConferencia(null);
      setReabrirOpen(false);
      return;
    }
    setForcarConferencia(false);
  }, [open, row?.id, row?.chave_acesso]);

  useEffect(() => {
    if (!open || !row || conteudo !== 'manifestacao') return;
    let cancelado = false;
    setPreparandoManifest(true);
    void onPrepararManifestacao()
      .then((doc) => {
        if (!cancelado) setManifestDoc(doc);
      })
      .finally(() => {
        if (!cancelado) setPreparandoManifest(false);
      });
    return () => {
      cancelado = true;
    };
  }, [open, row, conteudo, onPrepararManifestacao]);

  useEffect(() => {
    if (!open || !nfHistoricaId || conteudo !== 'resumo_final') return;
    setCarregandoResumo(true);
    void nfeEntradaConferenciaService
      .get(nfHistoricaId)
      .then((conf) => {
        setResumoConferencia({
          status: conf.status,
          estoque_aplicado_em: conf.estoque_aplicado_em,
          financeiro: conf.financeiro,
        });
      })
      .catch(() => setResumoConferencia(null))
      .finally(() => setCarregandoResumo(false));
  }, [open, nfHistoricaId, conteudo]);

  const handleUpdated = async () => {
    await onUpdated();
    setForcarConferencia(false);
  };

  const alertaExcecao = estadoInbox
    ? ['DIVERGENTE', 'BLOQUEADO'].includes(estadoInbox.estado.toUpperCase())
    : false;

  const tituloDocumento = row
    ? `${row.tipo_label} — ${row.numero || '—'}${row.serie ? ` / ${row.serie}` : ''}`
    : 'Documento';

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-4xl overflow-y-auto p-0 flex flex-col">
        <div className="sticky top-0 z-10 bg-background border-b px-4 py-4 sm:px-6 space-y-3">
          <SheetHeader className="text-left space-y-2">
            <SheetTitle className="text-lg">{tituloDocumento}</SheetTitle>
            <SheetDescription className="font-mono text-xs">
              {row?.chave_resumida || chaveNfeResumida(row?.chave_acesso)}
            </SheetDescription>
          </SheetHeader>

          {estadoInbox ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                status={badgeStatusEstadoConsolidado(estadoInbox.estado)}
                label={estadoInbox.label}
              />
              {row && isNfeFornecedor(row) && manifestacao ? (
                <StatusBadge status={statusManifestacaoExibicao(manifestacao, row).badge}>
                  {statusManifestacaoExibicao(manifestacao, row).label}
                </StatusBadge>
              ) : null}
              {row && isNfeFornecedor(row) ? (
                <StatusBadge status={statusXmlExibicao(manifestacao, row).badge}>
                  {statusXmlExibicao(manifestacao, row).label}
                </StatusBadge>
              ) : null}
            </div>
          ) : null}

          {alertasEstado.length > 0 ? (
            <div className="space-y-1.5">
              {alertasEstado.map((texto) => (
                <p
                  key={texto}
                  className={`text-xs rounded border px-2 py-1.5 leading-snug ${
                    alertaExcecao
                      ? 'text-orange-950 bg-orange-50 border-orange-200 dark:text-orange-100 dark:bg-orange-950/40 dark:border-orange-800'
                      : 'text-amber-950 bg-amber-50 border-amber-200 dark:text-amber-100 dark:bg-amber-950/40 dark:border-amber-800'
                  }`}
                >
                  {texto}
                </p>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex-1 px-4 py-4 sm:px-6 min-h-0">
          {!row ? (
            <p className="text-sm text-muted-foreground">Nenhum documento selecionado.</p>
          ) : conteudo === 'manifestacao' ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Manifestação do Destinatário — escolha um dos quatro eventos e confirme explicitamente.
              </p>
              {preparandoManifest || !manifestDoc ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Preparando registro para manifestação…
                </div>
              ) : (
                <ManifestacaoEventoForm
                  key={`ws-manifest-${manifestDoc.id}-${manifestDoc.chave_acesso}`}
                  documento={manifestDoc}
                  loadingAcao={loadingAcao}
                  onCancel={onClose}
                  onConfirm={(evento, justificativa) => {
                    void onExecutarManifestacao(evento, justificativa).then(() => handleUpdated());
                  }}
                />
              )}
            </div>
          ) : conteudo === 'xml_disponivel' ? (
            <div className="space-y-4">
              <div className="erp-card p-4 grid sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Emitente</div>
                  <div>{row.emitente_nome || '—'}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">CNPJ</div>
                  <div className="font-mono">{fmtCnpj(row.emitente_cnpj)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Emissão</div>
                  <div>{fmtData(row.data_emissao)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Valor</div>
                  <div>{fmtMoney(row.valor_total)}</div>
                </div>
              </div>

              {isNfeFornecedor(row) && !row.xml_armazenado ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 space-y-3">
                  <p className="text-sm text-amber-950">
                    O XML ainda não foi importado para a Base NF-e Entrada Importada. Importe antes de iniciar a conferência.
                  </p>
                  <Button type="button" disabled={loadingAcao} onClick={onIniciarArmazenarXmlNfe}>
                    {loadingAcao ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    {LABEL_IMPORTAR_XML_NFE}
                  </Button>
                  <p className="text-xs text-muted-foreground">{TOOLTIP_IMPORTAR_XML_NFE}</p>
                </div>
              ) : null}

              {isCteTransportadora(row) && !row.xml_armazenado ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 space-y-3">
                  <p className="text-sm text-amber-950">
                    Confirme o XML do CT-e na base importada antes de conferir.
                  </p>
                  <Button type="button" disabled={loadingAcao} onClick={onIniciarArmazenarXmlCte}>
                    {loadingAcao ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Importar XML CT-e
                  </Button>
                </div>
              ) : null}

              {(row.xml_armazenado || nfHistoricaId) && isNfeFornecedor(row) ? (
                <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap [&>button]:w-full sm:[&>button]:w-auto [&>a]:w-full sm:[&>a]:w-auto">
                  <Button type="button" onClick={() => setForcarConferencia(true)}>
                    Iniciar conferência
                  </Button>
                  {row.detalhe_rota ? (
                    <Link to={rotaAbrirBaseImportada(row)} className="erp-btn-outline erp-btn-sm inline-flex items-center">
                      {labelAbrirBaseImportada(row)}
                    </Link>
                  ) : null}
                </div>
              ) : null}

              {row.xml_armazenado && isCteTransportadora(row) ? (
                <Button type="button" onClick={() => setForcarConferencia(true)}>
                  Iniciar conferência CT-e
                </Button>
              ) : null}
            </div>
          ) : conteudo === 'conferencia_nfe' && nfHistoricaId ? (
            <div className="space-y-3">
              {forcarConferencia &&
              estadoInbox &&
              ['ESTOQUE_APLICADO', 'CONCLUIDO'].includes(estadoInbox.estado.toUpperCase()) ? (
                <div className="flex flex-wrap items-center gap-2 px-1">
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                    onClick={() => setForcarConferencia(false)}
                  >
                    Voltar ao resumo
                  </button>
                  <span className="text-xs text-muted-foreground">
                    Conferência aberta para alocação operacional (sem reaplicar estoque).
                  </span>
                </div>
              ) : null}
              <NFeEntradaConferenciaPanel
                nfeHistoricaId={nfHistoricaId}
                embedded
                onClose={onClose}
                onUpdated={() => void handleUpdated()}
              />
            </div>
          ) : conteudo === 'conferencia_cte' && cteHistoricoId ? (
            <CTeHistoricoDetalheModal
              open
              embedded
              cteId={cteHistoricoId}
              abaInicial={abaInicialCteWorkspace(estadoInbox?.estado || '')}
              onClose={onClose}
              onConferenciaAtualizada={() => void handleUpdated()}
            />
          ) : conteudo === 'resumo_final' ? (
            <div className="space-y-4">
              <div className="erp-card p-4 grid sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Emitente</div>
                  <div>{row.emitente_nome || '—'}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Entrada</div>
                  <div>{labelStatusEntradaNfeConferenciaFinalizada(row.status_entrada, row.status_entrada_label)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Emissão</div>
                  <div>{fmtData(row.data_emissao)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Valor</div>
                  <div>{fmtMoney(row.valor_total)}</div>
                </div>
              </div>

              {carregandoResumo ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando resumo…
                </p>
              ) : resumoConferencia ? (
                <div className="erp-card p-4 text-sm space-y-2">
                  <p>
                    Status conferência: <strong>{labelStatusConferenciaCabecalho(resumoConferencia.status)}</strong>
                  </p>
                  {resumoConferencia.estoque_aplicado_em ? (
                    <p className="text-emerald-700">
                      Estoque aplicado em{' '}
                      {new Date(resumoConferencia.estoque_aplicado_em).toLocaleString('pt-BR')}.
                    </p>
                  ) : null}
                </div>
              ) : null}

              {nfHistoricaId && isNfeFornecedor(row) ? (
                <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center [&>button]:w-full sm:[&>button]:w-auto [&>a]:w-full sm:[&>a]:w-auto">
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                    onClick={() => setReabrirOpen(true)}
                  >
                    Reabrir entrada para correção
                  </button>
                  <NFeEntradaFinanceiroAcoes
                    nfeEntradaId={nfHistoricaId}
                    conferenciaStatus={resumoConferencia?.status}
                    financeiro={resumoConferencia?.financeiro}
                    onGerar={() => setGerarCpOpen(true)}
                  />
                  {resumoConferencia?.financeiro?.contas_pagar_vinculadas?.[0]?.id ? (
                    <Link
                      to={`/financeiro/contas-pagar?titulo=${resumoConferencia.financeiro.contas_pagar_vinculadas[0].id}`}
                      className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
                    >
                      Abrir contas a pagar
                    </Link>
                  ) : null}
                </div>
              ) : null}

              {nfHistoricaId && row.tipo_documento === 'NFE_ENTRADA' ? (
                <div className="erp-card p-3 space-y-2 border border-primary/25 bg-primary/5">
                  <p className="text-sm font-medium text-foreground">Alocar entrada para Pedido de Venda</p>
                  <p className="text-xs text-muted-foreground">
                    Notas com estoque já aplicado continuam disponíveis para a alocação operacional
                    (sem movimentar estoque nem financeiro). Abra a conferência para vincular itens.
                  </p>
                  <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap [&>button]:w-full sm:[&>button]:w-auto [&>a]:w-full sm:[&>a]:w-auto">
                    <button
                      type="button"
                      className="erp-btn-primary erp-btn-sm w-full sm:w-auto"
                      onClick={() => setForcarConferencia(true)}
                    >
                      Abrir conferência / Alocar para venda
                    </button>
                    <Link
                      to={`/nfe-entrada/${nfHistoricaId}/conferencia`}
                      className="erp-btn-outline erp-btn-sm inline-flex items-center"
                    >
                      Abrir página de conferência
                    </Link>
                  </div>
                </div>
              ) : null}

              {row.detalhe_rota ? (
                <Link to={rotaAbrirBaseImportada(row)} className="erp-btn-ghost erp-btn-sm inline-flex w-full sm:w-auto">
                  {labelAbrirBaseImportada(row)}
                </Link>
              ) : null}
            </div>
          ) : (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>Documento recebido — aguardando próxima ação no fluxo fiscal.</p>
              {estadoInbox?.motivo ? (
                <p className="text-orange-800 bg-orange-50 border border-orange-200 rounded px-3 py-2">
                  {estadoInbox.motivo}
                </p>
              ) : null}
            </div>
          )}
        </div>

        {nfHistoricaId ? (
          <>
            <GerarContasPagarNfeEntradaModal
              open={gerarCpOpen}
              nfeEntradaId={nfHistoricaId}
              onClose={() => setGerarCpOpen(false)}
              onGenerated={() => {
                setGerarCpOpen(false);
                void handleUpdated();
              }}
            />
            <NFeEntradaReabrirModal
              open={reabrirOpen}
              nfeHistoricaId={nfHistoricaId}
              onOpenChange={setReabrirOpen}
              onSuccess={async (resultado) => {
                setResumoConferencia({
                  status: resultado.conferencia.status,
                  estoque_aplicado_em: resultado.conferencia.estoque_aplicado_em ?? null,
                  financeiro: resultado.conferencia.financeiro,
                });
                toast.success(resultado.mensagem);
                await onUpdated();
                setForcarConferencia(true);
              }}
            />
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
