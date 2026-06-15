import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
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
import { Textarea } from '@/components/ui/textarea';
import { nfeSaidasService, type NFeCartaCorrecaoResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';

export const TAMANHO_MINIMO_CORRECAO = 15;
export const TAMANHO_MAXIMO_CORRECAO = 1000;

export const MSG_AVISO_CCE_HOMOLOG =
  'Evento de homologação transmitido à SEFAZ de testes — sem valor fiscal. O XML autorizado da NF-e não será alterado.';

export const MSG_AVISO_CCE_PRODUCAO =
  'Evento fiscal real transmitido à SEFAZ. A Carta de Correção não altera o XML autorizado da NF-e, mas passa a integrar o histórico fiscal do documento.';

export const MSG_LIMITES_CCE =
  'A CC-e corrige apenas informações permitidas pela legislação (texto livre). Não altera valores, impostos, itens, destinatário, datas ou numeração.';

type Props = {
  open: boolean;
  nfeId: number | null;
  homologacao?: boolean;
  onClose: () => void;
  onEmitida?: (res: NFeCartaCorrecaoResponse) => void;
};

type Etapa = 'formulario' | 'confirmacao' | 'resultado';

export function NFeCartaCorrecaoModal({ open, nfeId, homologacao, onClose, onEmitida }: Props) {
  const [etapa, setEtapa] = useState<Etapa>('formulario');
  const [texto, setTexto] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<NFeCartaCorrecaoResponse | null>(null);

  const textoLimpo = useMemo(() => texto.trim(), [texto]);
  const tamanho = textoLimpo.length;
  const textoValido = tamanho >= TAMANHO_MINIMO_CORRECAO && texto.length <= TAMANHO_MAXIMO_CORRECAO;

  useEffect(() => {
    if (!open) {
      setEtapa('formulario');
      setTexto('');
      setLoading(false);
      setResultado(null);
    }
  }, [open]);

  const executar = async () => {
    if (!nfeId || loading || !textoValido) return;
    setLoading(true);
    try {
      const res = await nfeSaidasService.emitirCartaCorrecao(nfeId, { texto_correcao: textoLimpo });
      setResultado(res);
      setEtapa('resultado');
      if (res.ok) {
        toast.success(res.mensagem || 'Carta de Correção registrada na SEFAZ.');
        onEmitida?.(res);
      } else {
        toast.error(res.mensagem || 'Carta de Correção não registrada na SEFAZ.');
      }
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível transmitir a Carta de Correção.' }));
    } finally {
      setLoading(false);
    }
  };

  if (etapa === 'resultado' && resultado) {
    return (
      <AlertDialog open={open} onOpenChange={(v) => !v && onClose()}>
        <AlertDialogContent className="max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>Resultado — Carta de Correção</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-left">
                <p>
                  <span className="font-medium">Ambiente:</span>{' '}
                  {resultado.ambiente_label || resultado.ambiente}
                </p>
                <p>
                  <span className="font-medium">cStat:</span> {resultado.cstat || resultado.cStat || '—'}
                </p>
                <p>
                  <span className="font-medium">xMotivo:</span> {resultado.xmotivo || resultado.xMotivo || '—'}
                </p>
                {resultado.protocolo || resultado.protocolo_evento ? (
                  <p>
                    <span className="font-medium">Protocolo:</span>{' '}
                    {resultado.protocolo || resultado.protocolo_evento}
                  </p>
                ) : null}
                {resultado.sequencia_evento ? (
                  <p>
                    <span className="font-medium">Sequência:</span> {resultado.sequencia_evento}
                  </p>
                ) : null}
                {resultado.emitido_em ? (
                  <p>
                    <span className="font-medium">Transmissão em:</span>{' '}
                    {formatDateTimeBr(resultado.emitido_em)}
                  </p>
                ) : null}
                {resultado.texto_correcao ? (
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap border-t pt-2 mt-2">
                    <span className="font-medium text-foreground">Texto enviado:</span>{' '}
                    {resultado.texto_correcao}
                  </p>
                ) : null}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={onClose}>Fechar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    );
  }

  if (etapa === 'confirmacao') {
    return (
      <AlertDialog open={open} onOpenChange={(v) => !v && onClose()}>
        <AlertDialogContent className="max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              Confirmar transmissão à SEFAZ
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm text-left">
                <p>
                  Você está prestes a transmitir uma <strong>Carta de Correção Eletrônica</strong> à SEFAZ.
                  Esta ação é irreversível no ambiente fiscal.
                </p>
                <p className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs">
                  {homologacao ? MSG_AVISO_CCE_HOMOLOG : MSG_AVISO_CCE_PRODUCAO}
                </p>
                <p className="text-xs whitespace-pre-wrap rounded-md border p-2 bg-muted/30">{textoLimpo}</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading} onClick={() => setEtapa('formulario')}>
              Voltar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={loading || !nfeId}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void executar()}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin inline mr-1" /> : null}
              Transmitir CC-e
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    );
  }

  return (
    <AlertDialog open={open} onOpenChange={(v) => !v && onClose()}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Carta de Correção Eletrônica (CC-e)</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-left">
              <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
                <strong>Atenção:</strong> a CC-e é um evento fiscal transmitido à SEFAZ.{' '}
                {homologacao ? MSG_AVISO_CCE_HOMOLOG : MSG_AVISO_CCE_PRODUCAO}
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
                  rows={5}
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
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={loading || !nfeId || !textoValido}
            onClick={() => setEtapa('confirmacao')}
          >
            Continuar
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
