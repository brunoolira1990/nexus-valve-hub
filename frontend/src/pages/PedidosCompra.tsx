import { useState, useEffect } from 'react';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { pedidosCompraService } from '@/services/api/comercial';
import { fornecedoresService } from '@/services/api/fornecedores';
import { produtosService } from '@/services/api/produtos';
import { buildDueDates, parsePaymentCondition } from '@/lib/paymentTerms';
import type { PedidoCompra, ItemPedido, Fornecedor, Produto } from '@/types';
import {
  equivalentesPreco,
  labelPrecoPorUnidade,
  previewConversaoItem,
  todasUnidadesPadrao,
  unidadesNegociacaoProduto,
} from '@/lib/comercialDimensional';

const PedidosCompra = () => {
  const [items, setItems] = useState<PedidoCompra[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PedidoCompra | null>(null);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [form, setForm] = useState({
    numero: '',
    fornecedor_id: null as number | null,
    fornecedor_nome: '',
    data: '',
    status: 'Pendente',
    condicao_pagamento_texto: '30',
  });
  const [itens, setItens] = useState<ItemPedido[]>([]);

  const load = async () => setItems(await pedidosCompraService.getAll());
  useEffect(() => {
    load();
    fornecedoresService.getAll().then(setFornecedores).catch(() => setFornecedores([]));
    produtosService.getAll().then(setProdutos).catch(() => setProdutos([]));
  }, []);

  const addItem = () =>
    setItens((p) => [
      ...p,
      {
        id: Date.now(),
        produto_id: produtos[0]?.id ?? 0,
        produto_nome: '',
        quantidade: 1,
        quantidade_negociada: 1,
        unidade_negociada:
          produtos[0]?.unidade_compra_efetiva || produtos[0]?.unidade_compra_padrao || produtos[0]?.unidade || 'PC',
        valor_unitario: 0,
        preco_por_unidade_negociada: 0,
      },
    ]);
  const removeItem = (id: number) => setItens((p) => p.filter((i) => i.id !== id));
  const total = itens.reduce(
    (s, i) => s + (i.quantidade_negociada ?? i.quantidade) * (i.preco_por_unidade_negociada ?? i.valor_unitario),
    0,
  );

  const updateItem = (idx: number, patch: Partial<ItemPedido>) => {
    setItens((prev) => {
      const next = [...prev];
      const merged: ItemPedido = { ...next[idx], ...patch };
      if (Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada')) {
        merged.quantidade = Number(merged.quantidade_negociada ?? merged.quantidade ?? 0);
      }
      if (Object.prototype.hasOwnProperty.call(patch, 'preco_por_unidade_negociada')) {
        merged.valor_unitario = Number(merged.preco_por_unidade_negociada ?? merged.valor_unitario ?? 0);
      }
      next[idx] = merged;
      return next;
    });
  };

  const aplicarConversao = async (idx: number) => {
    const row = itens[idx];
    if (!row?.produto_id) return;
    const produto = produtos.find((p) => p.id === row.produto_id);
    if (!produto) return;
    const unidadeNegociada = (
      row.unidade_negociada ||
      produto.unidade_compra_efetiva ||
      produto.unidade_compra_padrao ||
      produto.unidade_venda_efetiva ||
      produto.unidade ||
      'PC'
    ).toUpperCase();
    const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
    const unidadeEstoque = (
      produto.unidade_estoque_efetiva ||
      produto.unidade_estoque ||
      produto.unidade ||
      unidadeNegociada
    ).toUpperCase();
    if (!produto.usa_conversao_dimensional_efetivo || unidadeNegociada === unidadeEstoque) {
      updateItem(idx, {
        unidade_negociada: unidadeNegociada,
        quantidade_negociada: quantidadeNegociada,
        unidade_estoque_calculada: unidadeEstoque,
        quantidade_estoque_calculada: quantidadeNegociada,
        fator_conversao: 1,
      });
      return;
    }
    try {
      const conv = await produtosService.converterMedida({
        produto_id: row.produto_id,
        quantidade: quantidadeNegociada,
        unidade_origem: unidadeNegociada,
        unidade_destino: unidadeEstoque,
      });
      const qtdOrig = Number(conv.quantidade_origem || quantidadeNegociada);
      const qtdDest = Number(conv.quantidade_destino || quantidadeNegociada);
      updateItem(idx, {
        unidade_negociada: unidadeNegociada,
        quantidade_negociada: qtdOrig,
        quantidade: qtdOrig,
        unidade_estoque_calculada: conv.unidade_estoque || unidadeEstoque,
        quantidade_estoque_calculada: qtdDest,
        peso_total_kg: Number(conv.peso_kg || 0),
        metros_total: Number(conv.metros || 0),
        barras_total: Number(conv.barras || 0),
        fator_conversao: qtdOrig ? qtdDest / qtdOrig : 0,
      });
    } catch {
      // Fluxo de compra segue editável mesmo sem fator de conversão.
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm({
      numero: '',
      fornecedor_id: fornecedores[0]?.id ?? null,
      fornecedor_nome: '',
      data: '',
      status: 'Pendente',
      condicao_pagamento_texto: '30',
    });
    setItens([]);
    setModalOpen(true);
  };
  const openEdit = (e: PedidoCompra) => {
    setEditing(e);
    setForm({
      ...e,
      fornecedor_id: e.fornecedor_id ?? null,
      fornecedor_nome: e.fornecedor_nome ?? '',
    });
    setItens(
      e.itens.map((it) => ({
        ...it,
        quantidade_negociada: it.quantidade_negociada ?? it.quantidade,
        preco_por_unidade_negociada: it.preco_por_unidade_negociada ?? it.valor_unitario,
      })),
    );
    setModalOpen(true);
  };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await pedidosCompraService.delete(id); load(); } };
  const handleSave = async () => {
    if (!form.fornecedor_id) {
      alert('Selecione um fornecedor.');
      return;
    }
    const dias = parsePaymentCondition(form.condicao_pagamento_texto);
    const vencimentos = buildDueDates(form.data, dias);
    const data = { ...form, itens, valor_total: total };
    const payload = { ...data, dias_parcelas: dias, quantidade_parcelas: dias.length, vencimentos_previstos: vencimentos };
    if (editing) await pedidosCompraService.update(editing.id, payload);
    else await pedidosCompraService.create(payload as Omit<PedidoCompra, 'id'>);
    setModalOpen(false); load();
  };

  const filtered = items.filter((i) => i.numero.includes(search));
  const diasPreview = (() => {
    try {
      return parsePaymentCondition(form.condicao_pagamento_texto);
    } catch {
      return null;
    }
  })();
  const vencimentosPreview = diasPreview ? buildDueDates(form.data, diasPreview) : [];

  return (
    <div>
      <PageHeader title="Pedidos de Compra" onAdd={openNew} addLabel="Novo Pedido" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Fornecedor</th><th>Data</th><th>Status</th><th>Valor Total</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.fornecedor_nome}</td><td>{e.data}</td>
                <td><span className={e.status === 'Recebido' ? 'erp-badge-success' : 'erp-badge-warning'}>{e.status}</span></td>
                <td>R$ {e.valor_total.toFixed(2)}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Pedido de Compra' : 'Novo Pedido de Compra'} size="xl">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
          <div>
            <label className="erp-label">Fornecedor</label>
            <select className="erp-select mt-1" value={form.fornecedor_id ?? ''} onChange={e => setForm(p => ({...p,fornecedor_id: e.target.value ? +e.target.value : null}))}>
              <option value="">Selecione</option>
              {fornecedores.map((f) => (
                <option key={f.id} value={f.id}>{f.razao_social}</option>
              ))}
            </select>
          </div>
          <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
          <div><label className="erp-label">Status</label><select className="erp-select mt-1" value={form.status} onChange={e => setForm(p => ({...p,status:e.target.value}))}><option>Pendente</option><option>Aprovado</option><option>Recebido</option></select></div>
          <div className="md:col-span-2"><label className="erp-label">Condição de pagamento</label><input className="erp-input mt-1" placeholder='Ex.: 30/45 DDL ou à vista' value={form.condicao_pagamento_texto} onChange={e => setForm(p => ({...p,condicao_pagamento_texto:e.target.value}))} /></div>
          <div><label className="erp-label">Parcelas</label><div className="erp-input mt-1 h-10 flex items-center">{diasPreview ? diasPreview.join(', ') || '—' : 'Condição inválida'}</div></div>
          <div className="md:col-span-3"><label className="erp-label">Vencimentos previstos</label><div className="erp-input mt-1 min-h-10 h-auto py-2">{vencimentosPreview.length ? vencimentosPreview.join(' | ') : 'Defina data e condição para visualizar vencimentos'}</div></div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button onClick={addItem} className="erp-btn-outline erp-btn-sm"><Plus className="h-3 w-3" /> Item</button>
          </div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-1 md:grid-cols-6 gap-2 mb-3 items-end rounded-md border border-border p-3">
              <div>
                <label className="text-xs text-muted-foreground">Produto</label>
                <select className="erp-input h-8 text-sm" value={item.produto_id || ''} onChange={e => { updateItem(idx, { produto_id: +e.target.value }); setTimeout(() => void aplicarConversao(idx), 0); }}>
                  <option value="">Selecione</option>
                  {produtos.map((pr) => (
                    <option key={pr.id} value={pr.id}>
                      {pr.codigo_completo ? `${pr.codigo_completo} — ` : ''}{pr.descricao}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Unidade negociada</label>
                <select className="erp-input h-8 text-sm" value={item.unidade_negociada || ''} onChange={e => { updateItem(idx, { unidade_negociada: e.target.value.toUpperCase() }); void aplicarConversao(idx); }}>
                  <option value="">Selecione</option>
                  {(() => {
                    const p = produtos.find((pr) => pr.id === item.produto_id);
                    const op = p ? unidadesNegociacaoProduto(p) : todasUnidadesPadrao();
                    return op.map((u) => <option key={u} value={u}>{u}</option>);
                  })()}
                </select>
              </div>
              <div><label className="text-xs text-muted-foreground">Quantidade negociada</label><input type="number" className="erp-input h-8 text-sm" value={item.quantidade_negociada ?? item.quantidade} onChange={e => { updateItem(idx, { quantidade_negociada: +e.target.value }); void aplicarConversao(idx); }} /></div>
              <div><label className="text-xs text-muted-foreground">{labelPrecoPorUnidade(item.unidade_negociada)}</label><input type="number" step="0.0001" className="erp-input h-8 text-sm" value={item.preco_por_unidade_negociada ?? item.valor_unitario} onChange={e => updateItem(idx, { preco_por_unidade_negociada: +e.target.value })} /></div>
              <div>
                <label className="text-xs text-muted-foreground">Valor total</label>
                <div className="erp-input h-8 text-sm flex items-center justify-end">
                  R$ {(((item.quantidade_negociada ?? item.quantidade) || 0) * ((item.preco_por_unidade_negociada ?? item.valor_unitario) || 0)).toFixed(2)}
                </div>
              </div>
              <button onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8"><X className="h-4 w-4" /></button>
              <div className="md:col-span-6 text-xs text-muted-foreground">
                {previewConversaoItem(item)}
                {equivalentesPreco(item).length ? ` | ${equivalentesPreco(item).join(' | ')}` : ''}
              </div>
            </div>
          ))}
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total: R$ {total.toFixed(2)}</div>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
            <div className="rounded-md border border-border bg-muted/20 p-2">
              Peso total estimado: {itens.reduce((s, i) => s + (i.peso_total_kg ?? 0), 0).toFixed(3)} KG
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-2">
              Metros totais: {itens.reduce((s, i) => s + (i.metros_total ?? 0), 0).toFixed(3)} M
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-2">
              Barras totais: {itens.reduce((s, i) => s + (i.barras_total ?? 0), 0).toFixed(3)} BR
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>
    </div>
  );
};

export default PedidosCompra;
