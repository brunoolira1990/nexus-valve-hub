import { describe, expect, it } from 'vitest';
import type { AtualizarImpostosPreviewResponse } from '@/services/api/fiscal';
import { modalNaoExibeAbasConferencia } from '@/components/fiscal/NFeSaidaAtualizarImpostosModal';
import {
  agruparAlteracoesPorItem,
  grupoAlteracaoImposto,
  isAlteracaoTextoFiscal,
  labelGrupoAlteracao,
  mensagemConfirmarDesabilitado,
  podeConfirmarAplicarImpostos,
  podeExibirBotaoAtualizarImpostos,
  temAlteracaoAplicavel,
  tooltipAtualizarImpostos,
  totalTextosFiscaisSugeridos,
} from './nfeSaidaAtualizarImpostos';

const previewBase: AtualizarImpostosPreviewResponse = {
  nfe_saida_id: 1,
  pode_aplicar: true,
  resumo: {
    itens_total: 2,
    itens_com_regra: 1,
    itens_sem_regra: 1,
    itens_com_alteracao: 1,
    itens_sem_alteracao: 1,
    reforma_configurada: 0,
    textos_fiscais_sugeridos: 0,
    recomendacoes_sugeridas: 0,
  },
  textos_fiscais: { alteracoes: [], recomendacoes: [] },
  itens: [
    {
      item_id: 10,
      produto_nome: 'Prod A',
      ncm: '84818200',
      regra_encontrada: true,
      regra_fiscal_saida_id: 5,
      regra_fiscal_saida_nome: 'Regra SP',
      alteracoes: [
        { campo: 'cfop', label: 'CFOP', antes: '—', depois: '5102' },
        { campo: 'cst_icms', label: 'CST ICMS', antes: '—', depois: '00' },
        { campo: 'cst_ibs_cbs', label: 'CST IBS/CBS', antes: '—', depois: '000' },
        { campo: 'classificacao_tributaria', label: 'Classificação tributária', antes: '—', depois: '000001' },
      ],
      alertas: [],
    },
    {
      item_id: 11,
      produto_nome: 'Prod B',
      ncm: '00000000',
      regra_encontrada: false,
      regra_fiscal_saida_id: null,
      regra_fiscal_saida_nome: '',
      alteracoes: [],
      alertas: ['Nenhuma regra fiscal de saída encontrada para este item.'],
    },
  ],
  alertas: [],
};

describe('nfeSaidaAtualizarImpostos agrupamento', () => {
  it('classifica CFOP e ICMS como fiscal_atual', () => {
    expect(grupoAlteracaoImposto('cfop')).toBe('fiscal_atual');
    expect(grupoAlteracaoImposto('cst_icms')).toBe('fiscal_atual');
    expect(grupoAlteracaoImposto('valor_pis')).toBe('fiscal_atual');
  });

  it('classifica IBS/CBS como reforma_tributaria', () => {
    expect(grupoAlteracaoImposto('cst_ibs_cbs')).toBe('reforma_tributaria');
    expect(grupoAlteracaoImposto('classificacao_tributaria')).toBe('reforma_tributaria');
    expect(grupoAlteracaoImposto('valor_cbs')).toBe('reforma_tributaria');
  });

  it('agruparAlteracoesPorItem separa fiscal e reforma', () => {
    const agrupado = agruparAlteracoesPorItem(previewBase.itens);
    expect(agrupado).toHaveLength(1);
    expect(agrupado[0].grupos.fiscal_atual?.map((a) => a.campo)).toEqual(['cfop', 'cst_icms']);
    expect(agrupado[0].grupos.reforma_tributaria?.map((a) => a.campo)).toEqual([
      'cst_ibs_cbs',
      'classificacao_tributaria',
    ]);
  });

  it('labelGrupoAlteracao retorna rótulos amigáveis', () => {
    expect(labelGrupoAlteracao('fiscal_atual')).toBe('Fiscal atual');
    expect(labelGrupoAlteracao('reforma_tributaria')).toBe('Reforma Tributária');
  });
});

