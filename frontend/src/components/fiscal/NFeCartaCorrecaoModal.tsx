import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, FileText, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  MSG_CONFIRMACAO_TRANSMISSAO_CCE,
  MSG_O_QUE_CCE_NAO_PODE_CORRIGIR,
  MSG_PREVIA_SEM_TRANSMISSAO,
  mapCartaCorrecaoDadosToContexto,
  openCcePdfBlob,
  type NFeCartaCorrecaoContexto,
} from '@/lib/nfeCartaCorrecaoPreview';
import {
  nfeSaidasService,
  type NFeCartaCorrecaoAnterior,
  type NFeCartaCorrecaoResponse,
} from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';

export const TAMANHO_MINIMO_CORRECAO = 15;
export const TAMANHO_MAXIMO_CORRECAO = 1000;

export const MSG_AVISO_CCE_HOMOLOG = 'Evento de homologação, sem valor fiscal.';
export const MSG_AVISO_CCE_PRODUCAO =
  'Evento fiscal real transmitido à SEFAZ após confirmação.';

export const MSG_LIMITES_CCE =
  'A CC-e corrige apenas informações permitidas pela legislação (texto livre). Não altera valores, impostos, itens, destinatário, datas ou numeração.';

type Etapa = 'redigir' | 'previa' | 'confirmacao' | 'transmitindo' | 'resultado' | 'erro';

type Props = {
  open: boolean;
  nfeId: number | null;
  homologacao?: boolean;
  contextoInicial?: NFeCartaCorrecaoContexto | null;
  onClose: () => void;
  onEmitida?: (res: NFeCartaCorrecaoResponse) => void;
};

const ETAPAS_FLUXO: Array<{ id: Etapa; label: string }> = [
  { id: 'redigir', label: 'Redigir' },
  { id: 'previa', label: 'Pré-visualizar' },
  { id: 'confirmacao', label: 'Transmitir' },
  { id: 'resultado', label: 'Resultado' },
];

function indiceEtapaAtual(etapa: Etapa): number {
  if (etapa === 'transmitindo') return 2;
  if (etapa === 'erro') return 2;
  if (etapa === 'resultado') return 3;
  return ETAPAS_FLUXO.findIndex((e) => e.id === etapa);
}

function IndicadorEtapas({ etapa }: { etapa: Etapa }) {
  const atual = indiceEtapaAtual(etapa);
  return (
    <ol className="flex flex-wrap gap-1 text-[11px] mb-4">
      {ETAPAS_FLUXO.map((step, idx) => (
        <li
          key={step.id}
          className={cn(
            'rounded px-2 py-0.5 border',
            idx === atual
              ? 'border-primary bg-primary/10 text-primary font-medium'
              : idx < atual
                ? 'border-emerald-600/30 bg-emerald-600/5 text-emerald-800 dark:text-emerald-200'
                : 'border-border text-muted-foreground',
          )}
        >
          {idx + 1}. {step.label}
        </li>
      ))}
    </ol>
  );
}

function CampoPrevia({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={cn('text-sm break-words', mono && 'font-mono text-xs')}>{value || '—'}</p>
    </div>
  );
}

