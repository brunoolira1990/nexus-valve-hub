import type { CorridaSplitConferencia } from '@/types';

export type CorridaSplitEditorProps = {
  qtyAlvo: number;
  unidade: string;
  splits: CorridaSplitConferencia[];
  onChange: (splits: CorridaSplitConferencia[]) => void;
  disabled?: boolean;
};

function parseQty(value: string): number {
  const n = Number(String(value).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

function formatQty(n: number): string {
  return n.toFixed(3);
}

function halfSplit(qtyAlvo: number): [number, number] {
  const half = Math.floor((qtyAlvo * 1000) / 2) / 1000;
  const rest = Math.round((qtyAlvo - half) * 1000) / 1000;
  return [half, rest];
}

export function CorridaSplitEditor({
  qtyAlvo,
  unidade,
  splits,
  onChange,
  disabled = false,
}: CorridaSplitEditorProps) {
  const totalAlocado = splits.reduce((acc, row) => acc + parseQty(row.quantidade), 0);
  const diff = Math.round((totalAlocado - qtyAlvo) * 1000) / 1000;
  const somaOk = Math.abs(diff) < 0.001;

  const updateRow = (index: number, patch: Partial<CorridaSplitConferencia>) => {
    const next = splits.map((row, i) => (i === index ? { ...row, ...patch } : row));
    onChange(next);
  };

  const removeRow = (index: number) => {
    const next = splits
      .filter((_, i) => i !== index)
      .map((row, i) => ({ ...row, ordem: i + 1 }));
    onChange(next);
  };

  const addRow = () => {
    const restante = Math.max(0, Math.round((qtyAlvo - totalAlocado) * 1000) / 1000);
    onChange([
      ...splits,
      {
        ordem: splits.length + 1,
        corrida: '',
        lote: '',
        quantidade: formatQty(restante > 0 ? restante : 0),
      },
    ]);
  };

  return (
    <div className="space-y-2 min-w-[14rem]">
      <div
        className={`text-[11px] rounded px-2 py-1 border ${
          somaOk
            ? 'text-green-800 bg-green-50 border-green-200'
            : 'text-red-800 bg-red-50 border-red-200'
        }`}
      >
        Total alocado: {formatQty(totalAlocado)} / {formatQty(qtyAlvo)} {unidade}
        {!somaOk ? ` (diferença ${diff > 0 ? '+' : ''}${formatQty(diff)})` : ''}
      </div>
      <div className="space-y-1">
        {splits.map((row, idx) => (
          <div key={`split-${row.ordem}-${idx}`} className="grid grid-cols-[1fr_1fr_4.5rem_auto] gap-1 items-center">
            <input
              className="erp-input h-8 text-xs"
              placeholder="Corrida"
              value={row.corrida}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { corrida: e.target.value })}
            />
            <input
              className="erp-input h-8 text-xs"
              placeholder="Lote"
              value={row.lote}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { lote: e.target.value })}
            />
            <input
              className="erp-input h-8 text-xs"
              placeholder="Qtd"
              value={row.quantidade}
              disabled={disabled}
              onChange={(e) => updateRow(idx, { quantidade: e.target.value })}
            />
            <button
              type="button"
              className="erp-btn-outline h-8 px-2 text-xs"
              disabled={disabled || splits.length <= 1}
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
          + Adicionar corrida
        </button>
      ) : null}
    </div>
  );
}

export function criarSplitsIniciais(qtyAlvo: number): CorridaSplitConferencia[] {
  const [a, b] = halfSplit(qtyAlvo);
  return [
    { ordem: 1, corrida: '', lote: '', quantidade: formatQty(a) },
    { ordem: 2, corrida: '', lote: '', quantidade: formatQty(b) },
  ];
}

export function itemUsaSplitCorrida(it: ItemConferenciaNFeEntradaLike): boolean {
  return Boolean(it.corridas_split && it.corridas_split.length > 0);
}

type ItemConferenciaNFeEntradaLike = {
  corridas_split?: CorridaSplitConferencia[];
};

export function qtyAlvoItemConferencia(it: ItemConferenciaNFeEntradaLike & {
  quantidade_estoque_calculada?: number;
  quantidade_nf: number;
}): number {
  const q = Number(it.quantidade_estoque_calculada || 0);
  return q > 0 ? q : Number(it.quantidade_nf || 0);
}

export function mapItemPayloadCorrida(it: ItemConferenciaNFeEntradaLike & {
  id: number;
  produto_id?: number | null;
  item_pedido_compra_id?: number | null;
  corrida?: string;
  lote?: string;
  status: string;
  motivo_ignorado?: string;
  observacao?: string;
}) {
  const base = {
    id: it.id,
    produto_id: it.produto_id ?? null,
    item_pedido_compra_id: it.item_pedido_compra_id ?? null,
    status: it.status,
    motivo_ignorado: it.motivo_ignorado ?? '',
    observacao: it.observacao ?? '',
  };
  if (itemUsaSplitCorrida(it)) {
    return {
      ...base,
      corrida: '',
      lote: '',
      corridas_split: (it.corridas_split || []).map((row, idx) => ({
        ordem: row.ordem || idx + 1,
        corrida: row.corrida || '',
        lote: row.lote || '',
        quantidade: row.quantidade,
      })),
    };
  }
  return {
    ...base,
    corrida: it.corrida ?? '',
    lote: it.lote ?? '',
    corridas_split: [],
  };
}
