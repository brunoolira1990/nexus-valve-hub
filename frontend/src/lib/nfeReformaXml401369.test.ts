import { describe, expect, it } from 'vitest';

import { agruparValidacaoPorSeveridade } from '@/lib/nfeSaidaConferenciaUx';

describe('nfeReformaXml401369', () => {
  it('exibe pendência quando Reforma calculada mas ausente no XML', () => {
    const val = agruparValidacaoPorSeveridade({
      status_prontidao: 'COM_PENDENCIAS',
      pode_emitir: false,
      total_pendencias: 1,
      total_alertas: 0,
      grupos: {
        reforma_tributaria: [
          {
            tipo: 'PENDENCIA',
            codigo: 'REFORMA_AUSENTE_XML',
            grupo: 'reforma_tributaria',
            mensagem: 'Reforma calculada na conferência, mas ausente no XML.',
          },
        ],
      },
      mensagens: [],
    });
    expect(val.pendencias.some((p) => p.codigo === 'REFORMA_AUSENTE_XML')).toBe(true);
  });

  it('exibe OK quando XML contém Reforma Tributária', () => {
    const val = agruparValidacaoPorSeveridade({
      status_prontidao: 'PRONTA',
      pode_emitir: true,
      total_pendencias: 0,
      total_alertas: 0,
      grupos: {
        reforma_tributaria: [
          {
            tipo: 'INFO',
            codigo: 'REFORMA_XML_OK',
            grupo: 'reforma_tributaria',
            mensagem: 'XML contém Reforma Tributária: CBS R$ 112,50 · IBS UF R$ 12,50.',
          },
        ],
      },
      mensagens: [],
    });
    expect(val.informacoes.some((i) => i.codigo === 'REFORMA_XML_OK')).toBe(true);
  });

  it('exibe pendência para cMun destinatário inconsistente', () => {
    const val = agruparValidacaoPorSeveridade({
      status_prontidao: 'COM_PENDENCIAS',
      pode_emitir: false,
      total_pendencias: 1,
      total_alertas: 0,
      grupos: {
        cliente: [
          {
            tipo: 'PENDENCIA',
            codigo: 'REFORMA_XML_GERACAO_FALHOU',
            grupo: 'reforma_tributaria',
            mensagem:
              'Endereço fiscal do destinatário inconsistente: cidade BELEM/PA possui cMun incompatível.',
          },
        ],
      },
      mensagens: [],
    });
    expect(val.pendencias[0]?.mensagem.toLowerCase()).toContain('incompatível');
  });
});
