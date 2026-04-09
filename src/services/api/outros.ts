import { delay } from './config';
import type { EstoqueItem, ApuracaoFiscal, ContaContabil, Balancete } from '@/types';

export const estoqueService = {
  getAll: async (): Promise<EstoqueItem[]> => {
    await delay();
    return [
      { produto_id:1, produto_nome:'Válvula Gaveta 2" Aço Carbono', corrida_id:1, corrida_numero:'C-2024-001', saldo:15 },
      { produto_id:2, produto_nome:'Válvula Esfera 4" Aço Inox', corrida_id:2, corrida_numero:'C-2024-002', saldo:8 },
      { produto_id:3, produto_nome:'Conexão WeldoFit 3"x2"', corrida_id:0, corrida_numero:'-', saldo:2 },
    ];
  },
};

export const apuracaoService = {
  get: async (_mes: number, _ano: number): Promise<ApuracaoFiscal> => {
    await delay();
    return { periodo: `${_mes}/${_ano}`, receita_bruta: 125000, irpj: 4800, csll: 2880, pis: 2062.50, cofins: 9500, icms: 15000, ipi: 6250, cbs: 3250, ibs: 4500 };
  },
};

let contas: ContaContabil[] = [
  { id:1, codigo:'1', nome:'ATIVO', tipo:'Sintética', pai_id:null },
  { id:2, codigo:'1.1', nome:'ATIVO CIRCULANTE', tipo:'Sintética', pai_id:1 },
  { id:3, codigo:'1.1.1', nome:'Caixa e Equivalentes', tipo:'Analítica', pai_id:2 },
  { id:4, codigo:'1.1.2', nome:'Contas a Receber', tipo:'Analítica', pai_id:2 },
  { id:5, codigo:'1.2', nome:'ATIVO NÃO CIRCULANTE', tipo:'Sintética', pai_id:1 },
  { id:6, codigo:'2', nome:'PASSIVO', tipo:'Sintética', pai_id:null },
  { id:7, codigo:'2.1', nome:'PASSIVO CIRCULANTE', tipo:'Sintética', pai_id:6 },
  { id:8, codigo:'2.1.1', nome:'Fornecedores', tipo:'Analítica', pai_id:7 },
  { id:9, codigo:'3', nome:'PATRIMÔNIO LÍQUIDO', tipo:'Sintética', pai_id:null },
  { id:10, codigo:'4', nome:'RECEITAS', tipo:'Sintética', pai_id:null },
  { id:11, codigo:'5', nome:'DESPESAS', tipo:'Sintética', pai_id:null },
];
let contaId = 12;

export const contabilService = {
  getContas: async () => { await delay(); return [...contas]; },
  createConta: async (data: Omit<ContaContabil, 'id'>) => { await delay(); const c = { ...data, id: contaId++ } as ContaContabil; contas.push(c); return c; },
  updateConta: async (id: number, data: Partial<ContaContabil>) => { await delay(); const i = contas.findIndex(c => c.id === id); if (i >= 0) contas[i] = { ...contas[i], ...data }; return contas[i]; },
  deleteConta: async (id: number) => { await delay(); contas = contas.filter(c => c.id !== id); },
  getBalancete: async (_mes: number, _ano: number): Promise<Balancete[]> => {
    await delay();
    return [
      { conta_id:3, conta_codigo:'1.1.1', conta_nome:'Caixa e Equivalentes', debito:85000, credito:42000, saldo:43000 },
      { conta_id:4, conta_codigo:'1.1.2', conta_nome:'Contas a Receber', debito:125000, credito:98000, saldo:27000 },
      { conta_id:8, conta_codigo:'2.1.1', conta_nome:'Fornecedores', debito:65000, credito:78000, saldo:-13000 },
    ];
  },
};
