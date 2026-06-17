import type { ConsultaCnpjResponse } from '@/services/api/consulta';
import { digitsOnly, formatCep, formatPhone } from '@/lib/masks';

export type CampoFormularioCnpj = string;

export type CampoSugestaoCnpj<TCampo extends CampoFormularioCnpj = CampoFormularioCnpj> = {
  campo: TCampo;
  label: string;
  atual: string;
  sugerido: string;
};

export type MapeamentoCampoCnpj<TCampo extends CampoFormularioCnpj> = {
  campo: TCampo;
  label: string;
  apiKey: keyof ConsultaCnpjResponse;
  apenasSeVazio?: boolean;
  formatar?: (valor: string) => string;
};

function normalizarComparacao(valor: string, campo: CampoFormularioCnpj): string {
  const v = (valor || '').trim();
  if (campo === 'ie') {
    return v.toUpperCase();
  }
  if (campo === 'cep') {
    return digitsOnly(v, 8);
  }
  if (campo === 'telefone' || campo === 'celular' || campo === 'telefone_alternativo') {
    return digitsOnly(v, 11);
  }
  return v.toUpperCase();
}

function valoresEquivalentes(atual: string, sugerido: string, campo: CampoFormularioCnpj): boolean {
  return normalizarComparacao(atual, campo) === normalizarComparacao(sugerido, campo);
}

export function montarSugestoesCnpj<TCampo extends CampoFormularioCnpj>(
  valoresAtuais: Record<TCampo, string>,
  dados: ConsultaCnpjResponse,
  mapeamento: MapeamentoCampoCnpj<TCampo>[],
): CampoSugestaoCnpj<TCampo>[] {
  const sugestoes: CampoSugestaoCnpj<TCampo>[] = [];
  for (const item of mapeamento) {
    const sugeridoBruto = String(dados[item.apiKey] ?? '').trim();
    if (!sugeridoBruto) continue;
    const sugerido = item.formatar ? item.formatar(sugeridoBruto) : sugeridoBruto;
    const atual = String(valoresAtuais[item.campo] ?? '').trim();
    if (!atual) continue;
    if (valoresEquivalentes(atual, sugerido, item.campo)) continue;
    sugestoes.push({
      campo: item.campo,
      label: item.label,
      atual,
      sugerido,
    });
  }
  return sugestoes;
}

export function aplicarConsultaCnpjCamposVazios<TCampo extends CampoFormularioCnpj>(
  valoresAtuais: Record<TCampo, string>,
  dados: ConsultaCnpjResponse,
  mapeamento: MapeamentoCampoCnpj<TCampo>[],
): Partial<Record<TCampo, string>> {
  const updates: Partial<Record<TCampo, string>> = {};
  for (const item of mapeamento) {
    const atual = String(valoresAtuais[item.campo] ?? '').trim();
    if (atual && item.apenasSeVazio !== false) continue;
    const sugeridoBruto = String(dados[item.apiKey] ?? '').trim();
    if (!sugeridoBruto) continue;
    updates[item.campo] = item.formatar ? item.formatar(sugeridoBruto) : sugeridoBruto;
  }
  return updates;
}

export const MAPEAMENTO_CNPJ_CLIENTE: MapeamentoCampoCnpj<
  | 'razao_social'
  | 'nome_fantasia'
  | 'cep'
  | 'logradouro'
  | 'numero'
  | 'complemento'
  | 'bairro'
  | 'cidade'
  | 'uf'
  | 'telefone'
  | 'email'
  | 'cnae'
  | 'regime_tributario'
>[] = [
  { campo: 'razao_social', label: 'Razão Social', apiKey: 'razao_social' },
  { campo: 'nome_fantasia', label: 'Nome Fantasia', apiKey: 'nome_fantasia' },
  { campo: 'cep', label: 'CEP', apiKey: 'cep', formatar: (v) => formatCep(v) },
  { campo: 'logradouro', label: 'Logradouro', apiKey: 'logradouro' },
  { campo: 'numero', label: 'Número', apiKey: 'numero' },
  { campo: 'complemento', label: 'Complemento', apiKey: 'complemento' },
  { campo: 'bairro', label: 'Bairro', apiKey: 'bairro' },
  { campo: 'cidade', label: 'Cidade', apiKey: 'cidade' },
  { campo: 'uf', label: 'UF', apiKey: 'uf' },
  { campo: 'telefone', label: 'Telefone', apiKey: 'telefone', formatar: (v) => formatPhone(v) },
  { campo: 'email', label: 'E-mail', apiKey: 'email' },
  { campo: 'cnae', label: 'CNAE', apiKey: 'cnae' },
  { campo: 'regime_tributario', label: 'Regime tributário', apiKey: 'regime_tributario' },
];

export const MAPEAMENTO_CNPJ_FORNECEDOR = MAPEAMENTO_CNPJ_CLIENTE;

export const MAPEAMENTO_CNPJ_TRANSPORTADORA: MapeamentoCampoCnpj<
  | 'razao_social'
  | 'nome_fantasia'
  | 'cep'
  | 'logradouro'
  | 'numero'
  | 'complemento'
  | 'bairro'
  | 'cidade'
  | 'uf'
  | 'telefone'
  | 'email'
  | 'cnae'
  | 'regime_tributario'
>[] = MAPEAMENTO_CNPJ_CLIENTE;

export const AVISO_IE_FONTE_ATUAL =
  'A fonte atual não retorna Inscrição Estadual para este CNPJ/UF.';

export function mensagemSucessoConsultaCnpj(dados: ConsultaCnpjResponse): string {
  const avisoIe = dados.aviso_ie?.trim() || AVISO_IE_FONTE_ATUAL;
  if (dados.inscricao_estadual_disponivel && dados.inscricao_estadual) {
    return `Dados cadastrais preenchidos. Inscrição Estadual sugerida: ${dados.inscricao_estadual}.`;
  }
  return `Dados cadastrais preenchidos (razão social, endereço e CNAE). ${avisoIe} Informe a IE manualmente.`;
}
