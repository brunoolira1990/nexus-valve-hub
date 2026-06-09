import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { formatDateBr, todayIso } from '@/lib/dateBr';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CREDITO_MESSAGES,
  mensagemSucessoAbatimento,
  validarAbatimentoForm,
  type TituloModo,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { apiErrorMessage } from '@/services/api/config';
import { financeiroService, type TituloFinanceiro } from '@/services/api/financeiro';

type Props = {
  open: boolean;
  onClose: () => void;
  modo: TituloModo;
  titulo: TituloFinanceiro | null;
  onSuccess: (mensagem: string, titulo: TituloFinanceiro) => void;
};

export function AbaterDevolucaoModal({ open, onClose, modo, titulo, onSuccess }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tituloFull, setTituloFull] = useState<TituloFinanceiro | null>(null);
  const [form, setForm] = useState({
    data: todayIso(),
    valor: '',
    parcela_id: '',
    motivo: '',
    documento_referencia: '',
    observacoes: '',
  });

  useEffect(() => {
    if (!open || !titulo) return;
    setErro(null);
    const load = async () => {
      const full =
        modo === 'RECEBER'
          ? await financeiroService.getContaReceber(titulo.id)
          : await financeiroService.getContaPagar(titulo.id);
      setTituloFull(full);
      const parcelasAbertas = (full.parcelas || []).filter((p) => Number(p.valor_aberto) > 0.01);
      const parcelaUnica = parcelasAbertas.length === 1 ? String(parcelasAbertas[0].id) : '';
      setForm({
        data: todayIso(),
        valor: parcelaUnica ? parcelasAbertas[0].valor_aberto : full.valor_aberto,
        parcela_id: parcelaUnica,
        motivo: '',
        documento_referencia: '',
        observacoes: '',
      });
    };
    void load();
  }, [open, titulo, modo]);

  const salvar = async () => {
    if (!titulo) return;
    const parcela = tituloFull?.parcelas?.find((p) => String(p.id) === form.parcela_id);
    const saldoTitulo = parcela?.valor_aberto ?? tituloFull?.valor_aberto ?? titulo.valor_aberto;
    const validacao = validarAbatimentoForm(form.valor, form.motivo, saldoTitulo);
    if (validacao) {
      setErro(validacao);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const payload = {
        data: form.data,
        valor: form.valor.replace(',', '.'),
        motivo: form.motivo.trim(),
        parcela: form.parcela_id ? Number(form.parcela_id) : null,
        observacoes: form.observacoes.trim(),
        documento_referencia: form.documento_referencia.trim(),
      };
      const res =
        modo === 'RECEBER'
          ? await financeiroService.abaterDevolucaoReceber(titulo.id, payload)
          : await financeiroService.abaterDevolucaoPagar(titulo.id, payload);
      const msg = mensagemSucessoAbatimento(res.titulo.valor_aberto);
      onSuccess(msg, res.titulo);
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível registrar o abatimento.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title={FINANCEIRO_ACTION_LABELS.abaterDevolucao} size="md">
      <div className="space-y-4">
        {titulo ? (
          <p className="text-sm text-muted-foreground">
            Título <span className="font-medium text-foreground">{titulo.numero}</span> — saldo em aberto{' '}
            <span className="font-medium">{formatMoneyBRL(tituloFull?.valor_aberto ?? titulo.valor_aberto)}</span>
          </p>
        ) : null}
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        {(tituloFull?.parcelas?.length ?? 0) > 1 ? (
          <div>
            <label className="erp-label">Parcela</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.parcela_id}
              onChange={(e) => {
                const pid = e.target.value;
                const parc = tituloFull?.parcelas?.find((p) => String(p.id) === pid);
                setForm((p) => ({
                  ...p,
                  parcela_id: pid,
                  valor: parc?.valor_aberto ?? p.valor,
                }));
              }}
            >
              <option value="">Selecione a parcela…</option>
              {tituloFull?.parcelas
                ?.filter((p) => Number(p.valor_aberto) > 0.01)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {String(p.numero_parcela).padStart(3, '0')} — venc. {formatDateBr(p.data_vencimento)} — saldo{' '}
                    {formatMoneyBRL(p.valor_aberto)}
                  </option>
                ))}
            </select>
          </div>
        ) : null}
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
            <label className="erp-label">Valor do abatimento</label>
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
        <div>
          <label className="erp-label">Documento de referência</label>
          <input
            className="erp-input mt-1 w-full"
            value={form.documento_referencia}
            onChange={(e) => setForm((p) => ({ ...p, documento_referencia: e.target.value }))}
            placeholder="Opcional"
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
          <button type="button" className="erp-btn-primary" onClick={() => void salvar()} disabled={loading || !titulo}>
            {loading ? 'Registrando…' : 'Confirmar abatimento'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
