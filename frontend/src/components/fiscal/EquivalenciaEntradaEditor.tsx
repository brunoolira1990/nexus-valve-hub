import type { EquivalenciaEntradaConferencia } from '@/types';
import { mapItemPayloadCorrida } from '@/components/fiscal/CorridaSplitEditor';

export type FatoresEquivalenciaEntrada = {
  pesoPorMetroKg: number | null;
  comprimentoPadraoBarraM: number | null;
};

export type EquivalenciaEntradaEditorProps = {
  qtyAlvo: number;
  unidadeAlvo: string;
  colunaAlvo: 'metros' | 'barras' | 'peso_kg';
  equivalencias: EquivalenciaEntradaConferencia[];
  fatores: FatoresEquivalenciaEntrada;
  onChange: (equivalencias: EquivalenciaEntradaConferencia[]) => void;
  disabled?: boolean;
};

function parseQty(value: string | undefined | null): number {
  if (value == null || value === '') return 0;
  const n = Number(String(value).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

function formatQty(n: number, decimals = 3): string {
  return n.toFixed(decimals);
}

function campoVazio(value: string | undefined | null): boolean {
  return value == null || String(value).trim() === '';
}

function sugerirCamposVazios(
  row: EquivalenciaEntradaConferencia,
  campoEditado: 'metros' | 'barras' | 'peso_kg',
  fatores: FatoresEquivalenciaEntrada,
): Partial<EquivalenciaEntradaConferencia> {
  const patch: Partial<EquivalenciaEntradaConferencia> = {};
  const metros = parseQty(row.metros);
  const barras = parseQty(row.barras);
  const peso = parseQty(row.peso_kg);
  const ppm = fatores.pesoPorMetroKg;
  const compBarra = fatores.comprimentoPadraoBarraM;

  if (campoEditado === 'peso_kg' && peso > 0) {
    if (campoVazio(row.metros) && ppm) {
      patch.metros = formatQty(peso / ppm);
    }
    const metrosRef = patch.metros ? parseQty(patch.metros) : metros;
    if (campoVazio(row.barras) && compBarra && metrosRef > 0) {
      patch.barras = formatQty(metrosRef / compBarra);
    }
  }

  if (campoEditado === 'metros' && metros > 0) {
    if (campoVazio(row.peso_kg) && ppm) {
      patch.peso_kg = formatQty(metros * ppm);
    }
    if (campoVazio(row.barras) && compBarra) {
      patch.barras = formatQty(metros / compBarra);
    }
  }

  if (campoEditado === 'barras' && barras > 0) {
    if (campoVazio(row.metros) && compBarra) {
      patch.metros = formatQty(barras * compBarra);
    }
    const metrosRef = patch.metros ? parseQty(patch.metros) : metros;
    if (campoVazio(row.peso_kg) && ppm && metrosRef > 0) {
      patch.peso_kg = formatQty(metrosRef * ppm);
    }
  }

  if (ppm && (patch.peso_kg || campoEditado === 'peso_kg' || patch.metros || campoEditado === 'metros')) {
    patch.peso_por_metro_utilizado = formatQty(ppm, 6);
  }

  return patch;
}

function labelUnidadeNf(unidadeNf: string): string {
  const u = (unidadeNf || '').trim().toUpperCase();
  if (u === 'M') return 'metros';
  if (u === 'BR') return 'barras';
  if (u === 'KG' || u === 'TON') return 'peso (kg)';
  return u || 'unidade NF';
}

/** Metros equivalentes a partir do campo preenchido na sub-linha (M, BR ou kg). */
function metrosEfetivosSubLinha(
  row: EquivalenciaEntradaConferencia,
  fatores: FatoresEquivalenciaEntrada,
): number | null {
  const metros = parseQty(row.metros);
  const barras = parseQty(row.barras);
  const peso = parseQty(row.peso_kg);
  const ppm = fatores.pesoPorMetroKg;
  const comp = fatores.comprimentoPadraoBarraM;
  if (metros > 0) return metros;
  if (barras > 0 && comp) return barras * comp;
  if (peso > 0 && ppm) return peso / ppm;
  return null;
}

/** Converte sub-linha para a unidade da NF (mesma regra do backend). */
export function valorSubLinhaNaUnidadeNf(
  row: EquivalenciaEntradaConferencia,
  unidadeNf: string,
  fatores: FatoresEquivalenciaEntrada,
): number | null {
  const metrosEfetivos = metrosEfetivosSubLinha(row, fatores);
  const u = (unidadeNf || '').trim().toUpperCase();
  const ppm = fatores.pesoPorMetroKg;
  const comp = fatores.comprimentoPadraoBarraM;
  if (metrosEfetivos != null) {
    if (u === 'M') return metrosEfetivos;
    if (u === 'BR' && comp) return metrosEfetivos / comp;
    if ((u === 'KG' || u === 'TON') && ppm) return metrosEfetivos * ppm;
  }
  const col = colunaAlvoEquivalenciaNf(unidadeNf);
  const direto = parseQty(row[col]);
  return direto > 0 ? direto : null;
}

export function totalEquivalenciaNaUnidadeNf(
  equivalencias: EquivalenciaEntradaConferencia[],
  unidadeNf: string,
  fatores: FatoresEquivalenciaEntrada,
): number {
  return equivalencias.reduce((acc, row) => acc + (valorSubLinhaNaUnidadeNf(row, unidadeNf, fatores) ?? 0), 0);
}

export function EquivalenciaEntradaEditor({
  qtyAlvo,
  unidadeAlvo,
  colunaAlvo,
  equivalencias,
  fatores,
  onChange,
  disabled = false,
}: EquivalenciaEntradaEditorProps) {
  const totalAlocado = totalEquivalenciaNaUnidadeNf(equivalencias, unidadeAlvo, fatores);
  const diff = Math.round((totalAlocado - qtyAlvo) * 1000) / 1000;
  const somaOk = Math.abs(diff) < 0.001;

  const updateRow = (index: number, patch: Partial<EquivalenciaEntradaConferencia>) => {
    const next = equivalencias.map((row, i) => (i === index ? { ...row, ...patch } : row));
    onChange(next);
  };

  const handleBlurCampo = (
    index: number,
    campo: 'metros' | 'barras' | 'peso_kg',
    value: string,
  ) => {
    const row = equivalencias[index];
    const atualizado = { ...row, [campo]: value };
    const sugestoes = sugerirCamposVazios(atualizado, campo, fatores);
    updateRow(index, { [campo]: value, ...sugestoes });
  };

  const removeRow = (index: number) => {
    const next = equivalencias
      .filter((_, i) => i !== index)
      .map((row, i) => ({ ...row, ordem: i + 1 }));
    onChange(next);
  };

  const addRow = () => {
    const restante = Math.max(0, Math.round((qtyAlvo - totalAlocado) * 1000) / 1000);
    const nova: EquivalenciaEntradaConferencia = {
      ordem: equivalencias.length + 1,
      metros: colunaAlvo === 'metros' ? formatQty(restante > 0 ? restante : 0) : '',
      barras: colunaAlvo === 'barras' ? formatQty(restante > 0 ? restante : 0) : '',
      peso_kg: colunaAlvo === 'peso_kg' ? formatQty(restante > 0 ? restante : 0) : '',
      peso_por_metro_utilizado: '',
    };
    onChange([...equivalencias, nova]);
  };

  return (
    <div className="space-y-2 min-w-[16rem]">
      <div
        className={`text-[11px] rounded px-2 py-1 border ${
          somaOk
            ? 'text-green-800 bg-green-50 border-green-200'
            : 'text-red-800 bg-red-50 border-red-200'
        }`}
      >
        Total {labelUnidadeNf(unidadeAlvo)}: {formatQty(totalAlocado)} / {formatQty(qtyAlvo)} {unidadeAlvo}
        {!somaOk ? ` (diferença ${diff > 0 ? '+' : ''}${formatQty(diff)})` : ''}
      </div>
      <div className="space-y-1">
        {equivalencias.map((row, idx) => (
          <div
            key={`equiv-${row.ordem}-${idx}`}
            className="grid grid-cols-[4rem_4rem_4.5rem_auto] gap-1 items-center"
          >
            <input
              className="erp-input h-8 text-xs"
              placeholder="M"
              title="Metros"
              value={row.metros ?? ''}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { metros: e.target.value })}
              onBlur={(e) => handleBlurCampo(idx, 'metros', e.target.value)}
            />
            <input
              className="erp-input h-8 text-xs"
              placeholder="BR"
              title="Barras"
              value={row.barras ?? ''}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { barras: e.target.value })}
              onBlur={(e) => handleBlurCampo(idx, 'barras', e.target.value)}
            />
            <input
              className="erp-input h-8 text-xs"
              placeholder="kg"
              title="Peso (kg)"
              value={row.peso_kg ?? ''}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { peso_kg: e.target.value })}
              onBlur={(e) => handleBlurCampo(idx, 'peso_kg', e.target.value)}
            />
            <button
              type="button"
              className="erp-btn-outline h-8 px-2 text-xs"
              disabled={disabled || equivalencias.length <= 1}
              onClick={() => removeRow(idx)}
              title="Remover sub-linha"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      {!disabled ? (
        <button type="button" className="text-xs text-primary hover:underline" onClick={addRow}>
          + Adicionar peça/barra
        </button>
      ) : null}
    </div>
  );
}

