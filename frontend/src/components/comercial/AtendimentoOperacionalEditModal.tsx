import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import {
  AlocacaoAtendimentoVinculosForm,
  type VinculosFormValues,
} from '@/components/comercial/AlocacaoAtendimentoVinculosForm';
import {
  AVISO_SEGURANCA_ALOCACAO,
  vinculosFromAlocacao,
} from '@/components/comercial/AlocacaoAtendimentoGerenciarPanel';
import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';
import { apiErrorMessage } from '@/services/api/config';
import {
  DESTINO_FISICO,
  ORIGEM_FISICA,
  STATUS_ENTRADA_FISCAL,
  TIPOS_ATENDIMENTO,
  type AlocacaoAtendimento,
  type AlocacaoAtendimentoPayload,
} from '@/types/alocacaoAtendimento';
import type {
  OpcaoCteConferido,
  OpcaoFornecedor,
  OpcaoNfeEntradaImportada,
  OpcaoNfeEntradaImportadaItem,
  OpcaoPedidoCompra,
  OpcaoPedidoCompraItem,
} from '@/types/alocacaoAtendimentoOpcoes';

type Props = {
  alocacaoId: number | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
};

type FormState = {
  quantidade_necessaria: string;
  quantidade_atendida: string;
  quantidade_pendente: string;
  tipo_atendimento: string;
  status_entrada_fiscal: string;
  origem_fisica: string;
  destino_fisico: string;
  observacao_operacional: string;
};

export function AtendimentoOperacionalEditModal({ alocacaoId, open, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [alocacao, setAlocacao] = useState<AlocacaoAtendimento | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [vinculos, setVinculos] = useState<VinculosFormValues>({
    fornecedor_id: null,
    pedido_compra_item_id: null,
    nf_entrada_historica_item_id: null,
    cte_historico_importado_id: null,
  });
  const [selFornecedor, setSelFornecedor] = useState<OpcaoFornecedor | null>(null);
  const [selPedidoCompra, setSelPedidoCompra] = useState<OpcaoPedidoCompra | null>(null);
  const [selPedidoCompraItem, setSelPedidoCompraItem] = useState<OpcaoPedidoCompraItem | null>(null);
  const [selNfeEntrada, setSelNfeEntrada] = useState<OpcaoNfeEntradaImportada | null>(null);
  const [selNfeEntradaItem, setSelNfeEntradaItem] = useState<OpcaoNfeEntradaImportadaItem | null>(null);
  const [selCte, setSelCte] = useState<OpcaoCteConferido | null>(null);

  const load = useCallback(async () => {
    if (!alocacaoId) return;
    setLoading(true);
    try {
      const data = await alocacaoAtendimentoService.get(alocacaoId);
      setAlocacao(data);
      const v = vinculosFromAlocacao(data);
      setVinculos(v.values);
      setSelFornecedor(v.fornecedor);
      setSelPedidoCompra(v.pedidoCompra);
      setSelPedidoCompraItem(v.pedidoCompraItem);
      setSelNfeEntrada(v.nfeEntrada);
      setSelNfeEntradaItem(v.nfeEntradaItem);
      setSelCte(v.cte);
      setForm({
        quantidade_necessaria: data.quantidade_necessaria,
        quantidade_atendida: data.quantidade_atendida,
        quantidade_pendente: data.quantidade_pendente,
        tipo_atendimento: data.tipo_atendimento,
        status_entrada_fiscal: data.status_entrada_fiscal,
        origem_fisica: data.origem_fisica,
        destino_fisico: data.destino_fisico,
        observacao_operacional: data.observacao_operacional || '',
      });
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar a alocação.' }));
      onClose();
    } finally {
      setLoading(false);
    }
  }, [alocacaoId, onClose]);

  useEffect(() => {
    if (open && alocacaoId) void load();
    if (!open) {
      setAlocacao(null);
      setForm(null);
    }
  }, [open, alocacaoId, load]);

  const handleSave = async () => {
    if (!alocacao || !form) return;
    setSaving(true);
    try {
      const payload: AlocacaoAtendimentoPayload = {
        produto_id: alocacao.produto_id,
        pedido_venda_item_id: alocacao.pedido_venda_item_id,
        item_nf_saida_id: alocacao.item_nf_saida_id,
        faturamento_item_id: alocacao.faturamento_item_id,
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
      await alocacaoAtendimentoService.update(alocacao.id, payload);
      toast.success('Atendimento operacional atualizado.');
      onSaved();
      onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível salvar.' }));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Editar atendimento operacional"
      size="lg"
    >
      {loading || !form || !alocacao ? (
        <p className="text-sm text-muted-foreground py-4">Carregando…</p>
      ) : (
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          <p className="text-xs text-muted-foreground border-b border-border pb-2">{AVISO_SEGURANCA_ALOCACAO}</p>
          <p className="text-sm">
            <span className="font-medium">{alocacao.produto_codigo}</span>
            {' — '}
            {alocacao.produto_nome}
            {alocacao.pedido_venda_numero ? (
              <span className="text-muted-foreground"> · PV {alocacao.pedido_venda_numero}</span>
            ) : null}
          </p>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="erp-label">Qtd necessária</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_necessaria}
                onChange={(e) => setForm((f) => (f ? { ...f, quantidade_necessaria: e.target.value } : f))}
              />
            </div>
            <div>
              <label className="erp-label">Qtd atendida</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_atendida}
                onChange={(e) => setForm((f) => (f ? { ...f, quantidade_atendida: e.target.value } : f))}
              />
            </div>
            <div>
              <label className="erp-label">Qtd pendente</label>
              <input
                className="erp-input mt-1 w-full"
                value={form.quantidade_pendente}
                onChange={(e) => setForm((f) => (f ? { ...f, quantidade_pendente: e.target.value } : f))}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="erp-label">Tipo de atendimento</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.tipo_atendimento}
                onChange={(e) => setForm((f) => (f ? { ...f, tipo_atendimento: e.target.value } : f))}
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
                onChange={(e) => setForm((f) => (f ? { ...f, status_entrada_fiscal: e.target.value } : f))}
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
                onChange={(e) => setForm((f) => (f ? { ...f, origem_fisica: e.target.value } : f))}
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
                onChange={(e) => setForm((f) => (f ? { ...f, destino_fisico: e.target.value } : f))}
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
            produtoId={alocacao.produto_id}
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
              onChange={(e) => setForm((f) => (f ? { ...f, observacao_operacional: e.target.value } : f))}
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <button type="button" className="erp-btn-outline" onClick={onClose}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" disabled={saving} onClick={() => void handleSave()}>
              {saving ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
