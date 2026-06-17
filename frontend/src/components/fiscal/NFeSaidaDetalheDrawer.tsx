import { useEffect, useMemo, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { NFeChecklistHomologacaoModal } from '@/components/fiscal/NFeChecklistHomologacaoModal';
import { NFeReformaTributariaResumo } from '@/components/fiscal/NFeReformaTributariaResumo';
import { formatDateBr } from '@/lib/dateBr';
import {
  formatAmbienteNfe,
  formatCurrencyBRL,
  formatNfeTituloListagem,
  formatStatusNfe,
} from '@/lib/nfeSaidaApresentacaoFormat';
import { getNfeFiscalSummaryBadge } from '@/lib/nfeSaidaListagemCompacta';
import { formatDateTimeBr, nfePodeDescartarRascunho } from '@/lib/nfeSaidaUi';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { GerarContasReceberNfeModal } from '@/components/fiscal/GerarContasReceberNfeModal';
import { NFeConsultaSefazModal } from '@/components/fiscal/NFeConsultaSefazModal';
import { NFeCartaCorrecaoModal } from '@/components/fiscal/NFeCartaCorrecaoModal';
import { NFeCancelamentoModal } from '@/components/fiscal/NFeCancelamentoModal';
import { NFeEnvioDanfeXmlModal } from '@/components/fiscal/NFeEnvioDanfeXmlModal';
import { buildCartaCorrecaoContextoFromNfe } from '@/lib/nfeCartaCorrecaoPreview';
import { NFeFinanceiroAcoes } from '@/components/fiscal/NFeFinanceiroAcoes';
import { NFeSaidaAcoesGruposPanel } from '@/components/fiscal/NFeSaidaAcoesGruposPanel';
import { toast } from 'sonner';
import {
  obterMatrizAcoesNfeSaida,
  resolverContextoNfeSaida,
} from '@/lib/nfeSaidaAcoesMatriz';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import { nfeSaidasService, type NFeChecklistHomologacaoResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeSaida } from '@/types';

type Props = {
  nfeId: number | null;
  open: boolean;
  onClose: () => void;
  onOpenConferencia?: (nfe: NFeSaida) => void;
};

export function NFeSaidaDetalheDrawer({ nfeId, open, onClose, onOpenConferencia }: Props) {
  const navigate = useNavigate();
  const [nfe, setNfe] = useState<NFeSaida | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [danfeLoading, setDanfeLoading] = useState(false);
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [checklistBadge, setChecklistBadge] = useState<
    'aprovado' | 'aprovado_com_alertas' | 'bloqueado' | null
  >(null);
  const [descarteOpen, setDescarteOpen] = useState(false);
  const [descarteLoading, setDescarteLoading] = useState(false);
  const [gerarCrOpen, setGerarCrOpen] = useState(false);
  const [consultaSefazOpen, setConsultaSefazOpen] = useState(false);
  const [cartaCorrecaoOpen, setCartaCorrecaoOpen] = useState(false);
  const [cancelamentoOpen, setCancelamentoOpen] = useState(false);
  const [envioEmailOpen, setEnvioEmailOpen] = useState(false);

  useEffect(() => {
    if (!open || !nfeId) {
      setChecklistBadge(null);
    }
  }, [open, nfeId]);

  useEffect(() => {
    if (!open || !nfeId) {
      setNfe(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void nfeSaidasService
      .getById(nfeId)
      .then(setNfe)
      .catch((e) => {
        setNfe(null);
        setError(apiErrorMessage(e));
      })
      .finally(() => setLoading(false));
  }, [open, nfeId]);

  const visualizarDanfe = async () => {
    if (!nfe?.id) return;
    setDanfeLoading(true);
    try {
      if (contextoAcao.autorizadaHomolog || contextoAcao.autorizadaProducao) {
        const { blob } = await nfeSaidasService.danfeAutorizadoBlob(nfe.id);
        openBlobInNewTab(blob);
        return;
      }
      const { blob } = await nfeSaidasService.previewDanfeBlob(nfe.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível visualizar o DANFE.' }));
    } finally {
      setDanfeLoading(false);
    }
  };

  const baixarXml = async () => {
    if (!nfe?.id) return;
    if (contextoAcao.temXmlAutorizado && (contextoAcao.autorizadaHomolog || contextoAcao.autorizadaProducao)) {
      try {
        await nfeSaidasService.downloadXmlAutorizado(nfe.id);
      } catch (e) {
        alert(apiErrorMessage(e, { fallback: 'Não foi possível baixar o XML autorizado.' }));
      }
      return;
    }
    try {
      const data = await nfeSaidasService.previewXmlPreliminar(nfe.id);
      const blob = new Blob([data.xml || ''], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nfe-${nfe.id}-preliminar.xml`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível baixar o XML.' }));
    }
  };

  const abrirConferencia = () => {
    if (!nfe) return;
    if (onOpenConferencia) onOpenConferencia(nfe);
    else navigate(`/nfe-saida?nfe=${nfe.id}`);
  };

  const ap = nfe?.apresentacao;
  const sefaz = nfe?.resumo_emissao_sefaz;
  const drawerTitulo =
    (nfe?.listagem_resumo?.titulo && formatNfeTituloListagem(nfe)) ||
    ap?.titulo_exibicao ||
    (nfe ? formatNfeTituloListagem(nfe) : 'NF-e Saída');
  const drawerSubtitulo = ap?.subtitulo_exibicao || nfe?.listagem_resumo?.subtitulo || '';
  const fiscalDrawer = nfe
    ? getNfeFiscalSummaryBadge(nfe.listagem_resumo, {
        status: nfe.status,
        status_emissao_sefaz:
          nfe.status_emissao_sefaz || nfe.resumo_emissao_sefaz?.status_emissao_sefaz,
      })
    : null;

  const descartePerm = nfe
    ? nfePodeDescartarRascunho({
        status: nfe.status,
        status_emissao_sefaz: nfe.status_emissao_sefaz || nfe.resumo_emissao_sefaz?.status_emissao_sefaz,
        protocolo_autorizacao: ap?.protocolo_autorizacao || sefaz?.nfe?.protocolo,
        cstat_autorizacao: nfe.cstat_autorizacao,
      })
    : { pode: false, motivo: '' };

  const contextoAcao = useMemo(() => {
    if (!nfe) {
      return resolverContextoNfeSaida({});
    }
    return resolverContextoNfeSaida(
      {
        status: nfe.status,
        status_emissao_sefaz: nfe.status_emissao_sefaz,
        resumo_emissao_sefaz: nfe.resumo_emissao_sefaz,
        ambiente_emissao: ap?.ambiente_emissao || sefaz?.ambiente_emissao,
        chave_acesso: ap?.chave_acesso,
        tem_xml_autorizado: sefaz?.tem_xml_autorizado,
      },
      sefaz ?? undefined,
    );
  }, [nfe, ap, sefaz]);

  const matrizAcoes = useMemo(
    () =>
      obterMatrizAcoesNfeSaida(contextoAcao, {
        podeDescartar: descartePerm.pode,
        podeValidar: !contextoAcao.autorizadaHomolog && !contextoAcao.autorizadaProducao,
        podeEmitirProducao: false,
      }),
    [contextoAcao, descartePerm.pode],
  );

  const descartarRascunho = async (motivo: string) => {
    if (!nfe?.id) return;
    setDescarteLoading(true);
    try {
      const r = await nfeSaidasService.descartarRascunho(nfe.id, { motivo });
      toast.success(r.mensagem || 'NF-e rascunho descartada internamente.');
      onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível descartar o rascunho.' }));
      throw e;
    } finally {
      setDescarteLoading(false);
    }
  };

  const handleChecklistResult = (res: NFeChecklistHomologacaoResponse) => {
    if (res.status === 'bloqueado') {
      setChecklistBadge('bloqueado');
    } else if (res.status === 'aprovado_com_alertas' || res.status === 'alerta') {
      setChecklistBadge('aprovado_com_alertas');
    } else {
      setChecklistBadge('aprovado');
    }
  };

  const checklistBadgeLabel =
    checklistBadge === 'bloqueado'
      ? 'Pré-homologação bloqueada'
      : checklistBadge === 'aprovado_com_alertas'
        ? 'Pré-homologação validada'
        : checklistBadge === 'aprovado'
          ? 'Checklist aprovado'
          : null;

  const checklistBadgeClass =
    checklistBadge === 'bloqueado'
      ? 'erp-badge-danger'
      : checklistBadge === 'aprovado_com_alertas'
        ? 'erp-badge-warning'
        : 'erp-badge-success';

  return (
    <>
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="inset-y-0 right-0 left-auto top-0 mt-0 h-full w-full max-w-lg rounded-none rounded-l-lg border-l flex flex-col max-h-[100vh]">
        <DrawerHeader className="text-left border-b border-border shrink-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <DrawerTitle className="text-base">{drawerTitulo}</DrawerTitle>
              {drawerSubtitulo ? (
                <p className="text-xs text-muted-foreground mt-1">{drawerSubtitulo}</p>
              ) : null}
              {fiscalDrawer?.hasData ? (
                <div className="flex flex-col gap-0.5 items-start mt-2">
                  <span className={fiscalDrawer.className}>{fiscalDrawer.label}</span>
                  {fiscalDrawer.subtexto ? (
                    <span className="text-xs text-muted-foreground">{fiscalDrawer.subtexto}</span>
                  ) : null}
                </div>
              ) : null}
              {checklistBadgeLabel ? (
                <span className={`${checklistBadgeClass} text-[10px] mt-2`}>{checklistBadgeLabel}</span>
              ) : null}
            </div>
            <DrawerClose asChild>
              <button type="button" className="erp-btn-ghost erp-btn-sm p-1" aria-label="Fechar">
                <X className="h-4 w-4" />
              </button>
            </DrawerClose>
          </div>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando detalhes…
            </div>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {nfe && !loading ? (
            <>
              <section className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Identidade fiscal
                </h3>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted-foreground">Número fiscal</dt>
                  <dd>{ap?.numero_fiscal || '—'}</dd>
                  <dt className="text-muted-foreground">Série</dt>
                  <dd>{ap?.serie_fiscal || '—'}</dd>
                  <dt className="text-muted-foreground">Ambiente</dt>
                  <dd>{formatAmbienteNfe(ap?.ambiente_emissao || sefaz?.ambiente_emissao)}</dd>
                  <dt className="text-muted-foreground">Status</dt>
                  <dd title={nfe.status}>{formatStatusNfe(nfe.status)}</dd>
                  <dt className="text-muted-foreground">cStat</dt>
                  <dd>{sefaz?.nfe?.cstat || nfe.resumo_emissao_sefaz?.cstat_autorizacao || '—'}</dd>
                  <dt className="text-muted-foreground">Chave</dt>
                  <dd className="col-span-2 font-mono text-[10px] break-all">
                    {ap?.chave_acesso || '—'}
                  </dd>
                  <dt className="text-muted-foreground">Protocolo</dt>
                  <dd>{ap?.protocolo_autorizacao || sefaz?.nfe?.protocolo || '—'}</dd>
                  <dt className="text-muted-foreground">Autorização</dt>
                  <dd>
                    {formatDateTimeBr(
                      sefaz?.nfe?.dh_autorizacao ||
                        sefaz?.nfe?.data_autorizacao ||
                        ap?.data_autorizacao ||
                        null,
                    )}
                  </dd>
                </dl>
              </section>

              <section className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Comercial</h3>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted-foreground">Cliente</dt>
                  <dd className="col-span-2">{nfe.cliente_nome}</dd>
                  <dt className="text-muted-foreground">Pedido</dt>
                  <dd>{nfe.pedido_venda_numero || (nfe.pedido_venda_id ? `#${nfe.pedido_venda_id}` : '—')}</dd>
                  <dt className="text-muted-foreground">Faturamento</dt>
                  <dd>
                    {ap?.numero_faturamento ||
                      (nfe.faturamento_pedido_venda_id ? `#${nfe.faturamento_pedido_venda_id}` : '—')}
                  </dd>
                  <dt className="text-muted-foreground">Valor</dt>
                  <dd>{formatCurrencyBRL(nfe.valor_total)}</dd>
                  <dt className="text-muted-foreground">Emissão</dt>
                  <dd>{formatDateBr(nfe.data)}</dd>
                </dl>
              </section>

              <section className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Duplicatas da NF-e
                </h3>
                <p className="text-xs text-muted-foreground">
                  As duplicatas representam a cobrança informada na NF-e. Nesta fase, não geram contas a
                  receber automaticamente.
                </p>
                {(nfe.duplicatas_nfe?.length ?? 0) > 0 ? (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-muted-foreground border-b">
                        <th className="text-left py-1">Nº</th>
                        <th className="text-left py-1">Vencimento</th>
                        <th className="text-right py-1">Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nfe.duplicatas_nfe!.map((d) => (
                        <tr key={d.numero} className="border-b border-border/60">
                          <td className="py-1">{d.numero}</td>
                          <td className="py-1">{d.vencimento_formatado}</td>
                          <td className="py-1 text-right">{d.valor_formatado}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-xs text-muted-foreground">Sem duplicatas nesta NF-e.</p>
                )}
              </section>

              <section className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Atendimento operacional
                </h3>
                <AtendimentoOperacionalResumo resumo={nfe.resumo_atendimento_operacional} />
              </section>

              <section className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Reforma Tributária
                </h3>
                <NFeReformaTributariaResumo payload={nfe.reforma_tributaria} />
              </section>
            </>
          ) : null}
        </div>

        <DrawerFooter className="border-t border-border shrink-0">
          {nfe ? (
            <NFeSaidaAcoesGruposPanel
              compact
              contexto={contextoAcao}
              acoes={matrizAcoes}
              danfeLoading={danfeLoading}
              onValidar={() => setChecklistOpen(true)}
              onAbrirNfe={abrirConferencia}
              onHistorico={abrirConferencia}
              onDanfe={() => void visualizarDanfe()}
              onXml={() => void baixarXml()}
              onXmlAutorizado={() => void baixarXml()}
              onDescartar={() => setDescarteOpen(true)}
              onConsultaSefaz={() => setConsultaSefazOpen(true)}
              onCartaCorrecao={() => setCartaCorrecaoOpen(true)}
              onCancelamento={() => setCancelamentoOpen(true)}
              onEnvioDanfeXml={() => setEnvioEmailOpen(true)}
              financeiroSlot={
                <NFeFinanceiroAcoes
                  nfeId={nfe.id}
                  status={nfe.status}
                  statusEmissaoSefaz={nfe.status_emissao_sefaz}
                  resumoEmissaoSefaz={nfe.resumo_emissao_sefaz}
                  financeiro={{
                    financeiro_gerado: nfe.financeiro_gerado,
                    pode_gerar_contas_receber: nfe.pode_gerar_contas_receber,
                    motivo_bloqueio_financeiro: nfe.motivo_bloqueio_financeiro,
                    contas_receber_vinculadas: nfe.contas_receber_vinculadas,
                    nfe_cancelada_com_financeiro: nfe.nfe_cancelada_com_financeiro,
                  }}
                  onGerar={() => setGerarCrOpen(true)}
                />
              }
            />
          ) : null}
          {!descartePerm.pode && nfe && (nfe.status || '').toUpperCase() !== 'DESCARTADA_INTERNA' ? (
            <p className="text-xs text-muted-foreground w-full mt-2">
              {descartePerm.motivo ||
                'Estorno interno não disponível. NF-e autorizada exige cancelamento SEFAZ (fase futura) ou Carta de Correção.'}
            </p>
          ) : null}
        </DrawerFooter>
      </DrawerContent>

      <NFeChecklistHomologacaoModal
        open={checklistOpen}
        onClose={() => setChecklistOpen(false)}
        nfeSaidaId={nfeId}
        onResult={handleChecklistResult}
      />

      <MotivoAcaoDestrutivaModal
        open={descarteOpen}
        onOpenChange={setDescarteOpen}
        title="Descartar NF-e rascunho"
        description="A NF-e será marcada como descartada internamente. O histórico, XML preliminar e DANFE de conferência são preservados."
        avisoSefaz="Nenhum evento será enviado à SEFAZ porque a NF-e não está autorizada."
        detalhes={
          nfe ? (
            <p className="text-sm text-muted-foreground">
              NF-e: <strong>{drawerTitulo}</strong>
            </p>
          ) : null
        }
        confirmLabel="Descartar rascunho"
        loading={descarteLoading}
        onConfirm={descartarRascunho}
      />

      <GerarContasReceberNfeModal
        open={gerarCrOpen}
        nfeId={nfeId}
        onClose={() => setGerarCrOpen(false)}
        onGenerated={({ titulo }) => {
          toast.success('Contas a receber geradas com sucesso.');
          if (nfeId) {
            void nfeSaidasService.getById(nfeId).then(setNfe).catch(() => undefined);
          }
          if (titulo?.id) {
            navigate(`/financeiro/contas-receber?titulo=${titulo.id}`);
          }
        }}
      />

      <NFeConsultaSefazModal
        open={consultaSefazOpen}
        nfeId={nfeId}
        onClose={() => setConsultaSefazOpen(false)}
        onConsultaConcluida={() => {
          if (nfeId) {
            void nfeSaidasService.getById(nfeId).then(setNfe).catch(() => undefined);
          }
        }}
      />

      <NFeCartaCorrecaoModal
        open={cartaCorrecaoOpen}
        nfeId={nfeId}
        homologacao={contextoAcao.autorizadaHomolog}
        contextoInicial={
          nfe ? buildCartaCorrecaoContextoFromNfe(nfe, { homologacao: contextoAcao.autorizadaHomolog }) : null
        }
        onClose={() => setCartaCorrecaoOpen(false)}
        onEmitida={() => {
          if (nfeId) {
            void nfeSaidasService.getById(nfeId).then(setNfe).catch(() => undefined);
          }
        }}
      />

      <NFeCancelamentoModal
        open={cancelamentoOpen}
        nfeId={nfeId}
        onClose={() => setCancelamentoOpen(false)}
        onCancelada={() => {
          if (nfeId) {
            void nfeSaidasService.getById(nfeId).then(setNfe).catch(() => undefined);
          }
        }}
      />

    </Drawer>

      <NFeEnvioDanfeXmlModal
        open={envioEmailOpen}
        nfeId={nfeId}
        onClose={() => setEnvioEmailOpen(false)}
        onEnviado={() => {
          if (nfeId) {
            void nfeSaidasService.getById(nfeId).then(setNfe).catch(() => undefined);
          }
        }}
      />
    </>
  );
}
