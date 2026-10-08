import { describe, expect, it } from 'vitest';
import type { ConsultaCnpjResponse } from '@/services/api/consulta';
import {
  aplicarConsultaCnpjCamposVazios,
  AVISO_IE_FONTE_ATUAL,
  MAPEAMENTO_CNPJ_CLIENTE,
  mensagemSucessoConsultaCnpj,
  montarSugestoesCnpj,
} from './consultaCnpjCadastro';

const dadosMock: ConsultaCnpjResponse = {
  cnpj: '00000000000191',
  razao_social: 'Empresa Teste LTDA',
  nome_fantasia: 'Empresa Teste',
  inscricao_estadual: '',
  inscricao_estadual_disponivel: false,
  cep: '01001000',
  logradouro: 'Rua Das Flores',
  numero: '100',
  complemento: '',
  bairro: 'Centro',
  cidade: 'São Paulo',
  uf: 'SP',
  telefone: '1133334444',
  email: 'contato@teste.local',
  cnae: '2511000',
  regime_tributario: 'Simples Nacional',
  aviso_ie: AVISO_IE_FONTE_ATUAL,
  consulta_ie_pendente: true,
  fonte: 'receitaws',
};

describe('consultaCnpjCadastro', () => {
  it('preenche apenas campos básicos vazios, sem IE', () => {
    const valores = {
      razao_social: '',
      nome_fantasia: 'Já preenchido',
      ie: '',
      cep: '',
      logradouro: '',
      numero: '',
      complemento: '',
      bairro: '',
      cidade: '',
      uf: '',
      telefone: '',
      email: '',
      cnae: '',
      regime_tributario: '',
    };

    const updates = aplicarConsultaCnpjCamposVazios(valores, dadosMock, MAPEAMENTO_CNPJ_CLIENTE);

    expect(updates.razao_social).toBe('Empresa Teste LTDA');
    expect(updates.ie).toBeUndefined();
    expect(updates.nome_fantasia).toBeUndefined();
  });

  it('não monta sugestão de IE a partir da consulta básica', () => {
    const valores = {
      razao_social: 'Empresa Teste LTDA',
      nome_fantasia: '',
      ie: '9999999999',
      cep: '',
      logradouro: '',
      numero: '',
      complemento: '',
      bairro: '',
      cidade: '',
      uf: '',
      telefone: '',
      email: '',
      cnae: '',
      regime_tributario: '',
    };

    const sugestoes = montarSugestoesCnpj(valores, dadosMock, MAPEAMENTO_CNPJ_CLIENTE);
    expect(sugestoes.find((item) => item.campo === 'ie')).toBeUndefined();
  });

  it('mensagem não trata consulta como sucesso completo sem IE', () => {
    const msg = mensagemSucessoConsultaCnpj(dadosMock);
    expect(msg).toContain('Dados cadastrais preenchidos');
    expect(msg).toContain(AVISO_IE_FONTE_ATUAL);
    expect(msg).toContain('Informe a IE manualmente');
    expect(msg).not.toContain('sucesso completo');
    expect(msg).not.toContain('incluindo sugestão de Inscrição Estadual');
  });
});
