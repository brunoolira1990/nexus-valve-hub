import { useState } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { FornecedorSearchSelect } from '@/components/financeiro/FornecedorSearchSelect';
import { apiErrorMessage } from '@/services/api/config';
import type { Fornecedor, FornecedorEntradaStatus } from '@/types';

type Props = {
  status?: FornecedorEntradaStatus | null;
  sugestaoCadastro?: Partial<FornecedorEntradaStatus['sugestao_cadastro']>;
  busy?: boolean;
  onVincular: (fornecedorId: number) => Promise<void>;
  onCadastrar: (payload: Record<string, unknown>) => Promise<void>;
  className?: string;
};

export function FornecedorEntradaAcoes({
  status,
  sugestaoCadastro,
  busy = false,
  onVincular,
  onCadastrar,
  className = '',
}: Props) {
  const [modalCadastro, setModalCadastro] = useState(false);
  const [modalVincular, setModalVincular] = useState(false);
  const [form, setForm] = useState({
    razao_social: '',
    cnpj: '',
    ie: '',
    uf: '',
    cidade: '',
    logradouro: '',
    numero: '',
    bairro: '',
    cep: '',
  });
  const [fornecedorSel, setFornecedorSel] = useState<Fornecedor | null>(null);
  const [acaoBusy, setAcaoBusy] = useState(false);

  const st = status;
  const identificado = Boolean(st?.identificado || st?.fornecedor_id);
  const sugestao = sugestaoCadastro || st?.sugestao_cadastro;

  const abrirCadastro = () => {
    setForm({
      razao_social: sugestao?.razao_social || st?.fornecedor_nome || '',
      cnpj: sugestao?.cnpj || st?.cnpj_documento || st?.fornecedor_cnpj || '',
      ie: sugestao?.ie || '',
      uf: sugestao?.uf || '',
      cidade: sugestao?.cidade || '',
      logradouro: sugestao?.logradouro || '',
      numero: sugestao?.numero || '',
      bairro: sugestao?.bairro || '',
      cep: sugestao?.cep || '',
    });
    setModalCadastro(true);
  };

  const salvarCadastro = async () => {
    setAcaoBusy(true);
    try {
      await onCadastrar(form);
      setModalCadastro(false);
      toast.success('Fornecedor cadastrado e vinculado à entrada.');
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setAcaoBusy(false);
    }
  };

  const salvarVinculo = async () => {
    if (!fornecedorSel?.id) {
      toast.error('Selecione um fornecedor.');
      return;
    }
    setAcaoBusy(true);
    try {
      await onVincular(fornecedorSel.id);
      setModalVincular(false);
      setFornecedorSel(null);
      toast.success('Fornecedor vinculado à entrada.');
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setAcaoBusy(false);
    }
  };

  if (st?.status === 'propria_empresa' || st?.remetente_propria_empresa) {
    return (
      <div className={`text-xs text-sky-900 bg-sky-50 border border-sky-200 rounded-md px-3 py-2 ${className}`}>
        <strong>Remetente é a própria empresa</strong>
        {st?.fornecedor_nome ? <> — {st.fornecedor_nome}</> : null}
        <span className="block mt-1 text-muted-foreground">
          {st?.mensagem ||
            'CT-e de frete de saída/remessa. Não cadastre como fornecedor. O credor do frete é a transportadora.'}
        </span>
      </div>
    );
  }

  if (identificado) {
    return (
      <div className={`text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-md px-3 py-2 ${className}`}>
        Fornecedor identificado: <strong>{st?.fornecedor_nome}</strong>
        {st?.vinculo_automatico ? ' (vínculo automático por CNPJ)' : ''}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
        {st?.mensagem || 'Fornecedor não identificado na NF-e Entrada.'}
        {st?.cnpj_documento ? (
          <span className="block mt-1 text-muted-foreground">CNPJ do XML: {st.cnpj_documento}</span>
        ) : null}
      </p>
      <div className="flex flex-wrap gap-2">
        {st?.pode_cadastrar !== false ? (
          <button type="button" className="erp-btn-outline erp-btn-sm" disabled={busy || acaoBusy} onClick={abrirCadastro}>
            Cadastrar fornecedor
          </button>
        ) : null}
        {st?.pode_vincular_manual !== false ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={busy || acaoBusy}
            onClick={() => setModalVincular(true)}
          >
            Vincular fornecedor
          </button>
        ) : null}
      </div>
      {st?.status === 'duplicidade' && (st.candidatos?.length ?? 0) > 0 ? (
        <ul className="text-xs text-muted-foreground list-disc pl-4">
          {st.candidatos?.map((c) => (
            <li key={c.id}>
              #{c.id} — {c.razao_social} ({c.cnpj}){c.ativo ? '' : ' [inativo]'}
            </li>
          ))}
        </ul>
      ) : null}

      <Modal isOpen={modalCadastro} onClose={() => setModalCadastro(false)} title="Cadastrar fornecedor">
        <div className="grid gap-3 sm:grid-cols-2 text-sm">
          <label className="sm:col-span-2">
            <span className="text-xs text-muted-foreground">Razão social *</span>
            <input
              className="erp-input mt-1 w-full"
              value={form.razao_social}
              onChange={(e) => setForm((f) => ({ ...f, razao_social: e.target.value }))}
            />
          </label>
          <label>
            <span className="text-xs text-muted-foreground">CNPJ</span>
            <input className="erp-input mt-1 w-full" value={form.cnpj} readOnly />
          </label>
          <label>
            <span className="text-xs text-muted-foreground">IE</span>
            <input
              className="erp-input mt-1 w-full"
              value={form.ie}
              onChange={(e) => setForm((f) => ({ ...f, ie: e.target.value }))}
            />
          </label>
          <label>
            <span className="text-xs text-muted-foreground">UF</span>
            <input
              className="erp-input mt-1 w-full"
              value={form.uf}
              onChange={(e) => setForm((f) => ({ ...f, uf: e.target.value }))}
            />
          </label>
          <label>
            <span className="text-xs text-muted-foreground">Cidade</span>
            <input
              className="erp-input mt-1 w-full"
              value={form.cidade}
              onChange={(e) => setForm((f) => ({ ...f, cidade: e.target.value }))}
            />
          </label>
          <label className="sm:col-span-2">
            <span className="text-xs text-muted-foreground">Logradouro</span>
            <input
              className="erp-input mt-1 w-full"
              value={form.logradouro}
              onChange={(e) => setForm((f) => ({ ...f, logradouro: e.target.value }))}
            />
          </label>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button type="button" className="erp-btn-outline" onClick={() => setModalCadastro(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" disabled={acaoBusy} onClick={() => void salvarCadastro()}>
            Salvar e vincular
          </button>
        </div>
      </Modal>

      <Modal isOpen={modalVincular} onClose={() => setModalVincular(false)} title="Vincular fornecedor existente">
        <FornecedorSearchSelect
          valueId={fornecedorSel?.id ?? null}
          selectedFornecedor={fornecedorSel}
          onSelect={setFornecedorSel}
          onClear={() => setFornecedorSel(null)}
        />
        <div className="flex justify-end gap-2 mt-4">
          <button type="button" className="erp-btn-outline" onClick={() => setModalVincular(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" disabled={acaoBusy} onClick={() => void salvarVinculo()}>
            Vincular
          </button>
        </div>
      </Modal>
    </div>
  );
}
