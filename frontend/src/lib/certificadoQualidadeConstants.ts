/**
 * Constantes e helpers compartilhados do Certificado de Qualidade (CQ).
 *
 * Extraido de pages/Certificados.tsx para permitir reuso no Workspace
 * dedicado (pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx).
 */

import type {
  CertificadoQualidade,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoQualidade,
} from '@/types';

export const TEXTO_PADRAO =
  'Os certificados originais encontram-se em nosso poder, à sua disposição, certificamos que o(s) produto(s) supra está(ão) aprovado(s), de acordo com as especificações acima mencionadas. Documento impresso eletronicamente, dispensa assinatura.';

export const COMPOSICAO_FIELDS = [
  'C', 'Mn', 'P', 'S', 'Si', 'Ni', 'Cr', 'Mo', 'Cu', 'V', 'Nb', 'Al', 'Ti', 'N', 'Zn', 'Fe', 'Sn', 'Pb', 'Ca', 'Ta', 'W', 'Li', 'Co',
] as const;

export const TRACAO_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'limite_escoamento', label: 'Limite de escoamento / Flow Limit (MPa)' },
  { key: 'limite_resistencia', label: 'Limite de resistência / Resistance Limit (MPa)' },
  { key: 'alongamento', label: 'Alongamento / Stretching (%)' },
  { key: 'estriccao', label: 'Estricção / Strictness (%)' },
  { key: 'dureza', label: 'Dureza' },
  { key: 'tratamento_termico', label: 'Tratamento térmico / Heat Treatment' },
];

export const IMPACTO_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'norma', label: 'Norma / Standard' },
  { key: 'corpo_prova', label: 'Corpo de prova / Specimen' },
  { key: 'direcao', label: 'Direção corpo / Specimen Direction' },
  { key: 'posicao', label: 'Posição corpo / Specimen Position' },
  { key: 'temperatura', label: 'Temperatura / Temperature' },
  { key: 'corpo_prova_a', label: 'Corpo de prova A / Specimen A' },
  { key: 'corpo_prova_b', label: 'Corpo de prova B / Specimen B' },
  { key: 'corpo_prova_c', label: 'Corpo de prova C / Specimen C' },
  { key: 'media', label: 'Média / Average' },
];

export const COMPONENTES_PADRAO = [
  'Corpo', 'Tampa/Castelo', 'Esfera', 'Haste', 'Porca', 'Prisioneiro', 'Sede/Vedação',
];

export const MOTIVOS_NAO_INCLUSAO = [
  'Cliente não solicitou certificado',
  'Item sem certificado fornecedor',
  'Item comercial/acessório',
  'Certificado será enviado separado',
  'Outro',
] as const;

export const CONFIRMAR_CANCELAMENTO_CERTIFICADO_QUALIDADE =
  'Cancelar este certificado de qualidade?\n\n'
  + 'O registro permanece no sistema para rastreabilidade. O PDF passará a exibir a marca CANCELADO e não deve ser usado como documento válido.\n\n'
  + 'Deseja continuar?';

export const AVISO_SEM_CF_MANUAL =
  'Sem Certificado do Fornecedor vinculado. Os dados técnicos deste CQ foram informados manualmente.';

export const LABEL_OBRIGATORIO_EMITIR = ' *';

export const emptyForm = (): Omit<CertificadoQualidade, 'id' | 'criado_em' | 'atualizado_em' | 'numero_formatado'> => ({
  numero: '',
  serie: '',
  cliente: null,
  cliente_nome_snapshot: '',
  cliente_cnpj_snapshot: '',
  pedido_cliente: '',
  nota_fiscal_numero: '',
  nota_fiscal: null,
  nota_fiscal_historica: null,
  data_emissao: '',
  observacoes: '',
  texto_padrao: TEXTO_PADRAO,
  status: 'rascunho',
  tipo_certificado: 'PADRAO_POR_NFE',
  itens: [],
});

export const ensureMap = (v: unknown): Record<string, string> => {
  if (!v || typeof v !== 'object') return {};
  return Object.entries(v as Record<string, unknown>).reduce<Record<string, string>>((acc, [k, val]) => {
    acc[k] = val == null ? '' : String(val);
    return acc;
  }, {});
};

