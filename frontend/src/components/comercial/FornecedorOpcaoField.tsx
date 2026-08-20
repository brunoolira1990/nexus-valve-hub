import { useCallback, useState } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { Modal } from '@/components/Modal';
import { formatCnpjDisplay, isValidCnpj, normalizeCnpj } from '@/lib/cnpj';
import { formatCnpj } from '@/lib/masks';
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { fornecedoresService } from '@/services/api/fornecedores';
import type { OpcaoFornecedor } from '@/types/alocacaoAtendimentoOpcoes';
import type { Fornecedor } from '@/types';

type QuickForm = {
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  ie: string;
  telefone: string;
  email: string;
  cep: string;
  logradouro: string;
  numero: string;
  bairro: string;
  cidade: string;
  uf: string;
  observacoes: string;
};

function emptyQuickForm(): QuickForm {
  return {
    cnpj: '',
    razao_social: '',
    nome_fantasia: '',
    ie: '',
    telefone: '',
    email: '',
    cep: '',
    logradouro: '',
    numero: '',
    bairro: '',
    cidade: '',
    uf: '',
    observacoes: '',
  };
}

export function fornecedorToOpcao(f: Fornecedor): OpcaoFornecedor {
  const label = (f.razao_social || f.nome_fantasia || `#${f.id}`).trim();
  return {
    id: f.id,
    label,
    cnpj: f.cnpj || '',
    cidade: f.cidade || '',
    uf: f.uf || '',
  };
}

function quickToCreatePayload(q: QuickForm): Omit<Fornecedor, 'id'> {
  const uf = (q.uf || '').trim().toUpperCase().slice(0, 2);
  return {
    razao_social: q.razao_social.trim(),
    nome_fantasia: q.nome_fantasia.trim(),
    cnpj: normalizeCnpj(q.cnpj),
    ie: q.ie.trim(),
    logradouro: q.logradouro.trim(),
    numero: q.numero.trim(),
    complemento: '',
    bairro: q.bairro.trim(),
    cidade: q.cidade.trim(),
    uf,
    cep: q.cep.trim(),
    telefone: q.telefone.trim(),
    email: q.email.trim(),
    contato_responsavel: '',
    observacoes: q.observacoes.trim(),
    inscricao_municipal: '',
    suframa: '',
    email_nf: '',
    telefone_alternativo: '',
    celular: '',
    condicao_pagamento_texto: '',
    dias_parcelas: [],
    quantidade_parcelas: 0,
    transportadora_padrao_id: null,
    prazo_entrega: 0,
    ativo: true,
    ddd: '',
    banco: '',
    agencia: '',
    conta: '',
    tipo_conta: '',
    cnae: '',
    regime_tributario: '',
    integracao_texto: '',
  };
}

export type FornecedorOpcaoFieldProps = {
  valueId: number | null;
  selectedOption: OpcaoFornecedor | null;
  disabled?: boolean;
  onSelect: (opt: OpcaoFornecedor | null) => void;
};

