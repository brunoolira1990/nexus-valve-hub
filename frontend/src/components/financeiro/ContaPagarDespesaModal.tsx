import { useEffect, useState } from 'react';
import { Modal } from '@/components/Modal';
import { FornecedorSearchSelect } from '@/components/financeiro/FornecedorSearchSelect';
import { todayIso } from '@/lib/dateBr';
import { FINANCEIRO_ACTION_LABELS, FINANCEIRO_FORNECEDOR_MESSAGES } from '@/lib/financeiroUi';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type FormaPagamentoFixa,
  type TituloFinanceiro,
} from '@/services/api/financeiro';
import type { Fornecedor } from '@/types';

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (titulo: TituloFinanceiro) => void;
  /** DESPESA_OPERACIONAL | SERVICO | OUTROS | FORNECEDOR */
  tipoLancamento: string;
  tituloModal?: string;
};

export function ContaPagarDespesaModal({
  open,
  onClose,
  onCreated,
  tipoLancamento,
  tituloModal = FINANCEIRO_ACTION_LABELS.novaDespesa,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [fornecedorErro, setFornecedorErro] = useState<string | null>(null);
  const [selectedFornecedor, setSelectedFornecedor] = useState<Fornecedor | null>(null);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [contasOpts, setContasOpts] = useState<{ id: number; nome: string }[]>([]);
  const [formasOpts, setFormasOpts] = useState<FormaPagamentoFixa[]>([]);
  const [form, setForm] = useState({
    descricao: '',
    categoria_id: '',
    data_emissao: todayIso(),
    competencia: todayIso().slice(0, 7),
    data_vencimento: todayIso(),
    valor_original: '',
    forma_pagamento_prevista_codigo: '',
    conta_financeira_prevista: '',
    observacoes: '',
  });

  useEffect(() => {
    if (!open) return;
    setErro(null);
    setFornecedorErro(null);
    setSelectedFornecedor(null);
    setForm({
      descricao: '',
      categoria_id: '',
      data_emissao: todayIso(),
      competencia: todayIso().slice(0, 7),
      data_vencimento: todayIso(),
      valor_original: '',
      forma_pagamento_prevista_codigo: '',
      conta_financeira_prevista: '',
      observacoes: '',
    });
    void Promise.all([
      financeiroService.listCategorias({ limit: 200, tipo: 'DESPESA' }),
      financeiroService.listContasAtivas(),
      financeiroService.listFormasAtivas(),
    ])
      .then(([cat, contas, formas]) => {
        setCategorias((cat.results ?? []).filter((c) => c.ativo));
        setContasOpts(contas.map((c) => ({ id: c.id, nome: c.nome })));
        setFormasOpts(formas);
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar os dados do formulário.' }));
        setCategorias([]);
        setContasOpts([]);
        setFormasOpts([]);
      });
  }, [open]);

  const competenciaIso = () => {
    const [y, m] = form.competencia.split('-');
    if (!y || !m) return null;
    return `${y}-${m}-01`;
  };

  const fornecedorObrigatorio = tipoLancamento === 'FORNECEDOR';

  const salvar = async () => {
    if (fornecedorObrigatorio && !selectedFornecedor) {
      setFornecedorErro(FINANCEIRO_FORNECEDOR_MESSAGES.selecioneFornecedor);
      return;
    }
    setLoading(true);
    setErro(null);
    setFornecedorErro(null);
    try {
      const titulo = await financeiroService.createContaPagar({
        tipo_lancamento: tipoLancamento,
        descricao: form.descricao,
        fornecedor: selectedFornecedor?.id ?? null,
        categoria: form.categoria_id ? Number(form.categoria_id) : null,
        data_emissao: form.data_emissao,
        competencia: competenciaIso(),
        data_vencimento: form.data_vencimento,
        valor_original: form.valor_original.replace(',', '.'),
        forma_pagamento_prevista_codigo: form.forma_pagamento_prevista_codigo || undefined,
        conta_financeira_prevista: form.conta_financeira_prevista
          ? Number(form.conta_financeira_prevista)
          : null,
        observacoes: form.observacoes,
      });
      onCreated(titulo);
      onClose();
    } catch (e) {
      setErro(
        apiErrorMessage(e, {
          fallback: 'Não foi possível salvar. Verifique descrição, vencimento e valor.',
        }),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={open} onClose={onClose} title={tituloModal} size="lg">
      <div className="space-y-4">
        {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        <div>
          <label htmlFor="cp-despesa-descricao" className="erp-label">Descrição</label>
          <input
            id="cp-despesa-descricao"
            className="erp-input mt-1 w-full"
            value={form.descricao}
            onChange={(e) => setForm((p) => ({ ...p, descricao: e.target.value }))}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="erp-label">
              Fornecedor{fornecedorObrigatorio ? '' : ' (opcional)'}
            </label>
            <FornecedorSearchSelect
              valueId={selectedFornecedor?.id ?? null}
              selectedFornecedor={selectedFornecedor}
              error={fornecedorErro}
              helperText={
                fornecedorObrigatorio ? undefined : FINANCEIRO_FORNECEDOR_MESSAGES.despesaFornecedorOpcional
              }
              onSelect={(f) => {
                setSelectedFornecedor(f);
                setFornecedorErro(null);
              }}
              onClear={() => {
                setSelectedFornecedor(null);
                setFornecedorErro(null);
              }}
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
            <label className="erp-label">Emissão</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_emissao}
              onChange={(e) => setForm((p) => ({ ...p, data_emissao: e.target.value }))}
            />
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
          <div>
            <label className="erp-label">Vencimento</label>
            <input
              type="date"
              className="erp-input mt-1 w-full"
              value={form.data_vencimento}
              onChange={(e) => setForm((p) => ({ ...p, data_vencimento: e.target.value }))}
            />
          </div>
          <div>
            <label htmlFor="cp-despesa-valor" className="erp-label">Valor</label>
            <input
              id="cp-despesa-valor"
              className="erp-input mt-1 w-full"
              value={form.valor_original}
              onChange={(e) => setForm((p) => ({ ...p, valor_original: e.target.value }))}
            />
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
