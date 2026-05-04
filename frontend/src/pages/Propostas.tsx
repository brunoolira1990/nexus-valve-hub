import { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import { CheckCircle2, Pencil, RefreshCw, ShoppingCart, Trash2, Plus, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { propostasService } from '@/services/api/comercial';
import { clientesService } from '@/services/api/clientes';
import { produtosService } from '@/services/api/produtos';
import { empresasService } from '@/services/api/empresas';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import { apiErrorMessage } from '@/services/api/config';
import { buildDueDates, parsePaymentCondition } from '@/lib/paymentTerms';
import {
  normalizeNcm,
  ncmFiscalDigitsValid,
  recalcPropostaItem,
  computeIpiEntradaValor,
  percentualSaidaTotal,
  computeValorCargaSaida,
} from '@/lib/propostaPricing';
import { equivalentesPreco, labelPrecoPorUnidade, previewConversaoItem, todasUnidadesPadrao, unidadesNegociacaoProduto } from '@/lib/comercialDimensional';
import type { Proposta, ItemProposta, Cliente, Produto, Empresa } from '@/types';
import { UFS } from '@/types';

const Propostas = () => {
  const [items, setItems] = useState<Proposta[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Proposta | null>(null);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const itensRef = useRef<ItemProposta[]>([]);
  const produtosRef = useRef<Produto[]>([]);
  const empresasRef = useRef<Empresa[]>([]);
  const [form, setForm] = useState({
    numero: '',
    cliente_id: null as number | null,
    cliente_avulso_nome: '',
    empresa_emitente_id: null as number | null,
    data: '',
    validade: '',
    vendedor: 'João Silva',
    status: 'Pendente',
    condicao_pagamento_texto: '30',
    uf_destino_avulso: '',
  });
  const [clienteAvulso, setClienteAvulso] = useState(false);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clientesError, setClientesError] = useState<string | null>(null);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [produtosError, setProdutosError] = useState<string | null>(null);
  const [itens, setItens] = useState<ItemProposta[]>([]);
  const [referenciaFrete, setReferenciaFrete] = useState<{
    periodo_utilizado: Record<string, string | undefined>;
    referencia_historica: {
      frete_medio_observado: number | null;
      peso_frete_sobre_faturamento: number | null;
      valor_total_fretes_periodo: number;
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
  const [custoCompraRefLoading, setCustoCompraRefLoading] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [wizardError, setWizardError] = useState<string | null>(null);
  const [wizardLoading, setWizardLoading] = useState(false);
  const [wizardProposta, setWizardProposta] = useState<Proposta | null>(null);
  const [wizardClienteId, setWizardClienteId] = useState<number | null>(null);
  const [novoClienteNome, setNovoClienteNome] = useState('');
  const [novoClienteCnpj, setNovoClienteCnpj] = useState('');
  const [itemLinks, setItemLinks] = useState<Record<number, number | null>>({});
  const [novoProdutoDescricao, setNovoProdutoDescricao] = useState<Record<number, string>>({});
  const numericClass =
    'erp-input h-8 text-sm text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none';

  const normalizeItem = (item: Partial<ItemProposta>): ItemProposta => {
    const base: ItemProposta = {
      id: item.id ?? Date.now(),
      produto_id: item.produto_id ?? null,
      produto_nome: item.produto_nome ?? '',
      descricao_avulsa: item.descricao_avulsa ?? '',
      ncm_avulso: item.ncm_avulso ?? '',
      quantidade: item.quantidade ?? 1,
      unidade_negociada: item.unidade_negociada ?? '',
      quantidade_negociada: item.quantidade_negociada ?? item.quantidade ?? 1,
      unidade_estoque_calculada: item.unidade_estoque_calculada ?? '',
      quantidade_estoque_calculada: item.quantidade_estoque_calculada ?? 0,
      peso_total_kg: item.peso_total_kg ?? 0,
      metros_total: item.metros_total ?? 0,
      barras_total: item.barras_total ?? 0,
      valor_unitario: item.valor_unitario ?? 0,
      preco_por_unidade_negociada: item.preco_por_unidade_negociada ?? item.valor_unitario ?? 0,
      preco_por_kg: item.preco_por_kg ?? 0,
      preco_por_metro: item.preco_por_metro ?? 0,
      fator_conversao: item.fator_conversao ?? 0,
      desconto: item.desconto ?? 0,
      custo_utilizado: item.custo_utilizado ?? 0,
      frete: item.frete ?? 0,
      despesas: item.despesas ?? 0,
      ipi_entrada_percentual: item.ipi_entrada_percentual ?? 0,
      ipi_custo: item.ipi_custo ?? 0,
      st_custo: item.st_custo ?? 0,
      outros_impostos_custo: item.outros_impostos_custo ?? 0,
      custo_final: item.custo_final ?? 0,
      icms_saida_percentual: item.icms_saida_percentual ?? 0,
      pis_saida_percentual: item.pis_saida_percentual ?? 0,
      cofins_saida_percentual: item.cofins_saida_percentual ?? 0,
      ipi_saida_percentual: item.ipi_saida_percentual ?? 0,
      regra_fiscal_id: item.regra_fiscal_id ?? null,
      irpj_estimado_percentual: item.irpj_estimado_percentual ?? 0,
      csll_estimada_percentual: item.csll_estimada_percentual ?? 0,
      comissao_percentual: item.comissao_percentual ?? 0,
      frete_saida: item.frete_saida ?? 0,
      outras_despesas_saida: item.outras_despesas_saida ?? 0,
      modo_preco: item.modo_preco ?? 'sugerido',
      preco_sugerido: item.preco_sugerido ?? 0,
      preco_final: item.preco_final ?? item.valor_unitario ?? 0,
      margem_resultante: item.margem_resultante ?? 0,
      lucro_resultante: item.lucro_resultante ?? 0,
    };
    base.quantidade = base.quantidade_negociada ?? base.quantidade;
    base.valor_unitario = base.preco_por_unidade_negociada ?? base.valor_unitario;
    return recalcPropostaItem(base);
  };

  const load = async () => setItems(await propostasService.getAll());
  const loadClientes = async () => {
    setClientesError(null);
    try {
      const data = await clientesService.getAll();
      setClientes(data);
    } catch (e) {
      setClientes([]);
      setClientesError(apiErrorMessage(e));
    }
  };
  const loadProdutos = async () => {
    setProdutosError(null);
    try {
      const data = await produtosService.getAll();
      setProdutos(data);
    } catch (e) {
      setProdutos([]);
      setProdutosError(apiErrorMessage(e));
    }
  };
  useEffect(() => {
    load();
    loadClientes();
    loadProdutos();
    empresasService
      .getAll()
      .then((list) => setEmpresas(list))
      .catch(() => setEmpresas([]));
  }, []);

  itensRef.current = itens;
  produtosRef.current = produtos;
  empresasRef.current = empresas;

  const resolveUfDestino = useCallback((): string => {
    if (!clienteAvulso && form.cliente_id) {
      const c = clientes.find((x) => x.id === form.cliente_id);
      return (c?.uf || '').toUpperCase().slice(0, 2);
    }
    return (form.uf_destino_avulso || '').toUpperCase().slice(0, 2);
  }, [clienteAvulso, form.cliente_id, form.uf_destino_avulso, clientes]);

  const resolveUfOrigemEmitente = useCallback((): string => {
    const list = empresasRef.current;
    const id = form.empresa_emitente_id ?? list[0]?.id;
    const emp = list.find((x) => x.id === id) ?? list[0];
    return (emp?.uf || '').toUpperCase().slice(0, 2);
  }, [form.empresa_emitente_id]);

  const mergeRowWithFiscal = useCallback(
    async (row: ItemProposta): Promise<ItemProposta> => {
      const ufOrigem = resolveUfOrigemEmitente();
      const ufDestino = resolveUfDestino();
      const operacao = 'Saída';
      let ncm = '';
      if (row.produto_id) {
        const prod = produtosRef.current.find((p) => p.id === row.produto_id);
        ncm = normalizeNcm(prod?.ncm || '');
      } else {
        ncm = normalizeNcm(row.ncm_avulso || '');
      }
      if (!ncm || ufOrigem.length !== 2 || ufDestino.length !== 2) {
        return {
          ...row,
          icms_saida_percentual: 0,
          pis_saida_percentual: 0,
          cofins_saida_percentual: 0,
          ipi_saida_percentual: 0,
          regra_fiscal_id: null,
        };
      }
      const regra = await regrasFiscaisService.buscar({
        ncm,
        uf_origem: ufOrigem,
        uf_destino: ufDestino,
        operacao,
      });
      if (!regra) {
        return {
          ...row,
          icms_saida_percentual: 0,
          pis_saida_percentual: 0,
          cofins_saida_percentual: 0,
          ipi_saida_percentual: 0,
          regra_fiscal_id: null,
        };
      }
      return {
        ...row,
        icms_saida_percentual: regra.aliquota_icms,
        pis_saida_percentual: regra.aliquota_pis,
        cofins_saida_percentual: regra.aliquota_cofins,
        ipi_saida_percentual: regra.aliquota_ipi,
        regra_fiscal_id: regra.id,
      };
    },
    [resolveUfOrigemEmitente, resolveUfDestino],
  );

  const fiscalTriggerKey = useMemo(
    () =>
      itens.map((i) => `${i.id}:${i.produto_id ?? ''}:${normalizeNcm(i.ncm_avulso || '')}`).join('|'),
    [itens],
  );

  const itemRefCusto = useMemo(
    () => itens.find((i) => i.produto_id || ncmFiscalDigitsValid(i.ncm_avulso || '')),
    [itens],
  );

  useLayoutEffect(() => {
    if (!modalOpen) return;
    const podeCusto =
      itemRefCusto &&
      (itemRefCusto.produto_id != null || ncmFiscalDigitsValid(itemRefCusto.ncm_avulso || ''));
    if (podeCusto) setCustoCompraRefLoading(true);
  }, [modalOpen, itemRefCusto]);

  useEffect(() => {
    if (!modalOpen || itens.length === 0) return;
    let cancelled = false;
    const t = setTimeout(() => {
      void (async () => {
        const cur = itensRef.current;
        const merged = await Promise.all(cur.map((r) => mergeRowWithFiscal(r)));
        if (!cancelled) setItens(merged.map((r) => recalcPropostaItem(r)));
      })();
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [
    modalOpen,
    form.empresa_emitente_id,
    form.uf_destino_avulso,
    form.cliente_id,
    clienteAvulso,
    mergeRowWithFiscal,
    itens.length,
    fiscalTriggerKey,
  ]);

  useEffect(() => {
    if (!modalOpen || empresas.length !== 1) return;
    setForm((f) => ({ ...f, empresa_emitente_id: empresas[0].id }));
  }, [modalOpen, empresas]);

  useEffect(() => {
    if (!modalOpen) {
      setReferenciaCustoCompra(null);
      setCustoCompraRefLoading(false);
      return;
    }
    const qs = new URLSearchParams();
    if (form.data) {
      const ym = form.data.slice(0, 7);
      if (ym.length === 7) qs.set('mes', ym);
    }
    if (form.empresa_emitente_id) qs.set('empresa_id', String(form.empresa_emitente_id));
    void propostasService.referenciaComercialFrete(qs).then((data) => {
      if (data && typeof data === 'object') setReferenciaFrete(data);
      else setReferenciaFrete(null);
    });

    const podeCusto =
      itemRefCusto &&
      (itemRefCusto.produto_id != null || ncmFiscalDigitsValid(itemRefCusto.ncm_avulso || ''));
    if (!podeCusto) {
      setReferenciaCustoCompra(null);
      setCustoCompraRefLoading(false);
      return;
    }
    const qsCusto = new URLSearchParams(qs.toString());
    if (itemRefCusto.produto_id) qsCusto.set('produto_id', String(itemRefCusto.produto_id));
    else if (itemRefCusto.ncm_avulso) qsCusto.set('ncm', itemRefCusto.ncm_avulso);
    setCustoCompraRefLoading(true);
    void propostasService
      .referenciaComercialCustoCompra(qsCusto)
      .then((data) => {
        if (data && typeof data === 'object') setReferenciaCustoCompra(data);
        else setReferenciaCustoCompra(null);
      })
      .finally(() => setCustoCompraRefLoading(false));
  }, [modalOpen, form.data, form.empresa_emitente_id, itemRefCusto]);

  const addItem = () => {
    const p0 = produtos[0];
    setItens((p) => [
      ...p,
      normalizeItem({
        id: Date.now(),
        produto_id: p0?.id ?? null,
        produto_nome: p0?.descricao ?? '',
        descricao_avulsa: '',
      }),
    ]);
  };
  const removeItem = (id: number) => setItens(p => p.filter(i => i.id !== id));
  const total = itens.reduce(
    (s, i) => s + (i.quantidade_negociada ?? i.quantidade) * (i.preco_por_unidade_negociada ?? i.preco_final) - i.desconto,
    0,
  );
  const custoTotal = itens.reduce((s, i) => s + i.quantidade * i.custo_final, 0);
  const receitaTotal = total;
  const lucroTotal = receitaTotal - custoTotal;
  const margemMedia = receitaTotal > 0 ? (lucroTotal / receitaTotal) * 100 : 0;
  const quantidadeTotalItens = itens.reduce((s, i) => s + (i.quantidade_negociada ?? i.quantidade), 0);
  const existeAvulsoSemNcm = itens.some((i) => !i.produto_id && !ncmFiscalDigitsValid(i.ncm_avulso || ''));

  const openNew = () => {
    setEditing(null);
    setClienteAvulso(false);
    setForm({
      numero: '',
      cliente_id: clientes[0]?.id ?? null,
      cliente_avulso_nome: '',
      empresa_emitente_id: empresas.length === 1 ? empresas[0]?.id ?? null : null,
      data: '',
      validade: '',
      vendedor: 'João Silva',
      status: 'Pendente',
      condicao_pagamento_texto: '30',
      uf_destino_avulso: '',
    });
    setItens([]);
    setModalOpen(true);
  };
  const openEdit = (e: Proposta) => {
    setEditing(e);
    setClienteAvulso(!e.cliente_id);
    setForm({
      numero: e.numero,
      cliente_id: e.cliente_id ?? null,
      cliente_avulso_nome: e.cliente_avulso_nome ?? '',
      empresa_emitente_id: e.empresa_emitente_id ?? (empresas.length === 1 ? empresas[0]?.id ?? null : null),
      data: e.data,
      validade: e.validade,
      vendedor: e.vendedor,
      status: e.status,
      condicao_pagamento_texto: e.condicao_pagamento_texto,
      uf_destino_avulso: e.uf_destino_avulso ?? '',
    });
    setItens(e.itens.map((it) => normalizeItem(it)));
    setModalOpen(true);
  };
  const handleDelete = async (id: number) => { if (confirm('Excluir?')) { await propostasService.delete(id); load(); } };
  const handleSave = async () => {
    if (!clienteAvulso && !form.cliente_id) {
      alert('Selecione um cliente cadastrado ou marque cliente avulso.');
      return;
    }
    if (empresas.length > 1 && !form.empresa_emitente_id) {
      alert('Selecione a empresa emitente (matriz ou filial).');
      return;
    }
    const dias = parsePaymentCondition(form.condicao_pagamento_texto);
    const vencimentos = buildDueDates(form.data, dias);
    const payloadForm = {
      ...form,
      cliente_id: clienteAvulso ? null : form.cliente_id,
      cliente_avulso_nome: clienteAvulso ? form.cliente_avulso_nome : '',
      uf_destino_avulso: clienteAvulso ? form.uf_destino_avulso : '',
    };
    const data = { ...payloadForm, itens, valor_total: total };
    const payload = { ...data, dias_parcelas: dias, quantidade_parcelas: dias.length, vencimentos_previstos: vencimentos };
    if (editing) await propostasService.update(editing.id, payload);
    else await propostasService.create(payload as Omit<Proposta, 'id'>);
    setModalOpen(false); load();
  };
  const refreshProposta = async (id: number) => {
    const updated = await propostasService.getById(id);
    setWizardProposta(updated);
    return updated;
  };

  const startWizard = async (proposta: Proposta) => {
    setWizardOpen(true);
    setWizardStep(1);
    setWizardError(null);
    setWizardLoading(true);
    try {
      const current = await propostasService.getById(proposta.id);
      setWizardProposta(current);
      setWizardClienteId(current.cliente_id ?? null);
      setNovoClienteNome(current.cliente_avulso_nome ?? '');
      setNovoClienteCnpj('');
      const nextLinks: Record<number, number | null> = {};
      const nextDescricoes: Record<number, string> = {};
      current.itens.forEach((it) => {
        nextLinks[it.id] = it.produto_id ?? null;
        nextDescricoes[it.id] = it.descricao_avulsa ?? it.produto_nome ?? '';
      });
      setItemLinks(nextLinks);
      setNovoProdutoDescricao(nextDescricoes);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível iniciar o wizard de conversão.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const vincularClienteExistente = async () => {
    if (!wizardProposta || !wizardClienteId) return;
    setWizardLoading(true);
    setWizardError(null);
    try {
      await propostasService.update(wizardProposta.id, { cliente_id: wizardClienteId, cliente_avulso_nome: '' });
      await refreshProposta(wizardProposta.id);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível vincular o cliente.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const criarClienteDaProposta = async () => {
    if (!wizardProposta) return;
    const nome = (novoClienteNome || wizardProposta.cliente_avulso_nome || '').trim();
    const cnpj = novoClienteCnpj.replace(/\D/g, '');
    if (!nome) {
      setWizardError('Informe a razão social para criar o cliente.');
      return;
    }
    if (cnpj.length !== 14) {
      setWizardError('Informe um CNPJ válido com 14 dígitos para criar o cliente.');
      return;
    }
    setWizardLoading(true);
    setWizardError(null);
    try {
      const cliente = await clientesService.create({
        razao_social: nome,
        nome_fantasia: nome,
        cnpj,
        ie: '',
        logradouro: '',
        numero: '',
        complemento: '',
        bairro: '',
        cidade: '',
        uf: '',
        cep: '',
        telefone: '',
        email: '',
        contato_responsavel: '',
        observacoes: '',
        inscricao_municipal: '',
        suframa: '',
        email_nf: '',
        telefone_alternativo: '',
        celular: '',
        limite_credito: 0,
        condicao_pagamento_texto: '0',
        dias_parcelas: [0],
        quantidade_parcelas: 1,
        transportadora_padrao_id: null,
        vendedor_padrao: '',
        bloqueado: false,
        ativo: true,
        ddd: '',
        banco: '',
        agencia: '',
        conta: '',
        tipo_conta: '',
        cnae: '',
        regime_tributario: '',
        integracao_texto: '',
      });
      await propostasService.update(wizardProposta.id, { cliente_id: cliente.id, cliente_avulso_nome: '' });
      await Promise.all([refreshProposta(wizardProposta.id), loadClientes()]);
      setWizardClienteId(cliente.id);
      setWizardStep(2);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível criar o cliente cadastrado.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const vincularItemExistente = async (itemId: number) => {
    if (!wizardProposta) return;
    const produtoId = itemLinks[itemId];
    if (!produtoId) {
      setWizardError('Selecione um produto para vincular o item avulso.');
      return;
    }
    const itensAtualizados = wizardProposta.itens.map((it) =>
      it.id === itemId ? { ...it, produto_id: produtoId, descricao_avulsa: '' } : it,
    );
    setWizardLoading(true);
    setWizardError(null);
    try {
      await propostasService.update(wizardProposta.id, { itens: itensAtualizados });
      await refreshProposta(wizardProposta.id);
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível vincular o item ao produto.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const criarProdutoParaItem = async (itemId: number) => {
    if (!wizardProposta) return;
    const descricao = (novoProdutoDescricao[itemId] || '').trim();
    if (!descricao) {
      setWizardError('Informe a descrição do novo produto.');
      return;
    }
    setWizardLoading(true);
    setWizardError(null);
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
      const itensAtualizados = wizardProposta.itens.map((it) =>
        it.id === itemId ? { ...it, produto_id: produto.id, descricao_avulsa: '' } : it,
      );
      await propostasService.update(wizardProposta.id, { itens: itensAtualizados });
      await Promise.all([refreshProposta(wizardProposta.id), loadProdutos()]);
      setItemLinks((prev) => ({ ...prev, [itemId]: produto.id }));
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível criar o produto para o item.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const clienteResolvido = Boolean(wizardProposta?.cliente_id);
  const itensPendentes = wizardProposta?.itens.filter((it) => !it.produto_id) ?? [];
  const itensResolvidos = (wizardProposta?.itens.length ?? 0) - itensPendentes.length;
  const podeConverter = Boolean(wizardProposta && clienteResolvido && itensPendentes.length === 0);

  const concluirConversao = async () => {
    if (!wizardProposta || !podeConverter) return;
    setWizardLoading(true);
    setWizardError(null);
    try {
      await propostasService.convertToPedido(wizardProposta.id);
      setWizardOpen(false);
      await load();
      alert('Proposta convertida em pedido com sucesso.');
    } catch (e) {
      setWizardError(apiErrorMessage(e, { fallback: 'Não foi possível converter a proposta em pedido.' }));
    } finally {
      setWizardLoading(false);
    }
  };

  const filtered = items.filter(i => i.numero.includes(search) || i.cliente_nome.toLowerCase().includes(search.toLowerCase()));
  const diasPreview = (() => {
    try {
      return parsePaymentCondition(form.condicao_pagamento_texto);
    } catch {
      return null;
    }
  })();
  const vencimentosPreview = diasPreview ? buildDueDates(form.data, diasPreview) : [];
  const margemBadgeClass =
    margemMedia >= 20
      ? 'erp-badge-success'
      : margemMedia >= 10
        ? 'erp-badge-warning'
        : 'erp-badge-danger';

  const updateItem = (idx: number, patch: Partial<ItemProposta>) => {
    let snapshot: ItemProposta | null = null;
    setItens((prev) => {
      const merged = { ...prev[idx], ...patch };
      if (Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada')) {
        merged.quantidade = Number(merged.quantidade_negociada ?? merged.quantidade ?? 0);
      }
      if (Object.prototype.hasOwnProperty.call(patch, 'preco_por_unidade_negociada')) {
        const p = Number(merged.preco_por_unidade_negociada ?? merged.preco_final ?? 0);
        merged.preco_final = p;
        merged.valor_unitario = p;
      }
      snapshot = merged;
      const next = [...prev];
      next[idx] = recalcPropostaItem(merged);
      return next;
    });
    if (
      snapshot &&
      (Object.prototype.hasOwnProperty.call(patch, 'produto_id') ||
        Object.prototype.hasOwnProperty.call(patch, 'ncm_avulso') ||
        Object.prototype.hasOwnProperty.call(patch, 'quantidade') ||
        Object.prototype.hasOwnProperty.call(patch, 'quantidade_negociada') ||
        Object.prototype.hasOwnProperty.call(patch, 'unidade_negociada'))
    ) {
      void mergeRowWithFiscal(snapshot).then((f) => {
        setItens((prev) => {
          const n = [...prev];
          if (!n[idx]) return prev;
          n[idx] = recalcPropostaItem({ ...n[idx], ...f });
          return n;
        });
      });
      void (async () => {
        const row = snapshot;
        if (!row?.produto_id) return;
        const produto = produtosRef.current.find((p) => p.id === row.produto_id);
        const unidadeNegociada = (row.unidade_negociada || produto?.unidade_venda_efetiva || produto?.unidade || 'PC').toUpperCase();
        const quantidadeNegociada = Number(row.quantidade_negociada ?? row.quantidade ?? 0);
        const unidadeEstoque = (produto?.unidade_estoque_efetiva || produto?.unidade_estoque || produto?.unidade || 'PC').toUpperCase();
        if (!produto?.usa_conversao_dimensional_efetivo || unidadeNegociada === unidadeEstoque) {
          setItens((prev) => {
            const n = [...prev];
            if (!n[idx]) return prev;
            n[idx] = recalcPropostaItem({
              ...n[idx],
              unidade_negociada: unidadeNegociada,
              quantidade_negociada: quantidadeNegociada,
              unidade_estoque_calculada: unidadeEstoque,
              quantidade_estoque_calculada: quantidadeNegociada,
              fator_conversao: 1,
            });
            return n;
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
          setItens((prev) => {
            const n = [...prev];
            if (!n[idx]) return prev;
            n[idx] = recalcPropostaItem({
              ...n[idx],
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
            return n;
          });
        } catch {
          // Sem bloqueio na fase 1: mantém fluxo comercial atual.
        }
      })();
    }
  };

  return (
    <div>
      <PageHeader title="Propostas" onAdd={openNew} addLabel="Nova Proposta" searchValue={search} onSearch={setSearch} />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead><tr><th>Número</th><th>Cliente</th><th>Data</th><th>Validade</th><th>Vendedor</th><th>Status</th><th>Valor Total</th><th className="w-24">Ações</th></tr></thead>
          <tbody>
            {filtered.map(e => (
              <tr key={e.id}>
                <td className="font-medium">{e.numero}</td><td>{e.cliente_nome || e.cliente_avulso_nome || 'Cliente avulso'}</td><td>{e.data}</td><td>{e.validade}</td><td>{e.vendedor}</td>
                <td><span className={e.status === 'Aprovada' ? 'erp-badge-success' : e.status === 'Pendente' ? 'erp-badge-warning' : 'erp-badge-danger'}>{e.status}</span></td>
                <td>R$ {e.valor_total.toFixed(2)}</td>
                <td><div className="flex gap-1">
                  <button onClick={() => startWizard(e)} className="erp-btn-ghost erp-btn-sm" title="Converter em pedido"><ShoppingCart className="h-4 w-4" /></button>
                  <button onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm"><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive"><Trash2 className="h-4 w-4" /></button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Proposta' : 'Nova Proposta'} size="xl">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div><label className="erp-label">Número</label><input className="erp-input mt-1" value={form.numero} onChange={e => setForm(p => ({...p,numero:e.target.value}))} /></div>
          <div>
            <label className="erp-label">Cliente</label>
            <div className="mt-1 space-y-2">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={clienteAvulso} onChange={(e) => setClienteAvulso(e.target.checked)} />
                Cliente avulso (sem cadastro)
              </label>
              {clienteAvulso ? (
                <div className="space-y-2">
                  <input
                    className="erp-input"
                    placeholder="Nome do cliente avulso"
                    value={form.cliente_avulso_nome}
                    onChange={(e) => setForm((p) => ({ ...p, cliente_avulso_nome: e.target.value }))}
                  />
                  <div>
                    <label className="text-xs text-muted-foreground">UF destino (para regra fiscal)</label>
                    <select
                      className="erp-select mt-1 w-full"
                      value={form.uf_destino_avulso}
                      onChange={(e) => setForm((p) => ({ ...p, uf_destino_avulso: e.target.value }))}
                    >
                      <option value="">Selecione</option>
                      {UFS.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <select className="erp-select" value={form.cliente_id ?? ''} onChange={e => setForm(p => ({...p,cliente_id:e.target.value ? +e.target.value : null}))}>
                  <option value="">Selecione um cliente</option>
                  {clientes.map((cliente) => (
                    <option key={cliente.id} value={cliente.id}>
                      {cliente.razao_social}
                    </option>
                  ))}
                </select>
              )}
              {clientesError ? <p className="text-xs text-destructive">{clientesError}</p> : null}
            </div>
          </div>
          <div><label className="erp-label">Vendedor</label><input className="erp-input mt-1" value={form.vendedor} onChange={e => setForm(p => ({...p,vendedor:e.target.value}))} /></div>
          <div><label className="erp-label">Data</label><input type="date" className="erp-input mt-1" value={form.data} onChange={e => setForm(p => ({...p,data:e.target.value}))} /></div>
          <div><label className="erp-label">Validade</label><input type="date" className="erp-input mt-1" value={form.validade} onChange={e => setForm(p => ({...p,validade:e.target.value}))} /></div>
          <div><label className="erp-label">Status</label><select className="erp-select mt-1" value={form.status} onChange={e => setForm(p => ({...p,status:e.target.value}))}><option>Pendente</option><option>Aprovada</option><option>Rejeitada</option></select></div>
          <div className="md:col-span-2"><label className="erp-label">Condição de pagamento</label><input className="erp-input mt-1" placeholder='Ex.: 30/45 DDL ou à vista' value={form.condicao_pagamento_texto} onChange={e => setForm(p => ({...p,condicao_pagamento_texto:e.target.value}))} /></div>
          <div><label className="erp-label">Parcelas</label><div className="erp-input mt-1 h-10 flex items-center">{diasPreview ? diasPreview.join(', ') || '—' : 'Condição inválida'}</div></div>
          <div className="md:col-span-3"><label className="erp-label">Vencimentos previstos</label><div className="erp-input mt-1 min-h-10 h-auto py-2">{vencimentosPreview.length ? vencimentosPreview.join(' | ') : 'Defina data e condição para visualizar vencimentos'}</div></div>
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
              <p className="text-xs text-muted-foreground mt-1">
                A UF de origem para a regra fiscal é obtida automaticamente do cadastro desta empresa. Operação: sempre saída.
              </p>
            </div>
          ) : empresas.length === 1 ? (
            <div className="md:col-span-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
              Emitente: <span className="font-medium text-foreground">{empresas[0].razao_social}</span>
              {empresas[0].uf ? ` · UF origem ${empresas[0].uf}` : ''} · Operação fiscal: saída (automático)
            </div>
          ) : null}
        </div>

        <div className="border border-border rounded-md p-3">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-medium text-sm">Itens</h3>
            <button onClick={addItem} className="erp-btn-outline erp-btn-sm"><Plus className="h-3 w-3" /> Adicionar Item</button>
          </div>
          {existeAvulsoSemNcm ? (
            <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
              Há item(ns) avulso(s) sem NCM válido (8 dígitos): a proposta segue como <strong>simulação comercial</strong> para tributos de
              saída. Para converter em pedido ou faturar, informe o NCM em cada item avulso e depois vincule um produto cadastrado.
            </div>
          ) : null}
          {itens.map((item, idx) => {
            const pctSaida = percentualSaidaTotal(item);
            const precoRef = item.modo_preco === 'manual' ? item.preco_final : item.preco_sugerido;
            const valCarga = computeValorCargaSaida(precoRef, pctSaida);
            const ipiEntradaVal = computeIpiEntradaValor(
              item.custo_utilizado,
              item.ipi_entrada_percentual ?? 0,
              item.ipi_custo ?? 0,
            );
            const margemBadge =
              item.margem_resultante >= 15 ? 'erp-badge-success' : item.margem_resultante >= 8 ? 'erp-badge-warning' : 'erp-badge-danger';
            const ufO = resolveUfOrigemEmitente();
            const ufD = resolveUfDestino();
            const ncmBusca = item.produto_id
              ? normalizeNcm(produtos.find((p) => p.id === item.produto_id)?.ncm || '')
              : normalizeNcm(item.ncm_avulso || '');
            let msgRegra = '';
            if (!item.produto_id && !ncmFiscalDigitsValid(item.ncm_avulso || '')) {
              msgRegra =
                'Item avulso sem NCM (8 dígitos): tributos de saída zerados. Informe o NCM para buscar a Regra Fiscal ou vincule um produto cadastrado.';
            } else if (ufO.length !== 2 || ufD.length !== 2) {
              msgRegra = 'Defina empresa emitente com UF, cliente com UF ou UF destino (cliente avulso) para localizar a regra fiscal.';
            } else if (!item.regra_fiscal_id) {
              msgRegra =
                'Não encontramos regra fiscal para este NCM com UF origem/destino e operação saída. Cadastre a regra em Regras fiscais ou revise o NCM.';
            } else {
              msgRegra = `Regra fiscal aplicada (id ${item.regra_fiscal_id}).`;
            }
            return (
              <div key={item.id} className="mb-4 rounded-md border border-border p-3 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 md:col-span-2">
                    <label className="text-xs text-muted-foreground">Produto / item</label>
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={!item.produto_id}
                        onChange={(e) =>
                          updateItem(
                            idx,
                            e.target.checked
                              ? { produto_id: null }
                              : { produto_id: produtos[0]?.id ?? null, descricao_avulsa: '', ncm_avulso: '' },
                          )
                        }
                      />
                      Item avulso
                    </label>
                  </div>
                  <button type="button" onClick={() => removeItem(item.id)} className="erp-btn-ghost erp-btn-sm text-destructive h-8">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                {!item.produto_id ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-3xl">
                    <div>
                      <label className="text-xs text-muted-foreground">Descrição (item avulso)</label>
                      <input
                        className="erp-input h-8 text-sm mt-1"
                        placeholder="Descrição comercial"
                        value={item.descricao_avulsa ?? ''}
                        onChange={(e) => updateItem(idx, { descricao_avulsa: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">NCM (8 dígitos — regra fiscal)</label>
                      <input
                        className="erp-input h-8 text-sm mt-1 font-mono"
                        placeholder="Ex.: 84818099"
                        value={item.ncm_avulso ?? ''}
                        onChange={(e) => updateItem(idx, { ncm_avulso: e.target.value })}
                      />
                    </div>
                  </div>
                ) : (
                  <select
                    className="erp-input h-8 text-sm max-w-xl"
                    value={item.produto_id ?? ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      updateItem(idx, { produto_id: v ? +v : null, descricao_avulsa: '', ncm_avulso: '' });
                    }}
                  >
                    <option value="">Selecione o produto</option>
                    {produtos.map((pr) => (
                      <option key={pr.id} value={pr.id}>
                        {pr.codigo_completo ? `${pr.codigo_completo} — ` : ''}
                        {pr.descricao}
                      </option>
                    ))}
                  </select>
                )}

                <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                  <div>
                    <label className="text-xs text-muted-foreground">Unidade negociada</label>
                    <select
                      className={numericClass.replace('text-right', 'text-left')}
                      value={item.unidade_negociada || ''}
                      onChange={(e) => updateItem(idx, { unidade_negociada: e.target.value.toUpperCase() })}
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
                      inputMode="decimal"
                      className={numericClass}
                      value={item.quantidade_negociada ?? item.quantidade}
                      onChange={(e) => updateItem(idx, { quantidade_negociada: +e.target.value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">{labelPrecoPorUnidade(item.unidade_negociada)}</label>
                    <input
                      type="number"
                      inputMode="decimal"
                      step="0.0001"
                      className={numericClass}
                      value={item.preco_por_unidade_negociada ?? item.preco_final}
                      onChange={(e) => updateItem(idx, { preco_por_unidade_negociada: +e.target.value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Desc. (R$)</label>
                    <input
                      type="number"
                      inputMode="decimal"
                      step="0.01"
                      className={numericClass}
                      value={item.desconto}
                      onChange={(e) => updateItem(idx, { desconto: +e.target.value || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Valor total</label>
                    <div className={`${numericClass} flex items-center justify-end`}>R$ {(((item.quantidade_negociada ?? item.quantidade) || 0) * ((item.preco_por_unidade_negociada ?? item.preco_final) || 0)).toFixed(2)}</div>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{previewConversaoItem(item)}</p>
                {equivalentesPreco(item).length ? (
                  <p className="text-xs text-muted-foreground">{equivalentesPreco(item).join(' | ')}</p>
                ) : null}

                <div className="rounded-md border border-border bg-muted/10 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Bloco 1 — Custo de entrada</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">Custo do produto</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.custo_utilizado}
                        onChange={(e) => updateItem(idx, { custo_utilizado: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI entrada %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.ipi_entrada_percentual ?? 0}
                        onChange={(e) => updateItem(idx, { ipi_entrada_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">ST (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.st_custo}
                        onChange={(e) => updateItem(idx, { st_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Frete entrada</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.frete}
                        onChange={(e) => updateItem(idx, { frete: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Despesas entrada</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.despesas}
                        onChange={(e) => updateItem(idx, { despesas: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Outros (entrada)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.outros_impostos_custo}
                        onChange={(e) => updateItem(idx, { outros_impostos_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI entrada (R$ legado)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        title="Compatível com propostas antigas: usado só se IPI % = 0"
                        value={item.ipi_custo}
                        onChange={(e) => updateItem(idx, { ipi_custo: +e.target.value || 0 })}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs text-muted-foreground">IPI entrada calculado (R$)</label>
                      <div className="erp-input h-8 text-sm flex items-center">R$ {ipiEntradaVal.toFixed(2)}</div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs text-muted-foreground font-medium">Custo carregado</label>
                      <div className="erp-input h-8 text-sm flex items-center font-medium">R$ {item.custo_final.toFixed(2)}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-border bg-muted/10 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Bloco 2 — Tributos e despesas da venda</p>
                  <p className="text-[11px] font-medium text-muted-foreground">Da Regra Fiscal (automático)</p>
                  <p className="text-[11px] text-muted-foreground">
                    ICMS, PIS, COFINS e IPI de saída vêm da regra cadastrada (NCM {ncmBusca || '—'} + UF origem {ufO || '—'} + UF destino{' '}
                    {ufD || '—'} + saída). Campos somente leitura.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                    <div>
                      <label className="text-xs text-muted-foreground">ICMS saída %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{(item.icms_saida_percentual ?? 0).toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">PIS %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{(item.pis_saida_percentual ?? 0).toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">COFINS %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{(item.cofins_saida_percentual ?? 0).toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">IPI saída %</label>
                      <div className="erp-input h-8 text-sm flex items-center bg-muted/40">{(item.ipi_saida_percentual ?? 0).toFixed(2)}</div>
                    </div>
                    <div className="md:col-span-2 text-[11px] text-muted-foreground flex items-end leading-snug">{msgRegra}</div>
                  </div>
                  <p className="text-[11px] font-medium text-muted-foreground pt-1">Camada gerencial (estimativa de margem — não vem da Regra Fiscal)</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">IRPJ estimado %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.irpj_estimado_percentual ?? 0}
                        onChange={(e) => updateItem(idx, { irpj_estimado_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">CSLL estimada %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.csll_estimada_percentual ?? 0}
                        onChange={(e) => updateItem(idx, { csll_estimada_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Comissão %</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.comissao_percentual ?? 0}
                        onChange={(e) => updateItem(idx, { comissao_percentual: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Frete saída (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.frete_saida ?? 0}
                        onChange={(e) => updateItem(idx, { frete_saida: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Outras despesas saída (R$)</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        className={numericClass}
                        value={item.outras_despesas_saida ?? 0}
                        onChange={(e) => updateItem(idx, { outras_despesas_saida: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">% carga tributária + gerencial</label>
                      <div className="erp-input h-8 text-sm flex items-center">{pctSaida.toFixed(2)}%</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-border bg-muted/10 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Bloco 3 — Resultado</p>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                    <div>
                      <label className="text-xs text-muted-foreground">Preço base (custo ÷ 0,60)</label>
                      <div className="erp-input h-8 text-sm flex items-center font-medium">R$ {item.preco_sugerido.toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Modo preço</label>
                      <select
                        className="erp-input h-8 text-sm"
                        value={item.modo_preco}
                        onChange={(e) => updateItem(idx, { modo_preco: e.target.value as 'sugerido' | 'manual' })}
                      >
                        <option value="sugerido">Automático (preço base)</option>
                        <option value="manual">Manual</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Preço final / unitário</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        disabled={item.modo_preco !== 'manual'}
                        className={numericClass}
                        value={item.preco_final}
                        onChange={(e) => updateItem(idx, { preco_final: +e.target.value || 0 })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Carga da venda (R$)</label>
                      <div className="erp-input h-8 text-sm flex items-center">R$ {valCarga.toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Lucro líquido estimado</label>
                      <div className="erp-input h-8 text-sm flex items-center">R$ {item.lucro_resultante.toFixed(2)}</div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Margem líquida estimada</label>
                      <div className="erp-input h-8 text-sm flex items-center gap-2">
                        <span>{item.margem_resultante.toFixed(2)}%</span>
                        <span className={margemBadge}>
                          {item.margem_resultante >= 15 ? 'OK' : item.margem_resultante >= 8 ? 'Atenção' : 'Risco'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          <div className="text-right mt-3 pt-3 border-t border-border font-bold">Total da proposta: R$ {total.toFixed(2)}</div>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Custo total</p>
              <p className="text-lg font-semibold">R$ {custoTotal.toFixed(2)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Receita total</p>
              <p className="text-lg font-semibold">R$ {receitaTotal.toFixed(2)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Lucro total</p>
              <p className="text-lg font-semibold">R$ {lucroTotal.toFixed(2)}</p>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Margem média</p>
              <div className="mt-1">
                <span className={margemBadgeClass}>{margemMedia.toFixed(2)}%</span>
              </div>
            </div>
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Quantidade total</p>
              <p className="text-lg font-semibold">{quantidadeTotalItens.toFixed(3)}</p>
            </div>
          </div>
        </div>

        {referenciaFrete && (
          <div className="mt-4 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Referência comercial de frete (apoio gerencial)</p>
            <p className="text-xs text-muted-foreground mt-1">{referenciaFrete.mensagem || '—'}</p>
            {referenciaFrete.tem_base_historica === false && (
              <p className="text-xs text-amber-800 dark:text-amber-200 mt-1">
                Sem base histórica de frete no período selecionado. Os indicadores abaixo podem aparecer vazios.
              </p>
            )}
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Frete médio observado</div>
                <div className="font-medium">
                  {referenciaFrete.referencia_historica?.frete_medio_observado == null
                    ? '—'
                    : `R$ ${referenciaFrete.referencia_historica.frete_medio_observado.toFixed(2)}`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Peso médio do frete</div>
                <div className="font-medium">
                  {referenciaFrete.referencia_historica?.peso_frete_sobre_faturamento == null
                    ? '—'
                    : `${(referenciaFrete.referencia_historica.peso_frete_sobre_faturamento).toFixed(2)}%`}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">CT-es válidos</div>
                <div className="font-medium">{referenciaFrete.referencia_historica?.quantidade_ctes_validos ?? '—'}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Período da referência</div>
                <div className="font-medium">
                  {(referenciaFrete.periodo_utilizado?.data_inicio || '—')} a {(referenciaFrete.periodo_utilizado?.data_fim || '—')}
                </div>
              </div>
            </div>
            {referenciaFrete.referencia_historica?.transportadora_referencia && (
              <p className="mt-2 text-xs text-muted-foreground">
                Referência da transportadora selecionada:{' '}
                {referenciaFrete.referencia_historica.transportadora_referencia.transportadora_nome ?? '—'}.
              </p>
            )}
          </div>
        )}

        <div className="mt-3 rounded-md border border-border bg-muted/20 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Referência comercial de custo de compra (apoio gerencial)
          </p>
          {!itemRefCusto && (
            <p className="text-xs text-muted-foreground mt-1">
              Selecione um produto (ou informe NCM fiscal válido) no item da proposta para consultar a referência histórica de custo.
            </p>
          )}
          {itemRefCusto && custoCompraRefLoading && (
            <p className="text-xs text-muted-foreground mt-1">Carregando referência de custo…</p>
          )}
          {itemRefCusto && !custoCompraRefLoading && !referenciaCustoCompra && (
            <p className="text-xs text-muted-foreground mt-1">
              Não foi possível carregar a referência de custo. A proposta segue com o fluxo comercial normal; tente de novo se precisar da referência.
            </p>
          )}
          {itemRefCusto && referenciaCustoCompra && (
            <>
              <p className="text-xs text-muted-foreground mt-1">{referenciaCustoCompra.mensagem || '—'}</p>
              {referenciaCustoCompra.tem_base_historica === false && (
                <p className="text-xs text-amber-800 dark:text-amber-200 mt-1">
                  Não há base histórica fiscal suficiente no período para este produto ou NCM. Use apenas como orientação gerencial.
                </p>
              )}
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Custo médio observado</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.custo_medio_observado == null
                      ? '—'
                      : `R$ ${referenciaCustoCompra.referencia_historica.custo_medio_observado.toFixed(2)}`}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Última compra observada</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.ultimo_custo_observado == null
                      ? '—'
                      : `R$ ${referenciaCustoCompra.referencia_historica.ultimo_custo_observado.toFixed(2)}`}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Fornecedor de referência</div>
                  <div className="font-medium">
                    {referenciaCustoCompra.referencia_historica?.fornecedor_referencia || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Período da referência</div>
                  <div className="font-medium">
                    {(referenciaCustoCompra.periodo_utilizado?.data_inicio || '—')} a{' '}
                    {(referenciaCustoCompra.periodo_utilizado?.data_fim || '—')}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button onClick={() => setModalOpen(false)} className="erp-btn-outline">Cancelar</button>
          <button onClick={handleSave} className="erp-btn-primary">Salvar</button>
        </div>
      </Modal>

      <Modal
        isOpen={wizardOpen}
        onClose={() => setWizardOpen(false)}
        title={wizardProposta ? `Converter Proposta ${wizardProposta.numero}` : 'Converter proposta'}
        size="xl"
      >
        {wizardLoading && !wizardProposta ? <p className="text-sm text-muted-foreground">Carregando dados da proposta...</p> : null}
        {wizardProposta ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {[1, 2, 3].map((step) => (
                <button
                  key={step}
                  type="button"
                  disabled={wizardLoading}
                  onClick={() => setWizardStep(step as 1 | 2 | 3)}
                  className={`rounded-md border px-3 py-2 text-sm ${wizardStep === step ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground'}`}
                >
                  {step === 1 ? '1. Cliente' : step === 2 ? '2. Itens' : '3. Validação final'}
                </button>
              ))}
            </div>

            {wizardError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{wizardError}</div>
            ) : null}

            {wizardStep === 1 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3">
                  <p className="text-sm">
                    <span className="font-medium">Cliente atual:</span>{' '}
                    {wizardProposta.cliente_nome || wizardProposta.cliente_avulso_nome || 'Não definido'}
                  </p>
                  {clienteResolvido ? (
                    <p className="mt-2 inline-flex items-center gap-1 text-xs text-success"><CheckCircle2 className="h-4 w-4" /> Cliente cadastrado já vinculado.</p>
                  ) : (
                    <p className="mt-2 text-xs text-warning">Cliente avulso detectado. Vincule ou crie cadastro antes da conversão.</p>
                  )}
                </div>

                {!clienteResolvido ? (
                  <>
                    <div className="rounded-md border border-border p-3">
                      <p className="mb-2 text-sm font-medium">Vincular cliente existente</p>
                      <div className="flex gap-2">
                        <select
                          className="erp-select"
                          value={wizardClienteId ?? ''}
                          onChange={(e) => setWizardClienteId(e.target.value ? Number(e.target.value) : null)}
                        >
                          <option value="">Selecione um cliente</option>
                          {clientes.map((cliente) => (
                            <option key={cliente.id} value={cliente.id}>
                              {cliente.razao_social}
                            </option>
                          ))}
                        </select>
                        <button type="button" className="erp-btn-outline" disabled={!wizardClienteId || wizardLoading} onClick={vincularClienteExistente}>
                          Vincular
                        </button>
                      </div>
                    </div>

                    <div className="rounded-md border border-border p-3">
                      <p className="mb-2 text-sm font-medium">Criar novo cliente a partir da proposta</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <input
                          className="erp-input"
                          placeholder="Razão social"
                          value={novoClienteNome}
                          onChange={(e) => setNovoClienteNome(e.target.value)}
                        />
                        <input
                          className="erp-input"
                          placeholder="CNPJ (somente números)"
                          value={novoClienteCnpj}
                          onChange={(e) => setNovoClienteCnpj(e.target.value)}
                        />
                      </div>
                      <button type="button" className="erp-btn-outline mt-2" disabled={wizardLoading} onClick={criarClienteDaProposta}>
                        Criar cliente e vincular
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            {wizardStep === 2 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3 text-sm">
                  Itens vinculados: <span className="font-semibold">{itensResolvidos}</span> / {wizardProposta.itens.length}
                </div>
                <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground leading-relaxed">
                  Itens avulsos usam NCM informado na proposta para a Regra Fiscal. A conversão em pedido exige <strong>NCM válido (8 dígitos)</strong> e{' '}
                  <strong>produto cadastrado</strong> em cada linha — o pedido e o faturamento seguem o cadastro de produtos.
                </div>
                {wizardProposta.itens.map((item) => (
                  <div key={item.id} className="rounded-md border border-border p-3 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium">{item.produto_nome || item.descricao_avulsa || `Item #${item.id}`}</p>
                      <div className="flex flex-wrap items-center gap-1">
                        {!item.produto_id && !ncmFiscalDigitsValid(item.ncm_avulso || '') ? (
                          <span className="erp-badge-danger text-xs">Sem NCM (8 dígitos)</span>
                        ) : null}
                        {item.produto_id ? (
                          <span className="erp-badge-success">Vinculado</span>
                        ) : (
                          <span className="erp-badge-warning">Pendente produto</span>
                        )}
                      </div>
                    </div>
                    {!item.produto_id ? (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <select
                          className="erp-select"
                          value={itemLinks[item.id] ?? ''}
                          onChange={(e) => setItemLinks((prev) => ({ ...prev, [item.id]: e.target.value ? Number(e.target.value) : null }))}
                        >
                          <option value="">Selecionar produto existente</option>
                          {produtos.map((produto) => (
                            <option key={produto.id} value={produto.id}>
                              {produto.codigo_completo} - {produto.descricao}
                            </option>
                          ))}
                        </select>
                        <button type="button" className="erp-btn-outline" disabled={!itemLinks[item.id] || wizardLoading} onClick={() => vincularItemExistente(item.id)}>
                          Vincular produto
                        </button>
                        <button type="button" className="erp-btn-ghost" disabled={wizardLoading} onClick={loadProdutos}>
                          <RefreshCw className="h-4 w-4" /> Atualizar produtos
                        </button>
                        <input
                          className="erp-input md:col-span-2"
                          placeholder="Descrição para novo produto"
                          value={novoProdutoDescricao[item.id] ?? ''}
                          onChange={(e) => setNovoProdutoDescricao((prev) => ({ ...prev, [item.id]: e.target.value }))}
                        />
                        <button type="button" className="erp-btn-outline" disabled={wizardLoading} onClick={() => criarProdutoParaItem(item.id)}>
                          Criar produto
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
                {produtosError ? <p className="text-xs text-destructive">{produtosError}</p> : null}
              </div>
            ) : null}

            {wizardStep === 3 ? (
              <div className="space-y-3">
                <div className="rounded-md border border-border p-3">
                  <p className="text-sm"><span className="font-medium">Cliente cadastrado:</span> {clienteResolvido ? 'OK' : 'Pendente'}</p>
                  <p className="text-sm"><span className="font-medium">Itens vinculados:</span> {itensPendentes.length === 0 ? 'OK' : `${itensPendentes.length} pendente(s)`}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    A conversão cria um Pedido de Venda com snapshot da proposta e impede nova conversão da mesma proposta.
                  </p>
                </div>
              </div>
            ) : null}

            <div className="flex justify-between border-t border-border pt-4">
              <button type="button" className="erp-btn-outline" onClick={() => setWizardOpen(false)} disabled={wizardLoading}>
                Fechar
              </button>
              <div className="flex gap-2">
                <button type="button" className="erp-btn-outline" disabled={wizardStep === 1 || wizardLoading} onClick={() => setWizardStep((s) => (s > 1 ? (s - 1) as 1 | 2 | 3 : s))}>
                  Voltar
                </button>
                {wizardStep < 3 ? (
                  <button
                    type="button"
                    className="erp-btn-primary"
                    disabled={wizardLoading || (wizardStep === 1 && !clienteResolvido) || (wizardStep === 2 && itensPendentes.length > 0)}
                    onClick={() => setWizardStep((s) => (s < 3 ? (s + 1) as 1 | 2 | 3 : s))}
                  >
                    Próximo
                  </button>
                ) : (
                  <button type="button" className="erp-btn-primary" disabled={!podeConverter || wizardLoading} onClick={concluirConversao}>
                    Converter em pedido
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default Propostas;
