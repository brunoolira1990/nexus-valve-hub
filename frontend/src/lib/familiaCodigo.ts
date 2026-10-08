import type { FamiliaProduto } from '@/types';

/** Decisão de cadastro (não persistida no model). */
export type ModoCodigoFigura = 'AUTOMATICO' | 'MANUAL';

export const MODO_CODIGO_FIGURA_PADRAO: ModoCodigoFigura = 'AUTOMATICO';

/** Mensagem exibida no cadastro quando o código será gerado pelo backend. */
export const MENSAGEM_CODIGO_FIGURA_AUTO =
  'O código será gerado automaticamente ao salvar.';

export const MENSAGEM_CODIGO_FIGURA_MANUAL =
  'Informe o complemento no código somente quando o modelo de formação ' +
  'selecionado não o acrescentar automaticamente.';

export const MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO =
  'Informe o código da Família/Figura.';

export const MSG_DESCRICAO_BASE_OBRIGATORIA = 'Informe a descrição base.';

export const MSG_ALERTA_OD_REPETIDO_PELO_TEMPLATE =
  'Este código termina com OD e o modelo de formação selecionado também acrescenta OD ' +
  'ao gerar o código do produto. Considere usar apenas a base numérica (ex.: 6119).';

/** Regras alinhadas a `_prefixo_od` em montar_codigo_interno (backend). */
export const REGRAS_TEMPLATE_ACRESCENTAM_OD = [
  'BASE_OD_MM_ESPESSURA',
  'BASE_OD_POLEGADA_ESPESSURA',
] as const;

export function templateAcrescentaOd(tipoRegraCodigo: string | undefined | null): boolean {
  const t = (tipoRegraCodigo || '').trim();
  return (REGRAS_TEMPLATE_ACRESCENTAM_OD as readonly string[]).includes(t);
}

export function codigoFiguraTerminaComOd(codigo: string | undefined | null): boolean {
  return (codigo || '').trim().toUpperCase().endsWith('OD');
}

/**
 * Alerta contextual (não bloqueia salvar nem altera códigos existentes).
 * Dispara quando o manual termina com OD e o template também acrescenta OD.
 */
export function alertaCodigoManualRepeteComplementoTemplate(
  modo: ModoCodigoFigura,
  codigoFigura: string | undefined,
  tipoRegraCodigo: string | undefined,
): string | null {
  if (modo !== 'MANUAL') return null;
  if (!codigoFiguraTerminaComOd(codigoFigura)) return null;
  if (!templateAcrescentaOd(tipoRegraCodigo)) return null;
  return MSG_ALERTA_OD_REPETIDO_PELO_TEMPLATE;
}

export function familiaEmEdicao(editingFamilia: { id: number } | null): boolean {
  return editingFamilia != null;
}

export function campoCodigoFiguraVisivelNaCriacao(modo: ModoCodigoFigura): boolean {
  return modo === 'MANUAL';
}

/**
 * Monta o payload de criação/edição.
 *
 * Criação AUTOMATICO: envia modo_codigo e **não** envia codigo_figura.
 * Criação MANUAL: envia modo_codigo + codigo_figura.
 * Edição: inclui codigo_figura (backend ignora alteração).
 */
export function montarPayloadFamiliaSalvar(
  famQuick: Partial<FamiliaProduto> & { modo_codigo_figura?: ModoCodigoFigura },
  editingFamilia: FamiliaProduto | null,
  effSave: {
    usa_rosca_conexao: boolean;
    usa_schedule: boolean;
    usa_polegada_principal: boolean;
    usa_polegada_secundaria: boolean;
  },
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    descricao_base: (famQuick.descricao_base || '').trim(),
    categoria_produto: famQuick.categoria_produto,
    tipo_regra_codigo: famQuick.tipo_regra_codigo,
    tipo_dimensional: famQuick.tipo_dimensional || 'SIMPLES',
    separador_base_medidas: famQuick.separador_base_medidas,
    ativo: famQuick.ativo,
    usa_rosca_conexao: effSave.usa_rosca_conexao,
    usa_schedule: effSave.usa_schedule,
    usa_polegada_principal: effSave.usa_polegada_principal,
    usa_polegada_secundaria: effSave.usa_polegada_secundaria,
    ncm_padrao: famQuick.ncm_padrao,
    unidade_padrao: '',
    material_base: '',
    pressao_base: '',
    norma_base: '',
    usa_conversao_dimensional: famQuick.usa_conversao_dimensional,
    controla_composicao_fisica: famQuick.controla_composicao_fisica,
    tipo_composicao_fisica: famQuick.tipo_composicao_fisica || 'BARRA_M',
    tipo_fisico: famQuick.tipo_fisico || 'PECA',
    tipo_controle_unidade: famQuick.tipo_controle_unidade || 'PECA',
    unidade_estoque_padrao: famQuick.unidade_estoque_padrao || '',
    unidade_venda_padrao: famQuick.unidade_venda_padrao || '',
    unidade_compra_padrao: famQuick.unidade_compra_padrao || '',
    unidade_fiscal_padrao: famQuick.unidade_fiscal_padrao || '',
    unidades_venda_permitidas: famQuick.unidades_venda_permitidas || [],
    unidades_compra_permitidas: famQuick.unidades_compra_permitidas || [],
    comprimento_padrao_barra_m: famQuick.comprimento_padrao_barra_m,
    peso_por_metro_kg: famQuick.peso_por_metro_kg,
    peso_por_peca_kg: famQuick.peso_por_peca_kg,
    peso_por_chapa_kg: famQuick.peso_por_chapa_kg,
    densidade: famQuick.densidade,
    observacoes_conversao: famQuick.observacoes_conversao || '',
  };
  if (editingFamilia) {
    payload.codigo_figura = (famQuick.codigo_figura || '').trim();
    return payload;
  }

  const modo: ModoCodigoFigura = famQuick.modo_codigo_figura || MODO_CODIGO_FIGURA_PADRAO;
  payload.modo_codigo = modo;
  if (modo === 'MANUAL') {
    payload.codigo_figura = (famQuick.codigo_figura || '').trim();
  }
  // AUTOMATICO: nunca incluir codigo_figura (nem vazio / null / undefined).
  return payload;
}

