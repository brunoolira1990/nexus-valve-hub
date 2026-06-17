import { describe, expect, it } from 'vitest';
import type { ConsultaIeResponse } from '@/services/api/consulta';
import {
  deveDispararConsultaIeAutomatica,
  ieEstaAtiva,
  labelAcaoSecundariaConsultaIe,
  mensagemConsultaIe,
  mensagemIePreenchidaNoFormulario,
  mensagemIndicaErroConsultaIe,
  montarChaveConsultaIe,
  montarSugestaoIe,
  MENSAGEM_IE_PREENCHIDA_SEFAZ,
  MENSAGEM_UF_PENDENTE_IE,
  podeConsultarIeSefaz,
  resolverAplicacaoIe,
  resolverEstadoUiConsultaIe,
} from './consultaIeCadastro';

const respostaOk: ConsultaIeResponse = {
  sucesso: true,
  cnpj: '00000000000191',
  uf: 'SP',
  inscricao_estadual: '123456789012',
  situacao_ie: 'Habilitado',
  inscricoes_estaduais: [
    {
      inscricao_estadual: '123456789012',
      situacao_ie: 'Habilitado',
      uf: 'SP',
      habilitada: true,
    },
  ],
  mensagem_usuario: 'Inscrição Estadual encontrada na SEFAZ.',
  fonte: 'SEFAZ_NFE_CONSULTA_CADASTRO',
};

describe('consultaIeCadastro', () => {
  it('exige UF para consulta IE', () => {
    expect(podeConsultarIeSefaz('00000000000191', '')).toBe(MENSAGEM_UF_PENDENTE_IE);
  });

  it('monta chave anti-loop por CNPJ + UF', () => {
    expect(montarChaveConsultaIe('00.000.000/0001-91', 'mg')).toBe('00000000000191|MG');
  });

  it('evita consulta automática repetida na mesma sessão', () => {
    const chave = montarChaveConsultaIe('00000000000191', 'SP');
    expect(deveDispararConsultaIeAutomatica(chave, null, false)).toBe(true);
    expect(deveDispararConsultaIeAutomatica(chave, chave, false)).toBe(false);
    expect(deveDispararConsultaIeAutomatica(chave, null, true)).toBe(false);
  });

  it('mensagem de IE preenchida orienta salvar', () => {
    expect(mensagemIePreenchidaNoFormulario('123')).toBe(MENSAGEM_IE_PREENCHIDA_SEFAZ);
    expect(MENSAGEM_IE_PREENCHIDA_SEFAZ).toContain('Salvar');
  });

  it('resolve estado visual após IE preenchida pela SEFAZ', () => {
    expect(
      resolverEstadoUiConsultaIe({
        loading: false,
        uf: 'MG',
        ieAtual: '0010870822926',
        preenchidaPelaSefaz: true,
        ieSugestao: null,
        ieOpcoes: [],
        mensagem: MENSAGEM_IE_PREENCHIDA_SEFAZ,
      }),
    ).toBe('preenchida_sefaz');
  });

  it('resolve estado principal quando IE vazia e UF informada', () => {
    expect(
      resolverEstadoUiConsultaIe({
        loading: false,
        uf: 'MG',
        ieAtual: '',
        preenchidaPelaSefaz: false,
        ieSugestao: null,
        ieOpcoes: [],
        mensagem: null,
      }),
    ).toBe('principal');
  });

  it('resolve estado manual quando IE já existia', () => {
    expect(
      resolverEstadoUiConsultaIe({
        loading: false,
        uf: 'MG',
        ieAtual: '123',
        preenchidaPelaSefaz: false,
        ieSugestao: null,
        ieOpcoes: [],
        mensagem: null,
      }),
    ).toBe('manual');
    expect(labelAcaoSecundariaConsultaIe('manual')).toBe('Atualizar IE pela SEFAZ');
  });

  it('identifica mensagem de erro da consulta', () => {
    expect(mensagemIndicaErroConsultaIe('Consulta SEFAZ indisponível no momento.')).toBe(true);
    expect(mensagemIndicaErroConsultaIe(MENSAGEM_IE_PREENCHIDA_SEFAZ)).toBe(false);
  });

  it('monta sugestão quando IE difere', () => {
    const sugestao = montarSugestaoIe('999999999999', respostaOk);
    expect(sugestao?.sugerido).toBe('123456789012');
    expect(sugestao?.atual).toBe('999999999999');
  });

  it('não monta sugestão quando IE vazia', () => {
    expect(montarSugestaoIe('', respostaOk)).toBeNull();
  });

  it('mensagem não trata como sucesso genérico de CNPJ', () => {
    const msg = mensagemConsultaIe(respostaOk);
    expect(msg).toContain('SEFAZ');
  });

  it('aplica IE ativa automaticamente quando campo está vazio', () => {
    const resolucao = resolverAplicacaoIe('', respostaOk);
    expect(resolucao).toEqual({ tipo: 'direta', valor: '123456789012' });
  });

  it('reconhece IE ativa pela situação mesmo sem flag habilitada', () => {
    const dados: ConsultaIeResponse = {
      ...respostaOk,
      inscricoes_estaduais: [
        {
          inscricao_estadual: '123456789012',
          situacao_ie: 'Habilitado',
          uf: 'SP',
        },
      ],
    };
    expect(ieEstaAtiva(dados.inscricoes_estaduais?.[0])).toBe(true);
    expect(resolverAplicacaoIe('', dados)).toEqual({ tipo: 'direta', valor: '123456789012' });
  });

  it('exibe opções quando há múltiplas IEs', () => {
    const dados: ConsultaIeResponse = {
      ...respostaOk,
      inscricoes_estaduais: [
        { inscricao_estadual: '111111111111', situacao_ie: 'Não habilitado', uf: 'SP' },
        { inscricao_estadual: '222222222222', situacao_ie: 'Habilitado', uf: 'SP', habilitada: true },
      ],
    };
    const resolucao = resolverAplicacaoIe('', dados);
    expect(resolucao.tipo).toBe('opcoes');
    if (resolucao.tipo === 'opcoes') {
      expect(resolucao.opcoes).toHaveLength(2);
    }
  });

  it('mostra sugestão quando IE cadastrada difere da encontrada', () => {
    const resolucao = resolverAplicacaoIe('999999999999', respostaOk);
    expect(resolucao.tipo).toBe('sugestao');
  });
});
