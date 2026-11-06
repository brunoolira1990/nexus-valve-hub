import { forwardRef, useImperativeHandle, useState } from 'react';
import { toast } from 'sonner';

import { NFeEntradaReabrirModal } from '@/components/fiscal/NFeEntradaReabrirModal';
import type { ResultadoReaberturaEntradaFornecedor } from '@/types';

/**
 * Bloco de REABERTURA da entrada de fornecedor (PR 6 da Fase 2).
 *
 * Wrapper BURRO extraído do NFeEntradaConferenciaPanel: é dono do estado interno
 * `open` do modal de reabertura e instancia o NFeEntradaReabrirModal. Não toca em
 * nenhum estado compartilhado do painel (setDados / hydrateProdutoCache / load /
 * updateItem) — tudo que acontece depois do sucesso é delegado pelos props.
 *
 * O gatilho (botão "Reabrir para correção") continua no rodapé do painel porque
 * vive no grupo de ações operacionais junto com devolução / contas a pagar, sob a
 * mesma condição `acaoOperacionalDisponivel` e o mesmo `disabled={busy}`. Para
 * abrir o modal sem devolver o estado para o painel, o bloco expõe um handle
 * imperativo `abrir()` via forwardRef.
 */
export type ReaberturaEntradaBlocoProps = {
  nfId: number;
  embedded: boolean;
  /** Notifica o contêiner de que o documento mudou (era notifyUpdated no painel). */
  onUpdated?: () => void;
  /** Recebe o resultado da reabertura; o painel aplica setDados + hydrateProdutoCache. */
  onConferenciaReaberta: (resultado: ResultadoReaberturaEntradaFornecedor) => void;
  /** Navegação para a rota de conferência — só chamada quando !embedded. */
  onNavigateConferencia: () => void;
};

export type ReaberturaEntradaBlocoHandle = {
  abrir: () => void;
};

export const ReaberturaEntradaBloco = forwardRef<
  ReaberturaEntradaBlocoHandle,
  ReaberturaEntradaBlocoProps
>(function ReaberturaEntradaBloco({ nfId, embedded, onUpdated, onConferenciaReaberta, onNavigateConferencia }, ref) {
  const [open, setOpen] = useState(false);

  useImperativeHandle(ref, () => ({ abrir: () => setOpen(true) }), []);

  const handleClose = (next: boolean) => setOpen(next);

  const handleSuccess = (resultado: ResultadoReaberturaEntradaFornecedor) => {
    onConferenciaReaberta(resultado);
    toast.success(resultado.mensagem);
    onUpdated?.();
    if (!embedded) {
      onNavigateConferencia();
    }
  };

  return (
    <NFeEntradaReabrirModal
      open={open}
      nfeHistoricaId={nfId}
      onOpenChange={handleClose}
      onSuccess={handleSuccess}
    />
  );
});
