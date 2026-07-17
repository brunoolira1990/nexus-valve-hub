import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Loader2, ShieldAlert, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  avisoProducaoDesabilitada,
  botaoEmitirProducaoHabilitado,
  confirmacaoProducaoValida,
  exibirBlocoProducaoSefaz,
  feedbackFinanceiroPosAutorizacaoProducao,
  mensagemEmissaoProducaoResposta,
  montarPayloadEmitirProducao,
  podeExibirBotaoEmitirProducao,
  TEXTO_CONFIRMACAO_PRODUCAO,
  type FinanceiroPosAutorizacao,
  type NFeEmissaoProducaoConferencia,
  type NFeEmissaoProducaoPermissoes,
} from '@/lib/nfeSaidaEmissaoProducao';
import { fmtMoeda } from '@/lib/nfeSaidaConferencia';
import { extrairErrosXsd, formatNfeXsdErro, type NFeXsdErro } from '@/lib/nfeXsdErros';
import { nfeSaidasService, type NFeEmissaoProducaoResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';

type Props = {
  nfeId: number;
  emissaoProducao?: NFeEmissaoProducaoConferencia | null;
  permissoes?: NFeEmissaoProducaoPermissoes | null;
  statusConferencia?: string | null;
  marcadaProntaEm?: string | null;
  onEmissaoConcluida: () => void | Promise<void>;
  onAbrirGerarContasReceber?: () => void;
};

export function NFeSaidaEmissaoProducaoPanel({
  nfeId,
  emissaoProducao,
  permissoes,
  statusConferencia,
  marcadaProntaEm,
  onEmissaoConcluida,
  onAbrirGerarContasReceber,
}: Props) {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [checkboxOk, setCheckboxOk] = useState(false);
  const [textoConfirmacao, setTextoConfirmacao] = useState('');
  const [loading, setLoading] = useState(false);
  const [checklistLoading, setChecklistLoading] = useState(false);
  const [checklistApi, setChecklistApi] = useState<{
    pronta?: boolean;
    pendencias?: Array<{ codigo?: string; mensagem?: string }>;
    alertas?: Array<{ codigo?: string; mensagem?: string }>;
  } | null>(null);
  const [xsdErros, setXsdErros] = useState<NFeXsdErro[]>([]);
  const [resultadoMsg, setResultadoMsg] = useState<string | null>(null);
  const [resultadoTipo, setResultadoTipo] = useState<'sucesso' | 'rejeicao' | 'tecnico' | 'lote_sem_prot' | null>(
    null,
  );
  const [financeiroPosAuth, setFinanceiroPosAuth] = useState<FinanceiroPosAutorizacao | null>(null);

  const autorizada = Boolean(emissaoProducao?.autorizada_producao);

  useEffect(() => {
    if (!permissoes?.producao_habilitada || !permissoes?.usuario_pode_emitir_producao || autorizada) {
      setChecklistApi(null);
      return;
    }
    let cancelled = false;
    setChecklistLoading(true);
    void nfeSaidasService
      .validarEmissaoProducao(nfeId)
      .then((data) => {
        if (!cancelled) setChecklistApi(data);
      })
      .catch(() => {
        if (!cancelled) setChecklistApi(null);
      })
      .finally(() => {
        if (!cancelled) setChecklistLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    nfeId,
    permissoes?.producao_habilitada,
    permissoes?.usuario_pode_emitir_producao,
    autorizada,
    statusConferencia,
    marcadaProntaEm,
  ]);

  const checklist = useMemo(() => {
    const statusPronta = (statusConferencia || '').trim().toUpperCase() === 'PRONTA_PARA_EMISSAO';
    const filtrarPendencias = (items: Array<{ codigo?: string; mensagem?: string }>) =>
      statusPronta ? items.filter((p) => p.codigo !== 'conferencia_nao_pronta') : items;

    const pendenciasApi = filtrarPendencias(checklistApi?.pendencias ?? []);
    const pendenciasConf = filtrarPendencias(emissaoProducao?.pendencias ?? []);
    const apiObsoleta =
      statusPronta &&
      (checklistApi?.pendencias ?? []).some((p) => p.codigo === 'conferencia_nao_pronta');

    const pendencias = apiObsoleta || checklistApi == null ? pendenciasConf : pendenciasApi;
    const alertas = checklistApi?.alertas ?? emissaoProducao?.alertas ?? [];
    const prontaApi = checklistApi?.pronta;
    const prontaConf = emissaoProducao?.pronta;
    const pronta =
      pendencias.length === 0 &&
      (apiObsoleta || checklistApi == null ? Boolean(prontaConf) : Boolean(prontaApi ?? prontaConf));
    return { pendencias, alertas, pronta };
  }, [checklistApi, emissaoProducao, statusConferencia]);

  const feedbackFin = feedbackFinanceiroPosAutorizacaoProducao(financeiroPosAuth);

  if (!exibirBlocoProducaoSefaz(emissaoProducao, permissoes)) {
    return (
      <div
        className="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground"
        data-testid="nfe-producao-desabilitada"
      >
        Emissão produção SEFAZ desabilitada neste ambiente.
      </div>
    );
  }

  const aviso = avisoProducaoDesabilitada(permissoes, emissaoProducao);
  const mostrarBotao = podeExibirBotaoEmitirProducao(emissaoProducao, permissoes);
  const botaoAtivo = botaoEmitirProducaoHabilitado(emissaoProducao, permissoes, checklistApi);
  const confirmacaoOk = confirmacaoProducaoValida(checkboxOk, textoConfirmacao);

  const resetModal = () => {
    setCheckboxOk(false);
    setTextoConfirmacao('');
  };

  const fecharModal = () => {
    setModalOpen(false);
    resetModal();
  };

  const verContasReceber = (tituloId?: number | null) => {
    if (tituloId) {
      navigate(`/financeiro/contas-receber?titulo=${tituloId}`);
      return;
    }
    navigate('/financeiro/contas-receber');
  };

  const executarEmissao = async () => {
    if (!confirmacaoOk || loading) return;
    setLoading(true);
    setResultadoMsg(null);
    setResultadoTipo(null);
    setFinanceiroPosAuth(null);
    setXsdErros([]);
    try {
      const res: NFeEmissaoProducaoResponse = await nfeSaidasService.emitirProducao(
        nfeId,
        montarPayloadEmitirProducao(),
      );
      setXsdErros(extrairErrosXsd(res));
      const parsed = mensagemEmissaoProducaoResposta(res);
      setResultadoTipo(parsed.tipo);
      setResultadoMsg(parsed.texto);
      const fin = res.financeiro ?? null;
      setFinanceiroPosAuth(fin);
      const finFeedback = feedbackFinanceiroPosAutorizacaoProducao(fin);
      if (parsed.tipo === 'sucesso') {
        toast.success(`NF-e autorizada em produção — ${parsed.texto}`);
        if (finFeedback.tipo === 'gerado') {
          toast.success(finFeedback.texto);
        } else if (finFeedback.tipo === 'ja_existente') {
          toast.message(finFeedback.texto);
        } else if (finFeedback.tipo === 'erro') {
          toast.warning(finFeedback.texto);
        }
      } else if (parsed.tipo === 'rejeicao') {
        toast.error(`SEFAZ produção — ${parsed.texto}`);
      } else if (parsed.tipo === 'lote_sem_prot') {
        toast.warning(parsed.texto);
      } else {
        toast.error(parsed.texto);
      }
      if (parsed.tipo === 'sucesso') {
        fecharModal();
      }
      await onEmissaoConcluida();
    } catch (err) {
      const ax = err as { response?: { data?: NFeEmissaoProducaoResponse } };
      const data = ax.response?.data;
      if (data) setXsdErros(extrairErrosXsd(data));
      const msg = apiErrorMessage(err, {
        fallback: 'Falha ao emitir em produção SEFAZ. Verifique certificado, numeração e pendências.',
      });
      setResultadoTipo('tecnico');
      setResultadoMsg(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="rounded-md border-2 border-red-600/50 bg-red-950/5 dark:bg-red-950/20 p-4 space-y-3"
      data-testid="nfe-producao-panel"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-red-600 shrink-0" aria-hidden />
        <span className="font-semibold text-red-700 dark:text-red-400 uppercase tracking-wide text-sm">
          PRODUÇÃO SEFAZ — documento fiscal real
        </span>
      </div>

      {autorizada ? (
        <div className="space-y-1 text-sm" data-testid="nfe-producao-autorizada">
          <p className="font-medium text-emerald-700 dark:text-emerald-400">NF-e autorizada em produção SEFAZ.</p>
          {emissaoProducao?.protocolo_autorizacao ? (
            <p>Protocolo: {emissaoProducao.protocolo_autorizacao}</p>
          ) : null}
          {emissaoProducao?.cstat_autorizacao ? (
            <p>
              cStat {emissaoProducao.cstat_autorizacao}: {emissaoProducao.motivo_autorizacao || '—'}
            </p>
          ) : null}
          {emissaoProducao?.chave_acesso ? (
            <p className="font-mono text-xs break-all">Chave: {emissaoProducao.chave_acesso}</p>
          ) : null}
          {feedbackFin.tipo === 'gerado' || feedbackFin.tipo === 'ja_existente' ? (
            <div className="pt-2 space-y-2" data-testid="nfe-producao-financeiro-ok">
              <p className="text-emerald-700 dark:text-emerald-400">{feedbackFin.texto}</p>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm inline-flex"
                onClick={() => verContasReceber(financeiroPosAuth?.titulo_id)}
              >
                <Wallet className="h-3 w-3 mr-1" />
                Ver contas a receber
              </button>
            </div>
          ) : null}
          {feedbackFin.tipo === 'erro' ? (
            <div className="pt-2 space-y-2" data-testid="nfe-producao-financeiro-aviso">
              <p className="text-amber-800 dark:text-amber-200">{feedbackFin.texto}</p>
              {onAbrirGerarContasReceber ? (
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm inline-flex"
                  onClick={onAbrirGerarContasReceber}
                >
                  <Wallet className="h-3 w-3 mr-1" />
                  Gerar contas a receber
                </button>
              ) : null}
            </div>
          ) : null}
          {emissaoProducao?.tem_xml_autorizado ? (
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm inline-flex mt-2"
              onClick={() => {
                void nfeSaidasService.downloadXmlAutorizado(nfeId).catch((e) => {
                  toast.error(apiErrorMessage(e, { fallback: 'Não foi possível baixar o XML autorizado.' }));
                });
              }}
            >
              Baixar XML autorizado (produção)
            </button>
          ) : null}
        </div>
      ) : (
        <>
          {!permissoes?.producao_habilitada ? (
            <p className="text-sm text-muted-foreground" data-testid="nfe-producao-aviso-desabilitada">
              {aviso}
            </p>
          ) : !permissoes?.usuario_pode_emitir_producao ? (
            <p className="text-sm text-amber-800 dark:text-amber-200" data-testid="nfe-producao-sem-permissao">
              {aviso}
            </p>
          ) : (
            <>
              <div className="text-sm space-y-2" data-testid="nfe-producao-checklist">
                <p className="font-medium">Checklist pré-emissão produção</p>
                {checklistLoading ? (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Atualizando validação produção…
                  </p>
                ) : null}
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Status</dt>
                    <dd>{emissaoProducao?.status_producao_label || emissaoProducao?.status_emissao_sefaz || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Emitente</dt>
                    <dd>{emissaoProducao?.emitente?.nome || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Destinatário</dt>
                    <dd>{emissaoProducao?.destinatario?.nome || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Valor total</dt>
                    <dd>{fmtMoeda(emissaoProducao?.valor_total ?? 0)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Ambiente</dt>
                    <dd>{emissaoProducao?.ambiente_label || 'Produção SEFAZ'}</dd>
                  </div>
                  {emissaoProducao?.chave_acesso ? (
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Chave de acesso</dt>
                      <dd className="font-mono break-all">{emissaoProducao.chave_acesso}</dd>
                    </div>
                  ) : null}
                  {emissaoProducao?.numeracao_producao ? (
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Próxima numeração produção</dt>
                      <dd>
                        Série {emissaoProducao.numeracao_producao.serie}, nº{' '}
                        {emissaoProducao.numeracao_producao.proximo_numero}
                      </dd>
                    </div>
                  ) : null}
                  {emissaoProducao?.serie_nfe && emissaoProducao?.numero_nfe ? (
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Série / número reservados</dt>
                      <dd>
                        {emissaoProducao.serie_nfe} / {emissaoProducao.numero_nfe}
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {(checklist.pendencias?.length ?? 0) > 0 ? (
                  <ul className="list-disc pl-4 text-xs text-destructive space-y-0.5">
                    {checklist.pendencias?.map((p, i) => (
                      <li key={`pend-prod-${i}`}>{p.mensagem}</li>
                    ))}
                  </ul>
                ) : checklist.pronta ? (
                  <p className="text-xs text-emerald-700 dark:text-emerald-300">Checklist produção: pronta.</p>
                ) : null}
                {(checklist.alertas?.length ?? 0) > 0 ? (
                  <ul className="list-disc pl-4 text-xs text-amber-800 dark:text-amber-200 space-y-0.5">
                    {checklist.alertas?.map((a, i) => (
                      <li key={`alert-prod-${i}`}>{a.mensagem}</li>
                    ))}
                  </ul>
                ) : null}
              </div>

              {mostrarBotao ? (
                <div className="space-y-2">
                  {!botaoAtivo && aviso ? (
                    <div className="flex items-start gap-2 text-xs text-amber-900 dark:text-amber-100 rounded border border-amber-500/40 bg-amber-500/10 p-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{aviso}</span>
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="erp-btn-sm bg-red-700 hover:bg-red-800 text-white border-red-800 disabled:opacity-50"
                    disabled={!botaoAtivo || loading}
                    data-testid="nfe-producao-btn-emitir"
                    onClick={() => setModalOpen(true)}
                  >
                    Emitir em produção SEFAZ
                  </button>
                </div>
              ) : null}
            </>
          )}
        </>
      )}

      {resultadoMsg && !autorizada ? (
        <div
          className={`text-xs rounded p-2 ${
            resultadoTipo === 'sucesso'
              ? 'border border-emerald-500/40 bg-emerald-500/10'
              : 'border border-destructive/40 bg-destructive/5'
          }`}
          data-testid="nfe-producao-resultado"
        >
          {resultadoMsg}
          {xsdErros.length ? (
            <ul className="mt-2 list-disc pl-4 space-y-1 text-[11px] font-normal text-destructive">
              {xsdErros.map((e, i) => (
                <li key={`xsd-prod-${i}`}>{formatNfeXsdErro(e)}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <AlertDialog open={modalOpen} onOpenChange={(open) => (open ? setModalOpen(true) : fecharModal())}>
        <AlertDialogContent className="max-w-lg border-red-600/40" data-testid="nfe-producao-modal">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-700 dark:text-red-400">
              Confirmar emissão em PRODUÇÃO SEFAZ
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm text-foreground">
                <p className="font-semibold text-red-700 dark:text-red-400">
                  PRODUÇÃO SEFAZ — documento fiscal real
                </p>
                <p>
                  Esta ação transmitirá uma NF-e <strong>real</strong> para a SEFAZ em ambiente de{' '}
                  <strong>PRODUÇÃO</strong>.
                </p>
                <p>O documento terá validade fiscal se autorizado.</p>
                <p>
                  Confira emitente, cliente, itens, valores, CFOP, impostos, série e número antes de continuar.
                  Não é homologação.
                </p>
                <div className="flex items-start gap-2 rounded border border-border p-2">
                  <Checkbox
                    id="confirmar-producao-checkbox"
                    checked={checkboxOk}
                    onCheckedChange={(v) => setCheckboxOk(v === true)}
                    data-testid="nfe-producao-checkbox"
                  />
                  <Label htmlFor="confirmar-producao-checkbox" className="text-sm leading-snug cursor-pointer">
                    Entendo que esta NF-e será transmitida para a SEFAZ em produção.
                  </Label>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="confirmar-producao-texto" className="text-xs">
                    Digite <span className="font-mono font-semibold">{TEXTO_CONFIRMACAO_PRODUCAO}</span> para confirmar
                  </Label>
                  <Input
                    id="confirmar-producao-texto"
                    value={textoConfirmacao}
                    onChange={(e) => setTextoConfirmacao(e.target.value)}
                    placeholder={TEXTO_CONFIRMACAO_PRODUCAO}
                    autoComplete="off"
                    data-testid="nfe-producao-texto-confirmacao"
                  />
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading} onClick={fecharModal}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={loading || !confirmacaoOk}
              className="bg-red-700 hover:bg-red-800"
              data-testid="nfe-producao-confirmar"
              onClick={(e) => {
                e.preventDefault();
                void executarEmissao();
              }}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin inline mr-1" /> : null}
              Confirmar emissão produção
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