function ListaCceAnteriores({
  anteriores,
  nfeId,
}: {
  anteriores: NFeCartaCorrecaoAnterior[];
  nfeId: number;
}) {
  const [abrindoId, setAbrindoId] = useState<number | null>(null);

  const abrirComprovante = async (ev: NFeCartaCorrecaoAnterior) => {
    if (!ev.tem_comprovante) return;
    setAbrindoId(ev.evento_id);
    try {
      const blob = await nfeSaidasService.comprovanteCartaCorrecaoPdfBlob(nfeId, ev.evento_id);
      openCcePdfBlob(blob, `comprovante-cce-seq-${ev.sequencia}.pdf`);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível abrir o comprovante da CC-e.' }));
    } finally {
      setAbrindoId(null);
    }
  };

  if (!anteriores.length) return null;

  return (
    <div className="rounded-md border border-border bg-muted/10 p-3 space-y-2">
      <p className="text-xs font-semibold">Cartas de Correção já emitidas nesta NF-e</p>
      <ul className="space-y-2">
        {anteriores.map((ev) => (
          <li
            key={ev.evento_id}
            className={cn(
              'text-xs rounded border bg-background p-2 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2',
              ev.vigente && 'border-emerald-600/40 bg-emerald-600/5',
            )}
          >
            <div className="space-y-0.5 min-w-0">
              <p className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium">Seq. {ev.sequencia}</span>
                {ev.vigente ? (
                  <span className="erp-badge-success text-[10px]">Vigente</span>
                ) : null}
                <span className="text-muted-foreground">
                  · {formatDateTimeBr(ev.emitido_em)}
                  {ev.protocolo ? ` · prot. ${ev.protocolo}` : ''}
                </span>
              </p>
              <p className="text-muted-foreground">
                cStat {ev.cstat || '—'}
                {ev.xmotivo ? ` — ${ev.xmotivo}` : ''}
              </p>
              {ev.texto_resumo ? (
                <p className="text-muted-foreground truncate" title={ev.texto_correcao}>
                  {ev.texto_resumo}
                </p>
              ) : null}
            </div>
            {ev.tem_comprovante ? (
              <button
                type="button"
                className="erp-btn-outline erp-btn-xs shrink-0 inline-flex items-center gap-1"
                disabled={abrindoId === ev.evento_id}
                onClick={() => void abrirComprovante(ev)}
              >
                {abrindoId === ev.evento_id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <FileText className="h-3 w-3" />
                )}
                Comprovante
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="text-[10px] text-muted-foreground">
        A última CC-e autorizada é a vigente. Eventos anteriores permanecem no histórico para auditoria.
      </p>
    </div>
  );
}

function BlocoPreviaCce({
  contexto,
  textoCorrecao,
  geradoEm,
}: {
  contexto: NFeCartaCorrecaoContexto;
  textoCorrecao: string;
  geradoEm: string;
}) {
  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/20 p-3 text-sm">
      <div className="text-center border-b border-border pb-2">
        <p className="font-semibold text-base">Representação Gráfica de CC-e</p>
        <p className="text-xs text-muted-foreground">Carta de Correção Eletrônica</p>
        <p className="text-xs mt-1">{contexto.emitente}</p>
      </div>

      <p className="text-xs font-semibold text-center rounded-md border border-amber-600/50 bg-amber-500/10 text-amber-900 dark:text-amber-100 px-2 py-1.5">
        {MSG_PREVIA_SEM_TRANSMISSAO}
      </p>

      {contexto.homologacao ? (
        <p className="text-xs font-medium text-center rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100 px-2 py-1">
          HOMOLOGAÇÃO — SEM VALOR FISCAL
        </p>
      ) : null}

      <p
        className={cn(
          'text-xs rounded-md border px-2 py-1.5',
          contexto.homologacao
            ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
            : 'border-slate-500/30 bg-slate-500/5 text-muted-foreground',
        )}
      >
        <span className="font-medium">Ambiente:</span> {contexto.ambienteLabel}
      </p>

      {contexto.mensagemMultiplas ? (
        <p className="text-xs rounded-md border border-blue-500/30 bg-blue-500/5 px-2 py-1.5">
          {contexto.mensagemMultiplas}
        </p>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <CampoPrevia label="Emitente" value={contexto.emitente} />
        <CampoPrevia label="Destinatário" value={contexto.destinatario} />
        <CampoPrevia label="Número NF-e" value={contexto.numero} />
        <CampoPrevia label="Série" value={contexto.serie} />
        <CampoPrevia label="Sequência prevista do evento" value={String(contexto.sequenciaPrevista)} />
        <CampoPrevia label="Prévia gerada em" value={formatDateTimeBr(geradoEm)} />
      </div>

      <CampoPrevia label="Chave de acesso" value={contexto.chaveAcesso} mono />

      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide">Correções a serem consideradas</p>
        <p className="text-sm whitespace-pre-wrap break-words rounded-md border-2 border-border bg-background p-3 min-h-[6rem]">
          {textoCorrecao}
        </p>
      </div>

      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs">
        <p className="font-medium mb-1">Limitações da Carta de Correção</p>
        <p className="text-muted-foreground">{MSG_O_QUE_CCE_NAO_PODE_CORRIGIR}</p>
      </div>

      <p className="text-[10px] text-center text-muted-foreground">
        Documento de prévia — não transmitido à SEFAZ
      </p>
    </div>
  );
}

export function NFeCartaCorrecaoModal({
  open,
  nfeId,
  homologacao,
  contextoInicial,
  onClose,
  onEmitida,
}: Props) {
  const [etapa, setEtapa] = useState<Etapa>('redigir');
  const [texto, setTexto] = useState('');
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [contexto, setContexto] = useState<NFeCartaCorrecaoContexto | null>(contextoInicial ?? null);
  const [contextoLoading, setContextoLoading] = useState(false);
  const [previaGeradaEm, setPreviaGeradaEm] = useState('');
  const [resultado, setResultado] = useState<NFeCartaCorrecaoResponse | null>(null);
  const [erroTransmissao, setErroTransmissao] = useState<string | null>(null);
  const [textoBaseAplicado, setTextoBaseAplicado] = useState(false);

  const textoLimpo = useMemo(() => texto.trim(), [texto]);
  const tamanho = textoLimpo.length;
  const textoValido = tamanho >= TAMANHO_MINIMO_CORRECAO && texto.length <= TAMANHO_MAXIMO_CORRECAO;

  const carregarDados = useCallback(async () => {
    if (!nfeId) return;
    setContextoLoading(true);
    try {
      const dados = await nfeSaidasService.cartaCorrecaoDados(nfeId);
      if (!dados.ok) {
        toast.error(dados.mensagem || 'Não foi possível carregar dados da CC-e.');
        return;
      }
      setContexto(mapCartaCorrecaoDadosToContexto(dados));
      if (!textoBaseAplicado && dados.texto_consolidado_base) {
        setTexto(dados.texto_consolidado_base);
        setTextoBaseAplicado(true);
      }
    } catch (e) {
      if (!contextoInicial) setContexto(null);
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar dados da CC-e.' }));
    } finally {
      setContextoLoading(false);
    }
  }, [nfeId, contextoInicial, textoBaseAplicado]);

  useEffect(() => {
    if (!open) {
      setEtapa('redigir');
      setTexto('');
      setTextoBaseAplicado(false);
      setLoading(false);
      setPdfLoading(false);
      setContexto(contextoInicial ?? null);
      setContextoLoading(false);
      setPreviaGeradaEm('');
      setResultado(null);
      setErroTransmissao(null);
    }
  }, [open, contextoInicial]);

  useEffect(() => {
    if (!open || !nfeId) return;
    if (contextoInicial) setContexto(contextoInicial);
    void carregarDados();
  }, [open, nfeId, contextoInicial, carregarDados]);

  const executarTransmissao = async () => {
    if (!nfeId || loading || !textoValido) return;
    setErroTransmissao(null);
    setLoading(true);
    setEtapa('transmitindo');
    try {
      const res = await nfeSaidasService.emitirCartaCorrecao(nfeId, { texto_correcao: textoLimpo });
      setResultado(res);
      if (res.ok) {
        setEtapa('resultado');
        toast.success(res.mensagem || 'Carta de Correção registrada na SEFAZ.');
        onEmitida?.(res);
      } else {
        const msg = res.mensagem || res.xmotivo || res.xMotivo || 'A SEFAZ não registrou a CC-e.';
        setErroTransmissao(msg);
        setEtapa('erro');
        toast.error(msg);
      }
    } catch (e) {
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível transmitir a Carta de Correção.' });
      setErroTransmissao(msg);
      setEtapa('erro');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const abrirPdfPrevia = async () => {
    if (!nfeId || !textoValido || pdfLoading) return;
    setPdfLoading(true);
    try {
      const blob = await nfeSaidasService.previaCartaCorrecaoPdfBlob(nfeId, { texto_correcao: textoLimpo });
      openCcePdfBlob(blob, `previa-cce-nfe-${nfeId}.pdf`);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível gerar o PDF da prévia.' }));
    } finally {
      setPdfLoading(false);
    }
  };

  const abrirComprovanteResultado = async () => {
    if (!nfeId || !resultado?.evento_id || pdfLoading) return;
    setPdfLoading(true);
    try {
      const blob = await nfeSaidasService.comprovanteCartaCorrecaoPdfBlob(nfeId, resultado.evento_id);
      openCcePdfBlob(blob, `comprovante-cce-nfe-${nfeId}.pdf`);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível abrir o comprovante da CC-e.' }));
    } finally {
      setPdfLoading(false);
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && etapa !== 'transmitindo') onClose();
  };

  const irParaPrevia = async () => {
    if (!nfeId || !textoValido) return;
    setErroTransmissao(null);
    setLoading(true);
    try {
      const previa = await nfeSaidasService.previaCartaCorrecao(nfeId, { texto_correcao: textoLimpo });
      if (!previa.ok) {
        toast.error(previa.mensagem || 'Não foi possível montar a prévia da CC-e.');
        return;
      }
      setContexto(mapCartaCorrecaoDadosToContexto(previa));
      setPreviaGeradaEm(previa.previa_em || new Date().toISOString());
      setEtapa('previa');
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível montar a prévia da CC-e.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>Carta de Correção Eletrônica (CC-e)</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-left text-foreground">
              <IndicadorEtapas etapa={etapa} />

              {contextoLoading && etapa === 'redigir' ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando dados da NF-e…
                </div>
              ) : null}

              {etapa === 'redigir' ? (
                <>
                  <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
                    <strong>Evento fiscal SEFAZ (110110).</strong> Redija a correção, pré-visualize o conteúdo e só
                    então transmita à SEFAZ. Nada é enviado antes da confirmação explícita.
                  </p>
                  {contexto?.mensagemConsolidar ? (
                    <p className="text-xs rounded-md border border-emerald-600/30 bg-emerald-600/5 px-2 py-1.5 text-emerald-900 dark:text-emerald-100">
                      {contexto.mensagemConsolidar}
                    </p>
                  ) : null}
                  {contexto?.mensagemMultiplas ? (
                    <p className="text-xs rounded-md border border-blue-500/30 bg-blue-500/5 px-2 py-1.5">
                      {contexto.mensagemMultiplas}
                    </p>
                  ) : null}
                  {contexto?.cceAnteriores?.length && nfeId ? (
                    <ListaCceAnteriores anteriores={contexto.cceAnteriores} nfeId={nfeId} />
                  ) : null}
                  <p className="text-xs text-muted-foreground">{MSG_LIMITES_CCE}</p>
                  <div className="space-y-1.5">
                    <label htmlFor="cce-texto" className="text-sm font-medium">
                      Correções a serem consideradas <span className="text-destructive">*</span>
                    </label>
                    <Textarea
                      id="cce-texto"
                      value={texto}
                      onChange={(e) => setTexto(e.target.value)}
                      rows={8}
                      maxLength={TAMANHO_MAXIMO_CORRECAO}
                      placeholder={
                        contexto?.textoConsolidadoBase
                          ? 'Revise as correções anteriores e adicione novas linhas conforme necessário (Enter para nova correção).'
                          : 'Descreva as correções (mín. 15 caracteres). Use Enter para separar correções e linhas em branco entre elas.'
                      }
                      disabled={loading}
                      className="font-mono text-sm whitespace-pre-wrap"
                    />
                    <p
                      className={`text-xs ${tamanho > 0 && !textoValido ? 'text-destructive' : 'text-muted-foreground'}`}
                    >
                      {tamanho}/{TAMANHO_MAXIMO_CORRECAO} caracteres
                      {tamanho > 0 && tamanho < TAMANHO_MINIMO_CORRECAO
                        ? ` — mínimo ${TAMANHO_MINIMO_CORRECAO}`
                        : ''}
                    </p>
                  </div>
                </>
              ) : null}

              {etapa === 'previa' && contexto ? (
                <>
                  <BlocoPreviaCce
                    contexto={contexto}
                    textoCorrecao={textoLimpo}
                    geradoEm={previaGeradaEm || contexto.previaEm || new Date().toISOString()}
                  />
                  {contexto.cceAnteriores?.length && nfeId ? (
                    <ListaCceAnteriores anteriores={contexto.cceAnteriores} nfeId={nfeId} />
                  ) : null}
                </>
              ) : null}

              {etapa === 'previa' && contextoLoading && !contexto ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando dados da NF-e para a prévia…
                </div>
              ) : null}

              {etapa === 'confirmacao' ? (
                <div className="space-y-3">
                  <p className="flex items-start gap-2 text-destructive font-medium">
                    <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                    {MSG_CONFIRMACAO_TRANSMISSAO_CCE}
                  </p>
                  <p className="text-xs">
                    O evento será enviado ao ambiente <strong>{contexto?.ambienteLabel ?? '—'}</strong>. Esta ação
                    não altera o XML autorizado da NF-e, mas registra o evento na SEFAZ.
                  </p>
                  {contexto ? (
                    <BlocoPreviaCce
                      contexto={contexto}
                      textoCorrecao={textoLimpo}
                      geradoEm={previaGeradaEm || contexto.previaEm || new Date().toISOString()}
                    />
                  ) : null}
                </div>
              ) : null}

              {etapa === 'transmitindo' ? (
                <div className="flex flex-col items-center gap-3 py-8 text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <p className="font-medium">Transmitindo CC-e para a SEFAZ…</p>
                  <p className="text-xs text-muted-foreground">Aguarde. Não feche esta janela.</p>
                </div>
              ) : null}

              {etapa === 'resultado' && resultado ? (
                <div className="space-y-3">
                  <p className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-medium">
                    <CheckCircle2 className="h-5 w-5" />
                    CC-e transmitida — retorno SEFAZ
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                    <CampoPrevia label="Ambiente" value={resultado.ambiente_label || resultado.ambiente || '—'} />
                    <CampoPrevia label="cStat" value={resultado.cstat || resultado.cStat || '—'} />
                    <CampoPrevia
                      label="xMotivo"
                      value={resultado.xmotivo || resultado.xMotivo || '—'}
                    />
                    <CampoPrevia
                      label="Protocolo"
                      value={resultado.protocolo || resultado.protocolo_evento || '—'}
                    />
                    <CampoPrevia
                      label="Sequência"
                      value={String(resultado.sequencia_evento ?? contexto?.sequenciaPrevista ?? '—')}
                    />
                    <CampoPrevia
                      label="Transmissão em"
                      value={resultado.emitido_em ? formatDateTimeBr(resultado.emitido_em) : '—'}
                    />
                  </div>
                  {resultado.texto_correcao ? (
                    <div className="text-xs whitespace-pre-wrap border-t pt-2 text-muted-foreground">
                      <span className="font-medium text-foreground">Texto transmitido:</span> {resultado.texto_correcao}
                    </div>
                  ) : null}
                  {resultado.evento_id ? (
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1.5"
                      disabled={pdfLoading}
                      onClick={() => void abrirComprovanteResultado()}
                    >
                      {pdfLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ExternalLink className="h-4 w-4" />
                      )}
                      Abrir comprovante da CC-e
                    </button>
                  ) : null}
                </div>
              ) : null}

              {etapa === 'erro' ? (
                <div className="space-y-3">
                  <p className="flex items-start gap-2 text-destructive font-medium">
                    <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                    Falha na transmissão da CC-e
                  </p>
                  <p className="text-sm rounded-md border border-destructive/30 bg-destructive/5 p-3">
                    {erroTransmissao || resultado?.xmotivo || resultado?.xMotivo || 'Erro desconhecido.'}
                  </p>
                  {resultado && (resultado.cstat || resultado.cStat) ? (
                    <p className="text-xs text-muted-foreground">
                      cStat {resultado.cstat || resultado.cStat}: {resultado.xmotivo || resultado.xMotivo}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="flex-wrap gap-2">
          {etapa === 'redigir' ? (
            <>
              <AlertDialogCancel disabled={loading}>Cancelar</AlertDialogCancel>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm"
                disabled={loading || !nfeId || !textoValido}
                onClick={() => void irParaPrevia()}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1 inline" /> : null}
                Pré-visualizar CC-e
              </button>
            </>
          ) : null}

          {etapa === 'previa' ? (
            <>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={loading || pdfLoading}
                onClick={() => setEtapa('redigir')}
              >
                Voltar à redação
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                disabled={loading || pdfLoading || !nfeId || !textoValido}
                onClick={() => void abrirPdfPrevia()}
              >
                {pdfLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileText className="h-4 w-4" />
                )}
                Visualizar PDF da prévia
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm"
                disabled={loading || !contexto}
                onClick={() => setEtapa('confirmacao')}
              >
                Transmitir CC-e
              </button>
            </>
          ) : null}

          {etapa === 'confirmacao' ? (
            <>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={loading}
                onClick={() => setEtapa('previa')}
              >
                Voltar à prévia
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={loading || !nfeId}
                onClick={() => void executarTransmissao()}
              >
                Emitir Carta de Correção
              </button>
            </>
          ) : null}

          {etapa === 'erro' ? (
            <>
              <AlertDialogCancel disabled={loading}>Fechar</AlertDialogCancel>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={loading}
                onClick={() => {
                  setErroTransmissao(null);
                  setEtapa('previa');
                }}
              >
                Voltar à prévia
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm"
                disabled={loading || !nfeId}
                onClick={() => setEtapa('confirmacao')}
              >
                Tentar transmitir novamente
              </button>
            </>
          ) : null}

          {etapa === 'resultado' ? (
            <button type="button" className="erp-btn-primary erp-btn-sm" onClick={onClose}>
              Fechar
            </button>
          ) : null}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
