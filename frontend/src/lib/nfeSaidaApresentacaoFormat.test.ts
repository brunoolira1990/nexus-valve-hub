import { describe, expect, it } from 'vitest';
import {
  formatAmbienteNfe,
  formatCurrencyBRL,
  formatDateBr,
  formatNfeAtendimentoResumo,
  formatNfeTituloListagem,
  formatNfeValorListagem,
  formatStatusNfe,
} from './nfeSaidaApresentacaoFormat';
import type { NFeSaidaListagemResumo } from '@/types';

const resumoHomolog: NFeSaidaListagemResumo = {
  titulo: 'NF-e Homologação nº 000000002 — Série 0',
  subtitulo: 'FAT-20260522-0002 · PV-20260521-0002',
  fiscal_resumo: {
    badge: 'Homologação autorizada',
    variant: 'warning',
    subtexto: 'cStat 100 · Fora da apuração',
  },
  atendimento_resumo: {
    badges: [
      { label: 'Entrada pendente', variant: 'warning' },
      { label: 'Retirada no fornecedor', variant: 'info' },
    ],
    ocultos: 2,
  },
  tem_duplicatas: true,
  reforma_tributaria_status: 'nao_preparada',
};

describe('nfeSaidaApresentacaoFormat', () => {
  it('não usa RASCUNHO-FAT como título quando há resumo fiscal', () => {
    expect(
      formatNfeTituloListagem({ numero: 'RASCUNHO-FAT-2', listagem_resumo: resumoHomolog }),
    ).toBe('NF-e Homologação nº 000000002 — Série 0');
  });

  it('homologação autorizada nunca aparece como rascunho no título', () => {
    expect(
      formatNfeTituloListagem({
        numero: 'RASCUNHO-FAT-2',
        status: 'AUTORIZADA_HOMOLOGACAO',
        listagem_resumo: { ...resumoHomolog, titulo: 'NF-e em rascunho' },
      }),
    ).toContain('Homologação');
    expect(
      formatNfeTituloListagem({
        numero: 'RASCUNHO-FAT-2',
        status: 'AUTORIZADA_HOMOLOGACAO',
        listagem_resumo: { ...resumoHomolog, titulo: 'NF-e em rascunho' },
      }),
    ).not.toBe('NF-e em rascunho');
  });

  it('rascunho real mantém título em rascunho', () => {
    expect(
      formatNfeTituloListagem({
        numero: 'RASCUNHO-FAT-9',
        status: 'RASCUNHO',
        listagem_resumo: {
          ...resumoHomolog,
          titulo: 'NF-e em rascunho',
          fiscal_resumo: { badge: 'Rascunho', variant: 'neutral', subtexto: '' },
        },
      }),
    ).toBe('NF-e em rascunho');
  });

  it('formatStatusNfe amigável', () => {
    expect(formatStatusNfe('AUTORIZADA_HOMOLOGACAO')).toBe('Autorizada em homologação');
  });

  it('formatAmbienteNfe amigável', () => {
    expect(formatAmbienteNfe('homologacao')).toBe('Homologação');
  });

  it('valor pt-BR', () => {
    expect(formatNfeValorListagem(5000)).toBe('R$ 5.000,00');
    expect(formatCurrencyBRL(5000)).toContain('5.000,00');
  });

  it('data pt-BR', () => {
    expect(formatDateBr('2026-05-22')).toBe('22/05/2026');
  });

  it('atendimento com badges e ocultos', () => {
    const a = formatNfeAtendimentoResumo(resumoHomolog);
    expect(a.badges).toHaveLength(2);
    expect(a.badges[0].label).toBe('Entrada pendente');
    expect(a.ocultos).toBe(2);
  });
});
