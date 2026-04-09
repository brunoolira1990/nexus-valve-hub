import { delay } from './config';
import type { Corrida, ComposicaoQuimica, Tracao, Impacto } from '@/types';

const emptyComposicao: ComposicaoQuimica = { C:0,Mn:0,P:0,S:0,Si:0,Ni:0,Cr:0,Mo:0,Cu:0,V:0,Nb:0,Al:0,Ti:0,N:0,Zn:0,Fe:0,Sn:0,Pb:0,Ca:0,Ta:0,W:0,Li:0,CO:0 };
const emptyTracao: Tracao = { norma:'',corpo_prova:'',direcao:'',posicao:'',temperatura:0,limite_escoamento:0,limite_resistencia:0,alongamento:0,estriccao:0,dureza:'',tratamento_termico:'' };
const emptyImpacto: Impacto = { norma:'',corpo_prova:'',direcao:'',posicao:'',temperatura:0,valor_a:0,valor_b:0,valor_c:0,media:0 };

let items: Corrida[] = [
  { id:1, numero:'C-2024-001', produto_id:1, produto_nome:'Válvula Gaveta 2" Aço Carbono', fornecedor_id:1, fornecedor_nome:'Tupy S.A.', data_recebimento:'2024-03-15', nf_entrada:'NF-001', composicao_quimica:{...emptyComposicao,C:0.22,Mn:1.20,P:0.025,S:0.015,Si:0.30}, tracao:{...emptyTracao,norma:'ASTM A216',limite_escoamento:250,limite_resistencia:485,alongamento:22}, impacto:{...emptyImpacto,norma:'ASTM A216',temperatura:-29,valor_a:45,valor_b:42,valor_c:48,media:45} },
  { id:2, numero:'C-2024-002', produto_id:2, produto_nome:'Válvula Esfera 4" Aço Inox', fornecedor_id:2, fornecedor_nome:'Vallourec Tubos do Brasil', data_recebimento:'2024-04-10', nf_entrada:'NF-005', composicao_quimica:{...emptyComposicao,C:0.08,Mn:2.0,Cr:18.0,Ni:10.0}, tracao:{...emptyTracao,norma:'ASTM A351',limite_escoamento:205,limite_resistencia:515,alongamento:30}, impacto:{...emptyImpacto} },
];
let nextId = 3;

export const corridasService = {
  getAll: async () => { await delay(); return [...items]; },
  getById: async (id: number) => { await delay(); return items.find(e => e.id === id); },
  create: async (data: Omit<Corrida, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as Corrida; items.push(e); return e; },
  update: async (id: number, data: Partial<Corrida>) => { await delay(); const i = items.findIndex(e => e.id === id); if (i >= 0) items[i] = { ...items[i], ...data }; return items[i]; },
  delete: async (id: number) => { await delay(); items = items.filter(e => e.id !== id); },
};
