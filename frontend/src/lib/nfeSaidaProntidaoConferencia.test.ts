import { describe, expect, it } from 'vitest';

import {
  badgeStatusConferenciaNFe,
  mensagemOrientacaoProntidao,
  podeExibirBotaoMarcarPronta,
} from './nfeSaidaProntidaoConferencia';

describe('nfeSaidaProntidaoConferencia', () => {
  it('badge por status de conferência', () => {
    expect(badgeStatusConferenciaNFe('PRONTA_PARA_EMISSAO').label).toBe('Pronta para emissão');
    expect(badgeStatusConferenciaNFe('COM_PENDENCIAS').className).toContain('danger');
    expect(badgeStatusConferenciaNFe('EM_CONFERENCIA').label).toBe('Em conferência');
  });

  it('mensagem de orientação por status', () => {
    expect(mensagemOrientacaoProntidao('COM_PENDENCIAS')).toContain('pendências bloqueantes');
    expect(mensagemOrientacaoProntidao('PRONTA_PARA_EMISSAO')).toContain('SEFAZ');
  });

  it('botão marcar pronta conforme payload', () => {
    expect(podeExibirBotaoMarcarPronta({ pode_marcar_pronta: true } as never)).toBe(true);
    expect(podeExibirBotaoMarcarPronta({ pode_marcar_pronta: false } as never)).toBe(false);
  });
});
