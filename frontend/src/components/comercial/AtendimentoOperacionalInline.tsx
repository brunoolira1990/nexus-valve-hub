import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';
import { AtendimentoOperacionalBadge } from '@/components/comercial/AtendimentoOperacionalBadge';
import { cn } from '@/lib/utils';

type Props = {
  resumo: ResumoAtendimentoOperacional | null | undefined;
  className?: string;
  /** Quando false, exibe badge «não definido» na listagem. */
  apenasComAlocacao?: boolean;
  /** Máximo de badges na linha (listagens). */
  maxBadges?: number;
};

/** Badges em linha para listagens e cabeçalhos compactos. */
export function AtendimentoOperacionalInline({
  resumo,
  className,
  apenasComAlocacao = true,
  maxBadges = 3,
}: Props) {
  if (!resumo) return null;
  if (apenasComAlocacao && !resumo.tem_alocacao) return null;
  const badges = (resumo.badges ?? []).slice(0, maxBadges);
  if (!badges.length) return null;

  return (
    <div className={cn('flex flex-wrap gap-1', className)}>
      {badges.map((b) => (
        <AtendimentoOperacionalBadge key={b.status} badge={b} />
      ))}
    </div>
  );
}

/** Alias do spec ERP 4.0.11. */
export const AtendimentoOperacionalBadges = AtendimentoOperacionalInline;
