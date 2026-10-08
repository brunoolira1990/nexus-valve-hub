/**
 * Normalização e texto de diagnóstico para importação XML de NF-e (saída / entrada histórica).
 */

/** Falha de importação XML retornada pela API (formato padronizado + campos legados). */
export type NFeXmlImportFalhaApi = {
  arquivo: string;
  chave?: string;
  chave_acesso?: string;
  tipo_documento?: string;
  tipo_erro?: string;
  erro?: string;
  detalhe?: string;
  acao_sugerida?: string;
  /** Legado / alias de `detalhe` */
  mensagem?: string;
};

export type NFeXmlImportFalhaRaw = Record<string, unknown>;

export type FalhaImportacaoXmlNormalizada = {
  arquivo: string;
  chave: string;
  tipoDocumento: string;
  tipoErro: string;
  erroCurto: string;
  mensagemCompleta: string;
  acaoSugerida: string;
  /** Objeto original da API (para JSON no diagnóstico) */
  raw: NFeXmlImportFalhaRaw;
};

function str(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

export function normalizarFalhaImportacaoXml(raw: unknown): FalhaImportacaoXmlNormalizada {
  const r = raw && typeof raw === 'object' ? (raw as NFeXmlImportFalhaRaw) : {};
  const arquivo = str(r.arquivo) || '—';
  const chave = str(r.chave) || str(r.chave_acesso);
  const tipoDocumento = (str(r.tipo_documento) || 'DESCONHECIDO').toUpperCase();
  const tipoErro =
    str(r.tipo_erro) ||
    (() => {
      const m = str(r.mensagem) + str(r.detalhe) + str(r.erro);
      if (/traceback|Exception|Error|IntegrityError/i.test(m)) return 'Gravação no banco';
      if (/XML inválido|corrompido|ParseError/i.test(m)) return 'Leitura XML';
      return 'Validação / regra';
    })();
  const detalhe = str(r.detalhe) || str(r.mensagem);
  const erroCurto = str(r.erro) || (detalhe.length > 200 ? `${detalhe.slice(0, 197)}…` : detalhe) || '—';
  const mensagemCompleta = detalhe || erroCurto;
  const acaoSugerida =
    str(r.acao_sugerida) ||
    'Verifique se o XML é uma NF-e completa (nfeProc/NFe) ou evento válido; confira cadastros de Empresa/Cliente e a fila de importação.';
  return {
    arquivo,
    chave,
    tipoDocumento,
    tipoErro,
    erroCurto,
    mensagemCompleta,
    acaoSugerida,
    raw: r,
  };
}

export type ResumoImportSaida = {
  resumo: {
    total_arquivos: number;
    importadas: number;
    importadas_com_advertencia?: number;
    ja_existiam?: number;
    duplicadas: number;
    eventos_aplicados: number;
    eventos_duplicados: number;
    eventos_pendentes?: number;
    erros: number;
    falhas?: number;
  };
  importadas: { arquivo: string; chave_acesso: string; numero: string; serie: string }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string }[];
  eventos_aplicados: { arquivo: string; chave_acesso: string; tipo_evento: string; protocolo_evento: string; origem?: string }[];
  eventos_duplicados: { arquivo: string; chave_acesso: string; tipo_evento: string; mensagem: string }[];
  eventos_pendentes?: Record<string, unknown>[];
  erros: unknown[];
};

export type ResumoImportEntrada = {
  resumo: { total_arquivos: number; importadas: number; duplicadas: number; erros: number };
  importadas: { arquivo: string; chave_acesso: string; numero: string; serie: string }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string }[];
  erros: unknown[];
};

