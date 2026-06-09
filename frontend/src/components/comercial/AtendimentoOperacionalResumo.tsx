import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import { NexusCard } from '@/components/nexus/NexusCard';
import { AtendimentoOperacionalBadge } from '@/components/comercial/AtendimentoOperacionalBadge';
import { cn } from '@/lib/utils';

type Props = {
  resumo: ResumoAtendimentoOperacional | null | undefined;
  titulo?: string;
  compacto?: boolean;
  className?: string;
  /** Oculta quando não há alocação (evita poluir listagens). */
  ocultarSemAlocacao?: boolean;
};

function BadgesRow({ badges }: { badges: ResumoAtendimentoOperacional['badges'] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {badges.slice(0, 6).map((b) => (
        <AtendimentoOperacionalBadge key={b.status} badge={b} />
      ))}
    </div>
  );
}

function labelVinculo(ok: boolean | undefined, sim: string, nao: string): string {
  if (ok === undefined) return 'Não vinculado';
  return ok ? sim : nao;
}

export function AtendimentoOperacionalResumo({
  resumo,
  titulo = 'Atendimento operacional',
  compacto = false,
  className,
  ocultarSemAlocacao = false,
}: Props) {
  if (!resumo) return null;
  if (ocultarSemAlocacao && !resumo.tem_alocacao) return null;

  const badges = resumo.badges ?? [];
  const mensagem = resumo.mensagem?.trim();
  const alertas = resumo.alertas ?? [];

  if (compacto) {
    return (
      <div className={cn('space-y-1', className)}>
        {badges.length > 0 ? <BadgesRow badges={badges} /> : null}
        {mensagem ? <p className="text-xs text-muted-foreground">{mensagem}</p> : null}
      </div>
    );
  }

  return (
    <NexusCard className={cn('p-3 space-y-2', className)}>
      <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{titulo}</h4>
      {badges.length > 0 ? <BadgesRow badges={badges} /> : null}
      {mensagem ? <p className="text-sm text-muted-foreground">{mensagem}</p> : null}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground pt-1 border-t border-border">
        <dt>Tipo</dt>
        <dd className="text-foreground">
          {resumo.tipo_atendimento_label ||
            (resumo.tipo_principal ? resumo.tipo_principal.replace(/_/g, ' ') : 'Não definido')}
        </dd>
        <dt>Entrada fiscal</dt>
        <dd className="text-foreground">
          {resumo.status_entrada_fiscal_label ||
            (resumo.status_entrada_principal
              ? resumo.status_entrada_principal.replace(/_/g, ' ')
              : 'Indefinido')}
        </dd>
        <dt>Origem</dt>
        <dd className="text-foreground">
          {resumo.origem_fisica_label ||
            (resumo.origem_fisica_principal
              ? resumo.origem_fisica_principal.replace(/_/g, ' ')
              : 'Indefinida')}
        </dd>
        <dt>Destino</dt>
        <dd className="text-foreground">
          {resumo.destino_fisico_label ||
            (resumo.destino_fisico_principal
              ? resumo.destino_fisico_principal.replace(/_/g, ' ')
              : 'Indefinido')}
        </dd>
        <dt>Compra vinculada</dt>
        <dd className="text-foreground">
          {labelVinculo(resumo.tem_compra_vinculada, 'Sim', 'Não definida')}
        </dd>
        <dt>NF-e entrada</dt>
        <dd className="text-foreground">
          {labelVinculo(
            resumo.tem_nfe_entrada_vinculada,
            'Vinculada/conferida',
            'Não vinculada',
          )}
        </dd>
        <dt>CT-e</dt>
        <dd className="text-foreground">
          {labelVinculo(resumo.tem_cte_vinculado, 'Conferido/vinculado', 'Não definido')}
        </dd>
      </dl>
      {alertas.length > 0 ? (
        <ul className="text-xs text-amber-800 dark:text-amber-200 space-y-1 list-disc pl-4 border-t border-border pt-2">
          {alertas.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      ) : null}
      <p className="text-[10px] text-muted-foreground border-t border-border pt-2">
        Informação operacional — não bloqueia emissão, financeiro ou estoque.
      </p>
    </NexusCard>
  );
}
