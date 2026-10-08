import { useCallback, useState } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { fornecedoresService } from '@/services/api/fornecedores';
import { formatCnpjDisplay, isValidCnpj, normalizeCnpj } from '@/lib/cnpj';
import type { Fornecedor } from '@/types';

export type FornecedorPedidoCompraFieldProps = {
  valueId: number | null;
  selectedFornecedor: Fornecedor | null;
  disabled?: boolean;
  onSelect: (f: Fornecedor) => void;
  onClear: () => void;
  onCreatedAndUse: (f: Fornecedor) => void;
};

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
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  prazo_entrega_dias: string;
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
    complemento: '',
    bairro: '',
    cidade: '',
    uf: '',
    prazo_entrega_dias: '',
    observacoes: '',
  };
}

function quickToCreatePayload(q: QuickForm): Omit<Fornecedor, 'id'> {
  const prazo_entrega = Number(String(q.prazo_entrega_dias).replace(/\D/g, '')) || 0;
  const uf = (q.uf || '').trim().toUpperCase().slice(0, 2);
  return {
    razao_social: q.razao_social.trim(),
    nome_fantasia: q.nome_fantasia.trim(),
    cnpj: q.cnpj.trim(),
    ie: q.ie.trim(),
    logradouro: q.logradouro.trim(),
    numero: q.numero.trim(),
    complemento: q.complemento.trim(),
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
    prazo_entrega,
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

/** Stub mínimo para exibir fornecedor no autocomplete quando o GET por id falhar. */
export function fornecedorStubForDisplay(id: number, razaoSocial: string): Fornecedor {
  return {
    ...quickToCreatePayload(emptyQuickForm()),
    id,
    razao_social: razaoSocial || '—',
  };
}

const emailOk = (s: string) => {
  const t = s.trim();
  if (!t) return true;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
};

export function FornecedorPedidoCompraField({
  valueId,
  selectedFornecedor,
  disabled,
  onSelect,
  onClear,
  onCreatedAndUse,
}: FornecedorPedidoCompraFieldProps) {
  const [quickOpen, setQuickOpen] = useState(false);
  const [quick, setQuick] = useState<QuickForm>(() => emptyQuickForm());
  const [quickSaving, setQuickSaving] = useState(false);
  const [inlineMsg, setInlineMsg] = useState<string | null>(null);

  const buscar = useCallback((term: string, limit?: number) => fornecedoresService.search(term, limit ?? 25), []);

  const renderOption = useCallback((f: Fornecedor) => {
    const cidade = (f.cidade || '').trim();
    const uf = (f.uf || '').trim();
    const cidadeUf = cidade && uf ? `${cidade}/${uf}` : cidade || uf || '';
    return (
      <div>
        <div className="font-medium leading-snug">{f.razao_social}</div>
        {(f.nome_fantasia || '').trim() ? (
          <div className="text-xs text-muted-foreground">{f.nome_fantasia}</div>
        ) : null}
        <div className="text-xs text-muted-foreground tabular-nums">
          CNPJ: {formatCnpjDisplay(f.cnpj)}
          {cidadeUf ? ` · ${cidadeUf}` : ''}
        </div>
      </div>
    );
  }, []);

  const validarQuick = (): string | null => {
    const c = normalizeCnpj(quick.cnpj);
    if (c.length !== 14) return 'Informe o CNPJ com 14 dígitos.';
    if (!isValidCnpj(quick.cnpj)) return 'CNPJ inválido.';
    if (!quick.razao_social.trim()) return 'Razão social é obrigatória.';
    if (!emailOk(quick.email)) return 'E-mail inválido.';
    const uf = quick.uf.trim();
    if (uf && uf.length !== 2) return 'UF deve ter 2 letras.';
    const cepd = quick.cep.replace(/\D/g, '');
    if (quick.cep.trim() && cepd.length !== 8) return 'CEP deve ter 8 dígitos.';
    return null;
  };

  const handleConsultarCnpj = async () => {
    setInlineMsg(null);
    const c = normalizeCnpj(quick.cnpj);
    if (c.length !== 14) {
      setInlineMsg('Informe 14 dígitos de CNPJ para consultar.');
      return;
    }
    try {
      const { data } = await consultaCnpj(quick.cnpj);
      setQuick((prev) => ({
        ...prev,
        razao_social: (data.razao_social || prev.razao_social).trim() || prev.razao_social,
        nome_fantasia: (data.nome_fantasia || prev.nome_fantasia).trim() || prev.nome_fantasia,
        logradouro: (data.logradouro || prev.logradouro).trim() || prev.logradouro,
        numero: (data.numero || prev.numero).trim() || prev.numero,
        complemento: (data.complemento || prev.complemento).trim() || prev.complemento,
        bairro: (data.bairro || prev.bairro).trim() || prev.bairro,
        cidade: (data.cidade || prev.cidade).trim() || prev.cidade,
        uf: ((data.uf || prev.uf) as string).trim().toUpperCase().slice(0, 2) || prev.uf,
        cep: (data.cep || prev.cep).trim() || prev.cep,
        telefone: (data.telefone || prev.telefone).trim() || prev.telefone,
        email: (data.email || prev.email).trim() || prev.email,
      }));
    } catch (e: unknown) {
      setInlineMsg('Não foi possível consultar o CNPJ. Preencha manualmente.');
      if (import.meta.env.DEV) console.warn(apiErrorMessage(e));
    }
  };

  const handleConsultarCep = async () => {
    setInlineMsg(null);
    const d = quick.cep.replace(/\D/g, '');
    if (d.length !== 8) {
      setInlineMsg('Informe um CEP com 8 dígitos.');
      return;
    }
    try {
      const { data } = await consultaCep(quick.cep);
      setQuick((prev) => ({
        ...prev,
        logradouro: (data.logradouro || prev.logradouro).trim() || prev.logradouro,
        bairro: (data.bairro || prev.bairro).trim() || prev.bairro,
        cidade: (data.cidade || prev.cidade).trim() || prev.cidade,
        uf: ((data.uf || prev.uf) as string).trim().toUpperCase().slice(0, 2) || prev.uf,
        cep: (data.cep || prev.cep).trim() || prev.cep,
      }));
    } catch (e: unknown) {
      setInlineMsg(apiErrorMessage(e, { fallback: 'Não foi possível consultar o CEP.' }));
    }
  };

  const handleSalvarQuick = async () => {
    const v = validarQuick();
    if (v) {
      setInlineMsg(v);
      return;
    }
    setQuickSaving(true);
    setInlineMsg(null);
    try {
      const payload = quickToCreatePayload(quick);
      const created = await fornecedoresService.create(payload);
      onCreatedAndUse(created);
      setQuick(emptyQuickForm());
      setQuickOpen(false);
    } catch (e: unknown) {
      setInlineMsg(apiErrorMessage(e, { fallback: 'Não foi possível salvar o fornecedor.' }));
    } finally {
      setQuickSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <AsyncAutocomplete<Fornecedor>
        value={valueId}
        selectedOption={selectedFornecedor}
        placeholder="Busque por razão social, fantasia, CNPJ, cidade, UF, telefone ou e-mail…"
        disabled={disabled}
        minChars={2}
        limit={25}
        search={buscar}
        getOptionValue={(f) => f.id}
        getOptionLabel={(f) => f.razao_social}
        renderOption={renderOption}
        renderListFooter={() => (
          <div className="px-2 py-2">
            <button
              type="button"
              className="w-full rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-2 text-left text-sm font-medium text-primary hover:bg-primary/10"
              onClick={() => {
                setQuickOpen(true);
                setInlineMsg(null);
              }}
              disabled={disabled}
            >
              + Cadastrar novo fornecedor
            </button>
          </div>
        )}
        onChange={(id, opt) => {
          if (id == null || !opt) {
            onClear();
            return;
          }
          onSelect(opt);
        }}
      />
      <button
        type="button"
        className="text-sm font-medium text-primary hover:underline"
        onClick={() => {
          setQuickOpen(true);
          setInlineMsg(null);
        }}
        disabled={disabled}
      >
        + Cadastrar novo fornecedor
      </button>

      {quickOpen ? (
        <div className="rounded-md border border-border bg-muted/20 p-3 space-y-3">
          <div className="text-sm font-semibold text-foreground">Cadastro rápido de fornecedor</div>
          {inlineMsg ? <p className="text-sm text-destructive">{inlineMsg}</p> : null}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="sm:col-span-2 flex flex-wrap items-end gap-2">
              <div className="min-w-0 flex-1">
                <label className="erp-label">CNPJ</label>
                <input
                  className="erp-input mt-1"
                  value={quick.cnpj}
                  onChange={(e) => setQuick((p) => ({ ...p, cnpj: e.target.value }))}
                  disabled={quickSaving}
                />
              </div>
              <button type="button" className="erp-btn-outline erp-btn-sm shrink-0" onClick={() => void handleConsultarCnpj()} disabled={quickSaving}>
                Consultar CNPJ
              </button>
            </div>
            <div className="sm:col-span-2">
              <label className="erp-label">Razão social</label>
              <input
                className="erp-input mt-1"
                value={quick.razao_social}
                onChange={(e) => setQuick((p) => ({ ...p, razao_social: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="erp-label">Nome fantasia</label>
              <input
                className="erp-input mt-1"
                value={quick.nome_fantasia}
                onChange={(e) => setQuick((p) => ({ ...p, nome_fantasia: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Inscrição Estadual</label>
              <input
                className="erp-input mt-1"
                value={quick.ie}
                onChange={(e) => setQuick((p) => ({ ...p, ie: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Telefone</label>
              <input
                className="erp-input mt-1"
                value={quick.telefone}
                onChange={(e) => setQuick((p) => ({ ...p, telefone: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="erp-label">E-mail</label>
              <input
                type="email"
                className="erp-input mt-1"
                value={quick.email}
                onChange={(e) => setQuick((p) => ({ ...p, email: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div className="sm:col-span-2 flex flex-wrap items-end gap-2">
              <div className="min-w-0 flex-1">
                <label className="erp-label">CEP</label>
                <input
                  className="erp-input mt-1"
                  value={quick.cep}
                  onChange={(e) => setQuick((p) => ({ ...p, cep: e.target.value }))}
                  disabled={quickSaving}
                />
              </div>
              <button type="button" className="erp-btn-outline erp-btn-sm shrink-0" onClick={() => void handleConsultarCep()} disabled={quickSaving}>
                Consultar CEP
              </button>
            </div>
            <div className="sm:col-span-2">
              <label className="erp-label">Endereço</label>
              <input
                className="erp-input mt-1"
                value={quick.logradouro}
                onChange={(e) => setQuick((p) => ({ ...p, logradouro: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Número</label>
              <input
                className="erp-input mt-1"
                value={quick.numero}
                onChange={(e) => setQuick((p) => ({ ...p, numero: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Complemento</label>
              <input
                className="erp-input mt-1"
                value={quick.complemento}
                onChange={(e) => setQuick((p) => ({ ...p, complemento: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Bairro</label>
              <input
                className="erp-input mt-1"
                value={quick.bairro}
                onChange={(e) => setQuick((p) => ({ ...p, bairro: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Cidade</label>
              <input
                className="erp-input mt-1"
                value={quick.cidade}
                onChange={(e) => setQuick((p) => ({ ...p, cidade: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">UF</label>
              <input
                className="erp-input mt-1"
                maxLength={2}
                value={quick.uf}
                onChange={(e) => setQuick((p) => ({ ...p, uf: e.target.value.toUpperCase() }))}
                disabled={quickSaving}
              />
            </div>
            <div>
              <label className="erp-label">Prazo de entrega padrão (dias)</label>
              <input
                type="number"
                className="erp-input mt-1"
                value={quick.prazo_entrega_dias}
                onChange={(e) => setQuick((p) => ({ ...p, prazo_entrega_dias: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="erp-label">Observações</label>
              <textarea
                className="erp-input mt-1 min-h-[72px]"
                value={quick.observacoes}
                onChange={(e) => setQuick((p) => ({ ...p, observacoes: e.target.value }))}
                disabled={quickSaving}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2 justify-end border-t border-border pt-2">
            <button
              type="button"
              className="erp-btn-outline"
              onClick={() => {
                setQuickOpen(false);
                setInlineMsg(null);
              }}
              disabled={quickSaving}
            >
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" onClick={() => void handleSalvarQuick()} disabled={quickSaving}>
              {quickSaving ? 'Salvando…' : 'Salvar fornecedor e usar neste pedido'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
