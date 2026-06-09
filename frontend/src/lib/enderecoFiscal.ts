import type { ConsultaCepResponse } from '@/services/api/consulta';

export type EnderecoFiscalResumo = {
  consistente?: boolean;
  bloqueio_fiscal?: boolean;
  alertas?: string[];
  pendencias?: string[];
  uf_destino?: string;
  cidade_destino?: string;
};

export function normalizarLocalidade(val: string | undefined | null): string {
  return (val ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toUpperCase();
}

export function enderecoFiscalInconsistenteLocal(
  cidade: string | undefined,
  uf: string | undefined,
  cepData?: Pick<ConsultaCepResponse, 'cidade' | 'uf'> | null,
): boolean {
  if (!cepData) return false;
  const ufCad = (uf ?? '').trim().toUpperCase().slice(0, 2);
  const ufCep = (cepData.uf ?? '').trim().toUpperCase().slice(0, 2);
  const cidadeCad = normalizarLocalidade(cidade);
  const cidadeCep = normalizarLocalidade(cepData.cidade);
  if (ufCad && ufCep && ufCad !== ufCep) return true;
  if (cidadeCad && cidadeCep && cidadeCad !== cidadeCep) return true;
  return false;
}

export function mensagemEnderecoFiscalInconsistente(
  cidade: string | undefined,
  cep: string | undefined,
  uf: string | undefined,
  cepData?: Pick<ConsultaCepResponse, 'cidade' | 'uf'> | null,
): string {
  const ufCep = (cepData?.uf ?? '').trim().toUpperCase().slice(0, 2);
  if (ufCep && (uf ?? '').trim().toUpperCase().slice(0, 2) !== ufCep) {
    return `Endereço fiscal inconsistente para NF-e. CEP ${cep ?? '—'} / cidade ${cidade ?? '—'} não correspondem à UF ${uf ?? '—'} informada. UF do CEP: ${ufCep}. Revise CEP, cidade e UF.`;
  }
  return 'Endereço fiscal inconsistente para NF-e. Revise CEP, cidade e UF.';
}

export function enderecoFiscalBloqueado(resumo?: EnderecoFiscalResumo | null): boolean {
  if (!resumo) return false;
  return Boolean(resumo.bloqueio_fiscal || resumo.consistente === false);
}

export function mensagemEnderecoFiscalResumo(resumo?: EnderecoFiscalResumo | null): string {
  if (!resumo) return '';
  if (resumo.alertas?.length) return resumo.alertas[0]!;
  if (resumo.pendencias?.length) return resumo.pendencias[0]!;
  if (resumo.bloqueio_fiscal) {
    return 'Endereço fiscal inconsistente para NF-e. Revise CEP, cidade e UF.';
  }
  return '';
}

export type DiagnosticoFiscalPreview = {
  tipo?: string;
  pendencia?: string;
  detalhe?: string;
  informacao?: string;
};

export function mensagemPreviewSemRegra(
  preview: {
    contexto_fiscal?: { endereco_fiscal?: EnderecoFiscalResumo };
    diagnosticos?: DiagnosticoFiscalPreview[];
    alertas?: string[];
    resumo?: { itens_total?: number; itens_sem_regra?: number };
  } | null,
): string {
  if (!preview) return 'Carregando prévia…';
  const endereco = preview.contexto_fiscal?.endereco_fiscal;
  if (enderecoFiscalBloqueado(endereco)) {
    return mensagemEnderecoFiscalResumo(endereco) || preview.alertas?.[0] || 'Cliente com endereço fiscal inconsistente.';
  }
  const diag = preview.diagnosticos?.find((d) => d.tipo === 'REGRA_NAO_ENCONTRADA');
  if (diag?.detalhe) return diag.detalhe;
  const total = preview.resumo?.itens_total ?? 0;
  const semRegra = preview.resumo?.itens_sem_regra ?? 0;
  if (total > 0 && semRegra >= total) {
    return preview.alertas?.[0] || 'Não foi encontrada regra fiscal de saída para o contexto informado.';
  }
  return 'Nenhuma alteração fiscal ou texto fiscal encontrado com a regra atual.';
}
