import { forwardRef, useImperativeHandle, useState } from 'react';
import { toast } from 'sonner';

import { GerarContasPagarNfeEntradaModal } from '@/components/fiscal/GerarContasPagarNfeEntradaModal';
import type { TituloFinanceiro } from '@/services/api/financeiro';

/**
 * Bloco de FINANCEIRO da entrada de fornecedor (PR 8b da Fase 2).
 *
 * Wrapper BURRO extraído do NFeEntradaConferenciaPanel: é dono do estado interno `open`
 * (era `gerarCpOpen`, H19 do mapeamento do PR 5 — estado LOCAL deste bloco) e instancia o
 * GerarContasPagarNfeEntradaModal. Não chama nada do store: o `acoes.load(nfId)` e o
 * `notifyUpdated()` que o onSuccess fazia ficam no painel, alcançados pelo prop `onGerado`.
 *
 * Diferença de padrão frente à reabertura (PR 6): lá o `!embedded` é resolvido DENTRO do
 * wrapper, que recebe `onNavigateConferencia` já pronto. Aqui a condição do disco é
 * COMPOSTA — `titulo?.id && !embedded` — e mistura um dado do resultado com o ambiente.
 * Como o ambiente (`embedded`) e o `navigate` continuam no painel, o wrapper sobe apenas o
 * `tituloId` e o painel decide. É o que mantém o wrapper burro: ele toasta e delega.
 *
 * O fechamento não é reescrito aqui: no disco o próprio modal chama `onClose()` logo depois
 * de `onGenerated` (GerarContasPagarNfeEntradaModal.tsx:127-128), então o `open` já volta a
 * false pelo callback. Fechar também no sucesso adiantaria o efeito em um render e não é o
 * comportamento que estava no painel.
 *
 * O gatilho NÃO migrou para cá: no disco atual o botão "Gerar contas a pagar" vive dentro
 * de <NFeEntradaFinanceiroAcoes onGerar={...}>, no card de grid `dados &&` (painel :560-567)
 * — não no grupo de rodapé das ações operacionais. O painel continua dono desse JSX e chama
 * `abrir()` pelo handle, igual ao PR 6.
 */
export type FinanceiroEntradaBlocoProps = {
  nfId: number;
  /**
   * Recebe `titulo?.id ?? null` do payload do modal. O painel faz load + notifyUpdated e
   * só navega quando houver título E a tela não estiver embutida na Central DF-e.
   */
  onGerado: (tituloId: number | null) => void;
};

export type FinanceiroEntradaBlocoHandle = {
  abrir: () => void;
};

export const FinanceiroEntradaBloco = forwardRef<
  FinanceiroEntradaBlocoHandle,
  FinanceiroEntradaBlocoProps
>(function FinanceiroEntradaBloco({ nfId, onGerado }, ref) {
  const [open, setOpen] = useState(false);

  useImperativeHandle(ref, () => ({ abrir: () => setOpen(true) }), []);

  const handleGenerated = (payload: { titulo: TituloFinanceiro | null }) => {
    toast.success('Contas a pagar geradas com sucesso.');
    onGerado(payload.titulo?.id ?? null);
  };

  return (
    <GerarContasPagarNfeEntradaModal
      open={open}
      nfeEntradaId={nfId}
      onClose={() => setOpen(false)}
      onGenerated={handleGenerated}
    />
  );
});
