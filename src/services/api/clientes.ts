import { delay } from './config';
import type { Cliente } from '@/types';

let clientes: Cliente[] = [
  { id: 1, razao_social: 'Petrobrás S.A.', nome_fantasia: 'Petrobrás', cnpj: '33.000.167/0001-01', ie: '111222333', logradouro: 'Av. República do Chile', numero: '65', complemento: '', bairro: 'Centro', cidade: 'Rio de Janeiro', uf: 'RJ', cep: '20031-912', telefone: '(21) 3224-4477', email: 'compras@petrobras.com.br', contato_responsavel: 'Carlos Silva', observacoes: 'Cliente premium' },
  { id: 2, razao_social: 'Vale S.A.', nome_fantasia: 'Vale', cnpj: '33.592.510/0001-54', ie: '444555666', logradouro: 'Praia de Botafogo', numero: '186', complemento: 'Bloco A', bairro: 'Botafogo', cidade: 'Rio de Janeiro', uf: 'RJ', cep: '22250-145', telefone: '(21) 3485-3000', email: 'suprimentos@vale.com', contato_responsavel: 'Ana Mendes', observacoes: '' },
];
let nextId = 3;

export const clientesService = {
  getAll: async () => { await delay(); return [...clientes]; },
  getById: async (id: number) => { await delay(); return clientes.find(e => e.id === id); },
  create: async (data: Omit<Cliente, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Cliente; clientes.push(e); return e; },
  update: async (id: number, data: Partial<Cliente>) => { await delay(); const i = clientes.findIndex(e => e.id === id); if (i >= 0) clientes[i] = { ...clientes[i], ...data }; return clientes[i]; },
  delete: async (id: number) => { await delay(); clientes = clientes.filter(e => e.id !== id); },
};