export function colunaAlvoEquivalenciaNf(unidadeNf: string): 'metros' | 'barras' | 'peso_kg' {
  const u = (unidadeNf || '').trim().toUpperCase();
  if (u === 'BR') return 'barras';
  if (u === 'KG' || u === 'TON') return 'peso_kg';
  return 'metros';
}

export function itemUsaEquivalenciaEntrada(it: ItemConferenciaNFeEntradaLike): boolean {
  return Boolean(it.equivalencias && it.equivalencias.length > 0);
}

type ItemConferenciaNFeEntradaLike = {
  equivalencias?: EquivalenciaEntradaConferencia[];
};

export function criarEquivalenciasIniciais(
  qtyAlvo: number,
  colunaAlvo: 'metros' | 'barras' | 'peso_kg',
): EquivalenciaEntradaConferencia[] {
  const half = Math.floor((qtyAlvo * 1000) / 2) / 1000;
  const rest = Math.round((qtyAlvo - half) * 1000) / 1000;
  const mk = (q: number, ordem: number): EquivalenciaEntradaConferencia => ({
    ordem,
    metros: colunaAlvo === 'metros' ? formatQty(q) : '',
    barras: colunaAlvo === 'barras' ? formatQty(q) : '',
    peso_kg: colunaAlvo === 'peso_kg' ? formatQty(q) : '',
    peso_por_metro_utilizado: '',
  });
  return [mk(half, 1), mk(rest, 2)];
}

