import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const MOTIVO_MIN = 10;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  avisoSefaz?: string;
  detalhes?: React.ReactNode;
  confirmLabel: string;
  loading?: boolean;
  onConfirm: (motivo: string) => void | Promise<void>;
};

export function MotivoAcaoDestrutivaModal({
  open,
  onOpenChange,
  title,
  description,
  avisoSefaz,
  detalhes,
  confirmLabel,
  loading = false,
  onConfirm,
}: Props) {
  const [motivo, setMotivo] = useState('');
  const [erro, setErro] = useState<string | null>(null);

  const fechar = () => {
    if (loading) return;
    setMotivo('');
    setErro(null);
    onOpenChange(false);
  };

  const confirmar = async () => {
    const m = motivo.trim();
    if (m.length < MOTIVO_MIN) {
      setErro(`Informe um motivo com pelo menos ${MOTIVO_MIN} caracteres.`);
      return;
    }
    setErro(null);
    await onConfirm(m);
    setMotivo('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? onOpenChange(true) : fechar())}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {avisoSefaz ? (
          <p className="text-sm rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100 px-3 py-2">
            {avisoSefaz}
          </p>
        ) : null}
        {detalhes}
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="motivo-acao">
            Motivo do estorno/descarte
          </label>
          <textarea
            id="motivo-acao"
            className="erp-input w-full min-h-[88px] text-sm"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ex.: erro de quantidade antes da emissão"
            disabled={loading}
          />
          {erro ? <p className="text-xs text-destructive">{erro}</p> : null}
        </div>
        <DialogFooter className="gap-2 sm:gap-0">
          <button type="button" className="erp-btn-outline" disabled={loading} onClick={fechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary bg-destructive hover:bg-destructive/90 border-destructive"
            disabled={loading}
            onClick={() => void confirmar()}
          >
            {loading ? 'Processando…' : confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
