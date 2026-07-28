import type { ReactNode } from 'react';
import { formatMoneyBRL } from '@/lib/money';
import { SecoesIntegracoesExternas } from '@/components/financeiro/SecoesIntegracoesExternas';
import { SecaoProtestosCartorio } from '@/components/financeiro/SecaoProtestosCartorio';
import type { CapacidadeIntegracoesCredito } from '@/services/api/analiseFinanceira';

const AVISO_PARCIAL =
  'Alguns indicadores não puderam ser calculados com os dados disponíveis. A decisão deve ser revisada manualmente pelo Financeiro.';

const PLACEHOLDER_SNAPSHOT =
  'Não disponível no snapshot desta análise.';

type Metrica = {
  disponivel?: boolean;
  valor?: string | number | null;
  motivo_indisponibilidade?: string | null;
  motivo?: string | null;
};

type PeriodoComercial = {
  quantidade_vendas?: number;
  valor_vendido?: string | null;
  ticket_medio?: string | null;
  maior_venda?: string | null;
  primeira_compra?: string | null;
  ultima_compra?: string | null;
  frequencia_media_dias?: Metrica;
};

type PeriodoBaixas = {
  quantidade_baixas_analisadas?: number;
  quantidade_excluidas?: number;
  valor_total_recebido?: string | null;
  pontualidade_quantidade?: Metrica;
  pontualidade_valor?: Metrica;
  atraso_medio_dias?: Metrica;
  maior_atraso_historico_dias?: Metrica;
  data_ultimo_pagamento?: Metrica;
  quantidade_pagamentos_parciais?: number;
};

type SnapshotIndicadores = {
  schema_versao?: number;
  qualidade_dados?: string;
  dados_indisponiveis?: string[];
  data_corte?: string;
  resumo_restrito?: boolean;
  qualidade?: {
    status?: string;
    mensagem?: string;
    indisponiveis?: { indicador: string; motivo: string }[];
    fonte_historico_comercial?: string;
    divergencias?: { codigo?: string; motivo: string }[];
    pedidos_analisados?: number;
    titulos_analisados?: number;
    baixas_analisadas?: number;
    registros_excluidos?: number;
    periodo_inicio?: string | null;
    periodo_fim?: string | null;
  };
  indicadores?: {
    comercial?: {
      fonte?: string;
      fonte_historico_comercial?: string;
      ambiente_fiscal_considerado?: string;
      documentos_homologacao_ignorados?: number;
      motivo_fallback_comercial?: string | null;
      limitacao?: string | null;
      quantidade_pedidos_cancelados?: number;
      tempo_relacionamento_dias?: number | null;
      periodos?: Record<string, PeriodoComercial>;
    };
    contas_receber?: {
      saldo_aberto?: string | null;
      saldo_a_vencer?: string | null;
      saldo_vencido?: string | null;
      quantidade_titulos_abertos?: number;
      quantidade_titulos_vencidos?: number | null;
      maior_atraso_dias?: number | null;
    };
    baixas?: { periodos?: Record<string, PeriodoBaixas> };
    pedidos_nao_faturados?: {
      valor_residual?: string | null;
      quantidade_pedidos?: number | null;
      quantidade_itens_residual?: number | null;
    };
    exposicao?: {
      contas_receber?: string | null;
      pedidos_nao_faturados?: string | null;
      atual?: string | null;
      valor_proposta?: string | null;
      projetada?: string | null;
    };
    limite?: {
      cadastrado?: string | null;
      ambiguo?: boolean;
      mensagem?: string | null;
      disponivel_antes?: Metrica;
      disponivel_depois?: Metrica;
      excesso_sobre_limite?: Metrica;
    };
  };
  // v1 compat
  limite_credito_cadastrado?: { disponivel?: boolean; valor?: string | null; ambiguo?: boolean; mensagem?: string | null };
  contas_receber?: SnapshotIndicadores['indicadores'] extends infer I
    ? I extends { contas_receber?: infer C }
      ? C
      : never
    : never;
  pedidos_nao_faturados?: { valor_residual?: string | null; quantidade_pedidos?: number | null };
  exposicao?: { atual?: string | null; projetada?: string | null; valor_proposta?: string | null };
  percentual_pontualidade?: Metrica;
  atraso_medio_dias?: Metrica;
  data_ultima_compra?: Metrica;
  valor_comprado_12_meses?: Metrica;
};