/** Utilitário de teste / guard — true só se a chave existir no payload. */
export function payloadIncluiCodigoFigura(payload: Record<string, unknown>): boolean {
  return Object.prototype.hasOwnProperty.call(payload, 'codigo_figura');
}

/**
 * Limpa erro de código ao mudar para AUTOMATICO (UI deve espelhar isso).
 * Retorna null sempre — documento o contrato da alternância.
 */
export function erroCodigoAposAlternarModo(
  modoAnterior: ModoCodigoFigura,
  modoNovo: ModoCodigoFigura,
  erroAtual: string | null,
): string | null {
  if (modoNovo === 'AUTOMATICO') return null;
  if (modoAnterior === 'MANUAL' && modoNovo === 'MANUAL') return erroAtual;
  return null;
}

export function validarCodigoFiguraManualLocal(
  modo: ModoCodigoFigura,
  codigoFigura: string | undefined,
): string | null {
  if (modo !== 'MANUAL') return null;
  if (!(codigoFigura || '').trim()) return MSG_CODIGO_FIGURA_MANUAL_OBRIGATORIO;
  return null;
}

export function validarDescricaoBaseLocal(descricaoBase: string | undefined): string | null {
  if (!(descricaoBase || '').trim()) return MSG_DESCRICAO_BASE_OBRIGATORIA;
  return null;
}

/** Impede clique duplo / reentrada na mutation de create/update. */
export function podeIniciarSalvarFamilia(salvando: boolean): boolean {
  return !salvando;
}

/**
 * Após HTTP 400 de codigo_figura: só refetch da listagem em duplicidade.
 * Erros determinísticos (obrigatório / inválido) não devem disparar GET em loop.
 */
export function deveRecarregarFamiliasAposErroCodigoApi(mensagem: string): boolean {
  return /já existe/i.test(mensagem || '');
}

/** Chave mínima alinhada ao backend (trim, espaços, caixa). */
export function chaveDescricaoDuplicidadeFamilia(texto: string | undefined | null): string {
  return (texto || '').trim().replace(/\s+/g, ' ').toUpperCase();
}

export type FamiliaDuplicidadeResumo = {
  id: number;
  codigo_figura: string;
  descricao_base: string;
  tipo_regra_codigo?: string;
};

export type ClassificacaoDuplicidadeFamilia =
  | { tipo: 'nenhuma' }
  | {
      tipo: 'descricao_sem_modelo';
      existente: FamiliaDuplicidadeResumo;
      mensagem: string;
    }
  | {
      tipo: 'provavel_exata';
      existente: FamiliaDuplicidadeResumo;
      mensagem: string;
    }
  | {
      tipo: 'exata';
      existente: FamiliaDuplicidadeResumo;
      mensagem: string;
    }
  | {
      tipo: 'modelo_diferente';
      existente: FamiliaDuplicidadeResumo;
      mensagem: string;
    };

function resumoFamiliaDuplicidade(
  f: Pick<FamiliaProduto, 'id' | 'codigo_figura' | 'descricao_base' | 'tipo_regra_codigo'>,
): FamiliaDuplicidadeResumo {
  return {
    id: f.id,
    codigo_figura: f.codigo_figura,
    descricao_base: f.descricao_base,
    tipo_regra_codigo: f.tipo_regra_codigo || undefined,
  };
}

/**
 * Classifica duplicidade visual no formulário de família.
 *
 * - modeloConfirmado=false: não compara com o default do form (ex.: BASE_POLEGADA);
 *   usa a sugestão só para antecipar “provável duplicidade”.
 * - modeloConfirmado=true: compara com o modelo realmente aplicado/selecionado.
 */
