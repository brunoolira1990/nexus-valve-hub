import { describe, expect, it } from 'vitest';
import {
  extrairSerieNumeroDaChaveDfe,
  formatNumeroSerieInbox,
  resolverNumeroSerieInbox,
} from '@/lib/chaveDfeDocumento';

describe('chaveDfeDocumento', () => {
  it('extrai série e número da chave NF-e', () => {
    const chave = '35260622222222000122550010000208911123456782';
    const ext = extrairSerieNumeroDaChaveDfe(chave);
    expect(ext).not.toBeNull();
    expect(ext?.serie).toBe('1');
    expect(ext?.numero).toBe('20891');
    expect(ext?.modelo).toBe('55');
  });

  it('formata número confirmado via XML', () => {
    expect(
      formatNumeroSerieInbox({
        numero: '100',
        serie: '1',
        chave_acesso: '1'.repeat(44),
        xml_armazenado: true,
        numero_via_chave: false,
      }),
    ).toBe('100 / 1');
  });

  it('formata número via chave quando resumo sem XML', () => {
    const chave = '35260622222222000122550010000208911123456782';
    const info = resolverNumeroSerieInbox({
      numero: '20891',
      serie: '1',
      chave_acesso: chave,
      xml_armazenado: false,
      numero_via_chave: true,
    });
    expect(info.viaChave).toBe(true);
    expect(formatNumeroSerieInbox({
      numero: '20891',
      serie: '1',
      chave_acesso: chave,
      xml_armazenado: false,
      numero_via_chave: true,
    })).toBe('20891 / 1');
  });

  it('indica aguardando XML quando chave inválida e sem XML', () => {
    expect(
      formatNumeroSerieInbox({
        numero: '—',
        serie: '',
        chave_acesso: '123',
        xml_armazenado: false,
      }),
    ).toBe('Aguardando XML');
  });
});