type Negociacao = {
  proposta_numero?: string;
  cliente_nome?: string;
  valor_solicitado?: string;
  condicao?: string;
  vendedor?: string;
  solicitada_em?: string;
  data_corte?: string;
};

type Props = {
  snapshot?: Record<string, unknown> | SnapshotIndicadores | null;
  negociacao?: Negociacao | null;
  analiseId?: number | null;
  podeVerProtestoManual?: boolean;
  podeRegistrarProtestoManual?: boolean;
  /** Capability injetada (testes) — evita HTTP. */
  capacidadeIntegracoes?: CapacidadeIntegracoesCredito | null;
  carregarCapabilityIntegracoes?: boolean;
};

function money(value: string | number | null | undefined, disponivel = true): string {
  if (!disponivel || value === null || value === undefined || value === '') return 'Indisponível';
  const n = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(n)) return 'Indisponível';
  return formatMoneyBRL(n);
}

function textOrUnavailable(value: string | number | null | undefined, disponivel = true): string {
  if (!disponivel || value === null || value === undefined || value === '') return 'Indisponível';
  return String(value);
}

function dateLocal(iso: string | null | undefined): string {
  if (!iso) return 'Indisponível';
  return new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR');
}

function pct(m?: Metrica | null): string {
  if (!m || m.disponivel === false || m.valor === null || m.valor === undefined) {
    return 'Indisponível';
  }
  return `${m.valor}%`;
}

function metricaValor(m?: Metrica | null, asDate = false): string {
  if (!m || m.disponivel === false || m.valor === null || m.valor === undefined) return 'Indisponível';
  if (asDate) return dateLocal(String(m.valor));
  return String(m.valor);
}

function Row({ label, value, hint }: { label: string; value: string; hint?: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums text-sm" data-testid={`dossie-row-${label}`}>
        {value}
      </dd>
      {hint ? <p className="text-xs text-muted-foreground mt-0.5">{hint}</p> : null}
    </div>
  );
}

