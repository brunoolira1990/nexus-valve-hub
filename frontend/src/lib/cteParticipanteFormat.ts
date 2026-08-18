import { formatCnpjDisplay, normalizeCnpj } from './cnpj';

export type ParticipanteCteCard = {
  papel: string;
  razaoSocial: string;
  documento: string;
  ie: string;
  municipioUf: string;
  endereco: string;
};

function normDigits(v: unknown): string {
  return String(v ?? '').replace(/\D/g, '');
}

function docLabel(json: Record<string, unknown>): string {
  const cnpj = normalizeCnpj(String(json.CNPJ ?? ''));
  if (cnpj.length === 14 && /^[0-9A-Z]{14}$/.test(cnpj)) return formatCnpjDisplay(cnpj);
  const cpf = normDigits(json.CPF);
  if (cpf.length === 11) return cpf.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4');
  return '—';
}

function enderecoResumo(json: Record<string, unknown>): string {
  const ender = (json.enderEmit || json.enderReme || json.enderDest || json.enderExped || json.enderReceb || json.enderToma) as Record<string, unknown> | undefined;
  if (!ender || typeof ender !== 'object') {
    const mun = String(json.xMun || json.xNome || '').trim();
    const uf = String(json.UF || '').trim();
    return mun && uf ? `${mun}/${uf}` : mun || uf || '—';
  }
  const log = [ender.xLgr, ender.nro, ender.xBairro].filter(Boolean).join(', ');
  const mun = [ender.xMun, ender.UF].filter(Boolean).join('/');
  return [log, mun].filter(Boolean).join(' — ') || '—';
}

function municipioUf(json: Record<string, unknown>): string {
  const ender = (json.enderEmit || json.enderReme || json.enderDest || json.enderExped || json.enderReceb || json.enderToma) as Record<string, unknown> | undefined;
  if (ender && typeof ender === 'object') {
    const mun = String(ender.xMun || '').trim();
    const uf = String(ender.UF || '').trim();
    if (mun || uf) return `${mun}${mun && uf ? '/' : ''}${uf}`;
  }
  const mun = String(json.xMun || '').trim();
  const uf = String(json.UF || '').trim();
  return mun || uf ? `${mun}${mun && uf ? '/' : ''}${uf}` : '—';
}

export function participanteFromJson(papel: string, json: Record<string, unknown> | undefined | null): ParticipanteCteCard | null {
  if (!json || typeof json !== 'object' || Object.keys(json).length === 0) return null;
  const razao = String(json.xNome || json.xFant || '').trim();
  if (!razao && !json.CNPJ && !json.CPF) return null;
  return {
    papel,
    razaoSocial: razao || '—',
    documento: docLabel(json),
    ie: String(json.IE || '—'),
    municipioUf: municipioUf(json),
    endereco: enderecoResumo(json),
  };
}

export function participantesCteFromDetalhe(detalhe: {
  emit_json?: Record<string, unknown>;
  tomador_json?: Record<string, unknown>;
  rem_json?: Record<string, unknown>;
  dest_json?: Record<string, unknown>;
  exped_json?: Record<string, unknown>;
  receb_json?: Record<string, unknown>;
  transportadora_nome?: string;
  empresa_tomadora_nome?: string;
  fornecedor_remetente_nome?: string;
}): ParticipanteCteCard[] {
  const cards: ParticipanteCteCard[] = [];
  const emit = participanteFromJson('Emitente / Transportadora', detalhe.emit_json);
  if (emit) {
    if (detalhe.transportadora_nome) emit.razaoSocial = detalhe.transportadora_nome;
    cards.push(emit);
  }
  const tom = participanteFromJson('Tomador', detalhe.tomador_json);
  if (tom) {
    if (detalhe.empresa_tomadora_nome) tom.razaoSocial = detalhe.empresa_tomadora_nome;
    cards.push(tom);
  }
  const rem = participanteFromJson('Remetente', detalhe.rem_json);
  if (rem) {
    if (detalhe.fornecedor_remetente_nome) rem.razaoSocial = detalhe.fornecedor_remetente_nome;
    cards.push(rem);
  }
  for (const [papel, json] of [
    ['Destinatário', detalhe.dest_json],
    ['Expedidor', detalhe.exped_json],
    ['Recebedor', detalhe.receb_json],
  ] as const) {
    const p = participanteFromJson(papel, json);
    if (p) cards.push(p);
  }
  return cards;
}

export function formatComponentesFrete(componentes: unknown): { nome: string; valor: string }[] {
  if (!Array.isArray(componentes)) return [];
  return componentes.map((c, i) => {
    if (typeof c === 'object' && c !== null) {
      const row = c as Record<string, unknown>;
      const nome = String(row.xNome || row.nome || row.descricao || `Componente ${i + 1}`);
      const valor = row.vComp ?? row.valor ?? row.vFrete ?? '0';
      return { nome, valor: String(valor) };
    }
    return { nome: `Componente ${i + 1}`, valor: String(c) };
  });
}
