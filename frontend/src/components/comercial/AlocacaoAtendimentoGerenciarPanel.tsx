import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { AtendimentoOperacionalBadge } from '@/components/comercial/AtendimentoOperacionalBadge';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { NexusCard } from '@/components/nexus/NexusCard';
import {
  AlocacaoAtendimentoVinculosForm,
  type VinculosFormValues,
} from '@/components/comercial/AlocacaoAtendimentoVinculosForm';
import { AlocacaoVinculosLinha } from '@/components/comercial/AlocacaoVinculosLinha';
import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';
import { apiErrorMessage } from '@/services/api/config';
import { formatProdutoComercialLinha } from '@/lib/formatBr';
import type {
  OpcaoCteConferido,
  OpcaoFornecedor,
  OpcaoNfeEntradaImportada,
  OpcaoNfeEntradaImportadaItem,
  OpcaoPedidoCompra,
  OpcaoPedidoCompraItem,
} from '@/types/alocacaoAtendimentoOpcoes';
import {
  DESTINO_FISICO,
  ORIGEM_FISICA,
  STATUS_ENTRADA_FISCAL,
  TIPOS_ATENDIMENTO,
  type AlocacaoAtendimento,
  type AlocacaoAtendimentoPayload,
} from '@/types/alocacaoAtendimento';
import type { ItemPedido } from '@/types';
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

export const AVISO_SEGURANCA_ALOCACAO =
  'A gestão de atendimento é operacional e informativa. Esta ação não movimenta estoque, não gera financeiro, não cria expedição e não altera NF-e.';

const AVISO_SEGURANCA = AVISO_SEGURANCA_ALOCACAO;

export type NfeItemAlocacaoOption = {
  item_nf_saida_id: number;
  produto_id: number;
  label: string;
  quantidade: string;
};

type Props = {
  pedidoVendaId?: number;
  nfeSaidaId?: number;
  faturamentoId?: number;
  itens?: ItemPedido[];
  nfeItens?: NfeItemAlocacaoOption[];
  resumoInicial?: ResumoAtendimentoOperacional | null;
  compacto?: boolean;
  onResumoAtualizado?: (resumo: ResumoAtendimentoOperacional) => void;
};

type FormState = {
  id?: number;
  pedido_venda_item: string;
  item_nf_saida: string;
  produto: string;
  quantidade_necessaria: string;
  quantidade_atendida: string;
  quantidade_pendente: string;
  tipo_atendimento: string;
  status_entrada_fiscal: string;
  origem_fisica: string;
  destino_fisico: string;
  observacao_operacional: string;
};

const emptyVinculos = (): VinculosFormValues => ({
  fornecedor_id: null,
  pedido_compra_item_id: null,
  nf_entrada_historica_item_id: null,
  cte_historico_importado_id: null,
});

const emptyForm = (): FormState => ({
  pedido_venda_item: '',
  item_nf_saida: '',
  produto: '',
  quantidade_necessaria: '1',
  quantidade_atendida: '0',
  quantidade_pendente: '1',
  tipo_atendimento: 'RETIRADA_FORNECEDOR',
  status_entrada_fiscal: 'PENDENTE',
  origem_fisica: 'FORNECEDOR',
  destino_fisico: 'CLIENTE',
  observacao_operacional: '',
});

