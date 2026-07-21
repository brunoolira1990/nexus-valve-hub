import { describe, expect, it } from 'vitest';

import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import {
  abaInicialCteWorkspace,
  resolverConteudoWorkspace,
  resolverCteHistoricoId,
  resolverNfHistoricaId,
} from '@/lib/centralDfeWorkspaceUi';

const baseNfe: CentralDfeDocumento = {
  id: 10,
  tipo_documento: 'NFE_ENTRADA',
  chave_resumida: '1111…1111',
  chave_acesso: '1'.repeat(44),
  numero: '10',
  serie: '1',
  data_emissao: '2026-05-01',
  data_importacao: null,
  emitente_nome: 'Forn',
  emitente_cnpj: '11111111000111',
  uf: 'SP',
  valor_total: '100',
  status_entrada: 'PENDENTE_ENTRADA',
  status_entrada_label: 'Pendente',
  tipo_label: 'NF-e Fornecedor',
  detalhe_rota: '',
  empresa_id: 1,
  nf_entrada_historica_id: 99,
};

describe('centralDfeWorkspaceUi', () => {
  it('resolve nf histórica id priorizando campo da API', () => {
    expect(resolverNfHistoricaId(baseNfe, null)).toBe(99);
    expect(resolverNfHistoricaId({ ...baseNfe, nf_entrada_historica_id: null, xml_armazenado: true }, null)).toBe(10);
  });

  it('resolve id CT-e histórico', () => {
    expect(resolverCteHistoricoId({ ...baseNfe, id: 5, tipo_documento: 'CTE' })).toBe(5);
    expect(resolverCteHistoricoId(baseNfe)).toBeNull();
  });

  it('mapeia conteúdo por estado NF-e', () => {
    expect(resolverConteudoWorkspace(baseNfe, 'PRECISA_MANIFESTAR')).toBe('manifestacao');
    expect(resolverConteudoWorkspace(baseNfe, 'XML_DISPONIVEL')).toBe('xml_disponivel');
    expect(resolverConteudoWorkspace(baseNfe, 'EM_CONFERENCIA')).toBe('conferencia_nfe');
    expect(resolverConteudoWorkspace(baseNfe, 'CONFERIDO')).toBe('conferencia_nfe');
    expect(resolverConteudoWorkspace(baseNfe, 'ESTOQUE_APLICADO')).toBe('resumo_final');
    expect(resolverConteudoWorkspace(baseNfe, 'CONCLUIDO')).toBe('resumo_final');
  });

  it('força conferência NF-e quando solicitado (inclui notas finalizadas)', () => {
    expect(resolverConteudoWorkspace(baseNfe, 'XML_DISPONIVEL', true)).toBe('conferencia_nfe');
    expect(resolverConteudoWorkspace(baseNfe, 'ESTOQUE_APLICADO', true)).toBe('conferencia_nfe');
    expect(resolverConteudoWorkspace(baseNfe, 'CONCLUIDO', true)).toBe('conferencia_nfe');
  });

  it('mapeia CT-e para conferência ou xml', () => {
    const cte = { ...baseNfe, id: 7, tipo_documento: 'CTE' as const };
    expect(resolverConteudoWorkspace(cte, 'EM_CONFERENCIA')).toBe('conferencia_cte');
    expect(resolverConteudoWorkspace(cte, 'XML_DISPONIVEL')).toBe('xml_disponivel');
  });

  it('aba inicial CT-e prioriza conferência em pendências', () => {
    expect(abaInicialCteWorkspace('DIVERGENTE')).toBe('conferencia');
    expect(abaInicialCteWorkspace('CONCLUIDO')).toBe('resumo');
  });
});
