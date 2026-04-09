import { delay } from './config';
import type { NFeEntrada, NFeSaida, CTeEntrada } from '@/types';

let nfeEntradas: NFeEntrada[] = [
  { id:1, numero:'NF-001', fornecedor_id:1, fornecedor_nome:'Tupy S.A.', data:'2024-03-15', valor_total:8500, pedido_compra_id:1, itens:[{id:1,produto_id:1,produto_nome:'Válvula Gaveta 2"',quantidade:10,valor:850}] },
];
let nfeEntId = 2;

let nfeSaidas: NFeSaida[] = [
  { id:1, numero:'NFS-001', cliente_id:1, cliente_nome:'Petrobrás S.A.', data:'2024-03-20', valor_total:12500, status:'Emitida', pedido_venda_id:1, itens:[{id:1,produto_id:1,produto_nome:'Válvula Gaveta 2"',quantidade:10,valor:1250,corrida_id:1,corrida_numero:'C-2024-001'}] },
];
let nfeSaiId = 2;

let cteEntradas: CTeEntrada[] = [
  { id:1, numero:'CTE-001', transportadora_id:1, transportadora_nome:'Transportes Rápido Ltda', tomador_id:1, tomador_nome:'Nexus Válvulas Ltda', valor_frete:350, data:'2024-03-16', nfe_ids:[1] },
];
let cteId = 2;

export const nfeEntradasService = {
  getAll: async () => { await delay(); return [...nfeEntradas]; },
  getById: async (id: number) => { await delay(); return nfeEntradas.find(e => e.id === id); },
  create: async (data: Omit<NFeEntrada, 'id'>) => { await delay(); const e = { ...data, id: nfeEntId++ } as NFeEntrada; nfeEntradas.push(e); return e; },
  update: async (id: number, data: Partial<NFeEntrada>) => { await delay(); const i = nfeEntradas.findIndex(e => e.id === id); if (i >= 0) nfeEntradas[i] = { ...nfeEntradas[i], ...data }; return nfeEntradas[i]; },
  delete: async (id: number) => { await delay(); nfeEntradas = nfeEntradas.filter(e => e.id !== id); },
};

export const nfeSaidasService = {
  getAll: async () => { await delay(); return [...nfeSaidas]; },
  getById: async (id: number) => { await delay(); return nfeSaidas.find(e => e.id === id); },
  create: async (data: Omit<NFeSaida, 'id'>) => { await delay(); const e = { ...data, id: nfeSaiId++ } as NFeSaida; nfeSaidas.push(e); return e; },
  update: async (id: number, data: Partial<NFeSaida>) => { await delay(); const i = nfeSaidas.findIndex(e => e.id === id); if (i >= 0) nfeSaidas[i] = { ...nfeSaidas[i], ...data }; return nfeSaidas[i]; },
  delete: async (id: number) => { await delay(); nfeSaidas = nfeSaidas.filter(e => e.id !== id); },
};

export const cteEntradasService = {
  getAll: async () => { await delay(); return [...cteEntradas]; },
  getById: async (id: number) => { await delay(); return cteEntradas.find(e => e.id === id); },
  create: async (data: Omit<CTeEntrada, 'id'>) => { await delay(); const e = { ...data, id: cteId++ } as CTeEntrada; cteEntradas.push(e); return e; },
  update: async (id: number, data: Partial<CTeEntrada>) => { await delay(); const i = cteEntradas.findIndex(e => e.id === id); if (i >= 0) cteEntradas[i] = { ...cteEntradas[i], ...data }; return cteEntradas[i]; },
  delete: async (id: number) => { await delay(); cteEntradas = cteEntradas.filter(e => e.id !== id); },
};
