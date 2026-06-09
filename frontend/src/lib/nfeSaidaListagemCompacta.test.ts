import { describe, expect, it } from 'vitest';
import type { NFeSaidaListagemResumo } from '@/types';
import {
  fiscalResumoBadgeClass,
  getNfeFiscalSummaryBadge,
  getNfeOperationalSummaryBadges,
} from './nfeSaidaListagemCompacta';

const resumoHomolog: NFeSaidaListagemResumo = {
  titulo: 'NF-e Homologação nº 000000002',
  subtitulo: 'FAT-1 · PV-1',
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
    ocultos: 1,
  },
  tem_duplicatas: true,
  reforma_tributaria_status: 'nao_aplicavel',
};

describe('nfeSaidaListagemCompacta', () => {
  it('badge fiscal agrupado homologação', () => {
    const f = getNfeFiscalSummaryBadge(resumoHomolog);
    expect(f.label).toBe('Homologação autorizada');
    expect(f.className).toBe(fiscalResumoBadgeClass('warning'));
  });

  it('cStat no subtexto fiscal', () => {
    expect(getNfeFiscalSummaryBadge(resumoHomolog).subtexto).toContain('cStat 100');
  });

  it('atendimento no máximo dois badges visíveis na API', () => {
    const atend = getNfeOperationalSummaryBadges(resumoHomolog);
    expect(atend.badges).toHaveLength(2);
    expect(atend.badges[0].label).toBe('Entrada pendente');
    expect(atend.badges[1].label).toBe('Retirada no fornecedor');
  });

  it('contador de badges ocultos +N', () => {
    expect(getNfeOperationalSummaryBadges(resumoHomolog).ocultos).toBe(1);
  });

  it('não mistura badges fiscais separados no helper', () => {
    const f = getNfeFiscalSummaryBadge(resumoHomolog);
    expect(f.label).not.toContain('cStat');
    expect(f.subtexto).toContain('cStat');
  });

  it('rascunho mostra Fiscal = Rascunho', () => {
    const f = getNfeFiscalSummaryBadge({
      ...resumoHomolog,
      fiscal_resumo: { badge: 'Rascunho', variant: 'neutral', subtexto: '' },
    });
    expect(f.label).toBe('Rascunho');
    expect(f.hasData).toBe(true);
  });

  it('fallback fiscal quando resumo ausente mas status homolog', () => {
    const f = getNfeFiscalSummaryBadge(undefined, {
      status: 'AUTORIZADA_HOMOLOGACAO',
      status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
    });
    expect(f.label).toBe('Homologação autorizada');
    expect(f.hasData).toBe(true);
  });

  it('fiscal nunca fica vazio para rascunho sem resumo', () => {
    const f = getNfeFiscalSummaryBadge(undefined, { status: 'RASCUNHO' });
    expect(f.label).toBe('Rascunho');
    expect(f.hasData).toBe(true);
  });
});
