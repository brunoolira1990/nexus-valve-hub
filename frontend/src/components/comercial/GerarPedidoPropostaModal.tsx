import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/Modal';
import { formatMoneyBr } from '@/lib/numberFormat';
import { itemPodeSelecionarParaPedido, labelStatusItemProposta } from '@/lib/propostaStatus';
import type { AcaoItensNaoSelecionados, ItemProposta, Proposta } from '@/types';

function valorTotalItem(it: ItemProposta): number {
  const qtd = Number(it.quantidade_negociada ?? it.quantidade ?? 0);
  const preco = Number(it.preco_por_unidade_negociada ?? it.valor_unitario ?? it.preco_final ?? 0);
  return qtd * preco - Number(it.desconto ?? 0);
}

type Props = {
  open: boolean;
  proposta: Proposta | null;
  loading?: boolean;
  onClose: () => void;
  onConfirm: (payload: {
    itens: { proposta_item_id: number }[];
    acao_itens_nao_selecionados: AcaoItensNaoSelecionados;
    observacao: string;
  }) => void;
};

export function GerarPedidoPropostaModal({ open, proposta, loading, onClose, onConfirm }: Props) {
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [acao, setAcao] = useState<AcaoItensNaoSelecionados>('MANTER_PENDENTE');
  const [observacao, setObservacao] = useState('');

  useEffect(() => {
    if (!open || !proposta) return;
    const elegiveis = proposta.itens.filter((it) => itemPodeSelecionarParaPedido(it));
    setSelecionados(elegiveis.map((it) => it.id));
    setAcao('MANTER_PENDENTE');
    setObservacao('');
  }, [open, proposta]);

  const itens = proposta?.itens ?? [];
  const totalSelecionado = useMemo(
    () => itens.filter((it) => selecionados.includes(it.id)).reduce((acc, it) => acc + valorTotalItem(it), 0),
    [itens, selecionados],
  );

  const toggle = (id: number, pode: boolean) => {
    if (!pode) return;
    setSelecionados((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  return (
    <Modal open={open} onClose={onClose} title="Gerar Pedido de Venda a partir da Proposta" size="lg">
      {!proposta ? null : (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Selecione os itens que entrarão neste pedido. Itens já convertidos ou cancelados não podem ser selecionados.
          </p>
          <div className="overflow-x-auto border border-border rounded-md">
            <table className="erp-table w-full text-sm">
              <thead>
                <tr>
                  <th className="w-10" />
                  <th>Produto</th>
                  <th>Qtd</th>
                  <th>V. unit.</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((it) => {
                  const pode = itemPodeSelecionarParaPedido(it);
                  const st = it.status_comercial || 'PENDENTE';
                  const semProduto = !it.produto_id && !['CONVERTIDO_EM_PEDIDO', 'CANCELADO', 'PERDIDO'].includes(st.toUpperCase());
                  return (
                    <tr key={it.id} className={!pode ? 'opacity-60' : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selecionados.includes(it.id)}
                          disabled={!pode || loading}
                          onChange={() => toggle(it.id, pode)}
                        />
                      </td>
                      <td>
                        <div className="font-medium">{it.produto_nome || it.descricao_avulsa || '—'}</div>
                        {it.pedido_venda_numero ? (
                          <div className="text-xs text-muted-foreground">Pedido: {it.pedido_venda_numero}</div>
                        ) : null}
                        {semProduto ? (
                          <div className="text-xs text-warning">Pendente produto — vincule antes de selecionar</div>
                        ) : null}
                      </td>
                      <td>{it.quantidade_negociada ?? it.quantidade}</td>
                      <td>{formatMoneyBr(it.preco_por_unidade_negociada ?? it.valor_unitario ?? 0)}</td>
                      <td>{formatMoneyBr(valorTotalItem(it))}</td>
                      <td>{labelStatusItemProposta(st)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div>
            <p className="text-sm font-medium">O que fazer com os itens não selecionados?</p>
            <label className="flex items-center gap-2 mt-2 text-sm">
              <input
                type="radio"
                name="acao_itens"
                checked={acao === 'MANTER_PENDENTE'}
                disabled={loading}
                onChange={() => setAcao('MANTER_PENDENTE')}
              />
              Manter pendentes para pedido futuro
            </label>
            <label className="flex items-center gap-2 mt-1 text-sm">
              <input
                type="radio"
                name="acao_itens"
                checked={acao === 'CANCELAR'}
                disabled={loading}
                onChange={() => setAcao('CANCELAR')}
              />
              Cancelar/perder itens não selecionados
            </label>
          </div>
          <div>
            <label className="erp-label">Observação (opcional)</label>
            <textarea
              className="erp-input mt-1 w-full min-h-[72px]"
              value={observacao}
              disabled={loading}
              onChange={(e) => setObservacao(e.target.value)}
              placeholder="Ex.: Cliente aprovou apenas o item X para compra imediata"
            />
          </div>
          <p className="text-sm">
            Total selecionado: <strong>{formatMoneyBr(totalSelecionado)}</strong>
          </p>
          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <button type="button" className="erp-btn-outline" disabled={loading} onClick={onClose}>
              Cancelar
            </button>
            <button
              type="button"
              className="erp-btn-primary"
              disabled={loading || selecionados.length === 0}
              onClick={() =>
                onConfirm({
                  itens: selecionados.map((id) => ({ proposta_item_id: id })),
                  acao_itens_nao_selecionados: acao,
                  observacao: observacao.trim(),
                })
              }
            >
              {loading ? 'Gerando…' : 'Gerar Pedido de Venda'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