export function classificarDuplicidadeDescricaoFamilia(opts: {
  descricaoBase: string | undefined;
  tipoRegraFormulario: string | undefined;
  tipoRegraSugerido: string | undefined;
  modeloConfirmado: boolean;
  familias: Array<Pick<FamiliaProduto, 'id' | 'codigo_figura' | 'descricao_base' | 'tipo_regra_codigo'>>;
  editingId: number | null;
}): ClassificacaoDuplicidadeFamilia {
  const chave = chaveDescricaoDuplicidadeFamilia(opts.descricaoBase);
  if (!chave) return { tipo: 'nenhuma' };

  const mesmasDesc = opts.familias.filter(
    (f) =>
      f.id !== opts.editingId &&
      chaveDescricaoDuplicidadeFamilia(f.descricao_base) === chave,
  );
  if (!mesmasDesc.length) return { tipo: 'nenhuma' };

  const tipoForm = (opts.tipoRegraFormulario || '').trim();
  const tipoSug = (opts.tipoRegraSugerido || '').trim();

  if (!opts.modeloConfirmado) {
    if (tipoSug) {
      const hitSug = mesmasDesc.find((f) => (f.tipo_regra_codigo || '').trim() === tipoSug);
      if (hitSug) {
        const existente = resumoFamiliaDuplicidade(hitSug);
        return {
          tipo: 'provavel_exata',
          existente,
          mensagem:
            `A sugestão automática corresponde ao modelo da Família/Figura ${existente.codigo_figura}` +
            `${existente.descricao_base ? ` — ${existente.descricao_base}` : ''}. ` +
            `Ao aplicar a sugestão, este cadastro será tratado como duplicidade.`,
        };
      }
    }
    const existente = resumoFamiliaDuplicidade(mesmasDesc[0]);
    return {
      tipo: 'descricao_sem_modelo',
      existente,
      mensagem:
        `Já existe a Família/Figura ${existente.codigo_figura} com esta descrição. ` +
        `Selecione ou aplique o modelo de formação para confirmar se é o mesmo cadastro.`,
    };
  }

  if (!tipoForm) {
    const existente = resumoFamiliaDuplicidade(mesmasDesc[0]);
    return {
      tipo: 'descricao_sem_modelo',
      existente,
      mensagem:
        `Já existe a Família/Figura ${existente.codigo_figura} com esta descrição. ` +
        `Selecione ou aplique o modelo de formação para confirmar se é o mesmo cadastro.`,
    };
  }

  const hitIgual = mesmasDesc.find((f) => (f.tipo_regra_codigo || '').trim() === tipoForm);
  if (hitIgual) {
    const existente = resumoFamiliaDuplicidade(hitIgual);
    return {
      tipo: 'exata',
      existente,
      mensagem:
        `Já existe a Família/Figura ${existente.codigo_figura}` +
        `${existente.descricao_base ? ` — ${existente.descricao_base}` : ''} ` +
        `com o mesmo modelo de formação.`,
    };
  }

  const hitDif = mesmasDesc[0];
  const existente = resumoFamiliaDuplicidade(hitDif);
  return {
    tipo: 'modelo_diferente',
    existente,
    mensagem:
      'Já existe uma família com esta descrição, mas com outro modelo de formação. ' +
      'Confirme se deseja cadastrar uma variação técnica distinta.',
  };
}

/** @deprecated Preferir `classificarDuplicidadeDescricaoFamilia`. */
export function avisoMesmaDescricaoModeloDiferente(
  descricaoBase: string | undefined,
  tipoRegraCodigo: string | undefined,
  familias: Array<Pick<FamiliaProduto, 'id' | 'codigo_figura' | 'descricao_base' | 'tipo_regra_codigo'>>,
  editingId: number | null,
): string | null {
  const c = classificarDuplicidadeDescricaoFamilia({
    descricaoBase,
    tipoRegraFormulario: tipoRegraCodigo,
    tipoRegraSugerido: undefined,
    modeloConfirmado: !!(tipoRegraCodigo || '').trim(),
    familias,
    editingId,
  });
  return c.tipo === 'modelo_diferente' ? c.mensagem : null;
}

export function extrairDuplicidadeDescricaoModeloApi(
  data: Record<string, unknown> | undefined | null,
): { mensagem: string; existente: FamiliaDuplicidadeResumo | null } | null {
  if (!data || typeof data !== 'object') return null;
  const unwrap = (v: unknown): string => {
    if (Array.isArray(v)) return String(v[0] ?? '');
    if (v == null) return '';
    return String(v);
  };
  const msg = unwrap(data.descricao_base);
  const idRaw = unwrap(data.familia_existente_id);
  const codigo = unwrap(data.familia_existente_codigo);
  if (!msg && !idRaw && !codigo) return null;
  if (!/mesmo modelo de formação|família\/figura/i.test(msg) && !idRaw && !codigo) {
    return null;
  }
  const idNum = Number(idRaw);
  const existente =
    Number.isFinite(idNum) && idNum > 0
      ? {
          id: idNum,
          codigo_figura: codigo,
          descricao_base: unwrap(data.familia_existente_descricao),
          tipo_regra_codigo: unwrap(data.familia_existente_tipo_regra_codigo) || undefined,
        }
      : codigo
        ? {
            id: 0,
            codigo_figura: codigo,
            descricao_base: unwrap(data.familia_existente_descricao),
          }
        : null;
  return { mensagem: msg || 'Já existe uma Família/Figura com a mesma descrição e modelo.', existente };
}
