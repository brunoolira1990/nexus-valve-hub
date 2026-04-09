import { delay } from './config';
import type { RegraFiscal } from '@/types';

let items: RegraFiscal[] = [
  { id:1, ncm:'8481.80.99', uf_origem:'SC', uf_destino:'SP', operacao:'Saída', cfop:'6101', cst_icms:'00', aliquota_icms:12, cst_pis:'01', aliquota_pis:1.65, cst_cofins:'01', aliquota_cofins:7.6, cst_ipi:'50', aliquota_ipi:5, base_calculo:'OPERACAO' },
  { id:2, ncm:'7307.99.00', uf_origem:'SC', uf_destino:'RJ', operacao:'Saída', cfop:'6101', cst_icms:'00', aliquota_icms:12, cst_pis:'01', aliquota_pis:1.65, cst_cofins:'01', aliquota_cofins:7.6, cst_ipi:'50', aliquota_ipi:0, base_calculo:'OPERACAO' },
];
let nextId = 3;

export const regrasFiscaisService = {
  getAll: async () => { await delay(); return [...items]; },
  getById: async (id: number) => { await delay(); return items.find(e => e.id === id); },
  create: async (data: Omit<RegraFiscal, 'id'>) => { await delay(); const e = { ...data, id: nextId++ } as RegraFiscal; items.push(e); return e; },
  update: async (id: number, data: Partial<RegraFiscal>) => { await delay(); const i = items.findIndex(e => e.id === id); if (i >= 0) items[i] = { ...items[i], ...data }; return items[i]; },
  delete: async (id: number) => { await delay(); items = items.filter(e => e.id !== id); },
};
