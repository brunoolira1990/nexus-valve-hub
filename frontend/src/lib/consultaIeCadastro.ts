import type { ConsultaIeResponse, InscricaoEstadualSefazItem } from '@/services/api/consulta';

import { isValidCnpj, normalizeCnpj } from './cnpj';

export type SugestaoIeCampo = {
  campo: 'ie';
  label: string;
  atual: string;
  sugerido: string;
  situacao_ie?: string;
};

export function montarSugestaoIe(
  ieAtual: string,
  dados: ConsultaIeResponse,
): SugestaoIeCampo | null {
  const sugerido = (dados.inscricao_estadual || '').trim();
  if (!dados.sucesso || !sugerido) return null;
  const atual = (ieAtual || '').trim();
  if (!atual) return null;
  if (atual.toUpperCase() === sugerido.toUpperCase()) return null;
  return {
    campo: 'ie',
    label: 'Inscrição Estadual (IE)',
    atual,
    sugerido,
    situacao_ie: dados.situacao_ie,
  };
}

export const MENSAGEM_UF_PENDENTE_IE = 'Informe a UF no endereço para consultar IE na SEFAZ.';
export function podeConsultarIeSefaz(cnpj: string, uf: string): string | null {
  const cnpjCanonico = normalizeCnpj(cnpj || '');
  if (!isValidCnpj(cnpjCanonico)) return 'Informe um CNPJ válido para consultar a IE na SEFAZ.';
  if (!(uf || '').trim()) return MENSAGEM_UF_PENDENTE_IE;
  return null;
}


export const MENSAGEM_IE_PREENCHIDA_SEFAZ = 'IE preenchida pela SEFAZ. Clique em Salvar para persistir.';

export function mensagemIePreenchidaNoFormulario(_ie?: string): string {
  return MENSAGEM_IE_PREENCHIDA_SEFAZ;
}

export type EstadoUiConsultaIe =
  | 'loading'
  | 'uf_pendente'
  | 'principal'
  | 'preenchida_sefaz'
  | 'manual'
  | 'erro'
  | 'opcoes'
  | 'sugestao';

export function resolverEstadoUiConsultaIe(input: {
  loading: boolean;
  uf: string;
  ieAtual: string;
  preenchidaPelaSefaz: boolean;
  ieSugestao: SugestaoIeCampo | null;
  ieOpcoes: InscricaoEstadualSefazItem[];
  mensagem: string | null;
}): EstadoUiConsultaIe {
  if (input.loading) return 'loading';
  if ((input.ieOpcoes?.length || 0) > 0) return 'opcoes';
  if (input.ieSugestao) return 'sugestao';
  if (!(input.uf || '').trim()) return 'uf_pendente';
  if (
    (input.mensagem && mensagemIndicaErroConsultaIe(input.mensagem)) &&
    !(input.ieAtual || '').trim()
  ) {
    return 'erro';
  }
  if (input.preenchidaPelaSefaz && (input.ieAtual || '').trim()) return 'preenchida_sefaz';
  if (!(input.ieAtual || '').trim()) return 'principal';
  if (input.mensagem && mensagemIndicaErroConsultaIe(input.mensagem)) return 'erro';
  return 'manual';
}

export function mensagemIndicaErroConsultaIe(mensagem: string): boolean {
  const msg = (mensagem || '').trim();
  if (!msg) return false;
  if (msg === MENSAGEM_UF_PENDENTE_IE) return false;
  if (msg === MENSAGEM_IE_PREENCHIDA_SEFAZ) return false;
  if (msg.includes('Múltiplas inscrições')) return false;
  if (msg.toLowerCase().includes('escolha a correta')) return false;
  if (msg.includes('Revise antes de salvar')) return false;
  return true;
}

export function labelAcaoSecundariaConsultaIe(estado: EstadoUiConsultaIe): string {
  if (estado === 'manual' || estado === 'sugestao') return 'Atualizar IE pela SEFAZ';
  return 'Consultar novamente';
}

export function montarChaveConsultaIe(cnpj: string, uf: string): string {
  const cnpjCanonico = normalizeCnpj(cnpj || '');
  const ufNorm = (uf || '').trim().toUpperCase();
  return `${cnpjCanonico}|${ufNorm}`;
}

/** Evita consulta IE automática repetida para o mesmo CNPJ + UF na sessão do formulário. */
export function deveDispararConsultaIeAutomatica(
  chave: string,
  ultimaChave: string | null,
  emConsulta: boolean,
): boolean {
  if (emConsulta) return false;
  if (!chave || chave.endsWith('|')) return false;
  return ultimaChave !== chave;
}

export function mensagemConsultaIe(dados: ConsultaIeResponse): string {
  if (dados.sucesso && dados.inscricao_estadual) {
    if ((dados.inscricoes_estaduais?.length || 0) > 1) {
      return dados.mensagem_usuario || 'Múltiplas inscrições encontradas na SEFAZ. Escolha a correta.';
    }
    return dados.mensagem_usuario || `IE encontrada na SEFAZ: ${dados.inscricao_estadual}. Revise antes de salvar.`;
  }
  return dados.mensagem_usuario || dados.detail || 'Não foi possível consultar a IE na SEFAZ.';
}

export function ieEstaAtiva(
  item?: InscricaoEstadualSefazItem | null,
  dados?: Pick<ConsultaIeResponse, 'situacao_ie'>,
): boolean {
  if (item) {
    if (item.habilitada === true) return true;
    if (item.situacao_codigo === '1') return true;
    const situacao = (item.situacao_ie || '').trim().toLowerCase();
    if (situacao.includes('habilit')) return true;
    return false;
  }
  const situacao = (dados?.situacao_ie || '').trim().toLowerCase();
  return situacao.includes('habilit');
}

export function ieAplicavelAutomaticamente(item: InscricaoEstadualSefazItem): boolean {
  return ieEstaAtiva(item);
}

export type ResolucaoAplicacaoIe =
  | { tipo: 'nenhuma' }
  | { tipo: 'direta'; valor: string }
  | { tipo: 'opcoes'; opcoes: InscricaoEstadualSefazItem[] }
  | { tipo: 'sugestao'; sugestao: SugestaoIeCampo };

/** Define se a IE retornada deve preencher o campo, exibir opções ou sugestão Atual × Encontrado. */
export function resolverAplicacaoIe(ieAtual: string, dados: ConsultaIeResponse): ResolucaoAplicacaoIe {
  const atual = (ieAtual || '').trim();
  const ie = (dados.inscricao_estadual || '').trim();
  const opcoes = dados.inscricoes_estaduais || [];

  if (!dados.sucesso || !ie) {
    return { tipo: 'nenhuma' };
  }

  if (opcoes.length > 1) {
    return { tipo: 'opcoes', opcoes };
  }

  if (!atual) {
    if (opcoes.length === 1) {
      const item = opcoes[0];
      if (!ieEstaAtiva(item, dados)) {
        return { tipo: 'opcoes', opcoes };
      }
      return { tipo: 'direta', valor: ie };
    }
    return { tipo: 'direta', valor: ie };
  }

  const sugestao = montarSugestaoIe(atual, dados);
  if (sugestao) {
    return { tipo: 'sugestao', sugestao };
  }
  return { tipo: 'nenhuma' };
}
