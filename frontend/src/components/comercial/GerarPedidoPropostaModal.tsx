import { Fragment, useEffect, useMemo, useState } from 'react';
import { Modal, ModalFooterActions } from '@/components/Modal';
import { ProdutoComercialField } from '@/components/comercial/ProdutoComercialField';
import { formatMoneyBr } from '@/lib/numberFormat';
import { formatPrecoUnitarioBRL } from '@/lib/pedidoVendaValorUnitario';
import { itemPodeSelecionarParaPedido, labelStatusItemProposta } from '@/lib/propostaStatus';
import { apiErrorMessage } from '@/services/api/config';
import { propostasService } from '@/services/api/comercial';
import { produtosService } from '@/services/api/produtos';
import type { AcaoItensNaoSelecionados, ItemProposta, Proposta, Produto } from '@/types';

function valorTotalItem(it: ItemProposta): number {
  const qtd = Number(it.quantidade_negociada ?? it.quantidade ?? 0);
  const preco = Number(it.preco_por_unidade_negociada ?? it.valor_unitario ?? it.preco_final ?? 0);
  return qtd * preco - Number(it.desconto ?? 0);
}

/** Item avulso/pendente que ainda pode receber vínculo de produto. */
export function itemPendenteProdutoParaRegularizar(it: ItemProposta): boolean {
  if (it.produto_id) return false;
  const st = (it.status_comercial || 'PENDENTE').toUpperCase();
  return !['CONVERTIDO_EM_PEDIDO', 'CANCELADO', 'PERDIDO'].includes(st);
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
  onPropostaAtualizada?: (proposta: Proposta) => void;
};

