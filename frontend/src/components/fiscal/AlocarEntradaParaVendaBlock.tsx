import { useCallback, useEffect, useState } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';
import { apiErrorMessage } from '@/services/api/config';
import {
  LABEL_ESTADO_OPERACIONAL,
  type OpcaoPedidoVendaItemAlocacao,
  type ResumoEntradaVenda,
} from '@/types/alocacaoEntradaVenda';

type Props = {
  itemConferenciaId: number;
  produtoId?: number | null;
  onAtualizado?: () => void;
};

function badgeEstado(estado: ResumoEntradaVenda['estado_operacional']): string {
  if (estado === 'CONCILIADO') return 'erp-badge-success';
  if (estado === 'PARCIAL') return 'erp-badge-warning';
  if (estado === 'DIVERGENTE') return 'erp-badge-danger';
  return 'erp-badge-secondary';
}

export function AlocarEntradaParaVendaBlock({ itemConferenciaId, produtoId, onAtualizado }: Props) {
  const [resumo, setResumo] = useState<ResumoEntradaVenda | null>(null);
  const [erro, setErro] = useState('');
  const [busy, setBusy] = useState(false);
  const [aberto, setAberto] = useState(false);
  const [opcaoPv, setOpcaoPv] = useState<OpcaoPedidoVendaItemAlocacao | null>(null);
  const [quantidade, setQuantidade] = useState('');
  const [editId, setEditId] = useState<number | null>(null);
  const [editQty, setEditQty] = useState('');

  const load = useCallback(async () => {
    try {
      const data = await alocacaoAtendimentoService.resumoEntradaVenda({
        item_conferencia_id: itemConferenciaId,
      });
      setResumo(data);
      setErro('');
      setQuantidade((prev) => prev || data.saldo_entrada || '');
    } catch (e) {
      setErro(apiErrorMessage(e));
    }
  }, [itemConferenciaId]);

  useEffect(() => {
    void load();
  }, [load]);

  const buscarPvItens = useCallback(
    (term: string, limit?: number) =>
      alocacaoAtendimentoService.opcoesPedidosVendaItens(term, {
        limit: limit ?? 20,
        produto_id: produtoId ?? undefined,
      }),
    [produtoId],
  );

  const alocar = async () => {
    if (!opcaoPv) {
      setErro('Selecione um item de Pedido de Venda.');
      return;
    }
    setBusy(true);
    setErro('');
    try {
      const res = await alocacaoAtendimentoService.alocarEntradaVenda({
        item_conferencia_id: itemConferenciaId,
        pedido_venda_item_id: opcaoPv.id,
        quantidade,
      });
      setResumo(res.resumo);
      setOpcaoPv(null);
      setQuantidade(res.resumo.saldo_entrada);
      onAtualizado?.();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const salvarEdicao = async (id: number) => {
    setBusy(true);
    setErro('');
    try {
      const res = await alocacaoAtendimentoService.atualizarQuantidadeEntradaVenda(id, editQty);
      setResumo(res.resumo);
      setEditId(null);
      onAtualizado?.();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const desvincular = async (id: number) => {
    if (!window.confirm('Desvincular esta alocação operacional? Estoque, PC e NF-e não serão alterados.')) {
      return;
    }
    setBusy(true);
    setErro('');
    try {
      const res = await alocacaoAtendimentoService.desvincularEntradaVenda(id);
      if (res.resumo) setResumo(res.resumo);
      else await load();
      onAtualizado?.();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 pt-2 border-t border-border/60 space-y-1.5">
      <div className="flex flex-wrap items-center gap-1">
        <p className="text-[9px] font-medium text-foreground">Alocar para venda</p>
        {resumo ? (
          <span className={`${badgeEstado(resumo.estado_operacional)} text-[9px]`}>
            {LABEL_ESTADO_OPERACIONAL[resumo.estado_operacional]}
          </span>
        ) : null}
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm text-[9px] py-0 ml-auto"
          onClick={() => setAberto((v) => !v)}
        >
          {aberto ? 'Fechar' : 'Abrir'}
        </button>
      </div>

      {resumo ? (
        <p className="text-[9px] text-muted-foreground">
          Disponível: {resumo.quantidade_disponivel} {resumo.unidade_estoque_calculada} · Alocado:{' '}
          {resumo.total_alocado} · Saldo: {resumo.saldo_entrada}
        </p>
      ) : null}

      <p className="text-[9px] text-amber-700 dark:text-amber-400">
        Alocação operacional: não movimenta estoque, não baixa Pedido de Compra e não gera financeiro.
      </p>
      {resumo?.aviso_estoque ? (
        <p className="text-[9px] text-amber-700 dark:text-amber-400">{resumo.aviso_estoque}</p>
      ) : null}

      {(resumo?.alocacoes ?? []).map((a) => (
        <div key={a.id} className="rounded border border-border/50 p-1.5 space-y-1 text-[9px]">
          <div className="text-muted-foreground">
            {a.pedido_venda_numero} · {a.cliente_nome || '—'} · {a.produto_codigo} · qty {a.quantidade_alocada}
          </div>
          {(a.faturamento_numero || a.nfe_saida_numero) && (
            <div className="text-muted-foreground">
              {a.faturamento_numero ? `Fat. ${a.faturamento_numero}` : ''}
              {a.faturamento_numero && a.nfe_saida_numero ? ' · ' : ''}
              {a.nfe_saida_numero ? `NF-e ${a.nfe_saida_numero}` : ''}
            </div>
          )}
          {editId === a.id ? (
            <div className="flex flex-wrap items-center gap-1">
              <input
                className="erp-input h-6 w-20 text-[9px]"
                value={editQty}
                onChange={(e) => setEditQty(e.target.value)}
              />
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-[9px] py-0"
                disabled={busy}
                onClick={() => void salvarEdicao(a.id)}
              >
                Salvar
              </button>
              <button
                type="button"
                className="erp-btn-ghost erp-btn-sm text-[9px] py-0"
                disabled={busy}
                onClick={() => setEditId(null)}
              >
                Cancelar
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-[9px] py-0"
                disabled={busy}
                onClick={() => {
                  setEditId(a.id);
                  setEditQty(a.quantidade_alocada);
                }}
              >
                Editar qty
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-[9px] py-0 text-destructive"
                disabled={busy}
                onClick={() => void desvincular(a.id)}
              >
                Desvincular
              </button>
            </div>
          )}
        </div>
      ))}

      {aberto ? (
        <div className="space-y-1.5 pt-1">
          <AsyncAutocomplete<OpcaoPedidoVendaItemAlocacao>
            value={opcaoPv?.id ?? null}
            selectedOption={opcaoPv}
            placeholder="Buscar item de Pedido de Venda…"
            minChars={1}
            search={buscarPvItens}
            getOptionValue={(o) => o.id}
            getOptionLabel={(o) => o.label}
            onChange={(_v, option) => {
              setOpcaoPv(option ?? null);
              if (option) {
                const saldoDest = Number(option.saldo_destino || 0);
                const saldoEnt = Number(resumo?.saldo_entrada || 0);
                const sugerido = Math.min(saldoDest, saldoEnt);
                if (sugerido > 0) setQuantidade(sugerido.toFixed(3));
              }
            }}
            inputClassName="h-7 text-[10px]"
          />
          {opcaoPv ? (
            <div className="text-[9px] text-muted-foreground space-y-0.5">
              <div>
                Necessidade: {opcaoPv.quantidade_necessaria}
                {opcaoPv.unidade_necessidade ? ` ${opcaoPv.unidade_necessidade}` : ''} · Já alocado:{' '}
                {opcaoPv.quantidade_ja_alocada} · Saldo destino: {opcaoPv.saldo_destino}
              </div>
              {opcaoPv.documentos_relacionados?.cadeia_ambigua ? (
                <div>
                  Vários faturamentos/NF-e ligados a este item — exibidos só como informação; o destino
                  canônico é o item do PV.
                </div>
              ) : (
                (opcaoPv.faturamento_numero || opcaoPv.nfe_saida_numero) && (
                  <div>
                    {opcaoPv.faturamento_numero ? `Fat. ${opcaoPv.faturamento_numero}` : 'Sem faturamento'}
                    {' · '}
                    {opcaoPv.nfe_saida_numero ? `NF-e ${opcaoPv.nfe_saida_numero}` : 'Sem NF-e saída'}
                  </div>
                )
              )}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-1">
            <input
              className="erp-input h-6 w-20 text-[9px]"
              value={quantidade}
              onChange={(e) => setQuantidade(e.target.value)}
              placeholder="Qtd"
            />
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm text-[9px] py-0"
              disabled={busy || !opcaoPv}
              onClick={() => void alocar()}
            >
              Salvar alocação
            </button>
          </div>
        </div>
      ) : null}

      {erro ? <p className="text-[9px] text-destructive">{erro}</p> : null}
    </div>
  );
}