export function fatoresEquivalenciaDoProduto(produto?: {
  peso_por_metro_kg_efetivo?: number | null;
  peso_por_metro_kg?: number | null;
  comprimento_padrao_barra_m_efetivo?: number | null;
  comprimento_padrao_barra_m?: number | null;
} | null): FatoresEquivalenciaEntrada {
  if (!produto) {
    return { pesoPorMetroKg: null, comprimentoPadraoBarraM: null };
  }
  const ppm = produto.peso_por_metro_kg_efetivo ?? produto.peso_por_metro_kg ?? null;
  const comp = produto.comprimento_padrao_barra_m_efetivo ?? produto.comprimento_padrao_barra_m ?? null;
  return {
    pesoPorMetroKg: ppm != null ? Number(ppm) : null,
    comprimentoPadraoBarraM: comp != null ? Number(comp) : null,
  };
}

export function mapItemPayloadEquivalencia(
  it: ItemConferenciaNFeEntradaLike & {
    id: number;
    produto_id?: number | null;
    item_pedido_compra_id?: number | null;
    corrida?: string;
    lote?: string;
    corridas_split?: unknown[];
    status: string;
    motivo_ignorado?: string;
    observacao?: string;
  },
) {
  const base = {
    id: it.id,
    produto_id: it.produto_id ?? null,
    item_pedido_compra_id: it.item_pedido_compra_id ?? null,
    status: it.status,
    motivo_ignorado: it.motivo_ignorado ?? '',
    observacao: it.observacao ?? '',
    corrida: it.corrida ?? '',
    lote: it.lote ?? '',
    corridas_split: it.corridas_split ?? [],
  };
  if (itemUsaEquivalenciaEntrada(it)) {
    return {
      ...base,
      equivalencias: (it.equivalencias || []).map((row, idx) => ({
        ordem: row.ordem || idx + 1,
        metros: row.metros ?? '',
        barras: row.barras ?? '',
        peso_kg: row.peso_kg ?? '',
        peso_por_metro_utilizado: row.peso_por_metro_utilizado ?? '',
      })),
    };
  }
  return {
    ...base,
    equivalencias: [],
  };
}

export function mapItemPayloadConferencia(
  it: Parameters<typeof mapItemPayloadEquivalencia>[0] & Parameters<typeof mapItemPayloadCorrida>[0],
) {
  return mapItemPayloadEquivalencia(mapItemPayloadCorrida(it));
}
