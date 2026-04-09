import { delay } from './config';
import type { Transportadora } from '@/types';

let items: Transportadora[] = [
  { id: 1, razao_social: 'Transportes Rápido Ltda', cnpj: '55.666.777/0001-88', ie: '999000111', logradouro: 'Rod. BR-101', numero: 'Km 55', complemento: '', bairro: 'Industrial', cidade: 'Itajaí', uf: 'SC', cep: '88300-000', telefone: '(47) 3344-5566', email: 'contato@rapidotrans.com.br', placa_padrao: 'ABC-1234', uf_placa: 'SC' },
];
let nextId = 2;

export const transportadorasService = {
  getAll: async () => { await delay(); return [...items]; },
  getById: async (id: number) => { await delay(); return items.find(e => e.id === id); },
  create: async (data: Omit<Transportadora, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Transportadora; items.push(e); return e; },
  update: async (id: number, data: Partial<Transportadora>) => { await delay(); const i = items.findIndex(e => e.id === id); if (i >= 0) items[i] = { ...items[i], ...data }; return items[i]; },
  delete: async (id: number) => { await delay(); items = items.filter(e => e.id !== id); },
};
