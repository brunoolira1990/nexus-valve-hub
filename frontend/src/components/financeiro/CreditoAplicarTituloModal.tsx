import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { formatDateBr, todayIso } from '@/lib/dateBr';
import {
  FINANCEIRO_CREDITO_MESSAGES,
  mensagemSucessoAplicarCredito,
  validarAplicarCreditoForm,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type CreditoFinanceiro,
  type TituloFinanceiro,
} from '@/services/api/financeiro';

type Props = {
  open: boolean;
  onClose: () => void;
  credito: CreditoFinanceiro | null;
  onSuccess: (mensagem: string, credito: CreditoFinanceiro) => void;
};

export function CreditoAplicarTituloModal({ open, onClose, credito, onSuccess }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [titulos, setTitulos] = useState<TituloFinanceiro[]>([]);
  const [form, setForm] = useState({
    titulo_id: '',
    data: todayIso(),
    valor: '',
    motivo: '',
    observacoes: '',
  });

  const tituloSelecionado = titulos.find((t) => String(t.id) === form.titulo_id);

  useEffect(() => {
    if (!open || !credito) return;
    setErro(null);
    const load = async () => {
      const params =
        credito.tipo === 'CLIENTE'
          ? { cliente: String(credito.cliente), status: 'EM_ABERTO', limit: 100 }
          : { fornecedor: String(credito.fornecedor), status: 'EM_ABERTO', limit: 100 };
      const lista =
        credito.tipo === 'CLIENTE'
          ? await financeiroService.listContasReceber(params)
          : await financeiroService.listContasPagar(params);
      const abertos = (lista.results ?? []).filter((t) => Number(t.valor_aberto) > 0.01 && !t.cancelado);
      setTitulos(abertos);
      setForm({
        titulo_id: abertos.length === 1 ? String(abertos[0].id) : '',
        data: todayIso(),
        valor: credito.saldo,
        motivo: '',
        observacoes: '',
      });
    };
    void load();
  }, [open, credito]);

  const salvar = async () => {
    if (!credito || !tituloSelecionado) return;
    const validacao = validarAplicarCreditoForm(
      credito.id,
      form.valor,
      credito.saldo,
      tituloSelecionado.valor_aberto,
    );
    if (validacao) {
      setErro(validacao);
      return;
    }
    if (!(form.motivo.trim() || form.observacoes.trim())) {
      setErro(FINANCEIRO_CREDITO_MESSAGES.informeMotivo);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const res = await financeiroService.aplicarCredito(credito.id, {
        titulo: tituloSelecionado.id,
        valor: form.valor.replace(',', '.'),
        data: form.data,
        motivo: form.motivo.trim(),
        observacoes: form.observacoes.trim(),
      });
      const msg = mensagemSucessoAplicarCredito(res.titulo.valor_aberto);
      onSuccess(msg, res.credito);
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível aplicar o crédito.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title="Aplicar crédito em título" size="md">
      <div className="space-y-4">
        {credito ? (
          <p className="text-sm text-muted-foreground">
            Crédito #{credito.id} — saldo {formatMoneyBRL(credito.saldo)} — {credito.contraparte_nome}
          </p>
        ) : null}
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        {titulos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum título em aberto para aplicar este crédito.</p>
        ) : (
          <>
            <div>
              <label className="erp-label">Título de destino</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.titulo_id}
                onChange={(e) => {
                  const t = titulos.find((tit) => String(tit.id) === e.target.value);
                  setForm((p) => ({
                    ...p,
                    titulo_id: e.target.value,
                    valor: t?.valor_aberto ?? p.valor,
                  }));
                }}
              >
                <option value="">Selecione…</option>
                {titulos.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.numero} — venc. {formatDateBr(t.data_vencimento)} — saldo {formatMoneyBRL(t.valor_aberto)}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="erp-label">Data</label>
                <input
                  type="date"
                  className="erp-input mt-1 w-full"
                  value={form.data}
                  onChange={(e) => setForm((p) => ({ ...p, data: e.target.value }))}
                />
              </div>
              <div>
                <label className="erp-label">Valor a aplicar</label>
                <input
                  className="erp-input mt-1 w-full"
                  value={form.valor}
                  onChange={(e) => setForm((p) => ({ ...p, valor: e.target.value }))}
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
          </>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="erp-btn-outline" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary"
            onClick={() => void salvar()}
            disabled={loading || !credito || titulos.length === 0}
          >
            {loading ? 'Aplicando…' : 'Aplicar crédito'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
