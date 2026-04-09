import { delay } from './config';
import type { Fornecedor } from '@/types';

let fornecedores: Fornecedor[] = [
  { id: 1, razao_social: 'Tupy S.A.', nome_fantasia: 'Tupy', cnpj: '84.683.374/0001-49', ie: '250001009', logradouro: 'Rua Albano Schmidt', numero: '3400', complemento: '', bairro: 'Boa Vista', cidade: 'Joinville', uf: 'SC', cep: '89206-001', telefone: '(47) 3461-7000', email: 'vendas@tupy.com.br', contato_responsavel: 'Roberto Lima', observacoes: '' },
  { id: 2, razao_social: 'Vallourec Tubos do Brasil', nome_fantasia: 'Vallourec', cnpj: '17.469.701/0001-77', ie: '062001234', logradouro: 'Av. Brasil', numero: '5000', complemento: '', bairro: 'Industrial', cidade: 'Belo Horizonte', uf: 'MG', cep: '30000-000', telefone: '(31) 3333-5555', email: 'vendas@vallourec.com', contato_responsavel: 'Marcos Santos', observacoes: '' },
];
let nextId = 3;

export const fornecedoresService = {
  getAll: async () => { await delay(); return [...fornecedores]; },
  getById: async (id: number) => { await delay(); return fornecedores.find(e => e.id === id); },
  create: async (data: Omit<Fornecedor, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Fornecedor; fornecedores.push(e); return e; },
  update: async (id: number, data: Partial<Fornecedor>) => { await delay(); const i = fornecedores.findIndex(e => e.id === id); if (i >= 0) fornecedores[i] = { ...fornecedores[i], ...data }; return fornecedores[i]; },
  delete: async (id: number) => { await delay(); fornecedores = fornecedores.filter(e => e.id !== id); },
};