export function montarTextoDiagnosticoNfeSaidaXml(result: ResumoImportSaida): string {
  const { resumo } = result;
  const linhas: string[] = [];
  linhas.push('=== Diagnóstico importação XML — NF-e Saída Histórica ===', '');
  linhas.push('--- Resumo ---');
  linhas.push(`Total de arquivos no lote: ${resumo.total_arquivos}`);
  linhas.push(`Importadas: ${resumo.importadas}`);
  linhas.push(`Importadas com advertência: ${resumo.importadas_com_advertencia ?? 0}`);
  linhas.push(`Já existiam (NF-e): ${resumo.ja_existiam ?? resumo.duplicadas}`);
  linhas.push(`Ignoradas / duplicadas (campo legado): ${resumo.duplicadas}`);
  linhas.push(`Eventos aplicados: ${resumo.eventos_aplicados}`);
  linhas.push(`Eventos duplicados: ${resumo.eventos_duplicados}`);
  linhas.push(`Eventos pendentes: ${resumo.eventos_pendentes ?? (result.eventos_pendentes?.length || 0)}`);
  linhas.push(`Falhas: ${resumo.falhas ?? resumo.erros}`, '');

  linhas.push('--- Arquivos importados com sucesso ---');
  if (!result.importadas.length) linhas.push('(nenhuma)');
  else result.importadas.forEach((i) => linhas.push(`• ${i.arquivo} | NF ${i.numero}/${i.serie} | chave ${i.chave_acesso}`));
  linhas.push('');

  linhas.push('--- Duplicadas (NF-e) ---');
  if (!result.duplicadas.length) linhas.push('(nenhuma)');
  else
    result.duplicadas.forEach((d) =>
      linhas.push(`• ${d.arquivo} | chave ${d.chave_acesso} | ${d.mensagem}`),
    );
  linhas.push('');

  linhas.push('--- Eventos aplicados ---');
  if (!result.eventos_aplicados.length) linhas.push('(nenhum)');
  else
    result.eventos_aplicados.forEach((e) =>
      linhas.push(`• ${e.arquivo} | ${e.tipo_evento} | chave ${e.chave_acesso} | prot ${e.protocolo_evento}`),
    );
  linhas.push('');

  linhas.push('--- Eventos duplicados ---');
  if (!result.eventos_duplicados.length) linhas.push('(nenhum)');
  else
    result.eventos_duplicados.forEach((e) =>
      linhas.push(`• ${e.arquivo} | ${e.tipo_evento} | chave ${e.chave_acesso} | ${e.mensagem}`),
    );
  linhas.push('');

  linhas.push('--- Eventos pendentes (aguardando NF-e na base) ---');
  const pends = result.eventos_pendentes ?? [];
  if (!pends.length) linhas.push('(nenhum)');
  else
    pends.forEach((p) => {
      const o = p as Record<string, unknown>;
      linhas.push(
        `• ${String(o.arquivo ?? o.nome_arquivo ?? '—')} | chave ${String(o.chave_nfe ?? '')} | tp ${String(o.tipo_evento ?? '')} | ${String(o.mensagem ?? '')}`,
      );
    });
  linhas.push('');

  linhas.push('--- Falhas (detalhe por arquivo) ---');
  if (!result.erros.length) linhas.push('(nenhuma)');
  else {
    result.erros.forEach((raw, idx) => {
      const f = normalizarFalhaImportacaoXml(raw);
      linhas.push(`[${idx + 1}] ${f.arquivo}`);
      linhas.push(`    Chave: ${f.chave || '—'}`);
      linhas.push(`    Tipo documento: ${f.tipoDocumento}`);
      linhas.push(`    Tipo de erro: ${f.tipoErro}`);
      linhas.push(`    Erro (resumo): ${f.erroCurto}`);
      linhas.push(`    Mensagem completa:`);
      f.mensagemCompleta.split('\n').forEach((ln) => linhas.push(`      ${ln}`));
      linhas.push(`    Ação sugerida: ${f.acaoSugerida}`);
      linhas.push('');
    });
  }

  linhas.push('--- Payload técnico (eventos pendentes do lote) ---');
  linhas.push(JSON.stringify(result.eventos_pendentes ?? [], null, 2));
  linhas.push('--- Payload técnico (falhas) ---');
  linhas.push(JSON.stringify(result.erros, null, 2));

  return linhas.join('\n');
}

export function montarTextoDiagnosticoNfeEntradaXml(result: ResumoImportEntrada): string {
  const { resumo } = result;
  const linhas: string[] = [];
  linhas.push('=== Diagnóstico importação XML — NF-e Entrada Histórica ===', '');
  linhas.push('--- Resumo ---');
  linhas.push(`Total de arquivos: ${resumo.total_arquivos}`);
  linhas.push(`Importadas: ${resumo.importadas}`);
  linhas.push(`Duplicadas: ${resumo.duplicadas}`);
  linhas.push(`Falhas: ${resumo.erros}`, '');

  linhas.push('--- Importadas ---');
  if (!result.importadas.length) linhas.push('(nenhuma)');
  else result.importadas.forEach((i) => linhas.push(`• ${i.arquivo} | NF ${i.numero}/${i.serie} | ${i.chave_acesso}`));
  linhas.push('');

  linhas.push('--- Duplicadas ---');
  if (!result.duplicadas.length) linhas.push('(nenhuma)');
  else result.duplicadas.forEach((d) => linhas.push(`• ${d.arquivo} | ${d.chave_acesso} | ${d.mensagem}`));
  linhas.push('');

  linhas.push('--- Falhas ---');
  if (!result.erros.length) linhas.push('(nenhuma)');
  else {
    result.erros.forEach((raw, idx) => {
      const f = normalizarFalhaImportacaoXml(raw);
      linhas.push(`[${idx + 1}] ${f.arquivo}`);
      linhas.push(`    Chave: ${f.chave || '—'}`);
      linhas.push(`    Tipo documento: ${f.tipoDocumento}`);
      linhas.push(`    Tipo de erro: ${f.tipoErro}`);
      linhas.push(`    Mensagem completa:`);
      f.mensagemCompleta.split('\n').forEach((ln) => linhas.push(`      ${ln}`));
      linhas.push(`    Ação sugerida: ${f.acaoSugerida}`);
      linhas.push('');
    });
  }
  linhas.push('--- Payload técnico (falhas) ---');
  linhas.push(JSON.stringify(result.erros, null, 2));
  return linhas.join('\n');
}

export async function copiarTextoParaAreaDeTransferencia(texto: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(texto);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = texto;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}
