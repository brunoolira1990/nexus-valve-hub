import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
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
import { nfeSaidasService, type NFeConsultaSituacaoSefazResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';

export const MSG_CONFIRMACAO_CONSULTA_SEFAZ =
  'Esta ação apenas consulta a situação da NF-e na SEFAZ. Não cancela, não corrige e não transmite nova NF-e.';

type Props = {
  open: boolean;
  nfeId: number | null;
  onClose: () => void;
  onConsultaConcluida?: (res: NFeConsultaSituacaoSefazResponse) => void;
};

export function NFeConsultaSefazModal({ open, nfeId, onClose, onConsultaConcluida }: Props) {
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<NFeConsultaSituacaoSefazResponse | null>(null);

  useEffect(() => {
    if (!open) {
      setResultado(null);
      setLoading(false);
    }
  }, [open]);

  const executar = async () => {
    if (!nfeId || loading) return;
    setLoading(true);
    try {
      const res = await nfeSaidasService.consultarSituacaoSefaz(nfeId);
      setResultado(res);
      if (res.ok) {
        toast.success(res.mensagem || 'Consulta SEFAZ concluída.');
        onConsultaConcluida?.(res);
      } else {
        toast.error(res.mensagem || 'Consulta SEFAZ não concluída.');
      }
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível consultar a SEFAZ.' }));
    } finally {
      setLoading(false);
    }
  };

  if (resultado) {
    return (
      <AlertDialog open={open} onOpenChange={(v) => !v && onClose()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Resultado — Consulta SEFAZ</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-left">
                <p>
                  <span className="font-medium">Ambiente:</span> {resultado.ambiente_label || resultado.ambiente}
                </p>
                <p>
                  <span className="font-medium">cStat:</span> {resultado.cstat || resultado.cStat || '—'}
                </p>
                <p>
                  <span className="font-medium">xMotivo:</span> {resultado.xmotivo || resultado.xMotivo || '—'}
                </p>
                {resultado.protocolo || resultado.protocolo_autorizacao ? (
                  <p>
                    <span className="font-medium">Protocolo:</span>{' '}
                    {resultado.protocolo || resultado.protocolo_autorizacao}
                  </p>
                ) : null}
                {resultado.consultado_em ? (
                  <p>
                    <span className="font-medium">Consulta em:</span>{' '}
                    {formatDateTimeBr(resultado.consultado_em)}
                  </p>
                ) : null}
                {resultado.status_local_atualizado ? (
                  <p className="text-xs text-muted-foreground">
                    Status local sincronizado conforme resposta inequívoca da SEFAZ.
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

  return (
    <AlertDialog open={open} onOpenChange={(v) => !v && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Consultar situação na SEFAZ</AlertDialogTitle>
          <AlertDialogDescription>{MSG_CONFIRMACAO_CONSULTA_SEFAZ}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancelar</AlertDialogCancel>
          <AlertDialogAction disabled={loading || !nfeId} onClick={() => void executar()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin inline mr-1" /> : null}
            Consultar SEFAZ
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
