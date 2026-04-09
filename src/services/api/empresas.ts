import { delay } from './config';
import type { Empresa } from '@/types';

let empresas: Empresa[] = [
  { id: 1, razao_social: 'Nexus Válvulas Ltda', nome_fantasia: 'Nexus Válvulas', cnpj: '12.345.678/0001-90', ie: '123456789', im: '987654', regime_tributario: 'Lucro Presumido', logradouro: 'Rua das Indústrias', numero: '500', complemento: 'Galpão 3', bairro: 'Distrito Industrial', cidade: 'Joinville', uf: 'SC', cep: '89219-000', telefone: '(47) 3333-4444', email: 'contato@nexusvalvulas.com.br', site: 'www.nexusvalvulas.com.br', empresa_pai_id: null, certificado_digital: '', senha_certificado: '' },
  { id: 2, razao_social: 'Nexus Válvulas Filial SP', nome_fantasia: 'Nexus SP', cnpj: '12.345.678/0002-71', ie: '223456789', im: '', regime_tributario: 'Lucro Presumido', logradouro: 'Av. Paulista', numero: '1000', complemento: 'Sala 501', bairro: 'Bela Vista', cidade: 'São Paulo', uf: 'SP', cep: '01310-100', telefone: '(11) 2222-3333', email: 'sp@nexusvalvulas.com.br', site: '', empresa_pai_id: 1, certificado_digital: '', senha_certificado: '' },
];
let nextId = 3;

export const empresasService = {
  getAll: async () => { await delay(); return [...empresas]; },
  getById: async (id: number) => { await delay(); return empresas.find(e => e.id === id); },
  create: async (data: Omit<Empresa, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Empresa; empresas.push(e); return e; },
  update: async (id: number, data: Partial<Empresa>) => { await delay(); const i = empresas.findIndex(e => e.id === id); if (i >= 0) empresas[i] = { ...empresas[i], ...data }; return empresas[i]; },
  delete: async (id: number) => { await delay(); empresas = empresas.filter(e => e.id !== id); },
};
