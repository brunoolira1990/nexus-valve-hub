import type { AlocacaoVinculosExibicao } from '@/types/alocacaoAtendimentoOpcoes';

export function AlocacaoVinculosLinha({ vinculos }: { vinculos?: AlocacaoVinculosExibicao }) {
  if (!vinculos) return null;
  const linhas: string[] = [];
  if (vinculos.fornecedor_label) linhas.push(`Fornecedor: ${vinculos.fornecedor_label}`);
  if (vinculos.pedido_compra_label) linhas.push(`Compra: ${vinculos.pedido_compra_label}`);
  else if (!vinculos.tem_compra_vinculada) linhas.push('Compra: não vinculada');
  if (vinculos.nfe_entrada_label) {
    const st = vinculos.nfe_entrada_status_conferencia
      ? ` (${vinculos.nfe_entrada_status_conferencia})`
      : '';
    linhas.push(`NF-e Entrada: ${vinculos.nfe_entrada_label}${st}`);
  } else if (!vinculos.tem_nfe_entrada_vinculada) linhas.push('NF-e Entrada: não vinculada');
  if (vinculos.cte_label) {
    const st = vinculos.cte_status_conferencia ? ` — ${vinculos.cte_status_conferencia}` : '';
    linhas.push(`CT-e: ${vinculos.cte_label}${st}`);
  } else if (!vinculos.tem_cte_vinculado) linhas.push('CT-e: não vinculado');

  if (linhas.length === 0) return null;

  return (
    <ul className="text-[10px] text-muted-foreground mt-1 space-y-0.5 list-none">
      {linhas.map((l) => (
        <li key={l}>{l}</li>
      ))}
    </ul>
  );
}
