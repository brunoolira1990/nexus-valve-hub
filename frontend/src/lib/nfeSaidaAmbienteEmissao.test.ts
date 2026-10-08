import { describe, expect, it } from 'vitest';

import {
  ambienteEmissaoNfeDefinido,
  labelProximaNumeracaoCadastro,
  resolverAmbienteEmissaoNfeConferencia,
  resolverNumeracaoCadastroConferencia,
} from './nfeSaidaAmbienteEmissao';

describe('nfeSaidaAmbienteEmissao', () => {
  it('resolve ambiente da conferência', () => {
    expect(
      resolverAmbienteEmissaoNfeConferencia({
        apresentacao: { ambiente_emissao: 'producao' },
        emissao_sefaz: { ambiente_emissao: 'homologacao' },
      }),
    ).toBe('producao');
  });

  it('numeração por ambiente', () => {
    const conf = {
      emissao_sefaz: {
        numeracao_producao: { serie: '1', proximo_numero: 361 },
        numeracao_homologacao: { serie: '0', proximo_numero: 6 },
      },
    };
    expect(resolverNumeracaoCadastroConferencia(conf, 'producao')).toEqual({
      serie: '1',
      proximo_numero: 361,
    });
    expect(resolverNumeracaoCadastroConferencia(conf, 'homologacao')).toEqual({
      serie: '0',
      proximo_numero: 6,
    });
    expect(labelProximaNumeracaoCadastro('producao')).toContain('produção');
    expect(labelProximaNumeracaoCadastro('homologacao')).toContain('homologação');
  });

  it('ambiente definido', () => {
    expect(ambienteEmissaoNfeDefinido('producao')).toBe(true);
    expect(ambienteEmissaoNfeDefinido('')).toBe(false);
  });
});
