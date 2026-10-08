import type { NFeReformaTributariaPayload } from '@/types';

type Props = {
  payload: NFeReformaTributariaPayload | null | undefined;
};

export function NFeReformaTributariaResumo({ payload }: Props) {
  if (!payload) {
    return (
      <p className="text-sm text-muted-foreground">Reforma Tributária não aplicada a esta NF-e.</p>
    );
  }

  const { status, status_label, alerta_homologacao, itens, totais, config } = payload;

  return (
    <div className="space-y-3 text-sm">
      <p className="font-medium text-foreground">{status_label}</p>
      <p className="text-xs text-muted-foreground">
        Modo: {config.modo} · XML: {config.incluir_xml ? 'ativo' : 'desligado'} · DANFE:{' '}
        {config.incluir_danfe ? 'ativo' : 'desligado'}
      </p>
      {alerta_homologacao ? (
        <p className="text-xs text-amber-700 dark:text-amber-400 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5">
          {alerta_homologacao}
        </p>
      ) : null}
      {(status === 'preparacao' || status === 'configurada_sem_xml' || status === 'nao_preparada') &&
      !itens?.length ? (
        <p className="text-xs text-muted-foreground">
          Estrutura em pesquisa/preparação. XML e DANFE seguem layout atual (sem grupos RTC nesta fase).
        </p>
      ) : null}
      {itens && itens.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Itens</p>
          <ul className="space-y-1 text-xs">
            {itens.map((row) => (
              <li key={row.item_id} className="rounded border border-border/80 px-2 py-1">
                Item #{row.item_id} — CST {row.cst || '—'} · CBS R$ {row.cbs?.valor ?? '0.00'} · IBS R${' '}
                {row.ibs?.total ?? '0.00'}
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            Totais conferência: CBS {totais.valor_cbs} · IBS {totais.valor_ibs}
          </p>
        </div>
      ) : null}
      {config.producao_bloqueada ? (
        <p className="text-xs text-muted-foreground">Geração em produção bloqueada até validação oficial.</p>
      ) : null}
    </div>
  );
}
