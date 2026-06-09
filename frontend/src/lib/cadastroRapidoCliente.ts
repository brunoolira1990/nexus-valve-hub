import { isValidCnpj, normalizeCnpj } from '@/lib/cnpj';
import type { Cliente } from '@/types';

export type ClienteQuickForm = {
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  telefone: string;
  email: string;
  cep: string;
  logradouro: string;
  numero: string;
  bairro: string;
  cidade: string;
  uf: string;
};

export function emptyClienteQuickForm(prefill = ''): ClienteQuickForm {
  return {
    razao_social: prefill,
    nome_fantasia: '',
    cnpj: '',
    ie: '',
    telefone: '',
    email: '',
    cep: '',
    logradouro: '',
    numero: '',
    bairro: '',
    cidade: '',
    uf: '',
  };
}

export function validarClienteQuickForm(q: ClienteQuickForm): string | null {
  const cnpj = normalizeCnpj(q.cnpj);
  if (cnpj.length !== 14) return 'Informe o CNPJ com 14 dígitos.';
  if (!isValidCnpj(q.cnpj)) return 'CNPJ inválido.';
  if (!q.razao_social.trim()) return 'Razão social é obrigatória.';
  const email = q.email.trim();
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'E-mail inválido.';
  const uf = q.uf.trim();
  if (uf && uf.length !== 2) return 'UF deve ter 2 letras.';
  const cepd = q.cep.replace(/\D/g, '');
  if (q.cep.trim() && cepd.length !== 8) return 'CEP deve ter 8 dígitos.';
  return null;
}

export function clienteQuickToPayload(q: ClienteQuickForm): Omit<Cliente, 'id'> {
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
    uf: q.uf.trim().toUpperCase().slice(0, 2),
    cep: q.cep.trim(),
    telefone: q.telefone.trim(),
    email: q.email.trim(),
    contato_responsavel: '',
    observacoes: '',
    inscricao_municipal: '',
    suframa: '',
    email_nf: '',
    telefone_alternativo: '',
    celular: '',
    limite_credito: 0,
    condicao_pagamento_texto: '',
    dias_parcelas: [],
    quantidade_parcelas: 0,
    transportadora_padrao_id: null,
    vendedor_padrao: '',
    bloqueado: false,
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
