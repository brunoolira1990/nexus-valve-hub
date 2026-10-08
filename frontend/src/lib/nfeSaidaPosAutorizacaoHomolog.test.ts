import { describe, expect, it } from 'vitest';
import {
  badgeNfeSaidaLinhaListagem,
  badgeNfeSaidaStatus,
  deveExibirMensagemProntaEmissao,
  isAutorizadaHomologacao,
  mensagemCabecalhoNfeAutorizadaHomolog,
  nfeSalvarFormularioBloqueado,
} from '@/lib/nfeSaidaUi';

describe('nfeSaidaPosAutorizacaoHomolog', () => {
  const resumo = {
    status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
    serie_nfe: '0',
    numero_nfe: '000000002',
    nfe: { cstat: '100', protocolo: '13526005517408', xmotivo: 'Autorizado o uso da NF-e' },
    lote: { cstat: '104', xmotivo: 'Lote processado' },
  };

  it('detecta autorizada homologação', () => {
    expect(isAutorizadaHomologacao({ status: 'AUTORIZADA_HOMOLOGACAO', resumo_emissao_sefaz: resumo })).toBe(true);
    expect(isAutorizadaHomologacao({ status: 'RASCUNHO', resumo_emissao_sefaz: resumo })).toBe(true);
  });

  it('badge principal na listagem', () => {
    const linha = badgeNfeSaidaLinhaListagem({ status: 'RASCUNHO', resumo_emissao_sefaz: resumo });
    expect(linha.principal.label).toBe('Autorizada homologação');
    expect(linha.principal.className).toContain('success');
    expect(linha.secundario?.label).toContain('cStat 100');
  });

  it('status badge homologação', () => {
    expect(badgeNfeSaidaStatus('AUTORIZADA_HOMOLOGACAO').label).toBe('Autorizada homologação');
  });

  it('não exibe mensagem pronta emissão após autorização', () => {
    expect(deveExibirMensagemProntaEmissao('PRONTA_PARA_EMISSAO', true)).toBe(false);
    expect(deveExibirMensagemProntaEmissao('PRONTA_PARA_EMISSAO', false)).toBe(true);
  });

  it('mensagem cabeçalho homologação', () => {
    expect(mensagemCabecalhoNfeAutorizadaHomolog()).toContain('homologação');
    expect(mensagemCabecalhoNfeAutorizadaHomolog()).toContain('não vira produção');
  });

  it('bloqueia salvar formulário', () => {
    expect(nfeSalvarFormularioBloqueado('AUTORIZADA_HOMOLOGACAO')).toBe(true);
  });
});