export function FornecedorOpcaoField({
  valueId,
  selectedOption,
  disabled,
  onSelect,
}: FornecedorOpcaoFieldProps) {
  const [quickOpen, setQuickOpen] = useState(false);
  const [quick, setQuick] = useState<QuickForm>(() => emptyQuickForm());
  const [quickSaving, setQuickSaving] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);

  const buscar = useCallback(async (term: string, limit?: number) => {
    const rows = await fornecedoresService.search(term, limit ?? 25);
    return rows.map(fornecedorToOpcao);
  }, []);

  const abrirCadastro = () => {
    setQuick(emptyQuickForm());
    setQuickError(null);
    setQuickOpen(true);
  };

  const salvarQuick = async () => {
    setQuickError(null);
    const rs = quick.razao_social.trim();
    const cnpj = normalizeCnpj(quick.cnpj);
    if (!rs) {
      setQuickError('Informe a razão social.');
      return;
    }
    if (!cnpj) {
      setQuickError('Informe o CNPJ.');
      return;
    }
    if (!isValidCnpj(cnpj)) {
      setQuickError('CNPJ inválido.');
      return;
    }
    setQuickSaving(true);
    try {
      const created = await fornecedoresService.create(quickToCreatePayload(quick));
      onSelect(fornecedorToOpcao(created));
      setQuickOpen(false);
      setQuick(emptyQuickForm());
    } catch (e) {
      setQuickError(apiErrorMessage(e, { fallback: 'Não foi possível salvar o fornecedor.' }));
    } finally {
      setQuickSaving(false);
    }
  };

  const footer = (
    <div className="px-2 py-2">
      <button
        type="button"
        className="w-full rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-2 text-left text-sm font-medium text-primary hover:bg-primary/10"
        onClick={abrirCadastro}
        disabled={disabled}
      >
        + Cadastrar novo fornecedor
      </button>
    </div>
  );

  return (
    <>
      <AsyncAutocomplete<OpcaoFornecedor>
        value={valueId}
        selectedOption={selectedOption}
        placeholder="Buscar por nome ou CNPJ…"
        disabled={disabled}
        search={buscar}
        getOptionValue={(o) => o.id}
        getOptionLabel={(o) => o.label}
        renderOption={(o) => (
          <span>
            {o.label}
            {o.cnpj ? <span className="block text-xs text-muted-foreground">{formatCnpjDisplay(o.cnpj)}</span> : null}
          </span>
        )}
        renderListFooter={() => footer}
        onChange={(id, opt) => onSelect(id != null && opt ? opt : null)}
      />
      <button
        type="button"
        className="text-sm font-medium text-primary hover:underline mt-1"
        onClick={abrirCadastro}
        disabled={disabled}
      >
        + Cadastrar novo fornecedor
      </button>

      <Modal
        open={quickOpen}
        onClose={() => !quickSaving && setQuickOpen(false)}
        title="Cadastrar fornecedor"
        size="md"
        footer={
          <>
            <button type="button" className="erp-btn-outline" onClick={() => setQuickOpen(false)} disabled={quickSaving}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" onClick={() => void salvarQuick()} disabled={quickSaving}>
              {quickSaving ? 'Salvando…' : 'Salvar e usar'}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          {quickError ? <p className="text-sm text-destructive">{quickError}</p> : null}
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <label className="erp-label">CNPJ</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.cnpj}
                onChange={(e) => setQuick((p) => ({ ...p, cnpj: formatCnpj(e.target.value) }))}
                disabled={quickSaving}
              />
            </div>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm shrink-0"
              disabled={quickSaving}
              onClick={() => {
                const cnpj = normalizeCnpj(quick.cnpj);
                if (cnpj.length !== 14 || !isValidCnpj(cnpj)) {
                  setQuickError('Informe um CNPJ válido com 14 caracteres.');
                  return;
                }
                setQuickError(null);
                void consultaCnpj(cnpj).then(({ data }) =>
                  setQuick((prev) => ({
                    ...prev,
                    razao_social: (data.razao_social || prev.razao_social).trim(),
                    nome_fantasia: (data.nome_fantasia || prev.nome_fantasia).trim(),
                    logradouro: (data.logradouro || prev.logradouro).trim(),
                    numero: (data.numero || prev.numero).trim(),
                    bairro: (data.bairro || prev.bairro).trim(),
                    cidade: (data.cidade || prev.cidade).trim(),
                    uf: ((data.uf || prev.uf) as string).trim().toUpperCase().slice(0, 2),
                    cep: (data.cep || prev.cep).trim(),
                    telefone: (data.telefone || prev.telefone).trim(),
                    email: (data.email || prev.email).trim(),
                  })),
                );
              }}
            >
              Consultar CNPJ
            </button>
          </div>
          <div>
            <label className="erp-label">Razão social</label>
            <input
              className="erp-input mt-1 w-full"
              value={quick.razao_social}
              onChange={(e) => setQuick((p) => ({ ...p, razao_social: e.target.value }))}
              disabled={quickSaving}
            />
          </div>
          <div>
            <label className="erp-label">Nome fantasia</label>
            <input
              className="erp-input mt-1 w-full"
              value={quick.nome_fantasia}
              onChange={(e) => setQuick((p) => ({ ...p, nome_fantasia: e.target.value }))}
              disabled={quickSaving}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="erp-label">Telefone</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.telefone}
                onChange={(e) => setQuick((p) => ({ ...p, telefone: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">E-mail</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.email}
                onChange={(e) => setQuick((p) => ({ ...p, email: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <label className="erp-label">CEP</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.cep}
                onChange={(e) => setQuick((p) => ({ ...p, cep: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm shrink-0"
              disabled={quickSaving}
              onClick={() => {
                void consultaCep(quick.cep).then(({ data }) =>
                  setQuick((prev) => ({
                    ...prev,
                    logradouro: (data.logradouro || prev.logradouro).trim(),
                    bairro: (data.bairro || prev.bairro).trim(),
                    cidade: (data.cidade || prev.cidade).trim(),
                    uf: ((data.uf || prev.uf) as string).trim().toUpperCase().slice(0, 2),
                  })),
                );
              }}
            >
              Consultar CEP
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="col-span-2">
              <label className="erp-label">Logradouro</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.logradouro}
                onChange={(e) => setQuick((p) => ({ ...p, logradouro: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Número</label>
              <input
                className="erp-input mt-1 w-full"
                value={quick.numero}
                onChange={(e) => setQuick((p) => ({ ...p, numero: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">UF</label>
              <input
                className="erp-input mt-1 w-full"
                maxLength={2}
                value={quick.uf}
                onChange={(e) => setQuick((p) => ({ ...p, uf: e.target.value.toUpperCase() }))}
                disabled={quickSaving}
              />
            </div>
          </div>
          <div>
            <label className="erp-label">Observações</label>
            <textarea
              className="erp-input mt-1 w-full min-h-[60px]"
              value={quick.observacoes}
              onChange={(e) => setQuick((p) => ({ ...p, observacoes: e.target.value }))}
              disabled={quickSaving}
            />
          </div>
        </div>
      </Modal>
    </>
  );
}
