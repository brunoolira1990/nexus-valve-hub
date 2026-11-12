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
      entrega_xLgr: s(tr.entrega_xLgr),
      entrega_nro: s(tr.entrega_nro),
      entrega_xCmp: s(tr.entrega_xCmp),
      entrega_xBairro: s(tr.entrega_xBairro),
      entrega_xMun: s(tr.entrega_xMun),
      entrega_UF: s(tr.entrega_UF),
      entrega_CEP: s(tr.entrega_CEP),
      entrega_cMun: s(tr.entrega_cMun),
      entrega_cUF: s(tr.entrega_cUF),
      entrega_xNome: s(tr.entrega_xNome),
      entrega_cnpj: s(tr.entrega_cnpj),
      entrega_cpf: s(tr.entrega_cpf),
      retirada_xLgr: s(tr.retirada_xLgr),
      retirada_nro: s(tr.retirada_nro),
      retirada_xCmp: s(tr.retirada_xCmp),
      retirada_xBairro: s(tr.retirada_xBairro),
      retirada_xMun: s(tr.retirada_xMun),
      retirada_UF: s(tr.retirada_UF),
      retirada_CEP: s(tr.retirada_CEP),
      retirada_cMun: s(tr.retirada_cMun),
      retirada_cUF: s(tr.retirada_cUF),
      retirada_xNome: s(tr.retirada_xNome),
      retirada_cnpj: s(tr.retirada_cnpj),
      retirada_cpf: s(tr.retirada_cpf),
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
    Boolean(s(tr.numeracao_volumes)) ||
    Boolean(s(tr.entrega_xLgr)) ||
    Boolean(s(tr.entrega_nro)) ||
    Boolean(s(tr.entrega_xCmp)) ||
    Boolean(s(tr.entrega_xBairro)) ||
    Boolean(s(tr.entrega_xMun)) ||
    Boolean(s(tr.entrega_UF)) ||
    Boolean(s(tr.entrega_CEP)) ||
    Boolean(s(tr.entrega_cMun)) ||
    Boolean(s(tr.entrega_cUF)) ||
    Boolean(s(tr.entrega_xNome)) ||
    Boolean(s(tr.entrega_cnpj)) ||
    Boolean(s(tr.entrega_cpf)) ||
    Boolean(s(tr.retirada_xLgr)) ||
    Boolean(s(tr.retirada_nro)) ||
    Boolean(s(tr.retirada_xCmp)) ||
    Boolean(s(tr.retirada_xBairro)) ||
    Boolean(s(tr.retirada_xMun)) ||
    Boolean(s(tr.retirada_UF)) ||
    Boolean(s(tr.retirada_CEP)) ||
    Boolean(s(tr.retirada_cMun)) ||
    Boolean(s(tr.retirada_cUF)) ||
    Boolean(s(tr.retirada_xNome)) ||
    Boolean(s(tr.retirada_cnpj)) ||
    Boolean(s(tr.retirada_cpf))
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
    entrega_xLgr: conf.transporte.entrega_xLgr,
    entrega_nro: conf.transporte.entrega_nro,
    entrega_xCmp: conf.transporte.entrega_xCmp,
    entrega_xBairro: conf.transporte.entrega_xBairro,
    entrega_xMun: conf.transporte.entrega_xMun,
    entrega_UF: conf.transporte.entrega_UF,
    entrega_CEP: conf.transporte.entrega_CEP,
    entrega_cMun: conf.transporte.entrega_cMun,
    entrega_cUF: conf.transporte.entrega_cUF,
    entrega_xNome: conf.transporte.entrega_xNome,
    entrega_cnpj: conf.transporte.entrega_cnpj,
    entrega_cpf: conf.transporte.entrega_cpf,
    retirada_xLgr: conf.transporte.retirada_xLgr,
    retirada_nro: conf.transporte.retirada_nro,
    retirada_xCmp: conf.transporte.retirada_xCmp,
    retirada_xBairro: conf.transporte.retirada_xBairro,
    retirada_xMun: conf.transporte.retirada_xMun,
    retirada_UF: conf.transporte.retirada_UF,
    retirada_CEP: conf.transporte.retirada_CEP,
    retirada_cMun: conf.transporte.retirada_cMun,
    retirada_cUF: conf.transporte.retirada_cUF,
    retirada_xNome: conf.transporte.retirada_xNome,
    retirada_cnpj: conf.transporte.retirada_cnpj,
    retirada_cpf: conf.transporte.retirada_cpf,
    observacoes_nfe: conf.observacoes.observacoes_nfe,
    informacoes_adicionais: conf.observacoes.informacoes_adicionais,
    informacoes_fisco: conf.observacoes.informacoes_fisco,
    observacoes_internas: conf.observacoes.observacoes_internas,
    ind_final: (conf.indicadores_fiscais as { ind_final?: string })?.ind_final ?? '1',
    ind_pres: (conf.indicadores_fiscais as { ind_pres?: string })?.ind_pres ?? '1',
    indicadores_fiscais_confirmados: true,
  };
  // NF-e herdada: nunca envia produto/quantidade/valor — só complementos de item (ou omite itens).
  const itensPayload = montarItensComplementaresConferencia(
    conf.itens as Parameters<typeof montarItensComplementaresConferencia>[0],
    origemComercialTravada,
  );
  if (itensPayload !== undefined) {
    payload.itens = itensPayload;
  }
  return payload;
}
