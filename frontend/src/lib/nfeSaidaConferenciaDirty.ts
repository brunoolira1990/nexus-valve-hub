/** Detecção de alterações não salvas na conferência NF-e. */

import { montarItensComplementaresConferencia } from '@/lib/nfeSaidaConferenciaSave';
import type { NFeSaidaConferenciaPayload } from '@/services/api/fiscal';

export type ConferenciaDirtySnapshot = {
  pedido_cliente_numero: string;
  pedido_cliente_observacao: string;
  observacoes_nfe: string;
  informacoes_adicionais: string;
  informacoes_fisco: string;
  observacoes_internas: string;
  transporte: Record<string, unknown>;
  ind_final: string;
  ind_pres: string;
  itens: Array<Record<string, string>>;
};

function s(val: unknown): string {
  return String(val ?? '').trim();
}

function n(val: unknown): number {
  const x = Number(val);
  return Number.isFinite(x) ? x : 0;
}

export function snapshotConferenciaDirty(
  conf: NFeSaidaConferenciaPayload,
): ConferenciaDirtySnapshot {
  const tr = conf.transporte as Record<string, unknown>;
  const ind = (conf.indicadores_fiscais ?? {}) as Record<string, unknown>;
  return {
    pedido_cliente_numero: s(conf.nfe.pedido_cliente_numero),
    pedido_cliente_observacao: s(conf.nfe.pedido_cliente_observacao),
    observacoes_nfe: s(conf.observacoes.observacoes_nfe),
    informacoes_adicionais: s(conf.observacoes.informacoes_adicionais),
    informacoes_fisco: s(conf.observacoes.informacoes_fisco),
    observacoes_internas: s(conf.observacoes.observacoes_internas),
    transporte: {
      modalidade_frete: s(tr.modalidade_frete ?? '9'),
      transportadora_id: tr.transportadora_id ?? null,
      valor_frete: n(tr.valor_frete),
      quantidade_volumes: n(tr.quantidade_volumes),
      especie_volumes: s(tr.especie_volumes),
      marca_volumes: s(tr.marca_volumes),
      numeracao_volumes: s(tr.numeracao_volumes),
      peso_bruto: n(tr.peso_bruto),
      peso_liquido: n(tr.peso_liquido),
      placa_veiculo: s(tr.placa_veiculo),
      uf_veiculo: s(tr.uf_veiculo),
    },
    ind_final: s(ind.ind_final ?? '1'),
    ind_pres: s(ind.ind_pres ?? '1'),
    itens: (conf.itens || []).map((it) => ({
      item_id: String(it.item_id ?? ''),
      pedido_cliente_numero: s(it.pedido_cliente_numero_editavel ?? it.pedido_cliente_numero),
      pedido_cliente_item: s(it.pedido_cliente_item_editavel ?? it.pedido_cliente_item),
      observacao_item: s(it.observacao_item),
      informacao_adicional_item: s(it.informacao_adicional_item),
    })),
  };
}

export function conferenciaTemAlteracoesNaoSalvas(
  atual: NFeSaidaConferenciaPayload,
  baseline: ConferenciaDirtySnapshot | null,
): boolean {
  if (!baseline) return false;
  const snap = snapshotConferenciaDirty(atual);
  return JSON.stringify(snap) !== JSON.stringify(baseline);
}

export function transporteTemDadosPreenchidos(tr: Record<string, unknown>): boolean {
  return (
    Boolean(tr.transportadora_id) ||
    n(tr.quantidade_volumes) > 0 ||
    n(tr.peso_bruto) > 0 ||
    n(tr.peso_liquido) > 0 ||
    n(tr.valor_frete) > 0 ||
    Boolean(s(tr.placa_veiculo)) ||
    Boolean(s(tr.uf_veiculo)) ||
    Boolean(s(tr.especie_volumes)) ||
    Boolean(s(tr.marca_volumes)) ||
    Boolean(s(tr.numeracao_volumes))
  );
}

export function montarPayloadSalvarConferencia(
  conf: NFeSaidaConferenciaPayload,
  origemComercialTravada: boolean,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    pedido_cliente_numero: conf.nfe.pedido_cliente_numero,
    pedido_cliente_observacao: conf.nfe.pedido_cliente_observacao,
    transportadora_id: conf.transporte.transportadora_id,
    modalidade_frete: conf.transporte.modalidade_frete,
    valor_frete: conf.transporte.valor_frete,
    quantidade_volumes: conf.transporte.quantidade_volumes,
    peso_bruto: conf.transporte.peso_bruto,
    peso_liquido: conf.transporte.peso_liquido,
    especie_volumes: conf.transporte.especie_volumes,
    marca_volumes: conf.transporte.marca_volumes,
    numeracao_volumes: conf.transporte.numeracao_volumes,
    placa_veiculo: conf.transporte.placa_veiculo,
    uf_veiculo: conf.transporte.uf_veiculo,
    observacoes_nfe: conf.observacoes.observacoes_nfe,
    informacoes_adicionais: conf.observacoes.informacoes_adicionais,
    informacoes_fisco: conf.observacoes.informacoes_fisco,
    observacoes_internas: conf.observacoes.observacoes_internas,
    ind_final: (conf.indicadores_fiscais as { ind_final?: string })?.ind_final ?? '1',
    ind_pres: (conf.indicadores_fiscais as { ind_pres?: string })?.ind_pres ?? '1',
    indicadores_fiscais_confirmados: true,
  };
  const itensPayload = montarItensComplementaresConferencia(
    conf.itens as Parameters<typeof montarItensComplementaresConferencia>[0],
    origemComercialTravada,
  );
  if (itensPayload !== undefined) {
    payload.itens = itensPayload;
  }
  return payload;
}
