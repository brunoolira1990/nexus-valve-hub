import { delay } from './config';
import type { Proposta, PedidoVenda, PedidoCompra } from '@/types';

let propostas: Proposta[] = [
  { id:1, numero:'PROP-001', cliente_id:1, cliente_nome:'Petrobrás S.A.', data:'2024-03-01', validade:'2024-04-01', vendedor:'João Silva', status:'Aprovada', valor_total:12500, itens:[{id:1,produto_id:1,produto_nome:'Válvula Gaveta 2"',quantidade:10,valor_unitario:1250,desconto:0}] },
  { id:2, numero:'PROP-002', cliente_id:2, cliente_nome:'Vale S.A.', data:'2024-03-10', validade:'2024-04-10', vendedor:'Maria Santos', status:'Pendente', valor_total:35000, itens:[{id:1,produto_id:2,produto_nome:'Válvula Esfera 4"',quantidade:10,valor_unitario:3500,desconto:0}] },
];
let propId = 3;

let pedidosVenda: PedidoVenda[] = [
  { id:1, numero:'PV-001', cliente_id:1, cliente_nome:'Petrobrás S.A.', data:'2024-03-05', status:'Faturado', valor_total:12500, proposta_id:1, itens:[{id:1,produto_id:1,produto_nome:'Válvula Gaveta 2"',quantidade:10,valor_unitario:1250}] },
];
let pvId = 2;

let pedidosCompra: PedidoCompra[] = [
  { id:1, numero:'PC-001', fornecedor_id:1, fornecedor_nome:'Tupy S.A.', data:'2024-02-20', status:'Recebido', valor_total:8500, itens:[{id:1,produto_id:1,produto_nome:'Válvula Gaveta 2"',quantidade:10,valor_unitario:850}] },
];
let pcId = 2;

export const propostasService = {
  getAll: async () => { await delay(); return [...propostas]; },
  getById: async (id: number) => { await delay(); return propostas.find(e => e.id === id); },
  create: async (data: Omit<Proposta, 'id'>) => { await delay(); const e = { ...data, id: propId++ } as Proposta; propostas.push(e); return e; },
  update: async (id: number, data: Partial<Proposta>) => { await delay(); const i = propostas.findIndex(e => e.id === id); if (i >= 0) propostas[i] = { ...propostas[i], ...data }; return propostas[i]; },
  delete: async (id: number) => { await delay(); propostas = propostas.filter(e => e.id !== id); },
};

export const pedidosVendaService = {
  getAll: async () => { await delay(); return [...pedidosVenda]; },
  getById: async (id: number) => { await delay(); return pedidosVenda.find(e => e.id === id); },
  create: async (data: Omit<PedidoVenda, 'id'>) => { await delay(); const e = { ...data, id: pvId++ } as PedidoVenda; pedidosVenda.push(e); return e; },
  update: async (id: number, data: Partial<PedidoVenda>) => { await delay(); const i = pedidosVenda.findIndex(e => e.id === id); if (i >= 0) pedidosVenda[i] = { ...pedidosVenda[i], ...data }; return pedidosVenda[i]; },
  delete: async (id: number) => { await delay(); pedidosVenda = pedidosVenda.filter(e => e.id !== id); },
};

export const pedidosCompraService = {
  getAll: async () => { await delay(); return [...pedidosCompra]; },
  getById: async (id: number) => { await delay(); return pedidosCompra.find(e => e.id === id); },
  create: async (data: Omit<PedidoCompra, 'id'>) => { await delay(); const e = { ...data, id: pcId++ } as PedidoCompra; pedidosCompra.push(e); return e; },
  update: async (id: number, data: Partial<PedidoCompra>) => { await delay(); const i = pedidosCompra.findIndex(e => e.id === id); if (i >= 0) pedidosCompra[i] = { ...pedidosCompra[i], ...data }; return pedidosCompra[i]; },
  delete: async (id: number) => { await delay(); pedidosCompra = pedidosCompra.filter(e => e.id !== id); },
};
