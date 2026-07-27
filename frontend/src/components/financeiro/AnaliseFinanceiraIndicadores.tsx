import { formatMoneyBRL } from '@/lib/money';

const AVISO_PARCIAL =
  'Alguns indicadores não puderam ser calculados com os dados disponíveis. A decisão deve ser revisada manualmente pelo Financeiro.';

type MetricBlock = {
  disponivel?: boolean;
  valor?: string | number | null;
  motivo?: string;
};

type SnapshotIndicadores = {
  qualidade_dados?: string;
  dados_indisponiveis?: string[];
  data_corte?: string;
  resumo_restrito?: boolean;
  limite_credito_cadastrado?: MetricBlock & { valor?: string | null };
  contas_receber?: {
    disponivel?: boolean;
    saldo_aberto?: string | null;
    saldo_a_vencer?: string | null;
    saldo_vencido?: string | null;
    quantidade_titulos_vencidos?: number | null;
  };
  pedidos_nao_faturados?: {
    disponivel?: boolean;
    valor_residual?: string | null;
    quantidade_pedidos?: number | null;
  };
  exposicao?: {
    atual?: string | null;
    projetada?: string | null;
    valor_proposta?: string | null;
  };
  percentual_pontualidade?: MetricBlock;
  atraso_medio_dias?: MetricBlock;
  data_ultima_compra?: MetricBlock;
  valor_comprado_12_meses?: MetricBlock;
};

function moneyOrUnavailable(value: string | number | null | undefined, disponivel = true): string {
  if (!disponivel || value === null || value === undefined || value === '') return 'Indisponível';
  const n = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(n)) return 'Indisponível';
  return formatMoneyBRL(n);
}

function qtyOrUnavailable(value: number | null | undefined, disponivel = true): string {
  if (!disponivel || value === null || value === undefined) return 'Indisponível';
  return String(value);
}

function labelIndisponivel(chave: string): string {
  const map: Record<string, string> = {
    percentual_pontualidade: 'Percentual de pontualidade',
    atraso_medio_dias: 'Atraso médio (dias)',
    valor_pago_periodo: 'Valor pago no período',
    data_ultima_compra: 'Data da última compra',
    valor_comprado_12_meses: 'Valor comprado (12 meses)',
    quantidade_pedidos_historico: 'Quantidade de pedidos históricos',
  };
  return map[chave] || chave;
}

type Props = {
  snapshot?: Record<string, unknown> | SnapshotIndicadores | null;
};

export function AnaliseFinanceiraIndicadores({ snapshot }: Props) {
  const ind = (snapshot || {}) as SnapshotIndicadores;

  if (ind.resumo_restrito) {
    return (
      <div className="rounded border border-border bg-muted/20 p-3 space-y-2" data-testid="analise-fin-indicadores">
        <p className="text-sm font-medium">Indicadores financeiros</p>
        <p className="text-sm text-muted-foreground">
          Detalhe financeiro restrito. Qualidade dos dados:{' '}
          {ind.qualidade_dados || 'Indisponível'}.
        </p>
        {ind.qualidade_dados === 'PARCIAL' || ind.qualidade_dados === 'INSUFICIENTE' ? (
          <p className="text-sm text-amber-900" role="status" data-testid="analise-fin-aviso-parcial">
            {AVISO_PARCIAL}
          </p>
        ) : null}
      </div>
    );
  }

  const cr = ind.contas_receber || {};
  const ped = ind.pedidos_nao_faturados || {};
  const exp = ind.exposicao || {};
  const lim = ind.limite_credito_cadastrado || {};
  const indisponiveis = Array.isArray(ind.dados_indisponiveis) ? ind.dados_indisponiveis : [];

  const rows: { label: string; value: string }[] = [
    {
      label: 'Limite de crédito cadastrado',
      value: moneyOrUnavailable(lim.valor, lim.disponivel !== false),
    },
    {
      label: 'Saldo total a receber',
      value: moneyOrUnavailable(cr.saldo_aberto, cr.disponivel !== false),
    },
    {
      label: 'Saldo a vencer',
      value: moneyOrUnavailable(cr.saldo_a_vencer, cr.disponivel !== false),
    },
    {
      label: 'Saldo vencido',
      value: moneyOrUnavailable(cr.saldo_vencido, cr.disponivel !== false),
    },
    {
      label: 'Títulos vencidos',
      value: qtyOrUnavailable(cr.quantidade_titulos_vencidos, cr.disponivel !== false),
    },
    {
      label: 'Pedidos aprovados ainda não faturados',
      value: moneyOrUnavailable(ped.valor_residual, ped.disponivel !== false),
    },
    {
      label: 'Exposição atual',
      value: moneyOrUnavailable(exp.atual),
    },
    {
      label: 'Valor da Proposta',
      value: moneyOrUnavailable(exp.valor_proposta),
    },
    {
      label: 'Exposição projetada',
      value: moneyOrUnavailable(exp.projetada),
    },
    {
      label: 'Qualidade dos dados',
      value: ind.qualidade_dados || 'Indisponível',
    },
  ];

  return (
    <div className="rounded border border-border bg-muted/20 p-3 space-y-3" data-testid="analise-fin-indicadores">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">Indicadores financeiros</p>
        {ind.data_corte ? (
          <p className="text-xs text-muted-foreground">
            Corte: {new Date(`${ind.data_corte}T12:00:00`).toLocaleDateString('pt-BR')}
          </p>
        ) : null}
      </div>

      {ind.qualidade_dados === 'PARCIAL' || ind.qualidade_dados === 'INSUFICIENTE' ? (
        <p
          className="text-sm border border-amber-700/40 bg-amber-50 text-amber-950 rounded px-2 py-1.5"
          role="status"
          data-testid="analise-fin-aviso-parcial"
        >
          {AVISO_PARCIAL}
        </p>
      ) : null}

      <dl className="grid gap-2 sm:grid-cols-2 text-sm">
        {rows.map((row) => (
          <div key={row.label} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{row.label}</dt>
            <dd className="font-medium tabular-nums" data-testid={`indicador-${row.label}`}>
              {row.value}
            </dd>
          </div>
        ))}
      </dl>

      {indisponiveis.length > 0 ? (
        <div data-testid="analise-fin-indisponiveis">
          <p className="text-xs font-medium text-muted-foreground mb-1">Indicadores indisponíveis</p>
          <ul className="text-sm list-disc pl-5 space-y-0.5">
            {indisponiveis.map((chave) => (
              <li key={chave}>
                {labelIndisponivel(chave)}: Indisponível
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export const AVISO_QUALIDADE_PARCIAL = AVISO_PARCIAL;
