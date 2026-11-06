import { forwardRef, useImperativeHandle, useState } from 'react';
import { toast } from 'sonner';

import { NFeGerarDevolucaoCompraModal } from '@/components/fiscal/NFeGerarDevolucaoCompraModal';
import type { ItemConferenciaNFeEntrada, ResultadoGerarSaidaDevolucaoCompra } from '@/types';

/**
 * Bloco de DEVOLUÇÃO da entrada de fornecedor (PR 7 da Fase 2).
 *
 * Wrapper BURRO extraído do NFeEntradaConferenciaPanel: é dono do estado interno
 * `open` do modal de devolução e instancia o NFeGerarDevolucaoCompraModal. Não
 * toca em nenhum estado compartilhado do painel (load / setDados /
 * hydrateProdutoCache / updateItem) — o re-carregamento depois do sucesso é
 * delegado pelo prop `onDevolucaoGerada`.
 *
 * O gatilho (botão "Gerar devolução ao fornecedor") continua no rodapé do painel
 * porque vive no grupo de ações operacionais junto com a reabertura (PR 6), sob a
 * mesma condição `acaoOperacionalDisponivel` e o mesmo `disabled={busy}`. Para
 * abrir o modal sem devolver o estado para o painel, o bloco expõe um handle
 * imperativo `abrir()` via forwardRef.
 *
 * A ordem do onSuccess preserva o disco token-a-token: fecha, toasta com o texto
 * exato do painel, delega o load(). Diferente da reabertura, aqui o onSuccess do
 * disco NÃO tem ramificação embedded/!embedded nem recebe o resultado adiante.
 */
export type DevolucaoEntradaBlocoProps = {
  nfeHistoricaId: number;
  itensConferencia: ItemConferenciaNFeEntrada[];
  /** Recarrega a conferência no painel (era `void load()` no onSuccess extraído). */
  onDevolucaoGerada: () => void;
};

export type DevolucaoEntradaBlocoHandle = {
  abrir: () => void;
};

export const DevolucaoEntradaBloco = forwardRef<
  DevolucaoEntradaBlocoHandle,
  DevolucaoEntradaBlocoProps
>(function DevolucaoEntradaBloco({ nfeHistoricaId, itensConferencia, onDevolucaoGerada }, ref) {
  const [open, setOpen] = useState(false);

  useImperativeHandle(ref, () => ({ abrir: () => setOpen(true) }), []);

  const handleSuccess = (res: ResultadoGerarSaidaDevolucaoCompra) => {
    setOpen(false);
    toast.success(
      `Rascunho ${res.numero} criado (R$ ${res.valor_total}). NF-e de saída #${res.nf_saida_id}.`,
    );
    onDevolucaoGerada();
  };

  return (
    <NFeGerarDevolucaoCompraModal
      open={open}
      nfeHistoricaId={nfeHistoricaId}
      itensConferencia={itensConferencia}
      onClose={() => setOpen(false)}
      onSuccess={handleSuccess}
    />
  );
});
