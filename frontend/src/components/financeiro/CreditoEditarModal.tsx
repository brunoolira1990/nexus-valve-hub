import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { ClienteSearchSelect } from '@/components/financeiro/ClienteSearchSelect';
import { FornecedorSearchSelect } from '@/components/financeiro/FornecedorSearchSelect';
import {
  CREDITO_ORIGEM_LABELS,
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CREDITO_MESSAGES,
  validarCreditoForm,
  type CreditoFormValues,
} from '@/lib/financeiroUi';
import { apiErrorMessage } from '@/services/api/config';
import { financeiroService, type CreditoFinanceiro } from '@/services/api/financeiro';
import type { Cliente, Fornecedor } from '@/types';

type Props = {
  open: boolean;
  onClose: () => void;
  credito: CreditoFinanceiro | null;
  onUpdated: (credito: CreditoFinanceiro) => void;
};

const ORIGENS = Object.entries(CREDITO_ORIGEM_LABELS).filter(
  ([k]) => k !== 'NFE_DEVOLUCAO_FUTURO',
);

export function CreditoEditarModal({ open, onClose, credito, onUpdated }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [fornecedor, setFornecedor] = useState<Fornecedor | null>(null);
  const [form, setForm] = useState<CreditoFormValues>({
    valor_original: '',
    data_credito: '',
    origem_tipo: 'MANUAL',
    origem_numero: '',
    motivo: '',
    observacoes: '',
  });

  const tipo = credito?.tipo ?? 'CLIENTE';
  const edicaoCompleta = credito?.pode_editar_completo !== false && !credito?.possui_movimento;

  useEffect(() => {
    if (!open || !credito) return;
    setErro(null);
    setForm({
      valor_original: credito.valor_original,
      data_credito: credito.data_credito,
      origem_tipo: credito.origem_tipo || 'MANUAL',
      origem_numero: credito.origem_numero || '',
      motivo: credito.motivo || '',
      observacoes: credito.observacoes || '',
    });
    if (credito.tipo === 'CLIENTE' && credito.cliente) {
      setCliente({
        id: credito.cliente,
        razao_social: credito.cliente_nome || credito.contraparte_nome || '',
        cnpj: credito.cliente_cnpj || '',
      } as Cliente);
      setFornecedor(null);
    } else if (credito.fornecedor) {
      setFornecedor({
        id: credito.fornecedor,
        razao_social: credito.fornecedor_nome || credito.contraparte_nome || '',
        cnpj: credito.fornecedor_cnpj || '',
      } as Fornecedor);
      setCliente(null);
    }
  }, [open, credito]);

  const salvar = async () => {
    if (!credito) return;
    const contraparteId = tipo === 'CLIENTE' ? cliente?.id ?? null : fornecedor?.id ?? null;
    if (edicaoCompleta) {
      const validacao = validarCreditoForm(contraparteId, form, tipo);
      if (validacao) {
        setErro(validacao);
        return;
      }
    }
    setLoading(true);
    setErro(null);
    try {
      const payload = edicaoCompleta
        ? {
            cliente: tipo === 'CLIENTE' ? contraparteId : undefined,
            fornecedor: tipo === 'FORNECEDOR' ? contraparteId : undefined,
            valor_original: form.valor_original.replace(',', '.'),
            data_credito: form.data_credito,
            origem_tipo: form.origem_tipo,
            origem_numero: form.origem_numero.trim(),
            motivo: form.motivo.trim(),
            observacoes: form.observacoes.trim(),
          }
        : {
            origem_numero: form.origem_numero.trim(),
            motivo: form.motivo.trim(),
            observacoes: form.observacoes.trim(),
          };
      const atualizado = await financeiroService.patchCredito(credito.id, payload);
      onUpdated(atualizado);
      onClose();
    } catch (e) {
      setErro(
        apiErrorMessage(e, {
          fallback: FINANCEIRO_CREDITO_MESSAGES.creditoEdicaoBloqueada,
        }),
      );
    } finally {
      setLoading(false);
    }
  };

  if (!credito) return null;

  return (
    <Modal isOpen={open} onClose={onClose} title={FINANCEIRO_ACTION_LABELS.editarCredito} size="md">
      <div className="space-y-4">
        {!edicaoCompleta ? (
          <p className="text-sm text-muted-foreground rounded-md border border-border bg-muted/30 px-3 py-2">
            {FINANCEIRO_CREDITO_MESSAGES.creditoEdicaoBloqueada}
          </p>
        ) : null}
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        {tipo === 'CLIENTE' ? (
          <div>
            <label className="erp-label">Cliente</label>
            <ClienteSearchSelect
              valueId={cliente?.id ?? null}
              selectedCliente={cliente}
              onSelect={setCliente}
              onClear={() => setCliente(null)}
              disabled={!edicaoCompleta}
            />
          </div>
        ) : (
          <div>
            <label className="erp-label">Fornecedor</label>
            <FornecedorSearchSelect
              valueId={fornecedor?.id ?? null}
              selectedFornecedor={fornecedor}
              onSelect={setFornecedor}
              onClear={() => setFornecedor(null)}
              disabled={!edicaoCompleta}
            />
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="erp-label">Valor</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.valor_original}
              disabled={!edicaoCompleta}
              onChange={(e) => setForm((p) => ({ ...p, valor_original: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Data do crédito</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_credito}
              disabled={!edicaoCompleta}
              onChange={(e) => setForm((p) => ({ ...p, data_credito: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Origem</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.origem_tipo}
              disabled={!edicaoCompleta}
              onChange={(e) => setForm((p) => ({ ...p, origem_tipo: e.target.value }))}
            >
              {ORIGENS.map(([codigo, label]) => (
                <option key={codigo} value={codigo}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Documento de referência</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.origem_numero}
              onChange={(e) => setForm((p) => ({ ...p, origem_numero: e.target.value }))}
            />
          </div>
        </div>
        <div>
          <label className="erp-label">{edicaoCompleta ? 'Motivo' : 'Motivo complementar'}</label>
          <input
            className="erp-input mt-1 w-full"
            value={form.motivo}
            onChange={(e) => setForm((p) => ({ ...p, motivo: e.target.value }))}
          />
        </div>
        <div>
          <label className="erp-label">Observações</label>
          <textarea
            className="erp-input mt-1 w-full min-h-[72px]"
            value={form.observacoes}
            onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="erp-btn-outline" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void salvar()} disabled={loading}>
            {loading ? 'Salvando…' : 'Salvar alterações'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
