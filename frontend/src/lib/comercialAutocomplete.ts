import { formatCnpjDisplay } from '@/lib/cnpj';
import type { Cliente, Colaborador, Produto, Vendedor } from '@/types';

export function tituloProdutoLinha(p: Produto): string {
  const cod = (p.codigo_completo || '').trim() || '—';
  const desc = (p.descricao || '').trim() || '—';
  return `${cod} · ${desc}`;
}

export function ncmExibicaoProduto(p: Produto): string {
  return p.ncm_efetivo?.codigo || p.ncm || '—';
}

export function labelColaboradorSelecionado(c: Colaborador): string {
  const nome = (c.nome || '').trim() || '—';
  const cod = (c.codigo || '').trim();
  if (!cod) return nome;
  return `${nome} · ${cod}`;
}

export function colaboradorStubForDisplay(
  id: number,
  nome: string,
  codigo = '',
  vendedorId?: number | null,
): Colaborador {
  return {
    id,
    nome: nome || '—',
    codigo,
    ativo: true,
    usuario_id: null,
    email: '',
    telefone: '',
    observacoes: '',
    eh_vendedor: true,
    eh_comprador: false,
    eh_responsavel_fiscal: false,
    eh_responsavel_financeiro: false,
    eh_responsavel_estoque: false,
    eh_responsavel_qualidade: false,
    eh_administrador: false,
    vendedor_id: vendedorId ?? null,
  };
}

export function labelVendedorSelecionado(v: Vendedor): string {
  const nome = (v.nome || '').trim() || '—';
  const cod = (v.codigo || '').trim();
  if (!cod) return nome;
  return `${nome} · ${cod}`;
}

export function vendedorStubForDisplay(id: number, nome: string, codigo = ''): Vendedor {
  return {
    id,
    nome: nome || '—',
    codigo,
    ativo: true,
    usuario_id: null,
    email: '',
    telefone: '',
    observacoes: '',
  };
}

export function labelClienteSelecionado(c: Cliente): string {
  const nome = (c.razao_social || c.nome_fantasia || '').trim() || '—';
  const doc = (c.cnpj || '').trim();
  if (!doc) return nome;
  return `${nome} · ${formatCnpjDisplay(doc)}`;
}

export function labelFornecedorSelecionado(f: { razao_social?: string; nome_fantasia?: string; cnpj?: string }): string {
  const nome = (f.razao_social || f.nome_fantasia || '').trim() || '—';
  const doc = (f.cnpj || '').trim();
  if (!doc) return nome;
  return `${nome} · ${formatCnpjDisplay(doc)}`;
}

export function labelFornecedorExibicao(f: { razao_social?: string; nome_fantasia?: string } | null | undefined): string {
  if (!f) return '—';
  return (f.razao_social || f.nome_fantasia || '').trim() || '—';
}

export function clienteStubForDisplay(id: number, razaoSocial: string, cnpj = ''): Cliente {
  return {
    id,
    razao_social: razaoSocial || '—',
    nome_fantasia: '',
    cnpj,
    ie: '',
    logradouro: '',
    numero: '',
    complemento: '',
    bairro: '',
    cidade: '',
    uf: '',
    cep: '',
    telefone: '',
    email: '',
    contato_responsavel: '',
    observacoes: '',
    condicao_pagamento_texto: '',
    dias_parcelas: [],
    quantidade_parcelas: 0,
    ativo: true,
  } as Cliente;
}

export function produtoStubForDisplay(id: number, codigo: string, descricao: string): Produto {
  return {
    id,
    codigo_completo: codigo,
    descricao: descricao || '—',
    unidade: 'PC',
    ncm: '',
  } as Produto;
}
