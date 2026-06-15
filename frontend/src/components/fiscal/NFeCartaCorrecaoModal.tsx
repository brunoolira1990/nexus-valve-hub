import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
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
  buildCartaCorrecaoContextoFromNfe,
  type NFeCartaCorrecaoContexto,
} from '@/lib/nfeCartaCorrecaoPreview';
import { nfeSaidasService, type NFeCartaCorrecaoResponse } from '@/services/api/fiscal';
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
      <div>
        <p className="font-semibold">Prévia da Carta de Correção Eletrônica — CC-e</p>
        <p className="text-xs text-muted-foreground mt-0.5">Evento fiscal modelo 110110 — somente visualização</p>
      </div>

      <p
        className={cn(
          'text-xs rounded-md border px-2 py-1.5',
          contexto.homologacao
            ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
            : 'border-red-600/30 bg-red-950/5 text-red-800 dark:text-red-300',
        )}
      >
        <span className="font-medium">Ambiente:</span> {contexto.ambienteLabel}
        {' — '}
        {contexto.homologacao ? MSG_AVISO_CCE_HOMOLOG : MSG_AVISO_CCE_PRODUCAO}
      </p>

      <p className="text-xs text-muted-foreground border border-dashed rounded px-2 py-1.5">{MSG_PREVIA_SEM_TRANSMISSAO}</p>

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
        <p className="text-xs font-medium text-muted-foreground">Texto da correção</p>
        <p className="text-sm whitespace-pre-wrap rounded-md border bg-background p-2">{textoCorrecao}</p>
      </div>

      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs">
        <p className="font-medium mb-1">O que a CC-e não pode corrigir</p>
        <p className="text-muted-foreground">{MSG_O_QUE_CCE_NAO_PODE_CORRIGIR}</p>
      </div>
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
  const [contexto, setContexto] = useState<NFeCartaCorrecaoContexto | null>(contextoInicial ?? null);
  const [contextoLoading, setContextoLoading] = useState(false);
  const [previaGeradaEm, setPreviaGeradaEm] = useState('');
  const [resultado, setResultado] = useState<NFeCartaCorrecaoResponse | null>(null);
  const [erroTransmissao, setErroTransmissao] = useState<string | null>(null);

  const textoLimpo = useMemo(() => texto.trim(), [texto]);
  const tamanho = textoLimpo.length;
  const textoValido = tamanho >= TAMANHO_MINIMO_CORRECAO && texto.length <= TAMANHO_MAXIMO_CORRECAO;

  useEffect(() => {
    if (!open) {
      setEtapa('redigir');
      setTexto('');
      setLoading(false);
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

    let cancelado = false;
    setContextoLoading(true);
    void Promise.all([nfeSaidasService.getById(nfeId), nfeSaidasService.eventosNFeSaida(nfeId)])
      .then(([nfe, ev]) => {
        if (cancelado) return;
        setContexto(buildCartaCorrecaoContextoFromNfe(nfe, { homologacao, eventos: ev.eventos }));
      })
      .catch(() => {
        if (!cancelado && !contextoInicial) setContexto(null);
      })
      .finally(() => {
        if (!cancelado) setContextoLoading(false);
      });

    return () => {
      cancelado = true;
    };
  }, [open, nfeId, homologacao, contextoInicial]);

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

  const handleOpenChange = (next: boolean) => {
    if (!next && etapa !== 'transmitindo') onClose();
  };

  const irParaPrevia = () => {
    setPreviaGeradaEm(new Date().toISOString());
    setErroTransmissao(null);
    setEtapa('previa');
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>Carta de Correção Eletrônica (CC-e)</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-left text-foreground">
              <IndicadorEtapas etapa={etapa} />

              {etapa === 'redigir' ? (
                <>
                  <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
                    <strong>Evento fiscal SEFAZ (110110).</strong> Redija a correção, pré-visualize o conteúdo e só
                    então transmita à SEFAZ. Nada é enviado antes da confirmação explícita.
                  </p>
                  <p className="text-xs text-muted-foreground">{MSG_LIMITES_CCE}</p>
                  <div className="space-y-1.5">
                    <label htmlFor="cce-texto" className="text-sm font-medium">
                      Texto da correção <span className="text-destructive">*</span>
                    </label>
                    <Textarea
                      id="cce-texto"
                      value={texto}
                      onChange={(e) => setTexto(e.target.value)}
                      rows={6}
                      maxLength={TAMANHO_MAXIMO_CORRECAO}
                      placeholder="Descreva de forma clara e objetiva a correção (mín. 15 caracteres)."
                      disabled={loading}
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
                <BlocoPreviaCce contexto={contexto} textoCorrecao={textoLimpo} geradoEm={previaGeradaEm} />
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
                      geradoEm={previaGeradaEm || new Date().toISOString()}
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
                onClick={irParaPrevia}
              >
                Pré-visualizar CC-e
              </button>
            </>
          ) : null}

          {etapa === 'previa' ? (
            <>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={loading}
                onClick={() => setEtapa('redigir')}
              >
                Voltar à redação
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
