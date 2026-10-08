import { describe, expect, it } from 'vitest';
import {
  enderecoFiscalInconsistenteLocal,
  mensagemEnderecoFiscalInconsistente,
  mensagemPreviewSemRegra,
} from './enderecoFiscal';

describe('enderecoFiscal', () => {
  it('detecta cidade BELEM com UF SP divergente do CEP PA', () => {
    expect(
      enderecoFiscalInconsistenteLocal('BELEM', 'SP', { cidade: 'BELEM', uf: 'PA' }),
    ).toBe(true);
  });

  it('mensagem de inconsistência inclui CEP e UF do CEP', () => {
    const msg = mensagemEnderecoFiscalInconsistente('BELEM', '66630-505', 'SP', {
      cidade: 'BELEM',
      uf: 'PA',
    });
    expect(msg).toContain('66630-505');
    expect(msg).toContain('PA');
  });

  it('preview prioriza endereço inconsistente sobre regra genérica', () => {
    const msg = mensagemPreviewSemRegra({
      contexto_fiscal: {
        endereco_fiscal: {
          bloqueio_fiscal: true,
          alertas: ['CEP 66630-505 / cidade BELEM não correspondem à UF SP.'],
        },
      },
      resumo: { itens_total: 1, itens_sem_regra: 1 },
    });
    expect(msg).toContain('66630-505');
    expect(msg.toLowerCase()).not.toContain('não há regra fiscal encontrada');
  });

  it('preview informa falta de regra com NCM origem destino', () => {
    const msg = mensagemPreviewSemRegra({
      contexto_fiscal: { endereco_fiscal: { consistente: true, bloqueio_fiscal: false } },
      diagnosticos: [
        {
          tipo: 'REGRA_NAO_ENCONTRADA',
          detalhe: 'Não foi encontrada regra fiscal de saída para NCM 73079100, origem SP e destino PA.',
        },
      ],
      resumo: { itens_total: 1, itens_sem_regra: 1 },
    });
    expect(msg).toContain('73079100');
    expect(msg).toContain('SP');
    expect(msg).toContain('PA');
  });
});
