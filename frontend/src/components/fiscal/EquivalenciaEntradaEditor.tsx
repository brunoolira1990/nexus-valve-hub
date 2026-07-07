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
  /** Modo composição física: 1 linha = 1 barra, soma apenas metros reais. */
  modoComposicaoFisica?: boolean;
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

function labelUnidadeNf(unidadeNf: string): string {
  const u = (unidadeNf || '').trim().toUpperCase();
  if (u === 'M') return 'metros';
  if (u === 'BR') return 'barras';
  if (u === 'KG' || u === 'TON') return 'peso (kg)';
  return u || 'unidade NF';
}

/** Alvo em metros para validação da composição (NF em M ou KG convertido). */
export function qtyAlvoComposicaoMetros(
  quantidadeNf: number,
  unidadeNf: string,
  fatores: FatoresEquivalenciaEntrada,
): { metros: number | null; erro: string | null; hint: string | null } {
  const u = (unidadeNf || '').trim().toUpperCase();
  if (u === 'M') {
    return { metros: quantidadeNf, erro: null, hint: null };
  }
  if (u === 'KG' || u === 'TON') {
    const ppm = fatores.pesoPorMetroKg;
    if (!ppm) {
      return {
        metros: null,
        erro: 'Informe peso por metro no cadastro do produto/família para converter KG em metros.',
        hint: null,
      };
    }
    const kg = u === 'TON' ? quantidadeNf * 1000 : quantidadeNf;
    const metros = Math.round((kg / ppm) * 1000) / 1000;
    return {
      metros,
      erro: null,
      hint: `${formatQty(quantidadeNf)} ${u} ≈ ${formatQty(metros)} M (÷ ${ppm} kg/m)`,
    };
  }
  return {
    metros: null,
    erro: `Composição física ainda não suporta NF em ${u || 'unidade indefinida'}.`,
    hint: null,
  };
}

export function totalMetrosComposicao(equivalencias: EquivalenciaEntradaConferencia[]): number {
  return equivalencias.reduce((acc, row) => acc + parseQty(row.metros), 0);
}

