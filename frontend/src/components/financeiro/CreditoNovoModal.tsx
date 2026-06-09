import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Modal } from '@/components/Modal';
import { ClienteSearchSelect } from '@/components/financeiro/ClienteSearchSelect';
import { FornecedorSearchSelect } from '@/components/financeiro/FornecedorSearchSelect';
import { todayIso } from '@/lib/dateBr';
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
  tipo: 'CLIENTE' | 'FORNECEDOR';
  onCreated: (credito: CreditoFinanceiro) => void;
};

const ORIGENS = Object.entries(CREDITO_ORIGEM_LABELS).filter(
  ([k]) => k !== 'NFE_DEVOLUCAO_FUTURO',
);

export function CreditoNovoModal({ open, onClose, tipo, onCreated }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [fornecedor, setFornecedor] = useState<Fornecedor | null>(null);
  const [form, setForm] = useState<CreditoFormValues>({
    valor_original: '',
    data_credito: todayIso(),
    origem_tipo: 'MANUAL',
    origem_numero: '',
    motivo: '',
    observacoes: '',
  });

  useEffect(() => {
    if (!open) return;
    setErro(null);
    setCliente(null);
    setFornecedor(null);
    setForm({
      valor_original: '',
      data_credito: todayIso(),
      origem_tipo: 'MANUAL',
      origem_numero: '',
      motivo: '',
      observacoes: '',
    });
  }, [open, tipo]);

  const titulo =
    tipo === 'CLIENTE'
      ? FINANCEIRO_ACTION_LABELS.novoCreditoCliente
      : FINANCEIRO_ACTION_LABELS.novoCreditoFornecedor;

  const salvar = async () => {
    const contraparteId = tipo === 'CLIENTE' ? cliente?.id ?? null : fornecedor?.id ?? null;
    const validacao = validarCreditoForm(contraparteId, form, tipo);
    if (validacao) {
      setErro(validacao);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const credito = await financeiroService.createCredito({
        tipo,
        cliente: tipo === 'CLIENTE' ? contraparteId : null,
        fornecedor: tipo === 'FORNECEDOR' ? contraparteId : null,
        valor_original: form.valor_original.replace(',', '.'),
        data_credito: form.data_credito,
        motivo: form.motivo.trim(),
        origem_tipo: form.origem_tipo,
        origem_numero: form.origem_numero.trim(),
        observacoes: form.observacoes.trim(),
      });
      onCreated(credito);
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível registrar o crédito.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title={titulo} size="md">
      <div className="space-y-4">
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        {tipo === 'CLIENTE' ? (
          <div>
            <label className="erp-label">Cliente</label>
            <ClienteSearchSelect
              valueId={cliente?.id ?? null}
              selectedCliente={cliente}
              onSelect={setCliente}
              onClear={() => setCliente(null)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              <Link to="/clientes" className="underline">
                Cadastrar novo cliente
              </Link>
            </p>
          </div>
        ) : (
          <div>
            <label className="erp-label">Fornecedor</label>
            <FornecedorSearchSelect
              valueId={fornecedor?.id ?? null}
              selectedFornecedor={fornecedor}
              onSelect={setFornecedor}
              onClear={() => setFornecedor(null)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              <Link to="/fornecedores" className="underline">
                Cadastrar novo fornecedor
              </Link>
            </p>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="erp-label">Valor</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.valor_original}
              onChange={(e) => setForm((p) => ({ ...p, valor_original: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Data do crédito</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_credito}
              onChange={(e) => setForm((p) => ({ ...p, data_credito: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Origem</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.origem_tipo}
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
              placeholder="Opcional"
            />
          </div>
        </div>
        <div>
          <label className="erp-label">Motivo</label>
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
            {loading ? 'Salvando…' : 'Registrar crédito'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
