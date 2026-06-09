import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { formatDateBr, todayIso } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { tituloModoConfig, type TituloModo } from '@/lib/financeiroUi';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type BaixaPayload,
  type ContaFinanceira,
  type FormaPagamentoFixa,
  type TituloFinanceiro,
} from '@/services/api/financeiro';

type Props = {
  open: boolean;
  onClose: () => void;
  modo: TituloModo;
  titulo: TituloFinanceiro | null;
  onSuccess: (mensagem: string, titulo: TituloFinanceiro) => void;
};

export function TituloFinanceiroBaixaModal({ open, onClose, modo, titulo, onSuccess }: Props) {
  const cfg = tituloModoConfig(modo);
  const [contas, setContas] = useState<ContaFinanceira[]>([]);
  const [formas, setFormas] = useState<FormaPagamentoFixa[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tituloFull, setTituloFull] = useState<TituloFinanceiro | null>(null);
  const [form, setForm] = useState({
    data_baixa: todayIso(),
    valor: '',
    parcela_id: '',
    conta_financeira: '',
    forma_pagamento: '',
    juros: '0',
    multa: '0',
    desconto: '0',
    tarifa: '0',
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
      setForm((p) => ({
        ...p,
        data_baixa: todayIso(),
        valor: parcelaUnica ? parcelasAbertas[0].valor_aberto : full.valor_aberto,
        parcela_id: parcelaUnica,
        conta_financeira: full.conta_financeira_prevista
          ? String(full.conta_financeira_prevista)
          : p.conta_financeira,
        forma_pagamento: full.forma_pagamento_prevista_codigo || p.forma_pagamento,
      }));
    };
    void load();
    void Promise.all([financeiroService.listContasAtivas(), financeiroService.listFormasFixas()]).then(
      ([c, f]) => {
        setContas(c);
        setFormas(f.formas_pagamento);
      },
    );
  }, [open, titulo, modo]);

  const salvar = async () => {
    if (!titulo) return;
    setLoading(true);
    setErro(null);
    const payload: BaixaPayload = {
      data_baixa: form.data_baixa,
      valor: form.valor.replace(',', '.'),
      conta_financeira: form.conta_financeira ? Number(form.conta_financeira) : undefined,
      forma_pagamento_codigo: form.forma_pagamento,
      juros: form.juros.replace(',', '.'),
      multa: form.multa.replace(',', '.'),
      desconto: form.desconto.replace(',', '.'),
      tarifa: form.tarifa.replace(',', '.'),
      observacoes: form.observacoes,
      parcela: form.parcela_id ? Number(form.parcela_id) : null,
    };
    try {
      const res =
        modo === 'RECEBER'
          ? await financeiroService.baixarReceber(titulo.id, payload)
          : await financeiroService.baixarPagar(titulo.id, payload);
      onSuccess(
        titulo.tipo === 'RECEBER' ? 'Recebimento registrado com sucesso.' : 'Pagamento registrado com sucesso.',
        res.titulo,
      );
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível registrar a baixa. Verifique os dados.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title={cfg.baixarLabel} size="md">
      <div className="space-y-4">
        {titulo ? (
          <p className="text-sm text-muted-foreground">
            Título <span className="font-medium text-foreground">{titulo.numero}</span> — valor em aberto{' '}
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
              value={form.data_baixa}
              onChange={(e) => setForm((p) => ({ ...p, data_baixa: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Valor</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.valor}
              onChange={(e) => setForm((p) => ({ ...p, valor: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Conta / Caixa</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.conta_financeira}
              onChange={(e) => setForm((p) => ({ ...p, conta_financeira: e.target.value }))}
            >
              <option value="">Selecione…</option>
              {contas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Forma de pagamento</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.forma_pagamento}
              onChange={(e) => setForm((p) => ({ ...p, forma_pagamento: e.target.value }))}
            >
              <option value="">Selecione…</option>
              {formas.map((f) => (
                <option key={f.codigo} value={f.codigo}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Juros</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.juros}
              onChange={(e) => setForm((p) => ({ ...p, juros: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Multa</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.multa}
              onChange={(e) => setForm((p) => ({ ...p, multa: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Desconto</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.desconto}
              onChange={(e) => setForm((p) => ({ ...p, desconto: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Tarifa</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.tarifa}
              onChange={(e) => setForm((p) => ({ ...p, tarifa: e.target.value }))}
            />
          </div>
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
            {loading ? 'Registrando…' : 'Confirmar baixa'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
