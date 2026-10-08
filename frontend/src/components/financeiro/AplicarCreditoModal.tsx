import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { formatDateBr, todayIso } from '@/lib/dateBr';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_CREDITO_MESSAGES,
  mensagemSucessoAplicarCredito,
  tituloModoConfig,
  validarAplicarCreditoForm,
  type TituloModo,
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
  modo: TituloModo;
  titulo: TituloFinanceiro | null;
  onSuccess: (mensagem: string, titulo: TituloFinanceiro) => void;
};

export function AplicarCreditoModal({ open, onClose, modo, titulo, onSuccess }: Props) {
  const cfg = tituloModoConfig(modo);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [creditos, setCreditos] = useState<CreditoFinanceiro[]>([]);
  const [tituloFull, setTituloFull] = useState<TituloFinanceiro | null>(null);
  const [form, setForm] = useState({
    credito_id: '',
    data: todayIso(),
    valor: '',
    parcela_id: '',
    motivo: '',
    observacoes: '',
  });

  const creditoSelecionado = creditos.find((c) => String(c.id) === form.credito_id);

  useEffect(() => {
    if (!open || !titulo) return;
    setErro(null);
    const load = async () => {
      const full =
        modo === 'RECEBER'
          ? await financeiroService.getContaReceber(titulo.id)
          : await financeiroService.getContaPagar(titulo.id);
      setTituloFull(full);
      const params =
        modo === 'RECEBER'
          ? { cliente: String(titulo.cliente), disponivel: 'true', limit: 100 }
          : { fornecedor: String(titulo.fornecedor), disponivel: 'true', limit: 100 };
      const lista = await financeiroService.listCreditos(params);
      const disponiveis = (lista.results ?? []).filter((c) => c.pode_aplicar !== false);
      setCreditos(disponiveis);
      const parcelasAbertas = (full.parcelas || []).filter((p) => Number(p.valor_aberto) > 0.01);
      const parcelaUnica = parcelasAbertas.length === 1 ? String(parcelasAbertas[0].id) : '';
      const saldoTitulo = parcelaUnica ? parcelasAbertas[0].valor_aberto : full.valor_aberto;
      setForm({
        credito_id: disponiveis.length === 1 ? String(disponiveis[0].id) : '',
        data: todayIso(),
        valor: saldoTitulo,
        parcela_id: parcelaUnica,
        motivo: '',
        observacoes: '',
      });
    };
    void load();
  }, [open, titulo, modo]);

  const salvar = async () => {
    if (!titulo || !creditoSelecionado) return;
    const saldoCredito = creditoSelecionado.saldo;
    const parcela = tituloFull?.parcelas?.find((p) => String(p.id) === form.parcela_id);
    const saldoTitulo = parcela?.valor_aberto ?? tituloFull?.valor_aberto ?? titulo.valor_aberto;
    const validacao = validarAplicarCreditoForm(
      creditoSelecionado.id,
      form.valor,
      saldoCredito,
      saldoTitulo,
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
      const res = await financeiroService.aplicarCredito(creditoSelecionado.id, {
        titulo: titulo.id,
        valor: form.valor.replace(',', '.'),
        data: form.data,
        parcela: form.parcela_id ? Number(form.parcela_id) : null,
        motivo: form.motivo.trim(),
        observacoes: form.observacoes.trim(),
      });
      const msg = mensagemSucessoAplicarCredito(res.titulo.valor_aberto);
      onSuccess(msg, res.titulo);
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível aplicar o crédito.' }));
    } finally {
      setLoading(false);
    }
  };

  const tituloLabel =
    modo === 'RECEBER' ? FINANCEIRO_ACTION_LABELS.aplicarCredito : FINANCEIRO_ACTION_LABELS.aplicarCreditoFornecedor;

  return (
    <Modal isOpen={open} onClose={onClose} title={tituloLabel} size="md">
      <div className="space-y-4">
        {titulo ? (
          <p className="text-sm text-muted-foreground">
            Título <span className="font-medium text-foreground">{titulo.numero}</span> — saldo em aberto{' '}
            <span className="font-medium">{formatMoneyBRL(tituloFull?.valor_aberto ?? titulo.valor_aberto)}</span>
          </p>
        ) : null}
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        {creditos.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum crédito disponível para este {cfg.contraparteLabel.toLowerCase()}.
          </p>
        ) : (
          <>
            <div>
              <label className="erp-label">Crédito disponível</label>
              <select
                className="erp-select mt-1 w-full"
                value={form.credito_id}
                onChange={(e) => {
                  const c = creditos.find((cr) => String(cr.id) === e.target.value);
                  setForm((p) => ({
                    ...p,
                    credito_id: e.target.value,
                    valor: c?.saldo ?? p.valor,
                  }));
                }}
              >
                <option value="">Selecione…</option>
                {creditos.map((c) => (
                  <option key={c.id} value={c.id}>
                    #{c.id} — saldo {formatMoneyBRL(c.saldo)} — {c.motivo}
                  </option>
                ))}
              </select>
              {creditoSelecionado ? (
                <p className="text-xs text-muted-foreground mt-1">
                  Saldo do crédito: {formatMoneyBRL(creditoSelecionado.saldo)}
                </p>
              ) : null}
            </div>
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
            <div>
              <label className="erp-label">Observações</label>
              <textarea
                className="erp-input mt-1 w-full min-h-[72px]"
                value={form.observacoes}
                onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
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
            disabled={loading || !titulo || creditos.length === 0}
          >
            {loading ? 'Aplicando…' : 'Aplicar crédito'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
