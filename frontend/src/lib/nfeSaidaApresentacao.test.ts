import { describe, expect, it } from 'vitest';
import {
  badgeNfeSaidaLinhaListagem,
  mensagemCabecalhoNfeAutorizadaHomolog,
  subtituloListagemNfe,
  tituloListagemNfe,
} from '@/lib/nfeSaidaUi';

const apresentacaoAutorizada = {
  titulo_exibicao: 'NF-e Homologação nº 000000002 — Série 0',
  listagem_titulo: 'NF-e Homologação nº 000000002 — Série 0',
  listagem_subtitulo: 'Série 0 · FAT-20260523-0001 · PV-20260521-0002',
  linhas_subtitulo: [
    'Faturamento: FAT-20260523-0001',
    'Pedido de venda: PV-20260521-0002',
  ],
  numero_interno: 'RASCUNHO-FAT-2',
  numero_faturamento: 'FAT-20260523-0001',
  numero_pedido_venda: 'PV-20260521-0002',
  numero_fiscal: '000000002',
  serie_fiscal: '0',
  badge_principal: { label: 'Autorizada homologação', tipo: 'success' },
  badges_secundarios: [{ label: 'cStat 100', tipo: 'success' }],
  autorizada_homologacao: true,
  modo_leitura: true,
  status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
};

describe('nfeSaidaApresentacao', () => {
  it('titulo listagem usa identidade fiscal', () => {
    expect(
      tituloListagemNfe({
        numero: 'RASCUNHO-FAT-2',
        apresentacao: apresentacaoAutorizada,
      }),
    ).toBe('NF-e Homologação nº 000000002 — Série 0');
  });

  it('subtitulo listagem mostra FAT e PV', () => {
    expect(
      subtituloListagemNfe({ apresentacao: apresentacaoAutorizada }),
    ).toContain('FAT-20260523-0001');
    expect(subtituloListagemNfe({ apresentacao: apresentacaoAutorizada })).toContain('PV-20260521-0002');
  });

  it('badge principal autorizada homologação', () => {
    const linha = badgeNfeSaidaLinhaListagem({
      status: 'RASCUNHO',
      apresentacao: apresentacaoAutorizada,
      resumo_emissao_sefaz: {
        status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
        nfe: { cstat: '100' },
      },
    });
    expect(linha.principal.label).toBe('Autorizada homologação');
    expect(linha.secundario?.label).toBe('cStat 100');
    expect(linha.secundario?.label).not.toContain('FAT');
  });

  it('mensagem cabeçalho sem texto de nenhuma transmissão', () => {
    const msg = mensagemCabecalhoNfeAutorizadaHomolog();
    expect(msg).toContain('SEFAZ');
    expect(msg).not.toMatch(/nenhuma transmiss/i);
  });
});
