import { describe, expect, it } from 'vitest';

import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import {
  ESTADOS_INBOX_FILTRO,
  badgeStatusEstadoConsolidado,
  resolverEstadoConsolidadoExibicao,
  textosAlertaEstadoConsolidado,
  tomBadgeEstadoConsolidado,
} from '@/lib/inboxFiscalUi';

const baseDoc: CentralDfeDocumento = {
  id: 1,
  tipo_documento: 'NFE_ENTRADA',
  chave_resumida: '1111…1111',
  chave_acesso: '1'.repeat(44),
  numero: '10',
  serie: '1',
  data_emissao: '2026-05-01',
  data_importacao: '2026-05-02',
  emitente_nome: 'Forn',
  emitente_cnpj: '11111111000111',
  uf: 'SP',
  valor_total: '100',
  status_entrada: 'PENDENTE_ENTRADA',
  status_entrada_label: 'Pendente',
  tipo_label: 'NF-e Fornecedor',
  detalhe_rota: '',
  empresa_id: 1,
};

describe('inboxFiscalUi', () => {
  it('mapeia tons por estado consolidado', () => {
    expect(tomBadgeEstadoConsolidado('PRECISA_MANIFESTAR')).toBe('warning');
    expect(tomBadgeEstadoConsolidado('CONCLUIDO')).toBe('success');
    expect(tomBadgeEstadoConsolidado('DIVERGENTE')).toBe('danger');
    expect(tomBadgeEstadoConsolidado('CONFERIDO')).toBe('info');
  });

  it('prioriza campos da API na exibição', () => {
    const ex = resolverEstadoConsolidadoExibicao({
      ...baseDoc,
      estado_consolidado: 'XML_DISPONIVEL',
      estado_consolidado_label: 'XML disponível',
      estado_consolidado_motivo: 'Manifestação pendente',
    });
    expect(ex.estado).toBe('XML_DISPONIVEL');
    expect(ex.label).toBe('XML disponível');
    expect(ex.motivo).toBe('Manifestação pendente');
  });

  it('expõe alertas visíveis incluindo chave operacional duplicada', () => {
    const ex = resolverEstadoConsolidadoExibicao({
      ...baseDoc,
      estado_consolidado: 'XML_DISPONIVEL',
      estado_consolidado_label: 'XML disponível',
      estado_consolidado_detalhes: {
        chave_em_nfe_entrada_operacional: true,
        observacao: 'Conferência/estoque da base ainda não concluídos.',
      },
    });
    const alertas = textosAlertaEstadoConsolidado(ex);
    expect(alertas.some((a) => a.includes('Entrada Própria operacional'))).toBe(true);
    expect(alertas.some((a) => a.includes('base'))).toBe(true);
  });

  it('lista opções de filtro alinhadas ao backend', () => {
    expect(ESTADOS_INBOX_FILTRO.map((o) => o.value)).toContain('ESTOQUE_APLICADO');
    expect(ESTADOS_INBOX_FILTRO.map((o) => o.value)).toContain('BLOQUEADO');
  });

  it('gera token de badge compatível com StatusBadge', () => {
    expect(badgeStatusEstadoConsolidado('CONCLUIDO')).toBe('concluido');
    expect(badgeStatusEstadoConsolidado('DIVERGENTE')).toBe('divergente_qualidade');
  });
});
