import { describe, expect, it } from 'vitest';

type EmissaoSefaz = {
  status_emissao_sefaz?: string;
  serie_nfe?: string;
  numero_nfe?: string;
  lote?: { cstat?: string; xmotivo?: string };
  nfe?: { cstat?: string; xmotivo?: string; protocolo?: string };
};

export function labelBotaoEmitirHomolog(emissao?: EmissaoSefaz | null): string {
  const st = emissao?.status_emissao_sefaz ?? '';
  if (st === 'ERRO_TRANSMISSAO' || st === 'REJEITADA_HOMOLOGACAO' || st === 'LOTE_PROCESSADO_SEM_PROTOCOLO') {
    return 'Tentar emitir novamente em homologação';
  }
  return 'Emitir em homologação';
}

export function mensagemEmissaoResposta(res: {
  ok?: boolean;
  autorizado?: boolean;
  cstat?: string;
  cStat?: string;
  xmotivo?: string;
  xMotivo?: string;
  mensagem?: string;
  erros?: string[];
  etapa?: string;
  lote?: { cstat?: string; xmotivo?: string };
  nfe?: { cstat?: string; xmotivo?: string };
}): { tipo: 'sucesso' | 'rejeicao' | 'tecnico' | 'lote_sem_prot'; texto: string } {
  const cstatNfe = res.nfe?.cstat ?? res.cstat ?? res.cStat ?? '';
  const cstatLote = res.lote?.cstat ?? '';
  const xmotivoNfe = res.nfe?.xmotivo ?? res.xmotivo ?? res.xMotivo ?? '';
  const errosTxt = (res.erros ?? []).filter(Boolean).join(' · ');
  const msgBase = res.mensagem || xmotivoNfe || errosTxt || 'Emissão não concluída.';
  if (res.ok || res.autorizado) {
    const linha = cstatNfe ? `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}` : msgBase;
    return { tipo: 'sucesso', texto: linha };
  }
  if (cstatNfe && cstatNfe !== 'ERRO' && cstatNfe !== cstatLote) {
    return { tipo: 'rejeicao', texto: `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}`.trim() };
  }
  if (cstatLote === '104' && !cstatNfe) {
    return { tipo: 'lote_sem_prot', texto: `Lote processado (cStat 104) sem protocolo NF-e. ${msgBase}`.trim() };
  }
  const etapaTxt = res.etapa ? `Etapa: ${res.etapa}. ` : '';
  return { tipo: 'tecnico', texto: `${etapaTxt}${msgBase}${errosTxt ? ` (${errosTxt})` : ''}`.trim() };
}

export function exibeLoteSeparado(emissao?: EmissaoSefaz | null): boolean {
  return Boolean(emissao?.lote?.cstat);
}

describe('nfeSaidaEmissaoHomolog', () => {
  it('label retry em ERRO_TRANSMISSAO', () => {
    expect(labelBotaoEmitirHomolog({ status_emissao_sefaz: 'ERRO_TRANSMISSAO' })).toContain('novamente');
  });

  it('não trata 104 do lote como rejeição final', () => {
    const r = mensagemEmissaoResposta({
      ok: false,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
      nfe: { cstat: '225', xmotivo: 'Rejeição schema' },
    });
    expect(r.tipo).toBe('rejeicao');
    expect(r.texto).toContain('225');
    expect(r.texto).not.toMatch(/^cStat 104/);
  });

  it('lote 104 sem infProt', () => {
    const r = mensagemEmissaoResposta({
      ok: false,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
    });
    expect(r.tipo).toBe('lote_sem_prot');
  });

  it('autorizada quando nfe.cstat = 100', () => {
    const r = mensagemEmissaoResposta({
      ok: true,
      autorizado: true,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
      nfe: { cstat: '100', xmotivo: 'Autorizado', protocolo: '135' },
    });
    expect(r.tipo).toBe('sucesso');
    expect(r.texto).toContain('100');
  });

  it('exibe blocos lote e nfe separados', () => {
    expect(
      exibeLoteSeparado({
        lote: { cstat: '104' },
        nfe: { cstat: '225' },
      }),
    ).toBe(true);
  });

  it('mensagem específica rejeição 588', () => {
    const r = mensagemEmissaoResposta({
      ok: false,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
      nfe: {
        cstat: '588',
        xmotivo: 'Rejeição: Não é permitida a presença de caracteres de edição',
      },
    });
    expect(r.tipo).toBe('rejeicao');
    expect(r.texto).toContain('588');
  });

  it('mensagem específica rejeição 266', () => {
    const r = mensagemEmissaoResposta({
      ok: false,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
      nfe: {
        cstat: '266',
        xmotivo: 'Rejeição: Série utilizada fora da faixa permitida no Web Service',
      },
    });
    expect(r.tipo).toBe('rejeicao');
    expect(r.texto).toContain('266');
  });

  it('mensagem específica rejeição 225', () => {
    const r = mensagemEmissaoResposta({
      ok: false,
      lote: { cstat: '104', xmotivo: 'Lote processado' },
      nfe: { cstat: '225', xmotivo: 'Rejeição: Falha no Schema XML do lote de NFe' },
    });
    expect(r.tipo).toBe('rejeicao');
    expect(r.texto).toContain('225');
    expect(r.texto).toContain('Schema');
  });
});