/** Trim, colapsa espacos e maiusculas - alinhado ao criterio de busca no certificado fornecedor. */
export const normalizeCorridaLoteBusca = (raw: string) => raw.trim().replace(/\s+/g, ' ').toUpperCase();

/** FK `produto` pode vir como numero ou (em edge cases) objeto serializado. */
export const coerceProdutoItemId = (produto: ItemCertificadoQualidade['produto']): number | null => {
  if (produto == null || produto === '') return null;
  if (typeof produto === 'object' && produto !== null && 'id' in produto) {
    const id = Number((produto as { id: unknown }).id);
    return Number.isFinite(id) && id > 0 ? id : null;
  }
  const n = Number(produto);
  return Number.isFinite(n) && n > 0 ? n : null;
};

/** Corrida/lote efetivos do CQ (campo manual + snapshots de rastreio); em valvula, complementa pelos componentes. */
export const resolverCorridaLoteBuscaFornecedor = (item: ItemCertificadoQualidade) => {
  const corridaBruta = String(item.corrida || item.corrida_snapshot || '').trim();
  const loteBruto = String(item.lote || item.lote_snapshot || '').trim();
  let corrida = normalizeCorridaLoteBusca(corridaBruta);
  let lote = normalizeCorridaLoteBusca(loteBruto);
  if ((item.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES') {
    for (const comp of item.componentes || []) {
      if (!corrida) corrida = normalizeCorridaLoteBusca(String(comp.corrida || '').trim());
      if (!lote) lote = normalizeCorridaLoteBusca(String(comp.lote || '').trim());
      if (corrida && lote) break;
    }
  }
  return { corrida, lote };
};

export const itemTemDadosTecnicosPreenchidos = (item: ItemCertificadoQualidade): boolean => {
  if ((item.norma || '').trim()) return true;
  if (Object.values(ensureMap(item.composicao_json)).some((v) => String(v || '').trim())) return true;
  if (Object.values(ensureMap(item.ensaio_tracao_json)).some((v) => String(v || '').trim())) return true;
  if (Object.values(ensureMap(item.ensaio_impacto_json)).some((v) => String(v || '').trim())) return true;
  if (item.certificado_fornecedor_origem_id) return true;
  return false;
};

export const fornecedorResultadoSemProdutoVinculado = (src: DadosTecnicosFornecedorResultado) =>
  src.produto_match_tipo === 'sem_vinculo';

export const normNumeric = (v: string) => v.replace(',', '.');

export const parseBlockValues = (raw: string): string[] => {
  const line = (raw || '').trim();
  if (!line) return [];
  if (line.includes('\t')) return line.split('\t').map((x) => x.trim());
  if (line.includes(';')) return line.split(';').map((x) => x.trim());
  if (line.includes('|')) return line.split('|').map((x) => x.trim());
  return line.split(/\s+/).map((x) => x.trim());
};

export const ensureComp = (raw: unknown, ordem = 1) => {
  const obj = (raw && typeof raw === 'object') ? (raw as Record<string, unknown>) : {};
  return {
    ordem: Number(obj.ordem || ordem),
    nome_componente: String(obj.nome_componente || ''),
    descricao_componente: String(obj.descricao_componente || ''),
    norma: String(obj.norma || ''),
    corrida: String(obj.corrida || ''),
    lote: String(obj.lote || ''),
    revisao_corrida: String(obj.revisao_corrida || ''),
    numero_certificado_fornecedor_componente: String(obj.numero_certificado_fornecedor_componente || ''),
    quantidade: obj.quantidade == null || obj.quantidade === '' ? null : Number(obj.quantidade),
    composicao_json: ensureMap(obj.composicao_json),
    ensaio_tracao_json: ensureMap(obj.ensaio_tracao_json),
    ensaio_impacto_json: ensureMap(obj.ensaio_impacto_json),
    observacoes: String(obj.observacoes || ''),
    ativo: obj.ativo !== false,
  };
};
