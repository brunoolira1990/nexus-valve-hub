import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { ClienteSearchSelect } from '@/components/financeiro/ClienteSearchSelect';
import { todayIso } from '@/lib/dateBr';
import {
  FINANCEIRO_ACTION_LABELS,
  tituloModoConfig,
  validarContaReceberForm,
  type TituloModo,
} from '@/lib/financeiroUi';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type FormaPagamentoFixa,
  type TituloFinanceiro,
} from '@/services/api/financeiro';
import type { Cliente } from '@/types';

type Props = {
  open: boolean;
  onClose: () => void;
  modo: TituloModo;
  onCreated: (titulo: TituloFinanceiro) => void;
};

export function TituloFinanceiroNovoModal({ open, onClose, modo, onCreated }: Props) {
  const cfg = tituloModoConfig(modo);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [clienteErro, setClienteErro] = useState<string | null>(null);
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [centros, setCentros] = useState<{ id: number; nome: string }[]>([]);
  const [contasOpts, setContasOpts] = useState<{ id: number; nome: string }[]>([]);
  const [formasOpts, setFormasOpts] = useState<FormaPagamentoFixa[]>([]);
  const [form, setForm] = useState({
    data_emissao: todayIso(),
    data_vencimento: todayIso(),
    valor_original: '',
    categoria_id: '',
    centro_custo_id: '',
    forma_pagamento_prevista_codigo: '',
    conta_financeira_prevista: '',
    observacoes: '',
    gerar_parcelas: false,
    quantidade_parcelas: '1',
    intervalo_dias: '30',
    primeiro_vencimento_dias: '0',
  });

  useEffect(() => {
    if (!open || modo !== 'RECEBER') return;
    setErro(null);
    setClienteErro(null);
    setSelectedCliente(null);
    setForm({
      data_emissao: todayIso(),
      data_vencimento: todayIso(),
      valor_original: '',
      categoria_id: '',
      centro_custo_id: '',
      forma_pagamento_prevista_codigo: '',
      conta_financeira_prevista: '',
      observacoes: '',
      gerar_parcelas: false,
      quantidade_parcelas: '1',
      intervalo_dias: '30',
      primeiro_vencimento_dias: '0',
    });
    void Promise.all([
      financeiroService.listCategorias({ limit: 200, tipo: 'RECEITA' }),
      financeiroService.listCentrosCusto({ limit: 200 }),
      financeiroService.listContasAtivas(),
      financeiroService.listFormasAtivas(),
    ])
      .then(([cat, cc, contas, formas]) => {
        setCategorias((cat.results ?? []).filter((c) => c.ativo));
        setCentros((cc.results ?? []).filter((c) => c.ativo));
        setContasOpts(contas.map((c) => ({ id: c.id, nome: c.nome })));
        setFormasOpts(formas);
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar os dados do formulário.' }));
        setCategorias([]);
        setCentros([]);
        setContasOpts([]);
        setFormasOpts([]);
      });
  }, [open, modo]);

  const salvar = async () => {
    const erroValidacao = validarContaReceberForm(selectedCliente?.id ?? null, {
      data_emissao: form.data_emissao,
      data_vencimento: form.data_vencimento,
      valor_original: form.valor_original,
    });
    if (erroValidacao) {
      if (erroValidacao.includes('cliente')) setClienteErro(erroValidacao);
      else setErro(erroValidacao);
      return;
    }
    setLoading(true);
    setErro(null);
    setClienteErro(null);
    try {
      const titulo = await financeiroService.createContaReceber({
        cliente: selectedCliente!.id,
        data_emissao: form.data_emissao,
        data_vencimento: form.data_vencimento,
        valor_original: form.valor_original.replace(',', '.'),
        categoria: form.categoria_id ? Number(form.categoria_id) : null,
        centro_custo: form.centro_custo_id ? Number(form.centro_custo_id) : null,
        forma_pagamento_prevista_codigo: form.forma_pagamento_prevista_codigo || undefined,
        conta_financeira_prevista: form.conta_financeira_prevista
          ? Number(form.conta_financeira_prevista)
          : null,
        observacoes: form.observacoes,
        gerar_parcelas: form.gerar_parcelas,
        quantidade_parcelas: Number(form.quantidade_parcelas) || 1,
        intervalo_dias: Number(form.intervalo_dias) || 30,
        primeiro_vencimento_dias: Number(form.primeiro_vencimento_dias) || 0,
      });
      onCreated(titulo);
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: cfg.erroSalvar }));
    } finally {
      setLoading(false);
    }
  };

  if (modo !== 'RECEBER') return null;

  return (
    <Modal isOpen={open} onClose={onClose} title={FINANCEIRO_ACTION_LABELS.novaContaReceber} size="lg">
      <div className="space-y-4">
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        <div>
          <label className="erp-label">{cfg.contraparteLabel}</label>
          <ClienteSearchSelect
            valueId={selectedCliente?.id ?? null}
            selectedCliente={selectedCliente}
            error={clienteErro}
            onSelect={(c) => {
              setSelectedCliente(c);
              setClienteErro(null);
            }}
            onClear={() => {
              setSelectedCliente(null);
              setClienteErro(null);
            }}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="cr-emissao" className="erp-label">Emissão</label>
            <input
              id="cr-emissao"
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_emissao}
              onChange={(e) => setForm((p) => ({ ...p, data_emissao: e.target.value }))}
            />
          </div>
          <div>
            <label htmlFor="cr-vencimento" className="erp-label">Vencimento</label>
            <input
              id="cr-vencimento"
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_vencimento}
              onChange={(e) => setForm((p) => ({ ...p, data_vencimento: e.target.value }))}
            />
          </div>
          <div>
            <label htmlFor="cr-valor" className="erp-label">Valor</label>
            <input
              id="cr-valor"
              className="erp-input mt-1 w-full"
              value={form.valor_original}
              onChange={(e) => setForm((p) => ({ ...p, valor_original: e.target.value }))}
              placeholder="0,00"
            />
          </div>
          <div>
            <label className="erp-label">Categoria</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.categoria_id}
              onChange={(e) => setForm((p) => ({ ...p, categoria_id: e.target.value }))}
            >
              <option value="">—</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Centro de custo</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.centro_custo_id}
              onChange={(e) => setForm((p) => ({ ...p, centro_custo_id: e.target.value }))}
            >
              <option value="">—</option>
              {centros.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Forma de pagamento prevista</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.forma_pagamento_prevista_codigo}
              onChange={(e) =>
                setForm((p) => ({ ...p, forma_pagamento_prevista_codigo: e.target.value }))
              }
            >
              <option value="">—</option>
              {formasOpts.map((f) => (
                <option key={f.codigo} value={f.codigo}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Conta / Caixa prevista</label>
            <select
              className="erp-select mt-1 w-full"
              value={form.conta_financeira_prevista}
              onChange={(e) => setForm((p) => ({ ...p, conta_financeira_prevista: e.target.value }))}
            >
              <option value="">—</option>
              {contasOpts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={form.gerar_parcelas}
            onChange={(e) => setForm((p) => ({ ...p, gerar_parcelas: e.target.checked }))}
          />
          {FINANCEIRO_ACTION_LABELS.parcelarTitulo}
        </label>
        {form.gerar_parcelas ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 rounded-md border border-border p-3">
            <div>
              <label className="erp-label">Quantidade de parcelas</label>
              <input
                type="number"
                min={1}
                className="erp-input mt-1 w-full"
                value={form.quantidade_parcelas}
                onChange={(e) => setForm((p) => ({ ...p, quantidade_parcelas: e.target.value }))}
              />
            </div>
            <div>
              <label className="erp-label">Primeiro vencimento (dias)</label>
              <input
                type="number"
                min={0}
                className="erp-input mt-1 w-full"
                value={form.primeiro_vencimento_dias}
                onChange={(e) => setForm((p) => ({ ...p, primeiro_vencimento_dias: e.target.value }))}
              />
            </div>
            <div>
              <label className="erp-label">Intervalo entre parcelas (dias)</label>
              <input
                type="number"
                min={0}
                className="erp-input mt-1 w-full"
                value={form.intervalo_dias}
                onChange={(e) => setForm((p) => ({ ...p, intervalo_dias: e.target.value }))}
              />
            </div>
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