function sugerirCamposVazios(
  row: EquivalenciaEntradaConferencia,
  campoEditado: 'metros' | 'barras' | 'peso_kg',
  fatores: FatoresEquivalenciaEntrada,
  modoComposicaoFisica: boolean,
): Partial<EquivalenciaEntradaConferencia> {
  if (modoComposicaoFisica) {
    const patch: Partial<EquivalenciaEntradaConferencia> = {};
    const metros = parseQty(row.metros);
    const ppm = fatores.pesoPorMetroKg;
    if (campoEditado === 'metros' && metros > 0 && campoVazio(row.peso_kg) && ppm) {
      patch.peso_kg = formatQty(metros * ppm);
      patch.peso_por_metro_utilizado = formatQty(ppm, 6);
    }
    return patch;
  }

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

function metrosEfetivosSubLinha(
  row: EquivalenciaEntradaConferencia,
  fatores: FatoresEquivalenciaEntrada,
  modoComposicaoFisica: boolean,
): number | null {
  const metros = parseQty(row.metros);
  if (modoComposicaoFisica) {
    return metros > 0 ? metros : null;
  }
  const barras = parseQty(row.barras);
  const peso = parseQty(row.peso_kg);
  const ppm = fatores.pesoPorMetroKg;
  const comp = fatores.comprimentoPadraoBarraM;
  if (metros > 0) return metros;
  if (barras > 0 && comp) return barras * comp;
  if (peso > 0 && ppm) return peso / ppm;
  return null;
}

export function valorSubLinhaNaUnidadeNf(
  row: EquivalenciaEntradaConferencia,
  unidadeNf: string,
  fatores: FatoresEquivalenciaEntrada,
  modoComposicaoFisica = false,
): number | null {
  if (modoComposicaoFisica) {
    const m = parseQty(row.metros);
    return m > 0 ? m : null;
  }
  const metrosEfetivos = metrosEfetivosSubLinha(row, fatores, false);
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
  modoComposicaoFisica = false,
): number {
  if (modoComposicaoFisica) {
    return totalMetrosComposicao(equivalencias);
  }
  return equivalencias.reduce(
    (acc, row) => acc + (valorSubLinhaNaUnidadeNf(row, unidadeNf, fatores, false) ?? 0),
    0,
  );
}

export function EquivalenciaEntradaEditor({
  qtyAlvo,
  unidadeAlvo,
  colunaAlvo,
  equivalencias,
  fatores,
  onChange,
  disabled = false,
  modoComposicaoFisica = false,
}: EquivalenciaEntradaEditorProps) {
  const alvoComp = modoComposicaoFisica
    ? qtyAlvoComposicaoMetros(qtyAlvo, unidadeAlvo, fatores)
    : { metros: qtyAlvo, erro: null, hint: null };
  const qtyAlvoMetros = alvoComp.metros ?? 0;
  const totalAlocado = modoComposicaoFisica
    ? totalMetrosComposicao(equivalencias)
    : totalEquivalenciaNaUnidadeNf(equivalencias, unidadeAlvo, fatores, false);
  const alvoExibicao = modoComposicaoFisica ? qtyAlvoMetros : qtyAlvo;
  const diff = Math.round((totalAlocado - alvoExibicao) * 1000) / 1000;
  const somaOk = !alvoComp.erro && Math.abs(diff) < 0.001;

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
    const sugestoes = sugerirCamposVazios(atualizado, campo, fatores, modoComposicaoFisica);
    updateRow(index, { [campo]: value, ...sugestoes });
  };

  const removeRow = (index: number) => {
    const next = equivalencias
      .filter((_, i) => i !== index)
      .map((row, i) => ({ ...row, ordem: i + 1 }));
    onChange(next);
  };

  const addRow = () => {
    const restante = Math.max(0, Math.round((alvoExibicao - totalAlocado) * 1000) / 1000);
    const sugestaoMetros =
      modoComposicaoFisica && fatores.comprimentoPadraoBarraM && restante > 0
        ? Math.min(restante, fatores.comprimentoPadraoBarraM)
        : restante;
    const nova: EquivalenciaEntradaConferencia = {
      ordem: equivalencias.length + 1,
      metros: modoComposicaoFisica
        ? formatQty(sugestaoMetros > 0 ? sugestaoMetros : 0)
        : colunaAlvo === 'metros'
          ? formatQty(restante > 0 ? restante : 0)
          : '',
      barras: !modoComposicaoFisica && colunaAlvo === 'barras' ? formatQty(restante > 0 ? restante : 0) : '',
      peso_kg: !modoComposicaoFisica && colunaAlvo === 'peso_kg' ? formatQty(restante > 0 ? restante : 0) : '',
      peso_por_metro_utilizado: '',
    };
    onChange([...equivalencias, nova]);
  };

  return (
    <div className="space-y-2 min-w-[16rem]">
      {modoComposicaoFisica && alvoComp.hint ? (
        <div className="text-[11px] text-muted-foreground rounded px-2 py-1 border border-border bg-muted/30">
          {alvoComp.hint}
        </div>
      ) : null}
      {alvoComp.erro ? (
        <div className="text-[11px] text-red-800 bg-red-50 border border-red-200 rounded px-2 py-1">
          {alvoComp.erro}
        </div>
      ) : (
        <div
          className={`text-[11px] rounded px-2 py-1 border ${
            somaOk
              ? 'text-green-800 bg-green-50 border-green-200'
              : 'text-red-800 bg-red-50 border-red-200'
          }`}
        >
          {modoComposicaoFisica ? (
            <>
              Total composição: {formatQty(totalAlocado)} / {formatQty(alvoExibicao)} M
              {!somaOk ? ` (diferença ${diff > 0 ? '+' : ''}${formatQty(diff)})` : ''}
            </>
          ) : (
            <>
              Total {labelUnidadeNf(unidadeAlvo)}: {formatQty(totalAlocado)} / {formatQty(qtyAlvo)}{' '}
              {unidadeAlvo}
              {!somaOk ? ` (diferença ${diff > 0 ? '+' : ''}${formatQty(diff)})` : ''}
            </>
          )}
        </div>
      )}
      <div className="space-y-1">
        {equivalencias.map((row, idx) => (
          <div
            key={`equiv-${row.ordem}-${idx}`}
            className={
              modoComposicaoFisica
                ? 'grid grid-cols-[1fr_auto] gap-1 items-center'
                : 'grid grid-cols-[4rem_4rem_4.5rem_auto] gap-1 items-center'
            }
          >
            {modoComposicaoFisica ? (
              <input
                className="erp-input h-8 text-xs"
                placeholder={`Barra ${idx + 1} — comprimento (M)`}
                title="Comprimento real da barra em metros"
                value={row.metros ?? ''}
                disabled={disabled}
                onChange={(e) => updateRow(idx, { metros: e.target.value, barras: '' })}
                onBlur={(e) => handleBlurCampo(idx, 'metros', e.target.value)}
              />
            ) : (
              <>
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
              </>
            )}
            <button
              type="button"
              className="erp-btn-outline h-8 px-2 text-xs"
              disabled={disabled || equivalencias.length <= 1}
              onClick={() => removeRow(idx)}
              title="Remover barra"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      {!disabled ? (
        <button type="button" className="text-xs text-primary hover:underline" onClick={addRow}>
          {modoComposicaoFisica ? '+ Adicionar barra' : '+ Adicionar peça/barra'}
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

export function produtoControlaComposicaoFisica(produto?: {
  controla_composicao_fisica_efetivo?: boolean;
  controla_composicao_fisica?: boolean;
} | null): boolean {
  if (!produto) return false;
  return Boolean(produto.controla_composicao_fisica_efetivo ?? produto.controla_composicao_fisica);
}

export function criarEquivalenciasIniciais(
  qtyAlvo: number,
  colunaAlvo: 'metros' | 'barras' | 'peso_kg',
  opts?: { modoComposicaoFisica?: boolean; comprimentoPadraoBarraM?: number | null; unidadeNf?: string; fatores?: FatoresEquivalenciaEntrada },
): EquivalenciaEntradaConferencia[] {
  if (opts?.modoComposicaoFisica) {
    const fatores = opts.fatores ?? { pesoPorMetroKg: null, comprimentoPadraoBarraM: opts.comprimentoPadraoBarraM ?? null };
    const alvo = qtyAlvoComposicaoMetros(qtyAlvo, opts.unidadeNf || 'M', fatores);
    const metrosAlvo = alvo.metros ?? qtyAlvo;
    const padrao = opts.comprimentoPadraoBarraM ?? null;
    if (padrao && padrao > 0 && metrosAlvo > padrao) {
      const linhas: EquivalenciaEntradaConferencia[] = [];
      let restante = metrosAlvo;
      let ordem = 1;
      while (restante > 0.001) {
        const chunk = Math.min(restante, padrao);
        linhas.push({ ordem, metros: formatQty(chunk), barras: '', peso_kg: '', peso_por_metro_utilizado: '' });
        restante = Math.round((restante - chunk) * 1000) / 1000;
        ordem += 1;
      }
      return linhas.length ? linhas : [{ ordem: 1, metros: formatQty(metrosAlvo), barras: '', peso_kg: '', peso_por_metro_utilizado: '' }];
    }
    return [{ ordem: 1, metros: formatQty(metrosAlvo), barras: '', peso_kg: '', peso_por_metro_utilizado: '' }];
  }
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
