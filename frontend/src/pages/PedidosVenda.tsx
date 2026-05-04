import { useState, useEffect } from 'react';
import { Pencil, Trash2, Plus, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { pedidosVendaService } from '@/services/api/comercial';
import { clientesService } from '@/services/api/clientes';
import { empresasService } from '@/services/api/empresas';
import { produtosService } from '@/services/api/produtos';
import { buildDueDates, parsePaymentCondition } from '@/lib/paymentTerms';
import { apiErrorMessage } from '@/services/api/config';
import type { PedidoVenda, ItemPedido, Cliente, Empresa, Produto } from '@/types';
import { equivalentesPreco, labelPrecoPorUnidade, previewConversaoItem, todasUnidadesPadrao, unidadesNegociacaoProduto } from '@/lib/comercialDimensional';

const PedidosVenda = () => {
  const [items, setItems] = useState<PedidoVenda[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PedidoVenda | null>(null);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [form, setForm] = useState({
    numero: '',
    empresa_emitente_id: null as number | null,
    cliente_id: null as number | null,
    data: '',
    status: 'Pendente',
    proposta_id: undefined as number | undefined,
    condicao_pagamento_texto: '30',
  });
  const [itens, setItens] = useState<ItemPedido[]>([]);
  const [referenciaFrete, setReferenciaFrete] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      frete_medio_observado: number | null;
      peso_frete_sobre_faturamento: number | null;
      quantidade_ctes_validos: number;
      transportadora_referencia: { transportadora_id: number; transportadora_nome: string } | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);
  const [referenciaCustoCompra, setReferenciaCustoCompra] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      custo_medio_observado: number | null;
      ultimo_custo_observado: number | null;
      quantidade_notas_base: number;
      quantidade_itens_base: number;
      fornecedor_referencia: string | null;
    };
    mensagem: string;
    tem_base_historica: boolean;
  } | null>(null);

  const load = async () => setItems(await pedidosVendaService.getAll());
  useEffect(() => {
    load();
    clientesService.getAll().then(setClientes).catch(() => setClientes([]));
    empresasService.getAll().then(setEmpresas).catch(() => setEmpresas([]));
    produtosService.getAll().then(setProdutos).catch(() => setProdutos([]));
  }, []);

  useEffect(() => {
    if (!modalOpen || empresas.length !== 1) return;
    setForm((f) => ({ ...f, empresa_emitente_id: empresas[0].id }));
  }, [modalOpen, empresas]);

  useEffect(() => {
    if (!modalOpen) return;
    const qs = new URLSearchParams();
    if (form.data) {
      const ym = form.data.slice(0, 7);
      if (ym.length === 7) qs.set('mes', ym);
    }
    if (form.empresa_emitente_id) qs.set('empresa_id', String(form.empresa_emitente_id));
    void pedidosVendaService
      .referenciaComercialFrete(qs)
      .then(setReferenciaFrete)
      .catch(() => setReferenciaFrete(null));
    const itemRef = itens.find((i) => i.produto_id);
    if (itemRef?.produto_id) qs.set('produto_id', String(itemRef.produto_id));
    void pedidosVendaService
      .referenciaComercialCustoCompra(qs)
      .then(setReferenciaCustoCompra)
      .catch(() => setReferenciaCustoCompra(null));
  }, [modalOpen, form.data, form.empresa_emitente_id, itens]);

  const addItem = () =>
    setItens((p) => [
      ...p,
      {
        id: Date.now(),
        produto_id: produtos[0]?.id ?? 0,
        produto_nome: '',
        quantidade: 1,
        quantidade_negociada: 1,
        unidade_negociada: produtos[0]?.unidade_venda_efetiva || produtos[0]?.unidade || 'PC',
        valor_unitario: 0,
        preco_por_unidade_negociada: 0,
        corrida_id: undefined,
        corrida_numero: '',
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
    const unidadeNegociada = (row.unidade_negociada || produto.unidade_venda_efetiva || produto.unidade || 'PC').toUpperCase();
    const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
    const unidadeEstoque = (produto.unidade_estoque_efetiva || produto.unidade_estoque || produto.unidade || unidadeNegociada).toUpperCase();
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
      // Sem bloqueio do fluxo principal do pedido.
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm({
      numero: '',
      empresa_emitente_id: empresas.length === 1 ? empresas[0]?.id ?? null : null,
      cliente_id: clientes[0]?.id ?? null,
      data: '',
      status: 'Pendente',
      proposta_id: undefined,
      condicao_pagamento_texto: '30',
    });
    setItens([]);
    setModalOpen(true);
  };
  const openEdit = (e: PedidoVenda) => {
    setEditing(e);
    setForm({
      numero: e.numero,
      empresa_emitente_id: e.empresa_emitente_id ?? (empresas.length === 1 ? empresas[0]?.id ?? null : null),
      cliente_id: e.cliente_id,
      data: e.data,
      status: e.status,
      proposta_id: e.proposta_id,
      condicao_pagamento_texto: e.condicao_pagamento_texto,
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
  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await pedidosVendaService.delete(id);
      load();
    }
  };
  const handleSave = async () => {
    if (!form.cliente_id) {
      alert('Selecione um cliente.');
      return;
    }
    if (empresas.length > 1 && !form.empresa_emitente_id) {
      alert('Selecione a empresa emitente (matriz ou filial).');
      return;
    }
    try {
      const dias = parsePaymentCondition(form.condicao_pagamento_texto);
      const vencimentos = buildDueDates(form.data, dias);
      const data = { ...form, itens, valor_total: total };
      const payload = { ...data, dias_parcelas: dias, quantidade_parcelas: dias.length, vencimentos_previstos: vencimentos };
      if (editing) await pedidosVendaService.update(editing.id, payload);
      else await pedidosVendaService.create(payload as Omit<PedidoVenda, 'id'>);
      setModalOpen(false);
      load();
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const filtered = items.filter(
    (i) => i.numero.includes(search) || i.cliente_nome.toLowerCase().includes(search.toLowerCase()),
  );
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
      <PageHeader title="Pedidos de Venda" onAdd={openNew} addLabel="Novo Pedido" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Cliente</th>
              <th>Data</th>
              <th>Status</th>
              <th>Valor Total</th>
              <th className="w-24">Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td>
                <td>{e.cliente_nome}</td>
                <td>{e.data}</td>
                <td>
                  <span className={e.status === 'Faturado' ? 'erp-badge-success' : 'erp-badge-warning'}>{e.status}</span>
                </td>
                <td>R$ {e.valor_total.toFixed(2)}</td>
                <td>
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Pedido de Venda' : 'Novo Pedido de Venda'} size="xl">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="erp-label">Número</label>
            <input className="erp-input mt-1" value={form.numero} onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))} />
          </div>
          {empresas.length > 1 ? (
            <div className="md:col-span-2">
              <label className="erp-label">Empresa emitente</label>
              <select
                className="erp-select mt-1"
                value={form.empresa_emitente_id ?? ''}
                onChange={(e) =>
                  setForm((p) => ({ ...p, empresa_emitente_id: e.target.value ? Number(e.target.value) : null }))
                }
              >
                <option value="">Selecione matriz ou filial</option>
                {empresas.map((em) => (
                  <option key={em.id} value={em.id}>
                    {em.razao_social}
                    {em.uf ? ` (${em.uf})` : ''}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground mt-1">Operação fiscal do fluxo de venda: sempre saída. UF origem vem do cadastro da empresa.</p>
            </div>
          ) : empresas.length === 1 ? (
            <div className="md:col-span-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
              Emitente: <span className="font-medium text-foreground">{empresas[0].razao_social}</span>
              {empresas[0].uf ? ` · UF ${empresas[0].uf}` : ''}
            </div>
          ) : null}
          <div>
            <label className="erp-label">Cliente</label>
            <select
              className="erp-select mt-1"
              value={form.cliente_id ?? ''}
              onChange={(e) => setForm((p) => ({ ...p, cliente_id: e.target.value ? Number(e.target.value) : null }))}
            >
              <option value="">Selecione</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.razao_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Data</label>
            <input type="date" className="erp-input mt-1" value={form.data} onChange={(e) => setForm((p) => ({ ...p, data: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Status</label>
            <select className="erp-select mt-1" value={form.status} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
              <option>Pendente</option>
              <option>Em separação</option>
              <option>Faturado</option>
            </select>
          </div>
          <div>
            <label className="erp-label">Proposta vinculada (id)</label>
            <input
              className="erp-input mt-1"
              placeholder="Opcional"
              value={form.proposta_id ?? ''}
              onChange={(e) => setForm((p) => ({ ...p, proposta_id: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div className="md:col-span-2">
            <label className="erp-label">Condição de pagamento</label>
            <input
              className="erp-input mt-1"
              placeholder="Ex.: 30/45 DDL ou à vista"
              value={form.condicao_pagamento_texto}
              onChange={(e) => setForm((p) => ({ ...p, condicao_pagamento_texto: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Parcelas</label>
            <div className="erp-input mt-1 h-10 flex items-center">{diasPreview ? diasPreview.join(', ') || '—' : 'Condição inválida'}</div>
          </div>
          <div className="md:col-span-3">
            <label className="erp-label">Vencimentos previstos</label>
            <div className="erp-input mt-1 min-h-10 h-auto py-2">
              {vencimentosPreview.length ? vencimentosPreview.join(' | ') : 'Defina data e condição para visualizar vencimentos'}
            </div>
          </div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button onClick={addItem} className="erp-btn-outline erp-btn-sm">
              <Plus className="h-3 w-3" /> Item
            </button>
          </div>
          {itens.map((item, idx) => (
            <div key={item.id} className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-2 items-end">
              <div>
                <label className="text-xs text-muted-foreground">Produto</label>
                <select
                  className="erp-input h-8 text-sm"
                  value={item.produto_id || ''}
                  onChange={(e) => {
                    updateItem(idx, { produto_id: +e.target.value });
                    setTimeout(() => void aplicarConversao(idx), 0);
                  }}
                >
                  <option value="">Selecione</option>
                  {produtos.map((pr) => (
                    <option key={pr.id} value={pr.id}>
                      {pr.codigo_completo ? `${pr.codigo_completo} — ` : ''}
                      {pr.descricao}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Unidade negociada</label>
                <select
                  className="erp-input h-8 text-sm"
                  value={item.unidade_negociada || ''}
                  onChange={(e) => {
                    updateItem(idx, { unidade_negociada: e.target.value.toUpperCase() });
                    void aplicarConversao(idx);
                  }}
                >
                  <option value="">Selecione</option>
                  {(() => {
                    const p = produtos.find((pr) => pr.id === item.produto_id);
                    const op = p ? unidadesNegociacaoProduto(p) : todasUnidadesPadrao();
                    return op.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ));
                  })()}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Quantidade negociada</label>
                <input
                  type="number"
                  className="erp-input h-8 text-sm"
                  value={item.quantidade_negociada ?? item.quantidade}
                  onChange={(e) => {
                    updateItem(idx, { quantidade_negociada: +e.target.value });
                    void aplicarConversao(idx);
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">{labelPrecoPorUnidade(item.unidade_negociada)}</label>
                <input
                  type="number"
                  step="0.0001"
                  className="erp-input h-8 text-sm"
                  value={item.preco_por_unidade_negociada ?? item.valor_unitario}
                  onChange={(e) => {
                    updateItem(idx, { preco_por_unidade_negociada: +e.target.value });
                  }}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Corrida</label>
                <select
                  className="erp-input h-8 text-sm"
                  value={item.corrida_id ?? ''}
                  onChange={(e) => {
                    updateItem(idx, { corrida_id: e.target.value ? +e.target.value : undefined });
                  }}
                >
                  <option value="">—</option>
                </select>
              </div>
              <button type="button" onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8">
                <X className="h-4 w-4" />
              </button>
              <div className="md:col-span-5 text-xs text-muted-foreground">
                {previewConversaoItem(item)}
                {equivalentesPreco(item).length ? ` | ${equivalentesPreco(item).join(' | ')}` : ''}
              </div>
            </div>
          ))}
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total: R$ {total.toFixed(2)}</div>
        </div>
        {referenciaFrete && (
          <div className="mt-4 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Referência comercial de frete (apoio gerencial)</p>
            <p className="text-xs text-muted-foreground mt-1">{referenciaFrete.mensagem}</p>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Frete médio observado</div>
                <div className="font-medium">
                  {referenciaFrete.referencia_historica.frete_medio_observado == null
                    ? '—'
                    : `R$ ${referenciaFrete.referencia_historica.frete_medio_observado.toFixed(2)}`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Peso médio do frete</div>
                <div className="font-medium">{(referenciaFrete.referencia_historica.peso_frete_sobre_faturamento ?? 0).toFixed(2)}%</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">CT-es válidos</div>
                <div className="font-medium">{referenciaFrete.referencia_historica.quantidade_ctes_validos}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Período da referência</div>
                <div className="font-medium">
                  {(referenciaFrete.periodo_utilizado.data_inicio || '—')} a {(referenciaFrete.periodo_utilizado.data_fim || '—')}
                </div>
              </div>
            </div>
            {referenciaFrete.referencia_historica.transportadora_referencia && (
              <p className="mt-2 text-xs text-muted-foreground">
                Referência da transportadora selecionada: {referenciaFrete.referencia_historica.transportadora_referencia.transportadora_nome}.
              </p>
            )}
          </div>
        )}
        {referenciaCustoCompra && (
          <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Referência comercial de custo de compra (apoio gerencial)</p>
            <p className="text-xs text-muted-foreground mt-1">{referenciaCustoCompra.mensagem}</p>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Custo médio observado</div>
                <div className="font-medium">
                  {referenciaCustoCompra.referencia_historica.custo_medio_observado == null
                    ? '—'
                    : `R$ ${referenciaCustoCompra.referencia_historica.custo_medio_observado.toFixed(2)}`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Última compra observada</div>
                <div className="font-medium">
                  {referenciaCustoCompra.referencia_historica.ultimo_custo_observado == null
                    ? '—'
                    : `R$ ${referenciaCustoCompra.referencia_historica.ultimo_custo_observado.toFixed(2)}`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Fornecedor de referência</div>
                <div className="font-medium">{referenciaCustoCompra.referencia_historica.fornecedor_referencia || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Período da referência</div>
                <div className="font-medium">
                  {(referenciaCustoCompra.periodo_utilizado.data_inicio || '—')} a {(referenciaCustoCompra.periodo_utilizado.data_fim || '—')}
                </div>
              </div>
            </div>
          </div>
        )}
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
            Cancelar
          </button>
          <button type="button" onClick={handleSave} className="erp-btn-primary">
            Salvar
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default PedidosVenda;
