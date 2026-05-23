import { formatCnpjDisplay } from '@/lib/cnpj';
import type { Transportadora } from '@/types';
import type { ValidacaoNFeSaidaItem, ValidacaoNFeSaidaResponse } from '@/services/api/fiscal';

export const MODALIDADE_FRETE_OPCOES: { value: string; label: string }[] = [
  { value: '0', label: '0 — Contratação por conta do remetente (CIF)' },
  { value: '1', label: '1 — Contratação por conta do destinatário (FOB)' },
  { value: '2', label: '2 — Contratação por conta de terceiros' },
  { value: '3', label: '3 — Transporte próprio por conta do remetente' },
  { value: '4', label: '4 — Transporte próprio por conta do destinatário' },
  { value: '9', label: '9 — Sem ocorrência de transporte' },
];

export function labelModalidadeFrete(mod: string | undefined): string {
  const m = (mod ?? '9').trim();
  return MODALIDADE_FRETE_OPCOES.find((o) => o.value === m)?.label ?? `Modalidade ${m}`;
}

export function labelTransportadoraSelecionada(t: Transportadora | null | undefined): string {
  if (!t) return '';
  const nome = (t.razao_social || '').trim().toUpperCase();
  const doc = (t.cnpj || '').trim();
  if (!doc) return nome;
  return `${nome} · ${formatCnpjDisplay(doc)}`;
}

export function transportadoraStub(
  id: number,
  razao_social: string,
  cnpj = '',
): Transportadora {
  return {
    id,
    razao_social,
    nome_fantasia: '',
    cnpj,
    ie: '',
    inscricao_municipal: '',
    logradouro: '',
    numero: '',
    complemento: '',
    bairro: '',
    cidade: '',
    uf: '',
    cep: '',
    telefone: '',
    celular: '',
    email: '',
    contato: '',
    placa_padrao: '',
    uf_placa: '',
    valor_km: 0,
    ativo: true,
    observacoes: '',
    ddd: '',
    suframa: '',
    email_nf: '',
    banco: '',
    agencia: '',
    conta: '',
    tipo_conta: '',
    cnae: '',
    regime_tributario: '',
    integracao_texto: '',
  };
}

export function alertasTransporteLocal(opts: {
  modalidade_frete: string;
  transportadora_id: number | null | undefined;
  quantidade_volumes?: number;
  peso_bruto?: number;
  peso_liquido?: number;
}): string[] {
  const mod = (opts.modalidade_frete || '9').trim();
  const msgs: string[] = [];
  if (mod === '9') {
    msgs.push('Sem ocorrência de transporte — transportadora e frete são opcionais.');
    return msgs;
  }
  if (!opts.transportadora_id) {
    msgs.push('Modalidade com frete: informe a transportadora para conferência.');
  }
  if (!opts.quantidade_volumes && !opts.peso_bruto && !opts.peso_liquido) {
    msgs.push('Volumes ou pesos não informados — recomendado preencher para o DANFE.');
  }
  return msgs;
}

export type ValidacaoAgrupadaSeveridade = {
  pendencias: ValidacaoNFeSaidaItem[];
  alertas: ValidacaoNFeSaidaItem[];
  informacoes: ValidacaoNFeSaidaItem[];
};

export function agruparValidacaoPorSeveridade(
  v: ValidacaoNFeSaidaResponse | null | undefined,
): ValidacaoAgrupadaSeveridade {
  const out: ValidacaoAgrupadaSeveridade = { pendencias: [], alertas: [], informacoes: [] };
  if (!v) return out;
  const push = (lista: ValidacaoNFeSaidaItem[] | undefined) => {
    for (const item of lista || []) {
      const t = (item.tipo || '').toUpperCase();
      if (t === 'PENDENCIA') out.pendencias.push(item);
      else if (t === 'ALERTA') out.alertas.push(item);
      else out.informacoes.push(item);
    }
  };
  push(v.pendencias);
  push(v.alertas);
  if (v.grupos) {
    for (const lista of Object.values(v.grupos)) push(lista);
  }
  return out;
}

export function agruparValidacaoPorGrupo(
  itens: ValidacaoNFeSaidaItem[],
): Record<string, ValidacaoNFeSaidaItem[]> {
  const map: Record<string, ValidacaoNFeSaidaItem[]> = {};
  for (const item of itens) {
    const g = item.grupo || 'outros';
    if (!map[g]) map[g] = [];
    map[g].push(item);
  }
  return map;
}

export function diagnosticoReformaExibicao(diagnostico: string | undefined, status: string): string {
  const d = (diagnostico || '').trim();
  if (d) return d;
  const st = (status || '').toUpperCase();
  if (st === 'NAO_CONFIGURADA') return 'Reforma não configurada neste item.';
  return '';
}
