import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Pencil, Trash2, Plus } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { FornecedorPedidoCompraField, fornecedorStubForDisplay } from '@/components/pedidoCompra/FornecedorPedidoCompraField';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { pedidosCompraService } from '@/services/api/comercial';
import { alertMessageFromApiError } from '@/services/api/config';
import { fornecedoresService } from '@/services/api/fornecedores';
import { produtosService } from '@/services/api/produtos';
import {
  buildDueDates,
  formatDataIsoParaBr,
  MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA,
  parseCondicaoPagamentoPedido,
} from '@/lib/paymentTerms';
import { sugerirDataPrevistaEntregaIso } from '@/lib/prazoEntrega';
import { calcularFinanceiroItemPedidoCompra } from '@/lib/pedidoCompraFinanceiro';
import type { PedidoCompra, ItemPedido, Fornecedor, Produto } from '@/types';
import { equivalentesPreco, labelPrecoUnitarioPorUnidade, unidadesNegociacaoCompraProduto } from '@/lib/comercialDimensional';

const hojeIso = () => new Date().toISOString().slice(0, 10);

function ncmExibicao(p: Produto): string {
  return p.ncm_efetivo?.codigo || p.ncm || '—';
}

function tituloProdutoLinha(p: Produto): string {
  const cod = (p.codigo_completo || '').trim() || '—';
  const desc = (p.descricao || '').trim() || '—';
  return `${cod} — ${desc}`;
}

function itemPrecisaAtencao(it: ItemPedido): boolean {
  if (!it.produto_id) return true;
  if (!String(it.unidade_negociada || '').trim()) return true;
  const q = Number(it.quantidade_negociada ?? it.quantidade ?? 0);
  if (q <= 0) return true;
  const preco = Number(it.preco_por_unidade_negociada ?? it.valor_unitario ?? NaN);
  if (Number.isNaN(preco) || preco < 0) return true;
  return false;
}

function temImpostosOuAdicionais(it: ItemPedido): boolean {
  return (
    (it.ipi_percentual ?? 0) > 0 ||
    (it.ipi_valor ?? 0) > 0 ||
    (it.icms_st_percentual ?? 0) > 0 ||
    (it.icms_st_valor ?? 0) > 0 ||
    (it.desconto_valor ?? 0) > 0 ||
    (it.frete_valor ?? 0) > 0 ||
    (it.outras_despesas_valor ?? 0) > 0
  );
}

function resumoImpostosUmaLinha(it: ItemPedido, fin: ReturnType<typeof calcularFinanceiroItemPedidoCompra>): string {
  const parts: string[] = [];
  if (fin.valorIpi > 0) parts.push(`IPI R$ ${fin.valorIpi.toFixed(2)}`);
  if (fin.valorIcmsSt > 0) parts.push(`ST R$ ${fin.valorIcmsSt.toFixed(2)}`);
  if (fin.desconto > 0) parts.push(`Desc. R$ ${fin.desconto.toFixed(2)}`);
  if (fin.frete > 0) parts.push(`Frete R$ ${fin.frete.toFixed(2)}`);
  if (fin.outras > 0) parts.push(`Outras R$ ${fin.outras.toFixed(2)}`);
  return parts.join(' · ');
}

function linhaConversaoCompacta(item: ItemPedido, pendente: boolean): string {
  if (pendente) return 'Conversão pendente';
  const qe = item.quantidade_estoque_calculada ?? 0;
  const ue = (item.unidade_estoque_calculada || '—').toUpperCase();
  const pk = item.peso_total_kg ?? 0;
  const m = item.metros_total ?? 0;
  const b = item.barras_total ?? 0;
  return `Estoque: ${qe.toFixed(3)} ${ue} · Peso: ${pk.toFixed(3)} KG · Metros: ${m.toFixed(3)} M · Barras: ${b.toFixed(3)} BR`;
}

