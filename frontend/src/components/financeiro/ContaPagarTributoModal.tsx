import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { todayIso } from '@/lib/dateBr';
import { FINANCEIRO_ACTION_LABELS, TIPO_TRIBUTO_LABELS } from '@/lib/financeiroUi';
import { apiErrorMessage } from '@/services/api/config';
import { financeiroService, type ParcelaDefinidaPayload, type TituloFinanceiro } from '@/services/api/financeiro';

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (titulo: TituloFinanceiro) => void;
};

type ParcelaLinha = { data_vencimento: string; valor: string };

export function ContaPagarTributoModal({ open, onClose, onCreated }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [parcelar, setParcelar] = useState(false);
  const [parcelas, setParcelas] = useState<ParcelaLinha[]>([
    { data_vencimento: todayIso(), valor: '' },
  ]);
  const [form, setForm] = useState({
    tipo_tributo: 'ICMS',
    competencia: todayIso().slice(0, 7),
    periodo_apuracao: '',
    data_emissao: todayIso(),
    data_vencimento: todayIso(),
    valor_original: '',
    numero_guia: '',
    codigo_receita: '',
    observacoes: '',
  });

  useEffect(() => {
    if (!open) return;
    setErro(null);
    setParcelar(false);
    setParcelas([{ data_vencimento: todayIso(), valor: '' }]);
    setForm({
      tipo_tributo: 'ICMS',
      competencia: todayIso().slice(0, 7),
      periodo_apuracao: '',
      data_emissao: todayIso(),
      data_vencimento: todayIso(),
      valor_original: '',
      numero_guia: '',
      codigo_receita: '',
      observacoes: '',
    });
  }, [open]);

  const competenciaIso = () => {
    const [y, m] = form.competencia.split('-');
    if (!y || !m) return null;
    return `${y}-${m}-01`;
  };

  const adicionarParcela = () => {
    setParcelas((p) => [...p, { data_vencimento: todayIso(), valor: '' }]);
  };

  const salvar = async () => {
    setLoading(true);
    setErro(null);
    const valorTotal = form.valor_original.replace(',', '.');
    let payloadParcelas: ParcelaDefinidaPayload[] | undefined;
    if (parcelar) {
      payloadParcelas = parcelas.map((p, i) => ({
        numero_parcela: i + 1,
        data_vencimento: p.data_vencimento,
        valor: p.valor.replace(',', '.'),
      }));
    }
    try {
      const titulo = await financeiroService.createContaPagar({
        tipo_lancamento: 'TRIBUTO_IMPOSTO',
        tipo_tributo: form.tipo_tributo,
        competencia: competenciaIso(),
        periodo_apuracao: form.periodo_apuracao,
        data_emissao: form.data_emissao,
        data_vencimento: form.data_vencimento,
        valor_original: valorTotal,
        numero_guia: form.numero_guia,
        codigo_receita: form.codigo_receita,
        observacoes: form.observacoes,
        parcelas: payloadParcelas,
      });
      onCreated(titulo);
      onClose();
    } catch (e) {
      setErro(
        apiErrorMessage(e, {
          fallback: 'Não foi possível salvar o tributo. Verifique competência, vencimento e valor.',
        }),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title={FINANCEIRO_ACTION_LABELS.novoTributo} size="lg">
      <div className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Lançamento manual — não calcula impostos a partir de NF-e ou apuração fiscal.
        </p>
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="erp-label">Tipo de tributo</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.tipo_tributo}
              onChange={(e) => setForm((p) => ({ ...p, tipo_tributo: e.target.value }))}
            >
              {Object.entries(TIPO_TRIBUTO_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Competência</label>
            <input
              type="month"
              className="erp-input mt-1 w-full"
              value={form.competencia}
              onChange={(e) => setForm((p) => ({ ...p, competencia: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="erp-label">Período de apuração</label>
            <input
              className="erp-input mt-1 w-full"
              placeholder="Ex.: Jan/2026"
              value={form.periodo_apuracao}
              onChange={(e) => setForm((p) => ({ ...p, periodo_apuracao: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Emissão</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_emissao}
              onChange={(e) => setForm((p) => ({ ...p, data_emissao: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Vencimento</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_vencimento}
              onChange={(e) => setForm((p) => ({ ...p, data_vencimento: e.target.value }))}
              disabled={parcelar}
            />
          </div>
          <div>
            <label className="erp-label">Valor total</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.valor_original}
              onChange={(e) => setForm((p) => ({ ...p, valor_original: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Nº guia / documento (opcional)</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.numero_guia}
              onChange={(e) => setForm((p) => ({ ...p, numero_guia: e.target.value }))}
            />
          </div>
          <div>
            <label className="erp-label">Código de receita (opcional)</label>
            <input
              className="erp-input mt-1 w-full"
              value={form.codigo_receita}
              onChange={(e) => setForm((p) => ({ ...p, codigo_receita: e.target.value }))}
            />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={parcelar} onChange={(e) => setParcelar(e.target.checked)} />
          {FINANCEIRO_ACTION_LABELS.parcelar}
        </label>

        {parcelar ? (
          <div className="rounded-md border border-border p-3 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Parcelas</span>
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={adicionarParcela}>
                Adicionar parcela
              </button>
            </div>
            {parcelas.map((p, idx) => (
              <div key={idx} className="grid grid-cols-3 gap-2 items-end">
                <span className="text-sm text-muted-foreground pb-2">{String(idx + 1).padStart(3, '0')}</span>
                <input
                  type="date"
                  className="erp-input"
                  value={p.data_vencimento}
                  onChange={(e) =>
                    setParcelas((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, data_vencimento: e.target.value } : r)),
                    )
                  }
                />
                <input
                  className="erp-input"
                  placeholder="Valor"
                  value={p.valor}
                  onChange={(e) =>
                    setParcelas((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, valor: e.target.value } : r)),
                    )
                  }
                />
              </div>
            ))}
          </div>
        ) : null}

        <div>
          <label className="erp-label">Observações</label>
          <textarea
            className="erp-input mt-1 w-full min-h-[72px]"
            value={form.observacoes}
            onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
          />
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" className="erp-btn-outline" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void salvar()} disabled={loading}>
            {loading ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
