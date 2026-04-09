import { delay } from './config';
import type { Produto } from '@/types';

let items: Produto[] = [
  { id: 1, figura: 'VG', sufixo: '01', schedule: '40', polegada_principal: '2"', polegada_secundaria: '', descricao: 'Válvula Gaveta 2" Aço Carbono', material: 'Aço Carbono', tipo_peca: 'Válvula', pressao_nominal: '150#', norma: 'API 600', conexao: 'Flangeada', ncm: '8481.80.99', preco_custo: 850.00, preco_venda: 1250.00, estoque_minimo: 5, codigo_completo: 'VG.01.40.2' },
  { id: 2, figura: 'VE', sufixo: '02', schedule: '80', polegada_principal: '4"', polegada_secundaria: '', descricao: 'Válvula Esfera 4" Aço Inox', material: 'Aço Inoxidável', tipo_peca: 'Válvula', pressao_nominal: '300#', norma: 'API 608', conexao: 'Flangeada', ncm: '8481.80.99', preco_custo: 2200.00, preco_venda: 3500.00, estoque_minimo: 3, codigo_completo: 'VE.02.80.4' },
  { id: 3, figura: 'CW', sufixo: '01', schedule: '40', polegada_principal: '3"', polegada_secundaria: '2"', descricao: 'Conexão WeldoFit 3"x2"', material: 'Aço Carbono', tipo_peca: 'Conexão', pressao_nominal: '3000#', norma: 'ASME B16.11', conexao: 'Solda', ncm: '7307.99.00', preco_custo: 180.00, preco_venda: 320.00, estoque_minimo: 10, codigo_completo: 'CW.01.40.3' },
];
let nextId = 4;

export const produtosService = {
  getAll: async () => { await delay(); return [...items]; },
  getById: async (id: number) => { await delay(); return items.find(e => e.id === id); },
  create: async (data: Omit<Produto, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Produto; items.push(e); return e; },
  update: async (id: number, data: Partial<Produto>) => { await delay(); const i = items.findIndex(e => e.id === id); if (i >= 0) items[i] = { ...items[i], ...data }; return items[i]; },
  delete: async (id: number) => { await delay(); items = items.filter(e => e.id !== id); },
};
