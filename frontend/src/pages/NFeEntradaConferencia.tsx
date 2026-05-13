import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { apiErrorMessage } from '@/services/api/config';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { pedidosCompraService } from '@/services/api/comercial';
import { produtosService } from '@/services/api/produtos';
import { normalizeOperationalInput } from '@/lib/textNormalize';
import type { NFeEntradaConferencia, PedidoCompra, Produto } from '@/types';

const NFeEntradaConferenciaPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const nfId = Number(id);
  const [dados, setDados] = useState<NFeEntradaConferencia | null>(null);
  const [pedidos, setPedidos] = useState<PedidoCompra[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [erro, setErro] = useState('');
  const [busy, setBusy] = useState(false);

  const produtosMap = useMemo(() => {
    const m = new Map<number, Produto>();
    produtos.forEach((p) => m.set(p.id, p));
    return m;
  }, [produtos]);

  const load = async () => {
    if (!nfId) return;
    setErro('');
    const [conf, pcs, prods] = await Promise.all([
      nfeEntradaConferenciaService.get(nfId),
      pedidosCompraService.getAll(),
      produtosService.getAll(),
    ]);
    setDados(conf);
    setPedidos(pcs);
    setProdutos(prods);
  };

  useEffect(() => {
    void load().catch((e) => setErro(apiErrorMessage(e)));
  }, [nfId]);

  const updateItem = (itemId: number, patch: Record<string, unknown>) => {
    if (!dados) return;
    setDados({
      ...dados,
      itens: dados.itens.map((it) => (it.id === itemId ? { ...it, ...patch } : it)),
    });
  };

  const salvar = async () => {
    if (!dados) return;
    setBusy(true);
    setErro('');
    try {
      const payload = {
        pedido_compra_id: dados.pedido_compra_id,
        divergencias_aceitas: dados.divergencias_aceitas,
        observacao_divergencias: dados.observacao_divergencias,
        itens: dados.itens.map((it) => ({
          id: it.id,
          produto_id: it.produto_id ?? null,
          item_pedido_compra_id: it.item_pedido_compra_id ?? null,
          corrida: it.corrida ?? '',
          lote: it.lote ?? '',
          status: it.status,
          motivo_ignorado: it.motivo_ignorado ?? '',
          observacao: it.observacao ?? '',
        })),
      };
      const next = await nfeEntradaConferenciaService.salvar(nfId, payload);
      setDados(next);
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const preparar = async () => {
    setBusy(true);
    setErro('');
    try {
      const next = await nfeEntradaConferenciaService.prepararEstoque(nfId);
      setDados(next);
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Conferência NF-e de Entrada" />
      {dados && (
        <div className="erp-card p-4 mb-4 grid md:grid-cols-4 gap-3 text-sm">
          <div><div className="text-muted-foreground text-xs">Fornecedor</div><div>{dados.fornecedor_nome}</div></div>
          <div><div className="text-muted-foreground text-xs">CNPJ</div><div>{dados.fornecedor_cnpj || '—'}</div></div>
          <div><div className="text-muted-foreground text-xs">NF-e</div><div>{dados.numero}/{dados.serie}</div></div>
          <div><div className="text-muted-foreground text-xs">Status</div><div>{dados.status}</div></div>
          <div><div className="text-muted-foreground text-xs">Emissão</div><div>{dados.data_emissao?.slice(0, 10)}</div></div>
          <div><div className="text-muted-foreground text-xs">Valor total</div><div>R$ {Number(dados.valor_total || 0).toFixed(2)}</div></div>
          <div className="md:col-span-2">
            <div className="text-muted-foreground text-xs">Pedido de compra vinculado</div>
            <select
              className="erp-select mt-1"
              value={dados.pedido_compra_id ?? ''}
              onChange={(e) => setDados({ ...dados, pedido_compra_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Sem pedido vinculado</option>
              {pedidos
                .filter((p) => !dados.fornecedor_nome || p.fornecedor_nome === dados.fornecedor_nome)
                .map((p) => <option key={p.id} value={p.id}>{p.numero}</option>)}
            </select>
          </div>
        </div>
      )}
      {erro && <div className="text-destructive text-sm mb-3">{erro}</div>}
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Item</th><th>Fornecedor</th><th>NCM/CFOP</th><th>NF</th><th>Produto Nexus</th><th>Corrida/Lote</th><th>Estoque calc.</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {dados?.itens.map((it, idx) => (
              <tr key={it.id}>
                <td>{idx + 1}</td>
                <td>
                  <div>{it.dados_nf?.codigo_fornecedor || '—'}</div>
                  <div className="text-xs text-muted-foreground">{it.dados_nf?.descricao_fornecedor || '—'}</div>
                </td>
                <td>{it.dados_nf?.ncm || '—'} / {it.dados_nf?.cfop || '—'}</td>
                <td>{Number(it.quantidade_nf || 0).toFixed(3)} {it.unidade_nf}</td>
                <td>
                  <select
                    className="erp-select min-w-[260px]"
                    value={it.produto_id ?? ''}
                    onChange={(e) => updateItem(it.id, { produto_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">Selecionar produto</option>
                    {it.sugestoes_produto?.map((s) => (
                      <option key={`s-${s.id}`} value={s.id}>{s.codigo} - {s.descricao}</option>
                    ))}
                    {produtos.map((p) => (
                      <option key={p.id} value={p.id}>{p.codigo_completo} - {p.descricao}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <input className="erp-input h-8 mb-1" placeholder="Corrida" value={it.corrida || ''} onChange={(e) => updateItem(it.id, { corrida: normalizeOperationalInput(e.target.value) })} />
                  <input className="erp-input h-8" placeholder="Lote" value={it.lote || ''} onChange={(e) => updateItem(it.id, { lote: normalizeOperationalInput(e.target.value) })} />
                </td>
                <td>
                  {Number(it.quantidade_estoque_calculada || 0).toFixed(3)} {it.unidade_estoque_calculada || produtosMap.get(it.produto_id || 0)?.unidade_estoque_efetiva || '—'}
                  {it.divergencias?.length ? <div className="text-xs text-amber-600">{it.divergencias.join(', ')}</div> : null}
                  {it.alertas?.length ? <div className="text-xs text-destructive">{it.alertas.join(', ')}</div> : null}
                </td>
                <td>
                  <select className="erp-select" value={it.status} onChange={(e) => updateItem(it.id, { status: normalizeOperationalInput(e.target.value) })}>
                    <option value="PENDENTE_PRODUTO">PENDENTE_PRODUTO</option>
                    <option value="PRODUTO_VINCULADO">PRODUTO_VINCULADO</option>
                    <option value="CONFERIDO">CONFERIDO</option>
                    <option value="DIVERGENTE">DIVERGENTE</option>
                    <option value="IGNORADO">IGNORADO</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="erp-card p-4 mt-4">
        <label className="flex items-center gap-2 text-sm mb-2">
          <input
            type="checkbox"
            checked={Boolean(dados?.divergencias_aceitas)}
            onChange={(e) => dados && setDados({ ...dados, divergencias_aceitas: e.target.checked })}
          />
          Aceitar divergências
        </label>
        <textarea
          className="erp-input min-h-[88px]"
          placeholder="Observação das divergências"
          value={dados?.observacao_divergencias || ''}
          onChange={(e) => dados && setDados({ ...dados, observacao_divergencias: normalizeOperationalInput(e.target.value) })}
        />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button className="erp-btn-outline" onClick={() => navigate('/nfe-entrada-historica-importada')}>Voltar</button>
        <button className="erp-btn-outline" onClick={() => void salvar()} disabled={busy}>Salvar conferência</button>
        <button className="erp-btn-primary" onClick={() => void preparar()} disabled={busy}>Preparar estoque</button>
      </div>
      <p className="text-xs text-muted-foreground mt-3 max-w-3xl ml-auto text-right">
        &quot;Preparar estoque&quot; grava a conferência como PREPARADA (validações no servidor). Ainda não há endpoint que incremente{' '}
        <span className="font-mono">EstoqueCorrida</span> a partir desta NF histórica; isso virá na fase de aplicação de estoque.
      </p>
    </div>
  );
};

export default NFeEntradaConferenciaPage;