describe('nfeSaidaAtualizarImpostos botão e confirmar', () => {
  it('habilita com pode_atualizar_impostos=true', () => {
    expect(podeExibirBotaoAtualizarImpostos('RASCUNHO', true, 1)).toBe(true);
  });

  it('habilita em RASCUNHO mesmo com permissão ausente (reforma não configurada)', () => {
    expect(podeExibirBotaoAtualizarImpostos('RASCUNHO', undefined, 2)).toBe(true);
  });

  it('habilita com origem comercial travada quando backend permite', () => {
    expect(podeExibirBotaoAtualizarImpostos('RASCUNHO', true, 1)).toBe(true);
  });

  it('desabilita em CANCELADA_INTERNA', () => {
    expect(podeExibirBotaoAtualizarImpostos('CANCELADA_INTERNA', true, 1)).toBe(false);
  });

  it('confirmar habilita quando pode_aplicar=true', () => {
    expect(podeConfirmarAplicarImpostos(previewBase)).toBe(true);
    expect(temAlteracaoAplicavel(previewBase)).toBe(true);
  });

  it('confirmar habilita quando só há textos fiscais', () => {
    const soTextos: AtualizarImpostosPreviewResponse = {
      ...previewBase,
      pode_aplicar: true,
      resumo: {
        ...previewBase.resumo,
        itens_com_alteracao: 0,
        textos_fiscais_sugeridos: 1,
      },
      textos_fiscais: {
        alteracoes: [
          {
            campo: 'informacoes_adicionais',
            label: 'Informações adicionais',
            antes: '—',
            depois: 'Texto da regra',
          },
        ],
        recomendacoes: [],
      },
    };
    expect(temAlteracaoAplicavel(soTextos)).toBe(true);
    expect(mensagemConfirmarDesabilitado({ ...soTextos, pode_aplicar: false })).toContain('texto fiscal');
  });

  it('isAlteracaoTextoFiscal identifica campos de cabeçalho', () => {
    expect(isAlteracaoTextoFiscal('informacoes_adicionais')).toBe(true);
    expect(isAlteracaoTextoFiscal('cfop')).toBe(false);
  });

  it('confirmar desabilita quando não há alterações', () => {
    const semAlt = {
      ...previewBase,
      pode_aplicar: false,
      resumo: { ...previewBase.resumo, itens_com_alteracao: 0 },
    };
    expect(podeConfirmarAplicarImpostos(semAlt)).toBe(false);
    expect(mensagemConfirmarDesabilitado(semAlt)).toMatch(/alteração fiscal|texto fiscal/i);
  });

  it('confirmar desabilita quando todos sem regra', () => {
    const semRegra = {
      ...previewBase,
      pode_aplicar: false,
      resumo: {
        itens_total: 1,
        itens_com_regra: 0,
        itens_sem_regra: 1,
        itens_com_alteracao: 0,
        itens_sem_alteracao: 1,
        reforma_configurada: 0,
      },
      itens: [previewBase.itens[1]],
    };
    expect(podeConfirmarAplicarImpostos(semRegra)).toBe(false);
    expect(mensagemConfirmarDesabilitado(semRegra)).toContain('regra fiscal');
  });

  it('tooltip quando bloqueado', () => {
    expect(tooltipAtualizarImpostos('AUTORIZADA_INTERNA', true, 1)).toContain('rascunho');
  });
});

describe('modal UX 3.5.2.2', () => {
  it('abas da conferência não devem aparecer no modal focado', () => {
    expect(modalNaoExibeAbasConferencia('Resumo Itens Fiscal')).toBe(false);
    expect(modalNaoExibeAbasConferencia('Atualizar impostos Somente dados fiscais')).toBe(true);
  });
});