export function GerarPedidoPropostaModal({
  open,
  proposta,
  loading,
  onClose,
  onConfirm,
  onPropostaAtualizada,
}: Props) {
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [acao, setAcao] = useState<AcaoItensNaoSelecionados>('MANTER_PENDENTE');
  const [observacao, setObservacao] = useState('');
  const [regularizarItemId, setRegularizarItemId] = useState<number | null>(null);
  const [itemLinks, setItemLinks] = useState<Record<number, number | null>>({});
  const [novoProdutoDescricao, setNovoProdutoDescricao] = useState<Record<number, string>>({});
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(new Map());
  const [regularizando, setRegularizando] = useState(false);
  const [regularizacaoErro, setRegularizacaoErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !proposta) return;
    const elegiveis = proposta.itens.filter((it) => itemPodeSelecionarParaPedido(it));
    setSelecionados(elegiveis.map((it) => it.id));
    setAcao('MANTER_PENDENTE');
    setObservacao('');
    setRegularizarItemId(null);
    setRegularizacaoErro(null);
    const links: Record<number, number | null> = {};
    const descricoes: Record<number, string> = {};
    proposta.itens.forEach((it) => {
      if (itemPendenteProdutoParaRegularizar(it)) {
        links[it.id] = null;
        descricoes[it.id] = it.descricao_avulsa ?? it.produto_nome ?? '';
      }
    });
    setItemLinks(links);
    setNovoProdutoDescricao(descricoes);
    setProdutoCache(new Map());
  }, [open, proposta]);

  const itens = proposta?.itens ?? [];
  const totalSelecionado = useMemo(
    () => itens.filter((it) => selecionados.includes(it.id)).reduce((acc, it) => acc + valorTotalItem(it), 0),
    [itens, selecionados],
  );
  const qtdPendentesProduto = itens.filter((it) => itemPendenteProdutoParaRegularizar(it)).length;

  const toggle = (id: number, pode: boolean) => {
    if (!pode) return;
    setSelecionados((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const mergeProdutoCache = (produto: Produto) => {
    setProdutoCache((prev) => new Map(prev).set(produto.id, produto));
  };

  const aplicarPropostaAtualizada = (atualizada: Proposta) => {
    onPropostaAtualizada?.(atualizada);
    const elegiveis = atualizada.itens.filter((it) => itemPodeSelecionarParaPedido(it));
    setSelecionados((prev) => {
      const ids = new Set(prev);
      elegiveis.forEach((it) => ids.add(it.id));
      return [...ids];
    });
  };

  const vincularProdutoExistente = async (itemId: number) => {
    if (!proposta) return;
    const produtoId = itemLinks[itemId];
    if (!produtoId) {
      setRegularizacaoErro('Selecione um produto cadastrado para vincular ao item.');
      return;
    }
    setRegularizando(true);
    setRegularizacaoErro(null);
    try {
      const itensAtualizados = proposta.itens.map((it) =>
        it.id === itemId ? { ...it, produto_id: produtoId, descricao_avulsa: '' } : it,
      );
      await propostasService.update(proposta.id, { itens: itensAtualizados });
      const atualizada = await propostasService.getById(proposta.id);
      aplicarPropostaAtualizada(atualizada);
      setRegularizarItemId(null);
    } catch (e) {
      setRegularizacaoErro(apiErrorMessage(e, { fallback: 'Não foi possível vincular o produto ao item.' }));
    } finally {
      setRegularizando(false);
    }
  };

  const criarProdutoParaItem = async (itemId: number) => {
    if (!proposta) return;
    const descricao = (novoProdutoDescricao[itemId] || '').trim();
    if (!descricao) {
      setRegularizacaoErro('Informe a descrição do novo produto.');
      return;
    }
    setRegularizando(true);
    setRegularizacaoErro(null);
    try {
      const produto = await produtosService.create({
        figura: 'AV',
        sufixo: 'LIVRE',
        schedule: 'STD',
        polegada_principal: '1/2"',
        polegada_secundaria: '',
        descricao,
        material: '',
        tipo_peca: '',
        pressao_nominal: '',
        norma: '',
        conexao: '',
        ncm: '',
        preco_custo: 0,
        preco_venda: 0,
        estoque_minimo: 0,
        codigo_completo: '',
      });
      const itensAtualizados = proposta.itens.map((it) =>
        it.id === itemId ? { ...it, produto_id: produto.id, descricao_avulsa: '' } : it,
      );
      await propostasService.update(proposta.id, { itens: itensAtualizados });
      mergeProdutoCache(produto);
      const atualizada = await propostasService.getById(proposta.id);
      aplicarPropostaAtualizada(atualizada);
      setRegularizarItemId(null);
    } catch (e) {
      setRegularizacaoErro(apiErrorMessage(e, { fallback: 'Não foi possível criar o produto para o item.' }));
    } finally {
      setRegularizando(false);
    }
  };

  const bloqueado = Boolean(loading || regularizando);

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Gerar Pedido de Venda a partir da Proposta"
      subtitle={proposta?.numero ? `Proposta ${proposta.numero}` : undefined}
      size={regularizarItemId != null ? 'xl' : 'lg'}
      footer={
        !proposta ? null : (
          <>
            <span className="mr-auto text-sm text-muted-foreground">
              Selecionados: {selecionados.length}/{itens.length} · Total:{' '}
              <strong className="text-primary">{formatMoneyBr(totalSelecionado)}</strong>
            </span>
            <ModalFooterActions
              cancelLabel="Cancelar"
              saveLabel={loading ? 'Gerando…' : 'Gerar Pedido de Venda'}
              saving={bloqueado}
              onCancel={onClose}
              onSave={() =>
                onConfirm({
                  itens: selecionados.map((id) => ({ proposta_item_id: id })),
                  acao_itens_nao_selecionados: acao,
                  observacao: observacao.trim(),
                })
              }
            />
          </>
        )
      }
    >
      {!proposta ? null : (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Selecione os itens que entrarão neste pedido. Itens sem produto cadastrado não podem ser selecionados —
            você pode vinculá-los abaixo ou mantê-los pendentes para um pedido futuro.
          </p>
          {qtdPendentesProduto > 0 ? (
            <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-xs text-muted-foreground leading-relaxed">
              {qtdPendentesProduto} item(ns) pendente(s) de produto. A geração parcial segue disponível para os demais
              itens já vinculados.
            </div>
          ) : null}
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
                  <th className="w-36">Ações</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((it) => {
                  const pode = itemPodeSelecionarParaPedido(it);
                  const st = it.status_comercial || 'PENDENTE';
                  const pendenteProduto = itemPendenteProdutoParaRegularizar(it);
                  const expandir = regularizarItemId === it.id;
                  return (
                    <Fragment key={it.id}>
                      <tr className={!pode ? 'opacity-80' : undefined}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selecionados.includes(it.id)}
                            disabled={!pode || bloqueado}
                            onChange={() => toggle(it.id, pode)}
                          />
                        </td>
                        <td>
                          <div className="font-medium">{it.produto_nome || it.descricao_avulsa || '—'}</div>
                          {it.pedido_venda_numero ? (
                            <div className="text-xs text-muted-foreground">Pedido: {it.pedido_venda_numero}</div>
                          ) : null}
                          {pendenteProduto ? (
                            <div className="text-xs text-warning mt-0.5">
                              Pendente produto — vincule para incluir neste pedido
                            </div>
                          ) : null}
                        </td>
                        <td>{it.quantidade_negociada ?? it.quantidade}</td>
                        <td>{formatPrecoUnitarioBRL(it.preco_por_unidade_negociada ?? it.valor_unitario ?? 0)}</td>
                        <td>{formatMoneyBr(valorTotalItem(it))}</td>
                        <td>{labelStatusItemProposta(st)}</td>
                        <td>
                          {pendenteProduto ? (
                            <button
                              type="button"
                              className="erp-btn-outline erp-btn-sm whitespace-nowrap"
                              disabled={bloqueado}
                              onClick={() => {
                                setRegularizacaoErro(null);
                                setRegularizarItemId(expandir ? null : it.id);
                              }}
                            >
                              {expandir ? 'Fechar' : 'Vincular produto'}
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                      {expandir && pendenteProduto ? (
                        <tr key={`${it.id}-regularizar`}>
                          <td colSpan={7} className="bg-muted/15 p-3">
                            <div className="space-y-3 rounded-md border border-border bg-background p-3">
                              <p className="text-sm font-medium">Regularizar item avulso</p>
                              <p className="text-xs text-muted-foreground">
                                Vincule um produto cadastrado ou crie um novo. Após vincular, o item poderá ser
                                selecionado para este pedido.
                              </p>
                              {regularizacaoErro ? (
                                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                                  {regularizacaoErro}
                                </div>
                              ) : null}
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <div className="md:col-span-2">
                                  <label className="erp-label">Produto cadastrado</label>
                                  <ProdutoComercialField
                                    compact
                                    valueId={itemLinks[it.id] ?? null}
                                    selectedProduto={
                                      itemLinks[it.id] ? produtoCache.get(itemLinks[it.id]!) ?? null : null
                                    }
                                    disabled={bloqueado}
                                    onSelect={(pr) => {
                                      mergeProdutoCache(pr);
                                      setItemLinks((prev) => ({ ...prev, [it.id]: pr.id }));
                                    }}
                                    onClear={() => setItemLinks((prev) => ({ ...prev, [it.id]: null }))}
                                  />
                                </div>
                                <button
                                  type="button"
                                  className="erp-btn-outline"
                                  disabled={!itemLinks[it.id] || bloqueado}
                                  onClick={() => void vincularProdutoExistente(it.id)}
                                >
                                  {regularizando ? 'Vinculando…' : 'Confirmar vínculo'}
                                </button>
                                <div className="md:col-span-2">
                                  <label className="erp-label">Ou criar novo produto</label>
                                  <input
                                    className="erp-input mt-1 w-full"
                                    placeholder="Descrição para novo produto"
                                    value={novoProdutoDescricao[it.id] ?? ''}
                                    disabled={bloqueado}
                                    onChange={(e) =>
                                      setNovoProdutoDescricao((prev) => ({ ...prev, [it.id]: e.target.value }))
                                    }
                                  />
                                </div>
                                <button
                                  type="button"
                                  className="erp-btn-outline"
                                  disabled={bloqueado}
                                  onClick={() => void criarProdutoParaItem(it.id)}
                                >
                                  {regularizando ? 'Criando…' : 'Criar e vincular produto'}
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
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
                disabled={bloqueado}
                onChange={() => setAcao('MANTER_PENDENTE')}
              />
              Manter pendentes para pedido futuro
            </label>
            <label className="flex items-center gap-2 mt-1 text-sm">
              <input
                type="radio"
                name="acao_itens"
                checked={acao === 'CANCELAR'}
                disabled={bloqueado}
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
              disabled={bloqueado}
              onChange={(e) => setObservacao(e.target.value)}
              placeholder="Ex.: Cliente aprovou apenas o item X para compra imediata"
            />
          </div>
        </div>
      )}
    </Modal>
  );
}