function Section({ title, children, testId }: { title: string; children: ReactNode; testId?: string }) {
  return (
    <section className="rounded border border-border bg-muted/20 p-3 space-y-3" data-testid={testId}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function Placeholder({ children, testId }: { children: string; testId: string }) {
  return (
    <p className="text-sm text-muted-foreground" data-testid={testId}>
      {children}
    </p>
  );
}

function qualidadeMensagem(status?: string, mensagem?: string): string {
  if (mensagem) return mensagem;
  if (status === 'PARCIAL' || status === 'INSUFICIENTE') return AVISO_PARCIAL;
  if (status === 'DIVERGENTE') {
    return 'Foram detectadas inconsistências. A decisão deve ser revisada manualmente pelo Financeiro.';
  }
  if (status === 'COMPLETA') return 'Indicadores principais disponíveis sem divergências materiais.';
  return PLACEHOLDER_SNAPSHOT;
}

export function AnaliseFinanceiraIndicadores({
  snapshot,
  negociacao,
  analiseId = null,
  podeVerProtestoManual = false,
  podeRegistrarProtestoManual = false,
  capacidadeIntegracoes = null,
  carregarCapabilityIntegracoes = true,
}: Props) {
  const ind = (snapshot || {}) as SnapshotIndicadores;
  const schema = ind.schema_versao;
  const isV2 = schema === 2 && Boolean(ind.indicadores);
  const isLegacy = !isV2 && (Boolean(ind.contas_receber) || Boolean(ind.exposicao) || Boolean(ind.qualidade_dados));

  const secoesExternas = (
    <>
      <SecoesIntegracoesExternas
        capacidade={capacidadeIntegracoes}
        carregarCapability={carregarCapabilityIntegracoes}
      />
      <SecaoProtestosCartorio
        analiseId={analiseId}
        podeVer={podeVerProtestoManual}
        podeRegistrar={podeRegistrarProtestoManual}
        carregarHistorico={Boolean(analiseId && podeVerProtestoManual)}
      />
      <Section title="Recomendação automática" testId="dossie-recomendacao">
        <Placeholder testId="dossie-recomendacao-placeholder">
          Não existe política automática ativa. A decisão permanece sob responsabilidade do Financeiro.
        </Placeholder>
      </Section>
    </>
  );

  if (ind.resumo_restrito) {
    const status = ind.qualidade?.status || ind.qualidade_dados;
    return (
      <div className="space-y-3" data-testid="analise-fin-indicadores">
        <Section title="Qualidade dos dados" testId="dossie-qualidade">
          <p className="text-sm">Classificação: {status || 'Indisponível'}</p>
          <p className="text-sm text-muted-foreground" role="status">
            Detalhe financeiro restrito. {qualidadeMensagem(status, ind.qualidade?.mensagem)}
          </p>
        </Section>
        {secoesExternas}
      </div>
    );
  }

  if (!isV2 && !isLegacy) {
    return (
      <div className="rounded border border-border p-3" data-testid="analise-fin-indicadores">
        <p className="text-sm text-muted-foreground">{PLACEHOLDER_SNAPSHOT}</p>
      </div>
    );
  }

  const qualidadeStatus = ind.qualidade?.status || ind.qualidade_dados;
  const comercial = ind.indicadores?.comercial;
  const periodosC = comercial?.periodos || {};
  const cr = ind.indicadores?.contas_receber || ind.contas_receber;
  const baixas = ind.indicadores?.baixas?.periodos || {};
  const b12 = baixas['12_MESES'] || {};
  const ped = ind.indicadores?.pedidos_nao_faturados || ind.pedidos_nao_faturados;
  const exp = ind.indicadores?.exposicao || ind.exposicao;
  const limite = ind.indicadores?.limite;
  const limiteAmbiguo =
    limite?.ambiguo ?? ind.limite_credito_cadastrado?.ambiguo ?? ind.limite_credito_cadastrado?.disponivel === false;
  const indisponiveis =
    ind.qualidade?.indisponiveis ||
    (ind.dados_indisponiveis || []).map((nome) => ({ indicador: nome, motivo: 'Indisponível neste snapshot.' }));

  return (
    <div className="space-y-4" data-testid="analise-fin-indicadores">
      {negociacao ? (
        <Section title="Negociação" testId="dossie-negociacao">
          <dl className="grid gap-2 sm:grid-cols-2">
            <Row label="Proposta" value={negociacao.proposta_numero || '—'} />
            <Row label="Cliente" value={negociacao.cliente_nome || '—'} />
            <Row label="Valor" value={money(negociacao.valor_solicitado)} />
            <Row label="Condição" value={negociacao.condicao || '—'} />
            <Row label="Vendedor" value={negociacao.vendedor || '—'} />
            <Row
              label="Solicitada em"
              value={
                negociacao.solicitada_em
                  ? new Date(negociacao.solicitada_em).toLocaleString('pt-BR')
                  : '—'
              }
            />
            <Row label="Data de corte" value={dateLocal(negociacao.data_corte || ind.data_corte)} />
          </dl>
        </Section>
      ) : null}

      <Section title="Histórico interno — comercial" testId="dossie-comercial">
        {!isV2 ? (
          <p className="text-sm text-muted-foreground" data-testid="dossie-snapshot-antigo">
            {PLACEHOLDER_SNAPSHOT} (histórico comercial detalhado exige snapshot v2.)
          </p>
        ) : null}
        {isV2 ? (
          <>
            <p className="text-xs text-muted-foreground" data-testid="dossie-fonte-comercial">
              Fonte:{' '}
              {comercial?.fonte === 'NFE_SAIDA_PRODUCAO' || comercial?.fonte === 'NFE_SAIDA'
                ? 'NF-e de saída autorizada em produção'
                : comercial?.fonte === 'PEDIDO_VENDA'
                  ? 'Pedidos de Venda'
                  : 'Fonte indisponível'}
            </p>
            {comercial?.motivo_fallback_comercial ||
            (comercial?.documentos_homologacao_ignorados &&
              Number(comercial.documentos_homologacao_ignorados) > 0 &&
              comercial?.fonte === 'PEDIDO_VENDA') ? (
              <p
                className="text-sm border border-amber-700/40 bg-amber-50 text-amber-950 rounded px-2 py-1.5"
                role="status"
                data-testid="dossie-aviso-homologacao"
              >
                {comercial?.motivo_fallback_comercial ||
                  'O histórico comercial foi calculado pelos Pedidos de Venda. Documentos fiscais de homologação não são considerados como vendas reais.'}
              </p>
            ) : null}
            {comercial?.limitacao && comercial?.fonte === 'PEDIDO_VENDA' && !comercial?.motivo_fallback_comercial ? (
              <p className="text-xs text-muted-foreground">{comercial.limitacao}</p>
            ) : null}
            <dl className="grid gap-2 sm:grid-cols-2">
              {(['6_MESES', '12_MESES', '24_MESES', 'TOTAL'] as const).map((p) => {
                const block = periodosC[p] || {};
                const label =
                  p === 'TOTAL' ? 'Total' : p === '6_MESES' ? '6 meses' : p === '12_MESES' ? '12 meses' : '24 meses';
                return (
                  <div key={p} className="sm:col-span-2 border-t border-border/60 pt-2 first:border-0 first:pt-0">
                    <p className="text-xs font-medium mb-1">{label}</p>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Row label={`Vendas (${label})`} value={textOrUnavailable(block.quantidade_vendas, true)} />
                      <Row label={`Valor (${label})`} value={money(block.valor_vendido)} />
                      <Row label={`Ticket médio (${label})`} value={money(block.ticket_medio)} />
                      <Row label={`Maior venda (${label})`} value={money(block.maior_venda)} />
                      <Row label={`Primeira compra (${label})`} value={dateLocal(block.primeira_compra)} />
                      <Row label={`Última compra (${label})`} value={dateLocal(block.ultima_compra)} />
                      <Row
                        label={`Frequência média (${label})`}
                        value={
                          block.frequencia_media_dias?.disponivel
                            ? `${block.frequencia_media_dias.valor} dias`
                            : 'Indisponível'
                        }
                        hint={
                          block.frequencia_media_dias?.disponivel
                            ? null
                            : block.frequencia_media_dias?.motivo_indisponibilidade
                        }
                      />
                    </div>
                  </div>
                );
              })}
              <Row
                label="Tempo de relacionamento"
                value={
                  comercial?.tempo_relacionamento_dias != null
                    ? `${comercial.tempo_relacionamento_dias} dias`
                    : 'Indisponível'
                }
              />
              <Row
                label="Pedidos cancelados"
                value={textOrUnavailable(comercial?.quantidade_pedidos_cancelados, true)}
              />
            </dl>
          </>
        ) : (
          <dl className="grid gap-2 sm:grid-cols-2">
            <Row
              label="Última compra"
              value={textOrUnavailable(ind.data_ultima_compra?.valor, ind.data_ultima_compra?.disponivel !== false)}
            />
            <Row
              label="Valor 12 meses"
              value={money(ind.valor_comprado_12_meses?.valor, ind.valor_comprado_12_meses?.disponivel !== false)}
            />
          </dl>
        )}
      </Section>

      <Section title="Histórico interno — financeiro" testId="dossie-financeiro">
        <dl className="grid gap-2 sm:grid-cols-2">
          <Row label="Saldo total a receber" value={money(cr?.saldo_aberto)} />
          <Row label="Saldo a vencer" value={money(cr?.saldo_a_vencer)} />
          <Row label="Saldo vencido" value={money(cr?.saldo_vencido)} />
          <Row label="Títulos vencidos" value={textOrUnavailable(cr?.quantidade_titulos_vencidos)} />
          <Row
            label="Maior atraso aberto"
            value={cr?.maior_atraso_dias != null ? `${cr.maior_atraso_dias} dias` : 'Indisponível'}
          />
          {isV2 ? (
            <>
              <Row label="Valor recebido (12 meses)" value={money(b12.valor_total_recebido, b12.valor_total_recebido != null)} />
              <Row
                label="Pontualidade por quantidade (12 meses)"
                value={pct(b12.pontualidade_quantidade || ind.percentual_pontualidade)}
                hint={
                  b12.pontualidade_quantidade?.disponivel === false
                    ? b12.pontualidade_quantidade.motivo_indisponibilidade
                    : null
                }
              />
              <Row label="Pontualidade por valor (12 meses)" value={pct(b12.pontualidade_valor)} />
              <Row
                label="Atraso médio (12 meses)"
                value={
                  b12.atraso_medio_dias?.disponivel
                    ? `${b12.atraso_medio_dias.valor} dias`
                    : 'Indisponível'
                }
              />
              <Row
                label="Maior atraso histórico (12 meses)"
                value={
                  b12.maior_atraso_historico_dias?.disponivel
                    ? `${b12.maior_atraso_historico_dias.valor} dias`
                    : 'Indisponível'
                }
              />
              <Row
                label="Último pagamento (12 meses)"
                value={metricaValor(b12.data_ultimo_pagamento, true)}
              />
              <Row
                label="Pagamentos parciais (12 meses)"
                value={textOrUnavailable(b12.quantidade_pagamentos_parciais, true)}
              />
            </>
          ) : (
            <>
              <Row
                label="Pontualidade"
                value={pct(ind.percentual_pontualidade)}
                hint={ind.percentual_pontualidade?.motivo || PLACEHOLDER_SNAPSHOT}
              />
              <Row
                label="Atraso médio"
                value={
                  ind.atraso_medio_dias?.disponivel ? `${ind.atraso_medio_dias.valor} dias` : 'Indisponível'
                }
              />
            </>
          )}
        </dl>
      </Section>

      <Section title="Exposição e limite" testId="dossie-exposicao">
        <dl className="grid gap-2 sm:grid-cols-2">
          <Row label="Contas a receber" value={money(exp?.contas_receber ?? cr?.saldo_aberto)} />
          <Row label="Pedidos não faturados" value={money(exp?.pedidos_nao_faturados ?? ped?.valor_residual)} />
          <Row label="Exposição atual" value={money(exp?.atual)} />
          <Row label="Valor da Proposta" value={money(exp?.valor_proposta)} />
          <Row label="Exposição projetada" value={money(exp?.projetada)} />
          <Row
            label="Limite cadastrado"
            value={limiteAmbiguo ? 'Indisponível' : money(limite?.cadastrado ?? ind.limite_credito_cadastrado?.valor)}
            hint={limiteAmbiguo ? limite?.mensagem || ind.limite_credito_cadastrado?.mensagem || 'Limite não informado ou definido como zero.' : null}
          />
          <Row
            label="Limite disponível antes"
            value={
              limite?.disponivel_antes
                ? money(limite.disponivel_antes.valor, limite.disponivel_antes.disponivel !== false)
                : PLACEHOLDER_SNAPSHOT
            }
          />
          <Row
            label="Limite disponível depois"
            value={
              limite?.disponivel_depois
                ? money(limite.disponivel_depois.valor, limite.disponivel_depois.disponivel !== false)
                : PLACEHOLDER_SNAPSHOT
            }
          />
          <Row
            label="Excesso sobre o limite"
            value={
              limite?.excesso_sobre_limite
                ? money(limite.excesso_sobre_limite.valor, limite.excesso_sobre_limite.disponivel !== false)
                : PLACEHOLDER_SNAPSHOT
            }
          />
        </dl>
      </Section>

      <Section title="Qualidade dos dados" testId="dossie-qualidade">
        <p className="text-sm font-medium" data-testid="dossie-qualidade-status">
          {qualidadeStatus || 'Indisponível'}
        </p>
        <p className="text-sm" role="status" data-testid="analise-fin-aviso-parcial">
          {qualidadeMensagem(qualidadeStatus, ind.qualidade?.mensagem)}
        </p>
        {ind.qualidade?.fonte_historico_comercial ? (
          <p className="text-xs text-muted-foreground">Fonte comercial: {ind.qualidade.fonte_historico_comercial}</p>
        ) : null}
        {(ind.qualidade?.divergencias || []).length > 0 ? (
          <ul className="text-sm list-disc pl-5" data-testid="dossie-divergencias">
            {ind.qualidade!.divergencias!.map((d, i) => (
              <li key={i}>{d.motivo}</li>
            ))}
          </ul>
        ) : null}
        {indisponiveis.length > 0 ? (
          <div data-testid="analise-fin-indisponiveis">
            <p className="text-xs font-medium text-muted-foreground mb-1">Indicadores indisponíveis</p>
            <ul className="text-sm list-disc pl-5 space-y-0.5">
              {indisponiveis.map((item) => (
                <li key={item.indicador}>
                  {item.indicador}: {item.motivo || 'Indisponível'}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Section>

      {secoesExternas}
    </div>
  );
}

export const AVISO_QUALIDADE_PARCIAL = AVISO_PARCIAL;
export const MSG_SNAPSHOT_ANTIGO = PLACEHOLDER_SNAPSHOT;
