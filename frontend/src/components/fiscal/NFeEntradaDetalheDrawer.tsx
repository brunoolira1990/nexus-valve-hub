import { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NFeEntradaEmissaoPanel } from '@/components/fiscal/NFeEntradaEmissaoPanel';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import {
  emitenteDestinatarioLabelNfeEntrada,
  exibirAcaoRevisarDados,
  exibirPainelEmissaoEntrada,
  labelStatusOperacionalNfeEntrada,
  labelTipoOrigemNfeEntrada,
} from '@/lib/nfeEntradaOperacionalLabels';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';
import { nfeEntradasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeEntrada } from '@/types';

type Props = {
  nfeId: number | null;
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
};

export function NFeEntradaDetalheDrawer({ nfeId, open, onClose, onChanged }: Props) {
  const [nfe, setNfe] = useState<NFeEntrada | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!open || !nfeId) {
      setNfe(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void nfeEntradasService
      .getById(nfeId)
      .then(setNfe)
      .catch((e) => {
        setNfe(null);
        setError(apiErrorMessage(e));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when drawer opens / id changes
  }, [open, nfeId]);

  return (
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="max-h-[90vh]">
        <DrawerHeader className="border-b border-border pb-4">
          <div className="flex items-start justify-between gap-3">
            <DrawerTitle className="text-left">Detalhes da NF-e de entrada</DrawerTitle>
            <DrawerClose className="rounded-md p-1 hover:bg-muted" aria-label="Fechar">
              <X className="h-4 w-4" />
            </DrawerClose>
          </div>
          <p className="text-sm text-muted-foreground text-left mt-1">
            Resumo operacional — identificação, status e emissão SEFAZ quando aplicável.
          </p>
        </DrawerHeader>

        <div className="overflow-y-auto px-4 py-4 space-y-4 text-sm">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Carregando…
            </div>
          ) : null}
          {error ? <p className="text-destructive">{error}</p> : null}
          {!loading && !error && nfe ? (
            <>
              <div className="nexus-card p-4 space-y-4">
                <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-3">
                  <div>
                    <dt className="text-xs text-muted-foreground">Número / Série</dt>
                    <dd className="font-medium">
                      {nfe.numero}
                      {nfe.serie ? ` / ${nfe.serie}` : ''}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Emissão</dt>
                    <dd>{nfe.data ? formatDateBr(nfe.data) : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Tipo</dt>
                    <dd className="mt-0.5">
                      <StatusBadge status={labelTipoOrigemNfeEntrada(nfe)} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Status operacional</dt>
                    <dd className="mt-0.5">
                      <StatusBadge
                        status={labelStatusOperacionalNfeEntrada(nfe.status_operacional, nfe.status_operacional_label)}
                      />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Valor total</dt>
                    <dd className="font-semibold nexus-numeric">{formatMoneyBRL(nfe.valor_total)}</dd>
                  </div>
                  {nfe.importado_em ? (
                    <div>
                      <dt className="text-xs text-muted-foreground">Importado em</dt>
                      <dd>{formatDateTimeBr(nfe.importado_em)}</dd>
                    </div>
                  ) : null}
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Emitente / Destinatário</dt>
                    <dd>{emitenteDestinatarioLabelNfeEntrada(nfe)}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Chave de acesso</dt>
                    <dd className="font-mono text-xs break-all mt-0.5">{nfe.chave_acesso || '—'}</dd>
                  </div>
                </dl>
                {exibirAcaoRevisarDados(nfe) ? (
                  <p className="text-xs text-muted-foreground border-t border-border pt-3">
                    Para revisar itens e demais dados importados linha a linha, use a ação{' '}
                    <strong className="text-foreground">Revisar dados</strong> na listagem.
                  </p>
                ) : null}
              </div>
              {exibirPainelEmissaoEntrada(nfe) ? (
                <NFeEntradaEmissaoPanel
                  nfe={nfe}
                  onAtualizado={async () => {
                    load();
                    onChanged?.();
                  }}
                />
              ) : null}
            </>
          ) : null}
        </div>

        <DrawerFooter className="border-t border-border">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose}>
            Fechar
          </button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
