import { Wallet } from 'lucide-react';
import { fmtMoeda } from '@/lib/nfeSaidaConferencia';
import { isAutorizadaHomologacao } from '@/lib/nfeSaidaUi';
import { isAutorizadaProducao } from '@/lib/nfeSaidaAcoesMatriz';
import { NFeFinanceiroAcoes } from '@/components/fiscal/NFeFinanceiroAcoes';

type FinanceiroFlags = {
  financeiro_gerado?: boolean;
  pode_gerar_contas_receber?: boolean;
  motivo_bloqueio_financeiro?: string;
  contas_receber_vinculadas?: Array<{ id: number; numero: string; status?: string }>;
  nfe_cancelada_com_financeiro?: boolean;
};

type Props = {
  nfeId: number;
  status?: string;
  statusEmissaoSefaz?: string;
  resumoEmissaoSefaz?: { status_emissao_sefaz?: string; nfe?: { cstat?: string } } | null;
  financeiro?: FinanceiroFlags | null;
  numeroNfe?: string;
  serieNfe?: string;
  clienteNome?: string;
  valorTotal?: number | string;
  quantidadeParcelas?: number | null;
  onGerar: () => void;
};

function statusFinanceiroLabel(flags: FinanceiroFlags): { texto: string; tone: 'muted' | 'success' | 'warning' } {
  if (flags.financeiro_gerado) {
    return {
      texto: flags.motivo_bloqueio_financeiro || 'Contas a receber já foram geradas para esta NF-e.',
      tone: 'success',
    };
  }
  if (flags.pode_gerar_contas_receber) {
    return { texto: 'Contas a receber não geradas', tone: 'warning' };
  }
  if (flags.motivo_bloqueio_financeiro) {
    return { texto: flags.motivo_bloqueio_financeiro, tone: 'muted' };
  }
  return { texto: 'Disponível após autorização da NF-e.', tone: 'muted' };
}

export function NFeFinanceiroPanel({
  nfeId,
  status,
  statusEmissaoSefaz,
  resumoEmissaoSefaz,
  financeiro,
  numeroNfe,
  serieNfe,
  clienteNome,
  valorTotal,
  quantidadeParcelas,
  onGerar,
}: Props) {
  const flags = financeiro ?? {};
  const statusInfo = statusFinanceiroLabel(flags);
  const autorizadaHomolog = isAutorizadaHomologacao({
    status: status ?? '',
    status_emissao_sefaz: statusEmissaoSefaz,
    resumo_emissao_sefaz: resumoEmissaoSefaz ?? undefined,
  });
  const autorizadaProducao = isAutorizadaProducao(
    {
      status: status ?? '',
      status_emissao_sefaz: statusEmissaoSefaz,
      resumo_emissao_sefaz: resumoEmissaoSefaz ?? undefined,
    },
    resumoEmissaoSefaz ?? undefined,
  );
  const vinculados = flags.contas_receber_vinculadas ?? [];

  const statusClass =
    statusInfo.tone === 'success'
      ? 'border-emerald-600/30 bg-emerald-600/5 text-emerald-900 dark:text-emerald-100'
      : statusInfo.tone === 'warning'
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
        : 'border-border bg-muted/20 text-muted-foreground';

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2">
        <Wallet className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium">Contas a receber</p>
          <p className="text-xs text-muted-foreground">
            Geração manual a partir da NF-e autorizada em produção. Homologação não gera financeiro.
          </p>
        </div>
      </div>

      <div className={`rounded-md border px-3 py-2 text-sm ${statusClass}`}>{statusInfo.texto}</div>

      {flags.nfe_cancelada_com_financeiro ? (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
          A NF-e de origem foi cancelada. Revise os títulos financeiros vinculados.
        </p>
      ) : null}

      <div className="rounded-md border border-border p-3 space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Resumo da origem</p>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">NF-e</dt>
            <dd className="font-medium">{numeroNfe?.trim() || `#${nfeId}`}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Série</dt>
            <dd>{serieNfe?.trim() || '—'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-muted-foreground">Cliente</dt>
            <dd>{clienteNome?.trim() || '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Valor total</dt>
            <dd className="font-semibold">{fmtMoeda(valorTotal ?? 0)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Parcelas</dt>
            <dd>
              {quantidadeParcelas != null && quantidadeParcelas > 0
                ? quantidadeParcelas
                : flags.financeiro_gerado && vinculados.length
                  ? `${vinculados.length} título(s) vinculado(s)`
                  : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Origem</dt>
            <dd>NFE_SAIDA</dd>
          </div>
          {autorizadaProducao ? (
            <div>
              <dt className="text-xs text-muted-foreground">Ambiente</dt>
              <dd>Produção</dd>
            </div>
          ) : autorizadaHomolog ? (
            <div>
              <dt className="text-xs text-muted-foreground">Ambiente</dt>
              <dd>Homologação</dd>
            </div>
          ) : null}
        </dl>
      </div>

      {vinculados.length ? (
        <div className="rounded-md border border-border p-3 space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Títulos vinculados</p>
          <ul className="text-sm space-y-1">
            {vinculados.map((t) => (
              <li key={t.id}>
                {t.numero}
                {t.status ? <span className="text-xs text-muted-foreground ml-2">({t.status})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded-md border border-border p-3 space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Ações</p>
        <NFeFinanceiroAcoes
          nfeId={nfeId}
          status={status}
          statusEmissaoSefaz={statusEmissaoSefaz}
          resumoEmissaoSefaz={resumoEmissaoSefaz}
          financeiro={financeiro}
          onGerar={onGerar}
        />
      </div>
    </div>
  );
}
