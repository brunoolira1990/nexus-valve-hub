import { useState } from 'react';

import { apiErrorMessage } from '@/services/api/config';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import {
  AVISO_EQUIVALENCIA_SEM_ESTOQUE,
  badgeConfiancaEquivalencia,
  formatMoedaBRL,
  labelTipoComposicao,
  labelTipoEquivalencia,
  type EquivalenciasConferenciaPayload,
} from '@/lib/conferenciaEquivalencia';
import type { NFeEntradaConferencia } from '@/types';

export type EquivalenciaEntradaBlocoProps = {
  equivalencias: EquivalenciasConferenciaPayload;
  nfId: number;
  estoqueJaAplicado?: boolean;
  onResultado: (conferencia: NFeEntradaConferencia) => void;
  onErro: (msg: string) => void;
};

export function EquivalenciaEntradaBloco({
  equivalencias,
  nfId,
  estoqueJaAplicado = false,
  onResultado,
  onErro,
}: EquivalenciaEntradaBlocoProps) {
  const [equivalenciasAberto, setEquivalenciasAberto] = useState(true);
  const [eqBusy, setEqBusy] = useState(false);

  return (
    <details
      className="erp-card mb-4 group"
      open={equivalenciasAberto}
      onToggle={(e) => setEquivalenciasAberto(e.currentTarget.open)}
    >
      <summary className="cursor-pointer list-none px-4 py-3 flex flex-wrap items-center gap-2 border-b border-border/60">
        <span className="text-sm font-medium">Equivalências e Composições</span>
        {(equivalencias.sugestoes?.length ?? 0) > 0 ? (
          <span className="erp-badge-warning text-[10px]">
            {equivalencias.sugestoes.length} sugestão(ões)
          </span>
        ) : (
          <span className="erp-badge-info text-[10px]">Sem sugestões automáticas</span>
        )}
      </summary>
      <div className="px-4 py-3 text-sm space-y-3">
        <p className="text-xs text-muted-foreground">{AVISO_EQUIVALENCIA_SEM_ESTOQUE}</p>
        {equivalencias.comparacao_pedido_nf ? (
          <div className="text-xs border border-border/60 rounded-md p-2 space-y-1">
            <p className="font-medium">Comparação Pedido × NF (informativa)</p>
            <p>
              Produtos pedido: {formatMoedaBRL(equivalencias.comparacao_pedido_nf.valor_produtos_pedido)} ·
              Produtos NF: {formatMoedaBRL(equivalencias.comparacao_pedido_nf.valor_produtos_nf)} ·
              Diferença: {formatMoedaBRL(equivalencias.comparacao_pedido_nf.diferenca_produtos)}
            </p>
          </div>
        ) : null}
        {(equivalencias.sugestoes ?? []).map((sug, idx) => {
          const badge = badgeConfiancaEquivalencia(sug.nivel_confianca);
          return (
            <div key={`eq-sug-${idx}`} className="border border-border/60 rounded-md p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="erp-badge-primary text-[10px]">{labelTipoEquivalencia(sug.tipo)}</span>
                {sug.tipo_composicao ? (
                  <span className="erp-badge-outline text-[10px]">{labelTipoComposicao(sug.tipo_composicao)}</span>
                ) : null}
                <span className={`${badge.className} text-[10px]`}>{badge.label} ({sug.confianca}%)</span>
                {sug.dentro_tolerancia === false ? (
                  <span className="erp-badge-danger text-[10px]">Fora da tolerância</span>
                ) : (
                  <span className="erp-badge-success text-[10px]">Dentro da tolerância</span>
                )}
              </div>
              <p className="font-medium">
                {sug.produto_interno_codigo} — {sug.produto_interno_descricao}
              </p>
              {sug.alerta_filial ? <p className="text-xs text-amber-700 dark:text-amber-300">{sug.alerta_filial}</p> : null}
              <ul className="text-xs text-muted-foreground space-y-1">
                {(sug.itens_nfe ?? []).map((it, j) => (
                  <li key={`eq-it-${idx}-${j}`}>
                    {it.codigo_fornecedor || '—'} · {it.descricao || '—'} · qtd {it.quantidade} ·{' '}
                    {formatMoedaBRL(it.valor_total)}
                  </li>
                ))}
              </ul>
              <p className="text-xs">
                Total NF: {formatMoedaBRL(sug.valor_total_agrupado)} · Pedido:{' '}
                {formatMoedaBRL(sug.valor_pedido_referencia)} · Diferença:{' '}
                {formatMoedaBRL(sug.diferenca_valor)}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm"
                  disabled={eqBusy || estoqueJaAplicado}
                  onClick={async () => {
                    if (!sug.produto_interno_id || !(sug.itens_nfe_conferencia_ids?.length ?? 0)) return;
                    setEqBusy(true);
                    try {
                      const res = await nfeEntradaConferenciaService.confirmarEquivalencia(nfId, {
                        produto_interno_id: sug.produto_interno_id,
                        item_pedido_compra_id: sug.item_pedido_compra_id ?? undefined,
                        itens_nfe_conferencia_ids: sug.itens_nfe_conferencia_ids ?? [],
                        tipo_agrupamento: sug.tipo,
                        quantidade_equivalente: sug.quantidade_equivalente,
                        confianca: sug.confianca,
                        salvar_regra_fornecedor: true,
                      });
                      onResultado(res.conferencia);
                    } catch (err) {
                      onErro(apiErrorMessage(err));
                    } finally {
                      setEqBusy(false);
                    }
                  }}
                >
                  Confirmar vínculo
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={eqBusy}
                  onClick={async () => {
                    if (!sug.produto_interno_id) return;
                    setEqBusy(true);
                    try {
                      const res = await nfeEntradaConferenciaService.rejeitarEquivalencia(nfId, {
                        produto_interno_id: sug.produto_interno_id,
                        itens_nfe_conferencia_ids: sug.itens_nfe_conferencia_ids ?? [],
                      });
                      onResultado(res.conferencia);
                    } catch (err) {
                      onErro(apiErrorMessage(err));
                    } finally {
                      setEqBusy(false);
                    }
                  }}
                >
                  Rejeitar sugestão
                </button>
              </div>
            </div>
          );
        })}
        {(equivalencias.agrupamentos?.length ?? 0) > 0 ? (
          <div>
            <p className="font-medium text-xs mb-1">Agrupamentos confirmados</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              {equivalencias.agrupamentos.map((agr: { id?: number; produto_interno_codigo?: string; status?: string }) => (
                <li key={`agr-${agr.id}`}>
                  #{agr.id} · {agr.produto_interno_codigo} · {agr.status}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </details>
  );
}
