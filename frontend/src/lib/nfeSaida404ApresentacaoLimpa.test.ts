import { describe, expect, it } from 'vitest';
import {
  badgeNfeSaidaLinhaListagem,
  deveExibirStatusConferenciaListagem,
  isCanceladaInterna,
  subtituloListagemNfe,
  tituloListagemNfe,
} from '@/lib/nfeSaidaUi';

const apAutorizada = {
  titulo_exibicao: 'NF-e Homologação nº 000000002 — Série 0',
  listagem_titulo: 'NF-e Homologação nº 000000002 — Série 0',
  listagem_subtitulo: 'FAT-20260522-0002 · PV-20260521-0002',
  numero_faturamento: 'FAT-20260522-0002',
  numero_pedido_venda: 'PV-20260521-0002',
  numero_interno: 'RASCUNHO-FAT-2',
  badge_principal: { label: 'Autorizada homologação', tipo: 'success' },
  badges_secundarios: [{ label: 'cStat 100', tipo: 'success' }],
  autorizada_homologacao: true,
  ocultar_status_conferencia_listagem: true,
  linhas_subtitulo: ['Faturamento: FAT-20260522-0002', 'Pedido de venda: PV-20260521-0002'],
};

describe('nfeSaida404ApresentacaoLimpa', () => {
  it('titulo fiscal na listagem', () => {
    expect(tituloListagemNfe({ numero: 'RASCUNHO-FAT-2', apresentacao: apAutorizada })).toContain(
      'NF-e Homologação nº 000000002',
    );
  });

  it('subtitulo FAT e PV sem LEGADO', () => {
    const sub = subtituloListagemNfe({ apresentacao: apAutorizada });
    expect(sub).toContain('FAT-20260522-0002');
    expect(sub).toContain('PV-20260521-0002');
    expect(sub).not.toMatch(/LEGADO/i);
    expect(sub).not.toContain('Origem interna');
  });

  it('status autorizada apenas cStat no secundario', () => {
    const linha = badgeNfeSaidaLinhaListagem({
      status: 'RASCUNHO',
      apresentacao: apAutorizada,
      resumo_emissao_sefaz: { status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO', nfe: { cstat: '100' } },
    });
    expect(linha.principal.label).toBe('Autorizada homologação');
    expect(linha.secundario?.label).toBe('cStat 100');
    expect(linha.secundario?.label).not.toContain('FAT');
  });

  it('nao exibe conferencia quando autorizada', () => {
    expect(
      deveExibirStatusConferenciaListagem({
        status: 'AUTORIZADA_HOMOLOGACAO',
        status_conferencia: 'PRONTA_PARA_EMISSAO',
        apresentacao: apAutorizada,
      }),
    ).toBe(false);
  });

  it('cancelada interna sem conferencia', () => {
    expect(
      deveExibirStatusConferenciaListagem({
        status: 'CANCELADA_INTERNA',
        status_conferencia: 'EM_CONFERENCIA',
        apresentacao: { cancelada_interna: true, ocultar_status_conferencia_listagem: true },
      }),
    ).toBe(false);
    expect(isCanceladaInterna({ status: 'CANCELADA_INTERNA' })).toBe(true);
  });

  it('linhas subtitulo sem origem interna', () => {
    expect(apAutorizada.linhas_subtitulo?.join(' ')).not.toContain('Origem interna');
    expect(apAutorizada.linhas_subtitulo?.join(' ')).not.toContain('RASCUNHO-FAT');
  });
});
