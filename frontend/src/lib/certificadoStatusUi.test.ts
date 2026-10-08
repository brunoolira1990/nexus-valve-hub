import { describe, expect, it } from 'vitest';

import {
  origemFisicaCqBadge,
  origemFisicaCqItem,
  origemFisicaCqResumo,
} from './certificadoStatusUi';

const CF_ORIGEM = {
  certificado_fornecedor_origem_id: 100,
  item_certificado_fornecedor_origem_id: 200,
};

describe('origemFisicaCqItem — PADRAO_ITEM', () => {
  it('sem origem documental e sem dados -> NAO_CONFIRMADA', () => {
    expect(origemFisicaCqItem({})).toBe('NAO_CONFIRMADA');
  });

  it('sem origem documental com corrida manual -> MANUAL', () => {
    expect(origemFisicaCqItem({ corrida: 'C1' })).toBe('MANUAL');
  });

  it('com origem documental sem corrida_snapshot -> PARCIAL', () => {
    expect(origemFisicaCqItem({ ...CF_ORIGEM })).toBe('PARCIAL');
  });

  it('com origem documental + corrida_snapshot -> CONFIRMADA', () => {
    expect(origemFisicaCqItem({ ...CF_ORIGEM, corrida_snapshot: 'C1' })).toBe('CONFIRMADA');
  });

  it('com origem documental + corrida_snapshot + avisos -> PARCIAL', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        corrida_snapshot: 'C1',
        rastreabilidade_avisos: ['algum aviso'],
      }),
    ).toBe('PARCIAL');
  });
});

describe('origemFisicaCqItem — VALVULA_COMPONENTES (regra AND por componente)', () => {
  it('sem origem documental, todos componentes manuais -> MANUAL', () => {
    expect(
      origemFisicaCqItem({
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', corrida: 'C1', ativo: true },
          { nome_componente: 'assento', lote: 'L1', ativo: true },
        ],
      }),
    ).toBe('MANUAL');
  });

  it('sem origem documental, nenhum componente com corrida/lote -> NAO_CONFIRMADA', () => {
    expect(
      origemFisicaCqItem({
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', ativo: true },
          { nome_componente: 'assento', ativo: true },
        ],
      }),
    ).toBe('NAO_CONFIRMADA');
  });

  it('com origem documental, TODOS componentes ativos com corrida -> CONFIRMADA', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', corrida: 'C1', ativo: true },
          { nome_componente: 'assento', corrida: 'C2', ativo: true },
        ],
      }),
    ).toBe('CONFIRMADA');
  });

  it('com origem documental, UM componente ativo sem corrida -> PARCIAL', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', corrida: 'C1', ativo: true },
          { nome_componente: 'assento', corrida: '', ativo: true },
        ],
      }),
    ).toBe('PARCIAL');
  });

  it('componentes inativos e sem nome sao ignorados', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', corrida: 'C1', ativo: true },
          { nome_componente: 'assento', corrida: '', ativo: false },
          { nome_componente: '', corrida: 'C2', ativo: true },
        ],
      }),
    ).toBe('CONFIRMADA');
  });

  it('com origem documental, sem componente valido -> PARCIAL', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: '', corrida: 'C1', ativo: true },
          { nome_componente: 'x', corrida: '', ativo: false },
        ],
      }),
    ).toBe('PARCIAL');
  });

  it('apenas lote em componente conta como corrida/lote', () => {
    expect(
      origemFisicaCqItem({
        ...CF_ORIGEM,
        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',
        componentes: [
          { nome_componente: 'corpo', lote: 'L1', ativo: true },
          { nome_componente: 'assento', corrida: 'C1', ativo: true },
        ],
      }),
    ).toBe('CONFIRMADA');
  });
});

describe('origemFisicaCqResumo — agrega status', () => {
  it('todos confirmados -> CONFIRMADA', () => {
    expect(
      origemFisicaCqResumo([
        { ...CF_ORIGEM, corrida_snapshot: 'C1' },
        { ...CF_ORIGEM, lote_snapshot: 'L1' },
      ]),
    ).toBe('CONFIRMADA');
  });

  it('mistura confirmada + parcial -> PARCIAL', () => {
    expect(
      origemFisicaCqResumo([{ ...CF_ORIGEM, corrida_snapshot: 'C1' }, { ...CF_ORIGEM }]),
    ).toBe('PARCIAL');
  });

  it('todos manuais -> MANUAL', () => {
    expect(origemFisicaCqResumo([{ corrida: 'C1' }, { lote: 'L1' }])).toBe('MANUAL');
  });

  it('sem itens -> NAO_CONFIRMADA', () => {
    expect(origemFisicaCqResumo([])).toBe('NAO_CONFIRMADA');
  });
});

describe('origemFisicaCqBadge', () => {
  it('CONFIRMADA tem label e className', () => {
    const b = origemFisicaCqBadge('CONFIRMADA');
    expect(b.label).toBeTruthy();
    expect(b.className).toBeTruthy();
  });
});