const PedidosCompra = () => {
  const [items, setItems] = useState<PedidoCompra[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PedidoCompra | null>(null);
  const [fornecedorSelecionado, setFornecedorSelecionado] = useState<Fornecedor | null>(null);
  const [produtoCache, setProdutoCache] = useState<Map<number, Produto>>(() => new Map());
  const produtoCacheRef = useRef(produtoCache);
  produtoCacheRef.current = produtoCache;

  const [form, setForm] = useState({
    numero: '',
    fornecedor_id: null as number | null,
    fornecedor_nome: '',
    data: '',
    status: 'Pendente',
    condicao_pagamento_texto: '30',
    prazo_entrega_texto: '',
    data_prevista_entrega: '' as string,
  });
  const [dataEntregaTouched, setDataEntregaTouched] = useState(false);
  const prazoEntregaAnterior = useRef('');
  const [itens, setItens] = useState<ItemPedido[]>([]);
  const itensRef = useRef(itens);
  itensRef.current = itens;

  const [conversaoPendentePorItemId, setConversaoPendentePorItemId] = useState<Record<number, boolean>>({});
  const [expandedItemIds, setExpandedItemIds] = useState<Set<number>>(() => new Set());
  const [itemDestacadoId, setItemDestacadoId] = useState<number | null>(null);

  useEffect(() => {
    const ids = Object.entries(conversaoPendentePorItemId)
      .filter(([, v]) => v)
      .map(([k]) => Number(k));
    if (!ids.length) return;
    setExpandedItemIds((prev) => {
      const n = new Set(prev);
      ids.forEach((id) => n.add(id));
      return n;
    });
  }, [conversaoPendentePorItemId]);

  const load = async () => setItems(await pedidosCompraService.getAll());
  useEffect(() => {
    load();
  }, []);

  const buscarProdutos = useCallback((term: string, limit?: number) => produtosService.search(term, limit ?? 50), []);

  const contagensProduto = useMemo(() => {
    const m = new Map<number, number>();
    for (const i of itens) {
      if (!i.produto_id) continue;
      m.set(i.produto_id, (m.get(i.produto_id) || 0) + 1);
    }
    return m;
  }, [itens]);

  const linhasComProdutoDuplicado = useMemo(
    () => itens.filter((i) => i.produto_id && (contagensProduto.get(i.produto_id) ?? 0) > 1).length,
    [itens, contagensProduto],
  );

  const itensComConversaoPendente = useMemo(
    () => itens.filter((i) => conversaoPendentePorItemId[i.id]).length,
    [itens, conversaoPendentePorItemId],
  );

  const quantidadeNegociadaTotal = useMemo(
    () => itens.reduce((s, i) => s + Number(i.quantidade_negociada ?? i.quantidade ?? 0), 0),
    [itens],
  );

  const resumoFinanceiroPedido = useMemo(() => {
    let sub = 0;
    let ipi = 0;
    let st = 0;
    let desc = 0;
    let frete = 0;
    let outras = 0;
    let total = 0;
    for (const it of itens) {
      const c = calcularFinanceiroItemPedidoCompra(it);
      sub += c.valorProdutos;
      ipi += c.valorIpi;
      st += c.valorIcmsSt;
      desc += c.desconto;
      frete += c.frete;
      outras += c.outras;
      total += c.valorTotalItem;
    }
    return {
      subtotal_produtos: Math.round(sub * 100) / 100,
      total_ipi: Math.round(ipi * 100) / 100,
      total_icms_st: Math.round(st * 100) / 100,
      total_descontos: Math.round(desc * 100) / 100,
      total_frete: Math.round(frete * 100) / 100,
      total_outras_despesas: Math.round(outras * 100) / 100,
      valor_total_pedido: Math.round(total * 100) / 100,
    };
  }, [itens]);

  const pagamentoParsed = useMemo(
    () => parseCondicaoPagamentoPedido(form.condicao_pagamento_texto),
    [form.condicao_pagamento_texto],
  );

  const resumoPagamentoPedido = useMemo(() => {
    if (pagamentoParsed.kind === 'invalid') {
      return { estado: 'invalid' as const, message: pagamentoParsed.message };
    }
    const dias = pagamentoParsed.dias;
    if (dias.length === 0) {
      return { estado: 'vazio' as const };
    }
    const prazosTxt = `${dias.map((d) => String(d)).join(', ')} dias`;
    const parcelas = dias.length;
    if (!form.data) {
      return { estado: 'sem_data' as const, parcelas, prazosTxt };
    }
    const linhas = buildDueDates(form.data, dias).map(formatDataIsoParaBr);
    return { estado: 'ok' as const, parcelas, prazosTxt, vencTxt: linhas.join(' · ') };
  }, [pagamentoParsed, form.data]);

  useEffect(() => {
    if (form.prazo_entrega_texto !== prazoEntregaAnterior.current) {
      prazoEntregaAnterior.current = form.prazo_entrega_texto;
      setDataEntregaTouched(false);
    }
  }, [form.prazo_entrega_texto]);

  useEffect(() => {
    if (!modalOpen || dataEntregaTouched) return;
    const sug = sugerirDataPrevistaEntregaIso(form.data, form.prazo_entrega_texto);
    if (sug) setForm((p) => ({ ...p, data_prevista_entrega: sug }));
  }, [modalOpen, form.data, form.prazo_entrega_texto, dataEntregaTouched]);

  const addItem = () => {
    const nid = Date.now();
    setItens((p) => [
      ...p,
      {
        id: nid,
        produto_id: 0,
        produto_nome: '',
        quantidade: 1,
        quantidade_negociada: 1,
        unidade_negociada: '',
        valor_unitario: 0,
        preco_por_unidade_negociada: 0,
        ipi_percentual: 0,
        ipi_valor: 0,
        icms_st_percentual: 0,
        icms_st_valor: 0,
        desconto_valor: 0,
        frete_valor: 0,
        outras_despesas_valor: 0,
      },
    ]);
    setExpandedItemIds((prev) => new Set(prev).add(nid));
    setItemDestacadoId(null);
  };

  const removeItem = (id: number) => {
    setItens((p) => p.filter((i) => i.id !== id));
    setExpandedItemIds((prev) => {
      const n = new Set(prev);
      n.delete(id);
      return n;
    });
    setConversaoPendentePorItemId((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    if (itemDestacadoId === id) setItemDestacadoId(null);
  };

  const toggleItemExpand = (id: number) => {
    setExpandedItemIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

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

  const setPendenteConversao = (rowId: number, pendente: boolean) => {
    setConversaoPendentePorItemId((prev) => ({ ...prev, [rowId]: pendente }));
  };

  const runConversaoParaLinha = useCallback(async (rowId: number) => {
    const row = itensRef.current.find((r) => r.id === rowId);
    if (!row?.produto_id) {
      setPendenteConversao(rowId, false);
      return;
    }

    let produto = produtoCacheRef.current.get(row.produto_id);
    if (!produto) {
      try {
        produto = await produtosService.getById(row.produto_id);
        setProdutoCache((m) => new Map(m).set(produto!.id, produto!));
      } catch {
        setPendenteConversao(rowId, true);
        return;
      }
    }

    const unidadeNegociada = (row.unidade_negociada || '').trim().toUpperCase();
    if (!unidadeNegociada) {
      setPendenteConversao(rowId, false);
      return;
    }

    const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
    const unidadeEstoque = (
      produto.unidade_estoque_efetiva ||
      produto.unidade_estoque ||
      produto.unidade ||
      unidadeNegociada
    ).toUpperCase();

    if (!produto.usa_conversao_dimensional_efetivo || unidadeNegociada === unidadeEstoque) {
      setPendenteConversao(rowId, false);
      setItens((prev) => {
        const idx = prev.findIndex((r) => r.id === rowId);
        if (idx < 0) return prev;
        const cur = prev[idx];
        const next = [...prev];
        next[idx] = {
          ...cur,
          unidade_negociada: unidadeNegociada,
          quantidade_negociada: quantidadeNegociada,
          quantidade: quantidadeNegociada,
          unidade_estoque_calculada: unidadeEstoque,
          quantidade_estoque_calculada: quantidadeNegociada,
          peso_total_kg: 0,
          metros_total: 0,
          barras_total: 0,
          fator_conversao: 1,
        };
        return next;
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
      setPendenteConversao(rowId, false);
      setItens((prev) => {
        const idx = prev.findIndex((r) => r.id === rowId);
        if (idx < 0) return prev;
        const cur = prev[idx];
        const next = [...prev];
        next[idx] = {
          ...cur,
          unidade_negociada: unidadeNegociada,
          quantidade_negociada: qtdOrig,
          quantidade: qtdOrig,
          unidade_estoque_calculada: conv.unidade_estoque || unidadeEstoque,
          quantidade_estoque_calculada: qtdDest,
          peso_total_kg: Number(conv.peso_kg || 0),
          metros_total: Number(conv.metros || 0),
          barras_total: Number(conv.barras || 0),
          fator_conversao: qtdOrig ? qtdDest / qtdOrig : 0,
        };
        return next;
      });
    } catch {
      setPendenteConversao(rowId, true);
      setItens((prev) => {
        const idx = prev.findIndex((r) => r.id === rowId);
        if (idx < 0) return prev;
        const cur = prev[idx];
        const next = [...prev];
        next[idx] = {
          ...cur,
          unidade_negociada: unidadeNegociada,
          quantidade_negociada: quantidadeNegociada,
          quantidade: quantidadeNegociada,
          unidade_estoque_calculada: unidadeEstoque,
          quantidade_estoque_calculada: quantidadeNegociada,
          peso_total_kg: 0,
          metros_total: 0,
          barras_total: 0,
          fator_conversao: 1,
        };
        return next;
      });
    }
  }, []);

  const chaveConversaoItens = useMemo(
    () =>
      itens
        .map(
          (i) =>
            `${i.id}|${i.produto_id}|${(i.unidade_negociada || '').trim().toUpperCase()}|${i.quantidade_negociada ?? i.quantidade ?? 0}`,
        )
        .join(';;'),
    [itens],
  );

  useEffect(() => {
    if (!modalOpen) return;
    let cancelled = false;
    (async () => {
      for (const i of itensRef.current) {
        if (cancelled) return;
        await runConversaoParaLinha(i.id);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [modalOpen, chaveConversaoItens, runConversaoParaLinha]);

  const openNew = () => {
    setEditing(null);
    setProdutoCache(new Map());
    setConversaoPendentePorItemId({});
    setExpandedItemIds(new Set());
    setItemDestacadoId(null);
    setDataEntregaTouched(false);
    prazoEntregaAnterior.current = '';
    setFornecedorSelecionado(null);
    setForm({
      numero: '',
      fornecedor_id: null,
      fornecedor_nome: '',
      data: hojeIso(),
      status: 'Pendente',
      condicao_pagamento_texto: '30',
      prazo_entrega_texto: '',
      data_prevista_entrega: '',
    });
    setItens([]);
    setModalOpen(true);
  };

  const openEdit = async (e: PedidoCompra) => {
    setEditing(e);
    setConversaoPendentePorItemId({});
    setDataEntregaTouched(true);
    prazoEntregaAnterior.current = e.prazo_entrega_texto ?? '';
    setForm({
      ...e,
      fornecedor_id: e.fornecedor_id ?? null,
      fornecedor_nome: e.fornecedor_nome ?? '',
      prazo_entrega_texto: e.prazo_entrega_texto ?? '',
      data_prevista_entrega: e.data_prevista_entrega?.slice(0, 10) ?? '',
    });
    let fornSel: Fornecedor | null = null;
    try {
      fornSel = await fornecedoresService.getById(e.fornecedor_id);
    } catch {
      fornSel = fornecedorStubForDisplay(e.fornecedor_id, e.fornecedor_nome ?? '');
    }
    setFornecedorSelecionado(fornSel);
    const mapped = e.itens.map((it) => ({
      ...it,
      quantidade_negociada: it.quantidade_negociada ?? it.quantidade,
      preco_por_unidade_negociada: it.preco_por_unidade_negociada ?? it.valor_unitario,
      ipi_percentual: it.ipi_percentual ?? 0,
      ipi_valor: it.ipi_valor ?? 0,
      icms_st_percentual: it.icms_st_percentual ?? 0,
      icms_st_valor: it.icms_st_valor ?? 0,
      desconto_valor: it.desconto_valor ?? 0,
      frete_valor: it.frete_valor ?? 0,
      outras_despesas_valor: it.outras_despesas_valor ?? 0,
    }));
    const precisa = new Set(mapped.filter(itemPrecisaAtencao).map((i) => i.id));
    setExpandedItemIds(precisa.size ? precisa : new Set());
    setItemDestacadoId(null);
    setItens(mapped);
    void (async () => {
      const incoming = new Map<number, Produto>();
      await Promise.all(
        mapped.map(async (it) => {
          if (!it.produto_id) return;
          try {
            const p = await produtosService.getById(it.produto_id);
            incoming.set(p.id, p);
          } catch {
            /* ignore */
          }
        }),
      );
      if (incoming.size) {
        setProdutoCache((prev) => {
          const m = new Map(prev);
          incoming.forEach((v, k) => m.set(k, v));
          return m;
        });
      }
    })();
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await pedidosCompraService.delete(id);
      load();
    }
  };

  const validarPedido = (): { erros: string[]; itemIdDestacar: number | null } => {
    const erros: string[] = [];
    let itemIdDestacar: number | null = null;
    if (!form.fornecedor_id) erros.push('Selecione o fornecedor.');
    if (!String(form.data || '').trim()) erros.push('Informe a data do pedido.');
    const pagCond = parseCondicaoPagamentoPedido(form.condicao_pagamento_texto);
    if (pagCond.kind === 'invalid') erros.push(pagCond.message);
    if (pagCond.kind === 'dias' && pagCond.dias.length === 0) erros.push(MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA);
    if (itens.length === 0) erros.push('Inclua ao menos um item no pedido.');
    itens.forEach((it, n) => {
      const num = n + 1;
      const marcar = () => {
        if (itemIdDestacar == null) itemIdDestacar = it.id;
      };
      if (!it.produto_id) {
        erros.push(`Item ${num}: selecione o produto.`);
        marcar();
      }
      if (!String(it.unidade_negociada || '').trim()) {
        erros.push(`Item ${num}: selecione a unidade negociada.`);
        marcar();
      }
      const q = Number(it.quantidade_negociada ?? it.quantidade ?? 0);
      if (q <= 0) {
        erros.push(`Item ${num}: a quantidade negociada deve ser maior que zero.`);
        marcar();
      }
      const preco = Number(it.preco_por_unidade_negociada ?? it.valor_unitario ?? NaN);
      if (Number.isNaN(preco) || preco < 0) {
        erros.push(`Item ${num}: o preço unitário não pode ser negativo.`);
        marcar();
      }
      const neg = (label: string, v: number | undefined) => {
        if (v != null && v < 0) {
          erros.push(`Item ${num}: ${label} não pode ser negativo.`);
          marcar();
        }
      };
      neg('IPI %', it.ipi_percentual);
      neg('Valor de IPI', it.ipi_valor);
      neg('ICMS ST %', it.icms_st_percentual);
      neg('Valor de ICMS ST', it.icms_st_valor);
      neg('Desconto', it.desconto_valor);
      neg('Frete', it.frete_valor);
      neg('Outras despesas', it.outras_despesas_valor);
      const fin = calcularFinanceiroItemPedidoCompra(it);
      if (fin.valorTotalItem < 0) {
        erros.push(`Item ${num}: o valor total do item não pode ser negativo.`);
        marcar();
      }
    });
    if (form.data_prevista_entrega) {
      const d = form.data_prevista_entrega.slice(0, 10);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) erros.push('Data prevista de entrega inválida.');
    }
    return { erros, itemIdDestacar };
  };

  const handleSave = async () => {
    const { erros, itemIdDestacar } = validarPedido();
    if (erros.length) {
      if (itemIdDestacar != null) {
        setExpandedItemIds((s) => new Set(s).add(itemIdDestacar));
        setItemDestacadoId(itemIdDestacar);
      }
      alert(erros.join('\n'));
      return;
    }
    setItemDestacadoId(null);
    const pag = parseCondicaoPagamentoPedido(form.condicao_pagamento_texto);
    if (pag.kind === 'invalid') {
      alert(pag.message);
      return;
    }
    if (pag.dias.length === 0) {
      alert(MENSAGEM_CONDICAO_PAGAMENTO_PEDIDO_DEFINIDA);
      return;
    }
    const dias = pag.dias;
    const vencimentos = buildDueDates(form.data, dias);
    const vt = resumoFinanceiroPedido.valor_total_pedido;
    const data: Record<string, unknown> = {
      ...form,
      itens,
      valor_total: vt,
      data_prevista_entrega: form.data_prevista_entrega?.trim() ? form.data_prevista_entrega.slice(0, 10) : null,
    };
    if (!editing) {
      delete data.numero;
    }
    const payload = {
      ...data,
      dias_parcelas: dias,
      quantidade_parcelas: dias.length,
      vencimentos_previstos: vencimentos,
    };
    try {
      if (editing) await pedidosCompraService.update(editing.id, payload as Partial<PedidoCompra>);
      else await pedidosCompraService.create(payload as Omit<PedidoCompra, 'id'>);
      setModalOpen(false);
      load();
    } catch (e: unknown) {
      alert(alertMessageFromApiError(e));
    }
  };

  const filtered = items.filter((i) => (i.numero || '').toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader title="Pedidos de Compra" onAdd={openNew} addLabel="Novo Pedido" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Número</th>
              <th>Fornecedor</th>
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
                <td>{e.fornecedor_nome}</td>
                <td>{e.data}</td>
                <td>
                  <span className={e.status === 'Recebido' ? 'erp-badge-success' : 'erp-badge-warning'}>{e.status}</span>
                </td>
                <td>R$ {e.valor_total.toFixed(2)}</td>
                <td>
                  <div className="flex gap-1">
                    <button type="button" onClick={() => void openEdit(e)} className="erp-btn-ghost erp-btn-sm">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button type="button" onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar Pedido de Compra' : 'Novo Pedido de Compra'}
        size="xl"
        footer={
          <div className="space-y-3 p-4 pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Resumo financeiro</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-3 lg:grid-cols-4">
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Subtotal produtos</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.subtotal_produtos.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Total IPI</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.total_ipi.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Total ICMS ST</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.total_icms_st.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Descontos</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.total_descontos.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Frete</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.total_frete.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-2 tabular-nums">
                <span className="text-muted-foreground">Outras despesas</span>
                <span className="font-medium">R$ {resumoFinanceiroPedido.total_outras_despesas.toFixed(2)}</span>
              </div>
            </div>
            <div className="flex justify-between gap-3 border-t border-border pt-2 text-base font-bold tabular-nums">
              <span>Valor total do pedido</span>
              <span className="text-primary">R$ {resumoFinanceiroPedido.valor_total_pedido.toFixed(2)}</span>
            </div>
            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
                Cancelar
              </button>
              <button type="button" onClick={() => void handleSave()} className="erp-btn-primary">
                Salvar
              </button>
            </div>
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="erp-label">Número</label>
            {editing ? (
              <>
                <input className="erp-input mt-1 bg-muted/40" readOnly value={form.numero} />
                <p className="text-xs text-muted-foreground mt-1">Número interno do pedido (não editável).</p>
              </>
            ) : (
              <>
                <input
                  className="erp-input mt-1 bg-muted/40 cursor-not-allowed"
                  readOnly
                  disabled
                  value=""
                  placeholder="PC-AAAAMMDD-NNNN"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  O número será gerado automaticamente ao salvar o pedido.
                </p>
              </>
            )}
          </div>
          <div className="md:col-span-2">
            <label className="erp-label">Fornecedor</label>
            <FornecedorPedidoCompraField
              valueId={form.fornecedor_id}
              selectedFornecedor={fornecedorSelecionado}
              onSelect={(f) => {
                setFornecedorSelecionado(f);
                setForm((prev) => {
                  const patch: Partial<typeof prev> = {
                    fornecedor_id: f.id,
                    fornecedor_nome: f.razao_social,
                  };
                  if (!String(prev.prazo_entrega_texto || '').trim() && (f.prazo_entrega ?? 0) > 0) {
                    patch.prazo_entrega_texto = `${f.prazo_entrega} dias corridos`;
                  }
                  return { ...prev, ...patch };
                });
              }}
              onClear={() => {
                setFornecedorSelecionado(null);
                setForm((p) => ({ ...p, fornecedor_id: null, fornecedor_nome: '' }));
              }}
              onCreatedAndUse={(f) => {
                setFornecedorSelecionado(f);
                setForm((prev) => {
                  const patch: Partial<typeof prev> = {
                    fornecedor_id: f.id,
                    fornecedor_nome: f.razao_social,
                  };
                  if (!String(prev.prazo_entrega_texto || '').trim() && (f.prazo_entrega ?? 0) > 0) {
                    patch.prazo_entrega_texto = `${f.prazo_entrega} dias corridos`;
                  }
                  return { ...prev, ...patch };
                });
              }}
            />
          </div>
          <div>
            <label className="erp-label">Data</label>
            <input type="date" className="erp-input mt-1" value={form.data} onChange={(e) => setForm((p) => ({ ...p, data: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Status</label>
            <select className="erp-select mt-1" value={form.status} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
              <option>Pendente</option>
              <option>Aprovado</option>
              <option>Recebido</option>
            </select>
          </div>
          <div className="md:col-span-3">
            <label className="erp-label">Condições de Pagamento</label>
            <input
              className="erp-input mt-1"
              placeholder="Ex.: À vista, 30, 30/45/60 ou 30,45,60"
              value={form.condicao_pagamento_texto}
              onChange={(e) => setForm((p) => ({ ...p, condicao_pagamento_texto: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Acordo fechado com o fornecedor. Não use termos indefinidos (ex.: «a combinar», «sob consulta»).
            </p>
            <div className="mt-2 space-y-1 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm leading-relaxed">
              {resumoPagamentoPedido.estado === 'invalid' ? (
                <p className="text-destructive">{resumoPagamentoPedido.message}</p>
              ) : resumoPagamentoPedido.estado === 'vazio' ? (
                <p className="text-muted-foreground">
                  Preencha as condições para ver parcelas, prazos e vencimentos.
                </p>
              ) : (
                <>
                  <div>
                    <span className="text-muted-foreground">Parcelas:</span>{' '}
                    <span className="font-semibold tabular-nums text-foreground">{resumoPagamentoPedido.parcelas}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Prazos:</span>{' '}
                    <span className="text-foreground">{resumoPagamentoPedido.prazosTxt}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Vencimentos:</span>{' '}
                    {resumoPagamentoPedido.estado === 'sem_data' ? (
                      <span className="text-muted-foreground">Informe a data do pedido para calcular os vencimentos.</span>
                    ) : (
                      <span className="text-foreground tabular-nums">{resumoPagamentoPedido.vencTxt}</span>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="md:col-span-2">
            <label className="erp-label">Prazo de entrega combinado</label>
            <input
              className="erp-input mt-1"
              placeholder="Ex.: 7 dias úteis, 10 dias corridos, imediato, a combinar…"
              value={form.prazo_entrega_texto}
              onChange={(e) => setForm((p) => ({ ...p, prazo_entrega_texto: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Data prevista de entrega</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={form.data_prevista_entrega}
              onChange={(e) => {
                setDataEntregaTouched(true);
                setForm((p) => ({ ...p, data_prevista_entrega: e.target.value }));
              }}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Exibida como {form.data_prevista_entrega ? formatDataIsoParaBr(form.data_prevista_entrega) : '—'} · Ajuste manual
              sempre permitido; sugestão automática ao alterar o prazo combinado.
            </p>
          </div>
        </div>
        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button type="button" onClick={addItem} className="erp-btn-outline erp-btn-sm">
              <Plus className="h-3 w-3" /> Item
            </button>
          </div>
          {itens.map((item, idx) => {
            const produto = item.produto_id ? produtoCache.get(item.produto_id) : undefined;
            const dup = Boolean(item.produto_id) && (contagensProduto.get(item.produto_id) ?? 0) > 1;
            const pendenteConv = Boolean(conversaoPendentePorItemId[item.id]);
            const fin = calcularFinanceiroItemPedidoCompra(item);
            const exp = expandedItemIds.has(item.id);
            const q = Number(item.quantidade_negociada ?? item.quantidade ?? 0);
            const un = (item.unidade_negociada || "—").toUpperCase();
            const pu = Number(item.preco_por_unidade_negociada ?? item.valor_unitario ?? 0);
            const tituloResumo = produto
              ? tituloProdutoLinha(produto)
              : item.produto_id
                ? "Carregando produto…"
                : "Selecione o produto";
            const impLinha = resumoImpostosUmaLinha(item, fin);
            const ringErro = itemDestacadoId === item.id ? "ring-2 ring-destructive ring-offset-2 ring-offset-background" : "";

            return (
              <div key={item.id} className={`mb-2 rounded-md border border-border bg-muted/5 ${ringErro}`}>
                <div className="flex gap-2 p-2 sm:px-3 sm:py-2">
                  <button
                    type="button"
                    className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
                    onClick={() => toggleItemExpand(item.id)}
                    aria-expanded={exp}
                    aria-label={exp ? "Recolher item" : "Expandir item"}
                  >
                    {exp ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => toggleItemExpand(item.id)}>
                    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      Item {idx + 1}
                    </div>
                    <div className="line-clamp-2 text-sm font-medium leading-snug text-foreground">{tituloResumo}</div>
                    <div className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                      {q} {un} · Unit. R$ {pu.toFixed(2)} · Total R$ {fin.valorTotalItem.toFixed(2)}
                    </div>
                    {impLinha ? <div className="mt-0.5 text-xs text-foreground/85">{impLinha}</div> : null}
                    {pendenteConv ? (
                      <div className="mt-0.5 text-xs font-semibold text-destructive">Conversão pendente</div>
                    ) : null}
                  </button>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <button
                      type="button"
                      className="erp-btn-ghost h-7 px-2 text-[11px]"
                      onClick={() => toggleItemExpand(item.id)}
                    >
                      {exp ? "Recolher" : "Expandir"}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="erp-btn-ghost erp-btn-sm text-destructive"
                      aria-label="Remover item"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                {dup ? (
                  <div className="border-t border-amber-500/20 bg-amber-500/5 px-3 py-1.5 text-[11px] text-amber-950 dark:text-amber-100">
                    Produto duplicado neste pedido — revise linhas ou some quantidades.
                  </div>
                ) : null}
                {!exp && item.produto_id && String(item.unidade_negociada || '').trim() && !pendenteConv ? (
                  <div className="border-t border-border/50 px-3 py-1 text-[11px] text-muted-foreground tabular-nums">
                    {linhaConversaoCompacta(item, false)}
                  </div>
                ) : null}
                {exp ? (
                  <div className="space-y-2 border-t border-border p-3">
                    <div className="min-w-0 space-y-1">
                      <label className="erp-label text-xs">Produto</label>
                      <div className="relative min-w-0 max-w-full">
                        <AsyncAutocomplete<Produto>
                          value={item.produto_id || null}
                          selectedOption={produto ?? null}
                          placeholder="Código, descrição, NCM ou material…"
                          minChars={1}
                          limit={50}
                          search={buscarProdutos}
                          getOptionValue={(p) => p.id}
                          getOptionLabel={(p) => tituloProdutoLinha(p)}
                          listBoxClassName="absolute z-50 mt-1 max-h-80 min-w-[min(100vw-2rem,36rem)] w-max max-w-[min(100vw-2rem,48rem)] overflow-auto rounded-md border border-border bg-background shadow"
                          renderOption={(p) => (
                            <div className="space-y-0.5 py-0.5 text-left">
                              <div className="font-medium text-foreground break-words">{(p.codigo_completo || "").trim() || "—"}</div>
                              <div className="text-muted-foreground break-words">{p.descricao}</div>
                              <div className="text-xs text-muted-foreground">
                                {(p.material || "—").trim()} · Un. padrão: {(p.unidade_efetiva || p.unidade || "—").toUpperCase()} · NCM:{" "}
                                {ncmExibicao(p)}
                              </div>
                            </div>
                          )}
                          onChange={(val, opt) => {
                            const idv = val != null ? Number(val) : 0;
                            if (opt) {
                              setProdutoCache((m) => new Map(m).set(opt.id, opt));
                              const unidades = unidadesNegociacaoCompraProduto(opt);
                              updateItem(idx, {
                                produto_id: idv,
                                produto_nome: opt.descricao,
                                unidade_negociada: unidades[0] || "",
                              });
                            } else {
                              updateItem(idx, {
                                produto_id: 0,
                                produto_nome: "",
                                unidade_negociada: "",
                                unidade_estoque_calculada: undefined,
                                quantidade_estoque_calculada: undefined,
                                peso_total_kg: 0,
                                metros_total: 0,
                                barras_total: 0,
                                fator_conversao: 1,
                              });
                            }
                            setPendenteConversao(item.id, false);
                          }}
                        />
                      </div>
                    </div>
                    {produto ? (
                      <details className="rounded border border-border/80 bg-background/60 text-xs">
                        <summary className="cursor-pointer select-none px-2 py-1.5 font-medium text-primary hover:underline">
                          Ver detalhes do produto
                        </summary>
                        <div className="space-y-1 border-t border-border/60 px-2 py-2 text-muted-foreground">
                          <div>
                            <span className="font-medium text-foreground/85">Código:</span> {(produto.codigo_completo || "—").trim()}
                          </div>
                          <div>
                            <span className="font-medium text-foreground/85">Material:</span> {(produto.material || "—").trim()}
                          </div>
                          <div>
                            <span className="font-medium text-foreground/85">Descrição:</span> {produto.descricao}
                          </div>
                          <div>
                            <span className="font-medium text-foreground/85">NCM:</span> {ncmExibicao(produto)}
                          </div>
                          <div>
                            <span className="font-medium text-foreground/85">Unidade padrão:</span>{" "}
                            {(produto.unidade_efetiva || produto.unidade || "—").toUpperCase()}
                          </div>
                        </div>
                      </details>
                    ) : item.produto_id ? (
                      <p className="text-xs text-muted-foreground">Carregando dados do produto…</p>
                    ) : null}
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <label className="text-xs text-muted-foreground">Unidade negociada</label>
                        <select
                          className="erp-select mt-1 w-full"
                          value={item.unidade_negociada || ""}
                          onChange={(e) => {
                            updateItem(idx, { unidade_negociada: e.target.value.toUpperCase() });
                            setPendenteConversao(item.id, false);
                          }}
                        >
                          <option value="">Selecione</option>
                          {(produto ? unidadesNegociacaoCompraProduto(produto) : ["PC"]).map((u) => (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Quantidade negociada</label>
                        <input
                          type="number"
                          className="erp-input mt-1 w-full"
                          value={item.quantidade_negociada ?? item.quantidade}
                          onChange={(e) => {
                            updateItem(idx, { quantidade_negociada: +e.target.value });
                            setPendenteConversao(item.id, false);
                          }}
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">{labelPrecoUnitarioPorUnidade(item.unidade_negociada)}</label>
                        <input
                          type="number"
                          step="0.0001"
                          className="erp-input mt-1 w-full"
                          value={item.preco_por_unidade_negociada ?? item.valor_unitario}
                          onChange={(e) => updateItem(idx, { preco_por_unidade_negociada: +e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Valor produtos</label>
                        <div className="erp-input mt-1 flex h-10 items-center justify-end tabular-nums">R$ {fin.valorProdutos.toFixed(2)}</div>
                      </div>
                    </div>
                    <details
                      className="rounded-md border border-border bg-muted/10 text-sm open:bg-muted/15"
                      defaultOpen={temImpostosOuAdicionais(item)}
                    >
                      <summary className="cursor-pointer select-none px-2 py-1.5 text-xs font-medium text-foreground/90">
                        Impostos / adicionais
                      </summary>
                      <div className="grid grid-cols-1 gap-2 border-t border-border/60 px-2 pb-2 pt-2 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                          <label className="text-xs text-muted-foreground">IPI %</label>
                          <input
                            type="number"
                            step="0.0001"
                            className="erp-input mt-1 w-full"
                            value={item.ipi_percentual ?? 0}
                            onChange={(e) => updateItem(idx, { ipi_percentual: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Valor IPI (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="erp-input mt-1 w-full"
                            value={item.ipi_valor ?? 0}
                            onChange={(e) => updateItem(idx, { ipi_valor: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">ICMS ST %</label>
                          <input
                            type="number"
                            step="0.0001"
                            className="erp-input mt-1 w-full"
                            value={item.icms_st_percentual ?? 0}
                            onChange={(e) => updateItem(idx, { icms_st_percentual: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Valor ICMS ST (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="erp-input mt-1 w-full"
                            value={item.icms_st_valor ?? 0}
                            onChange={(e) => updateItem(idx, { icms_st_valor: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Desconto (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="erp-input mt-1 w-full"
                            value={item.desconto_valor ?? 0}
                            onChange={(e) => updateItem(idx, { desconto_valor: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Frete (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="erp-input mt-1 w-full"
                            value={item.frete_valor ?? 0}
                            onChange={(e) => updateItem(idx, { frete_valor: +e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Outras despesas (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="erp-input mt-1 w-full"
                            value={item.outras_despesas_valor ?? 0}
                            onChange={(e) => updateItem(idx, { outras_despesas_valor: +e.target.value })}
                          />
                        </div>
                      </div>
                    </details>
                    <div className="flex items-center justify-between gap-2 rounded border border-border bg-background/70 px-2 py-1.5 text-sm">
                      <span className="font-medium text-foreground">Valor total do item</span>
                      <span className="font-semibold tabular-nums">R$ {fin.valorTotalItem.toFixed(2)}</span>
                    </div>
                    <p
                      className={`text-xs leading-relaxed ${pendenteConv ? "font-semibold text-destructive" : "text-muted-foreground"}`}
                    >
                      {linhaConversaoCompacta(item, pendenteConv)}
                    </p>
                    {equivalentesPreco(item).length ? (
                      <p className="text-xs text-muted-foreground">{equivalentesPreco(item).join(" · ")}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
            <div className="rounded-md border border-border bg-muted/20 p-2">Peso total estimado: {itens.reduce((s, i) => s + (i.peso_total_kg ?? 0), 0).toFixed(3)} KG</div>
            <div className="rounded-md border border-border bg-muted/20 p-2">Metros totais: {itens.reduce((s, i) => s + (i.metros_total ?? 0), 0).toFixed(3)} M</div>
            <div className="rounded-md border border-border bg-muted/20 p-2">Barras totais: {itens.reduce((s, i) => s + (i.barras_total ?? 0), 0).toFixed(3)} BR</div>
            <div className="rounded-md border border-border bg-muted/20 p-2">Total de itens: {itens.length}</div>
            <div className="rounded-md border border-border bg-muted/20 p-2">Quantidade total negociada: {quantidadeNegociadaTotal.toFixed(3)}</div>
            <div className="rounded-md border border-border bg-muted/20 p-2">Itens com conversão pendente: {itensComConversaoPendente}</div>
            <div className="rounded-md border border-border bg-muted/20 p-2 sm:col-span-2 lg:col-span-3">
              Itens com produto duplicado (linhas): {linhasComProdutoDuplicado}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default PedidosCompra;
