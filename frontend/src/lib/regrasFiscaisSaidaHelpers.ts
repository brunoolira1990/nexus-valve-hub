import type {
  ConfiguracaoMatrizFiscalSaida,
  DestinatarioContribuinteSaida,
  RegraFiscalSaida,
  StatusConfiguracaoFiscalSaida,
} from '@/types';
import { labelCfopCatalogo } from '@/lib/catalogosFiscais';

export {
  REFORMA_TRIBUTARIA_KEYS,
  decFieldToForm,
  emptyReformaTributaria,
  reformaFromApi,
  reformaToApi,
  toApiDecimal,
  type ReformaTributariaForm,
} from '@/lib/regrasFiscaisEntradaHelpers';

export const AVISO_CENARIO_SAIDA_CADASTRAL =
  'Nesta fase, o cenário fiscal de saída é cadastral. Propostas continuam usando as regras fiscais atuais até a migração do motor. Use o comparativo em propostas (botão “Comparar fiscal”) para homologar o cenário novo. Após validar a cobertura, ative o cenário em propostas específicas antes de ligar a flag global.';

export const DESTINATARIO_OPCOES: { value: DestinatarioContribuinteSaida; label: string }[] = [
  { value: 'QUALQUER', label: 'Qualquer destinatário' },
  { value: 'CONTRIBUINTE', label: 'Contribuinte' },
  { value: 'NAO_CONTRIBUINTE', label: 'Não contribuinte' },
];

export const TIPOS_OP_SAIDA: { value: RegraFiscalSaida['tipo_operacao']; label: string }[] = [
  { value: '', label: '— Qualquer —' },
  { value: 'VENDA', label: 'Venda' },
  { value: 'DEVOLUCAO', label: 'Devolução' },
  { value: 'REMESSA', label: 'Remessa' },
  { value: 'BONIFICACAO', label: 'Bonificação' },
  { value: 'INDUSTRIALIZACAO', label: 'Industrialização' },
  { value: 'OUTROS', label: 'Outros' },
];

export function labelDestinatario(v: string): string {
  return DESTINATARIO_OPCOES.find((o) => o.value === v)?.label || v || '—';
}

export function labelStatusConfiguracaoSaida(status: StatusConfiguracaoFiscalSaida): string {
  switch (status) {
    case 'CONFIGURADO':
      return 'Configurado';
    case 'INCOMPLETO':
      return 'Incompleto';
    case 'SEM_CONFIGURACAO':
      return 'Não configurado';
    default:
      return status;
  }
}

export function badgeClassStatusConfiguracaoSaida(status: StatusConfiguracaoFiscalSaida): string {
  switch (status) {
    case 'CONFIGURADO':
      return 'erp-badge-info text-[10px]';
    case 'INCOMPLETO':
      return 'erp-badge-warning text-[10px]';
    default:
      return 'erp-badge-secondary text-[10px]';
  }
}

export function resumoEfeitosMatrizSaida(cfg: ConfiguracaoMatrizFiscalSaida): string {
  const partes: string[] = [];
  partes.push(cfg.efeitos.movimenta_estoque ? 'Mov. estoque' : 'Sem mov. estoque');
  partes.push(cfg.efeitos.gera_financeiro ? 'Gera financeiro' : 'Sem financeiro');
  return partes.join(' · ');
}

export function tituloCfopSaida(codigo: string): string {
  const c = (codigo || '').replace(/\D/g, '').slice(0, 4);
  if (!c) return '';
  const lbl = labelCfopCatalogo(c);
  return lbl.startsWith('Valor atual:') ? lbl : lbl || c;
}

export function boolTriFromApi(v: boolean | null | undefined): '' | 'sim' | 'nao' {
  if (v === true) return 'sim';
  if (v === false) return 'nao';
  return '';
}

export function boolTriToApi(v: '' | 'sim' | 'nao'): boolean | null {
  if (v === 'sim') return true;
  if (v === 'nao') return false;
  return null;
}

export function consumidorFinalFromApi(v: boolean | null | undefined): '' | 'sim' | 'nao' {
  return boolTriFromApi(v);
}

export function consumidorFinalToApi(v: '' | 'sim' | 'nao'): boolean | null {
  return boolTriToApi(v);
}