function numOrNull(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

function alertasContextuais(form: FormState, vinculos: VinculosFormValues): string[] {
  const msgs: string[] = [];
  if (form.status_entrada_fiscal === 'PENDENTE') {
    msgs.push(
      'Entrada fiscal pendente. Esta condição não bloqueia a emissão da NF-e conforme operação Nexus.',
    );
  }
  if (form.tipo_atendimento === 'ENTREGA_DIRETA_FORNECEDOR_CLIENTE') {
    msgs.push('Entrega direta registrada apenas como intenção operacional.');
  }
  if (
    vinculos.nf_entrada_historica_item_id ||
    vinculos.cte_historico_importado_id ||
    vinculos.pedido_compra_item_id
  ) {
    msgs.push('Documento vinculado para rastreabilidade. Não gera efeito automático.');
  }
  return msgs;
}

export function vinculosFromAlocacao(a: AlocacaoAtendimento): {
  values: VinculosFormValues;
  fornecedor: OpcaoFornecedor | null;
  pedidoCompra: OpcaoPedidoCompra | null;
  pedidoCompraItem: OpcaoPedidoCompraItem | null;
  nfeEntrada: OpcaoNfeEntradaImportada | null;
  nfeEntradaItem: OpcaoNfeEntradaImportadaItem | null;
  cte: OpcaoCteConferido | null;
} {
  const v = a.vinculos;
  const values: VinculosFormValues = {
    fornecedor_id: a.fornecedor_id,
    pedido_compra_item_id: a.pedido_compra_item_id,
    nf_entrada_historica_item_id: a.nf_entrada_historica_item_id,
    cte_historico_importado_id: a.cte_historico_importado_id,
  };
  return {
    values,
    fornecedor: a.fornecedor_id
      ? { id: a.fornecedor_id, label: v?.fornecedor_label || `Fornecedor #${a.fornecedor_id}`, cnpj: '', cidade: '', uf: '' }
      : null,
    pedidoCompra:
      v?.pedido_compra_id && v.pedido_compra_label
        ? {
            id: v.pedido_compra_id,
            numero: v.pedido_compra_label,
            fornecedor: '',
            fornecedor_id: a.fornecedor_id,
            data: '',
            status: '',
            valor_total: '',
            label: v.pedido_compra_label,
          }
        : null,
    pedidoCompraItem: a.pedido_compra_item_id
      ? {
          id: a.pedido_compra_item_id,
          pedido_compra_id: v?.pedido_compra_id ?? 0,
          produto_id: a.produto_id,
          produto_nome: a.produto_nome,
          quantidade: a.quantidade_necessaria,
          quantidade_disponivel_para_vinculo: a.quantidade_necessaria,
          unidade: 'UN',
          label: `${a.produto_nome} — ${v?.pedido_compra_label || 'PC'}`,
        }
      : null,
    nfeEntrada: v?.nfe_entrada_label
      ? {
          id: v.nfe_entrada_historica_id ?? 0,
          numero: '',
          serie: '',
          chave: '',
          chave_resumida: '',
          fornecedor: v.fornecedor_label || '',
          fornecedor_id: a.fornecedor_id,
          emissao: '',
          valor_total: '',
          status_conferencia: v.nfe_entrada_status_conferencia,
          label: v.nfe_entrada_label,
        }
      : null,
    nfeEntradaItem: a.nf_entrada_historica_item_id
      ? {
          id: a.nf_entrada_historica_item_id,
          nfe_entrada_historica_id: v?.nfe_entrada_historica_id ?? 0,
          produto_id: a.produto_id,
          produto_nome: a.produto_nome,
          codigo: a.produto_codigo,
          ncm: '',
          cfop: '',
          quantidade: a.quantidade_necessaria,
          valor_total: '',
          label: v?.nfe_entrada_label || `Item NF-e #${a.nf_entrada_historica_item_id}`,
        }
      : null,
    cte: v?.cte_label
      ? {
          id: a.cte_historico_importado_id ?? 0,
          numero: '',
          serie: '',
          transportadora: '',
          transportadora_id: null,
          tomador: '',
          valor_total: '',
          emissao: '',
          status_conferencia: v.cte_status_conferencia || 'CONFERIDO',
          label: v.cte_label,
        }
      : null,
  };
}

export function AlocacaoAtendimentoGerenciarPanel({
  pedidoVendaId,
  nfeSaidaId,
  faturamentoId,
  itens = [],
  nfeItens = [],
  resumoInicial,
  compacto = false,
  onResumoAtualizado,
}: Props) {
  const [alocacoes, setAlocacoes] = useState<AlocacaoAtendimento[]>([]);
  const [resumo, setResumo] = useState<ResumoAtendimentoOperacional | null | undefined>(resumoInicial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [vinculos, setVinculos] = useState<VinculosFormValues>(emptyVinculos);
  const [selFornecedor, setSelFornecedor] = useState<OpcaoFornecedor | null>(null);
  const [selPedidoCompra, setSelPedidoCompra] = useState<OpcaoPedidoCompra | null>(null);
  const [selPedidoCompraItem, setSelPedidoCompraItem] = useState<OpcaoPedidoCompraItem | null>(null);
  const [selNfeEntrada, setSelNfeEntrada] = useState<OpcaoNfeEntradaImportada | null>(null);
  const [selNfeEntradaItem, setSelNfeEntradaItem] = useState<OpcaoNfeEntradaImportadaItem | null>(null);
  const [selCte, setSelCte] = useState<OpcaoCteConferido | null>(null);
  const [saving, setSaving] = useState(false);

  const itensComId = useMemo(() => itens.filter((i) => i.id > 0), [itens]);

  const onResumoAtualizadoRef = useRef(onResumoAtualizado);
  useEffect(() => {
    onResumoAtualizadoRef.current = onResumoAtualizado;
  }, [onResumoAtualizado]);

  const load = useCallback(
    async (notifyParent = false) => {
      if (!pedidoVendaId && !nfeSaidaId) return;
      setLoading(true);
      setError(null);
      try {
        const data = pedidoVendaId
          ? await alocacaoAtendimentoService.listByPedidoVenda(pedidoVendaId, faturamentoId)
          : await alocacaoAtendimentoService.listByNFeSaida(nfeSaidaId!);
        setAlocacoes(data.alocacoes);
        setResumo(data.resumo_atendimento_operacional);
        if (notifyParent) {
          onResumoAtualizadoRef.current?.(data.resumo_atendimento_operacional);
        }
      } catch (e) {
        setError(apiErrorMessage(e, { fallback: 'Não foi possível carregar alocações de atendimento.' }));
      } finally {
        setLoading(false);
      }
    },
    [pedidoVendaId, nfeSaidaId, faturamentoId],
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  const resetVinculos = () => {
    setVinculos(emptyVinculos());
    setSelFornecedor(null);
    setSelPedidoCompra(null);
    setSelPedidoCompraItem(null);
    setSelNfeEntrada(null);
    setSelNfeEntradaItem(null);
    setSelCte(null);
  };

  const openCreate = () => {
    resetVinculos();
    const firstPv = itensComId[0];
    const firstNfe = nfeItens[0];
    setForm({
      ...emptyForm(),
      pedido_venda_item: firstPv ? String(firstPv.id) : '',
      item_nf_saida: firstNfe ? String(firstNfe.item_nf_saida_id) : '',
      produto: firstPv
        ? String(firstPv.produto_id)
        : firstNfe
          ? String(firstNfe.produto_id)
          : '',
      quantidade_necessaria: firstPv
        ? String(firstPv.quantidade_negociada ?? firstPv.quantidade ?? 1)
        : firstNfe
          ? firstNfe.quantidade
          : '1',
      quantidade_pendente: firstPv
        ? String(firstPv.quantidade_negociada ?? firstPv.quantidade ?? 1)
        : firstNfe
          ? firstNfe.quantidade
          : '1',
    });
    setFormOpen(true);
  };

  const openEdit = (a: AlocacaoAtendimento) => {
    const v = vinculosFromAlocacao(a);
    setVinculos(v.values);
    setSelFornecedor(v.fornecedor);
    setSelPedidoCompra(v.pedidoCompra);
    setSelPedidoCompraItem(v.pedidoCompraItem);
    setSelNfeEntrada(v.nfeEntrada);
    setSelNfeEntradaItem(v.nfeEntradaItem);
    setSelCte(v.cte);
    setForm({
      id: a.id,
      pedido_venda_item: a.pedido_venda_item_id ? String(a.pedido_venda_item_id) : '',
      item_nf_saida: a.item_nf_saida_id ? String(a.item_nf_saida_id) : '',
      produto: String(a.produto_id),
      quantidade_necessaria: a.quantidade_necessaria,
      quantidade_atendida: a.quantidade_atendida,
      quantidade_pendente: a.quantidade_pendente,
      tipo_atendimento: a.tipo_atendimento,
      status_entrada_fiscal: a.status_entrada_fiscal,
      origem_fisica: a.origem_fisica,
      destino_fisico: a.destino_fisico,
      observacao_operacional: a.observacao_operacional || '',
    });
    setFormOpen(true);
  };

  const buildPayload = (): AlocacaoAtendimentoPayload => {
    const produtoId = numOrNull(form.produto);
    if (!produtoId) throw new Error('Selecione o produto.');
    const pvi = numOrNull(form.pedido_venda_item);
    const itemNf = numOrNull(form.item_nf_saida);
    return {
      pedido_venda_item_id: pvi,
      item_nf_saida_id: itemNf,
      produto_id: produtoId,
      quantidade_necessaria: form.quantidade_necessaria,
      quantidade_atendida: form.quantidade_atendida,
      quantidade_pendente: form.quantidade_pendente,
      tipo_atendimento: form.tipo_atendimento,
      status_entrada_fiscal: form.status_entrada_fiscal,
      origem_fisica: form.origem_fisica,
      destino_fisico: form.destino_fisico,
      fornecedor_id: vinculos.fornecedor_id,
      pedido_compra_item_id: vinculos.pedido_compra_item_id,
      nf_entrada_historica_item_id: vinculos.nf_entrada_historica_item_id,
      cte_historico_importado_id: vinculos.cte_historico_importado_id,
      observacao_operacional: form.observacao_operacional,
    };
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = buildPayload();
      if (form.id) {
        await alocacaoAtendimentoService.update(form.id, payload);
        toast.success('Alocação atualizada.');
      } else {
        if (!payload.pedido_venda_item_id && !payload.item_nf_saida_id) {
          toast.error('Informe o item do pedido de venda ou o item da NF-e saída.');
          return;
        }
        await alocacaoAtendimentoService.create(payload);
        toast.success('Alocação criada.');
      }
      setFormOpen(false);
      await load(true);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível salvar a alocação.' }));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Excluir esta alocação de atendimento?')) return;
    try {
      await alocacaoAtendimentoService.remove(id);
      toast.success('Alocação excluída.');
      await load(true);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível excluir.' }));
    }
  };

  const onItemChange = (itemId: string) => {
    const item = itensComId.find((i) => String(i.id) === itemId);
    setForm((f) => ({
      ...f,
      pedido_venda_item: itemId,
      produto: item ? String(item.produto_id) : f.produto,
      quantidade_necessaria: item
        ? String(item.quantidade_negociada ?? item.quantidade)
        : f.quantidade_necessaria,
      quantidade_pendente: item
        ? String(item.quantidade_negociada ?? item.quantidade)
        : f.quantidade_pendente,
    }));
  };

  const ctxAlertas = alertasContextuais(form, vinculos);
  const produtoIdForm = numOrNull(form.produto);

  if (!pedidoVendaId && !nfeSaidaId) {
    return (
      <p className="text-sm text-muted-foreground">Salve o documento para gerenciar atendimento operacional.</p>
    );
  }

  return (
    <div className={compacto ? 'space-y-3' : 'space-y-4'}>
      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
        {AVISO_SEGURANCA}
      </div>

      {!compacto ? <AtendimentoOperacionalResumo resumo={resumo} titulo="Resumo do atendimento" /> : null}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Alocações por item</h4>
        <button type="button" className="erp-btn-primary erp-btn-sm inline-flex items-center gap-1" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5" />
          Adicionar alocação
        </button>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? <p className="text-xs text-muted-foreground">Carregando alocações…</p> : null}

      {!loading && alocacoes.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma alocação registrada. Use &quot;Adicionar alocação&quot; para definir a intenção operacional.</p>
      ) : null}

      {alocacoes.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                <th className="px-2 py-1.5">Produto</th>
                <th className="px-2 py-1.5">Qtd nec / at / pen</th>
                <th className="px-2 py-1.5">Tipo</th>
                <th className="px-2 py-1.5">Entrada</th>
                <th className="px-2 py-1.5 w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {alocacoes.map((a) => (
                <tr key={a.id} className="border-b border-border/60">
                  <td className="px-2 py-2">
                    <div
                      className="font-medium truncate max-w-[220px]"
                      title={formatProdutoComercialLinha(a.produto_codigo, a.produto_nome).tituloCompleto}
                    >
                      {formatProdutoComercialLinha(a.produto_codigo, a.produto_nome).linha}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {(a.badges ?? []).slice(0, 3).map((b) => (
                        <AtendimentoOperacionalBadge key={`${a.id}-${b.status}`} badge={b} />
                      ))}
                    </div>
                    <AlocacaoVinculosLinha vinculos={a.vinculos} />
                  </td>
                  <td className="px-2 py-2 tabular-nums text-xs">
                    {a.quantidade_necessaria} / {a.quantidade_atendida} / {a.quantidade_pendente}
                  </td>
                  <td className="px-2 py-2 text-xs">{a.tipo_atendimento_label}</td>
                  <td className="px-2 py-2 text-xs">{a.status_entrada_fiscal_label}</td>
                  <td className="px-2 py-2">
                    <div className="flex gap-1">
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm p-1"
                        title="Editar"
                        onClick={() => openEdit(a)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm p-1 text-destructive"
                        title="Excluir"
                        onClick={() => void handleDelete(a.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Modal
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        title={form.id ? 'Editar alocação de atendimento' : 'Nova alocação de atendimento'}
        size="lg"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          <p className="text-xs text-muted-foreground border-b border-border pb-2">{AVISO_SEGURANCA}</p>
          {ctxAlertas.map((msg) => (
            <p key={msg} className="text-xs text-amber-800 dark:text-amber-200 rounded bg-amber-500/10 px-2 py-1">
              {msg}
            </p>
          ))}

          {itensComId.length > 0 ? (
            <div>
              <label className="erp-label">Item do pedido de venda</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.pedido_venda_item}
                onChange={(e) => onItemChange(e.target.value)}
              >
                <option value="">—</option>
                {itensComId.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.produto_nome} (qtd {it.quantidade_negociada ?? it.quantidade})
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {nfeItens.length > 0 ? (
            <div>
              <label className="erp-label">Item da NF-e saída</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.item_nf_saida}
                onChange={(e) => {
                  const opt = nfeItens.find((x) => String(x.item_nf_saida_id) === e.target.value);
                  setForm((f) => ({
                    ...f,
                    item_nf_saida: e.target.value,
                    produto: opt ? String(opt.produto_id) : f.produto,
                    quantidade_necessaria: opt?.quantidade ?? f.quantidade_necessaria,
                    quantidade_pendente: opt?.quantidade ?? f.quantidade_pendente,
                  }));
                }}
              >
                <option value="">—</option>
                {nfeItens.map((it) => (
                  <option key={it.item_nf_saida_id} value={it.item_nf_saida_id}>
                    {it.label} (qtd {it.quantidade})
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="erp-label">Qtd necessária</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_necessaria}
                onChange={(e) => setForm((f) => ({ ...f, quantidade_necessaria: e.target.value }))}
              />
            </div>
            <div>
              <label className="erp-label">Qtd atendida</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_atendida}
                onChange={(e) => setForm((f) => ({ ...f, quantidade_atendida: e.target.value }))}
              />
            </div>
            <div>
              <label className="erp-label">Qtd pendente</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_pendente}
                onChange={(e) => setForm((f) => ({ ...f, quantidade_pendente: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="erp-label">Tipo de atendimento</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.tipo_atendimento}
                onChange={(e) => setForm((f) => ({ ...f, tipo_atendimento: e.target.value }))}
              >
                {TIPOS_ATENDIMENTO.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="erp-label">Status entrada fiscal</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.status_entrada_fiscal}
                onChange={(e) => setForm((f) => ({ ...f, status_entrada_fiscal: e.target.value }))}
              >
                {STATUS_ENTRADA_FISCAL.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="erp-label">Origem física</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.origem_fisica}
                onChange={(e) => setForm((f) => ({ ...f, origem_fisica: e.target.value }))}
              >
                {ORIGEM_FISICA.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="erp-label">Destino físico</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.destino_fisico}
                onChange={(e) => setForm((f) => ({ ...f, destino_fisico: e.target.value }))}
              >
                {DESTINO_FISICO.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <AlocacaoAtendimentoVinculosForm
            produtoId={produtoIdForm}
            values={vinculos}
            fornecedor={selFornecedor}
            pedidoCompra={selPedidoCompra}
            pedidoCompraItem={selPedidoCompraItem}
            nfeEntrada={selNfeEntrada}
            nfeEntradaItem={selNfeEntradaItem}
            cte={selCte}
            onChange={(patch) => setVinculos((v) => ({ ...v, ...patch }))}
            onSelectFornecedor={setSelFornecedor}
            onSelectPedidoCompra={setSelPedidoCompra}
            onSelectPedidoCompraItem={setSelPedidoCompraItem}
            onSelectNfeEntrada={setSelNfeEntrada}
            onSelectNfeEntradaItem={setSelNfeEntradaItem}
            onSelectCte={setSelCte}
          />

          <div>
            <label className="erp-label">Observação operacional</label>
            <textarea
              className="erp-input mt-1 w-full min-h-[72px]"
              value={form.observacao_operacional}
              onChange={(e) => setForm((f) => ({ ...f, observacao_operacional: e.target.value }))}
            />
          </div>

          <input type="hidden" value={form.produto} readOnly />

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <button type="button" className="erp-btn-outline" onClick={() => setFormOpen(false)}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" disabled={saving} onClick={() => void handleSave()}>
              {saving ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

/** Botão + painel expansível para faturamento / NF-e. */
export function AlocacaoAtendimentoGerenciarSection(props: Props) {
  const [open, setOpen] = useState(false);
  return (
    <NexusCard className="p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium">Atendimento operacional</span>
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setOpen((v) => !v)}>
          {open ? 'Ocultar' : 'Gerenciar atendimento'}
        </button>
      </div>
      {open ? <AlocacaoAtendimentoGerenciarPanel {...props} compacto /> : null}
    </NexusCard>
  );
}
