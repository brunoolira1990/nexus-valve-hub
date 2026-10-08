import type { Produto } from '@/types';

const MATERIAL_INFORMADO_VAZIO = '—';

/** Exibe material na listagem/detalhe com prioridade material_label → material → fallback. */
export function formatProdutoMaterial(
  produto: Pick<Produto, 'material' | 'material_label'> | null | undefined,
): string {
  if (!produto) return MATERIAL_INFORMADO_VAZIO;
  const label = (produto.material_label || '').trim();
  if (label) return label;
  const raw = (produto.material || '').trim();
  if (!raw) return MATERIAL_INFORMADO_VAZIO;
  if (raw === raw.toUpperCase() && raw.length > 2) {
    return raw
      .toLowerCase()
      .split(' ')
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join(' ');
  }
  return raw;
}

/** Valor inicial do select Material (compatível com MATERIAIS). */
export function materialValorParaForm(
  produto: Pick<Produto, 'material' | 'material_label'> | null | undefined,
  fallback = 'Aço Carbono',
): string {
  if (!produto) return fallback;
  const label = (produto.material_label || '').trim();
  if (label) return label;
  const raw = (produto.material || '').trim();
  return raw || fallback;
}

/** Inclui material no payload só se preenchido (evita apagar em PATCH acidental). */
export function materialParaPayload(
  material: string | undefined,
  editing: Pick<Produto, 'material'> | null,
): { material?: string } {
  const valor = (material || '').trim();
  if (valor) return { material: valor };
  if (editing) return {};
  return { material: 'Aço Carbono' };
}
