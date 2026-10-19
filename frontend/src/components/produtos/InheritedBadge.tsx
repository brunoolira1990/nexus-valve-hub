import { X } from 'lucide-react';

interface InheritedBadgeProps {
  /** Rótulo humano do campo (ex.: "Norma técnica") — sai no título de acessibilidade. */
  campo: string;
  /** Valor que a família fornece; aparece no título ao passar o mouse. */
  valor: string;
  /** Zera o campo para o usuário digitar um override próprio. */
  onLimpar: () => void;
}

/**
 * Tag de herança família -> produto. Some sozinha quando o valor do produto
 * deixa de ser igual ao da família (override).
 */
export function InheritedBadge({ campo, valor, onLimpar }: InheritedBadgeProps) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200"
      title={`${campo}: ${valor || '—'} (herdado da Família/Figura)`}
    >
      Herdado da Família
      <button
        type="button"
        onClick={onLimpar}
        aria-label={`Remover herança de ${campo} e digitar outro valor`}
        className="rounded-full p-0.5 text-sky-700 transition-colors hover:bg-sky-100 hover:text-sky-950 dark:text-sky-300 dark:hover:bg-sky-500/20"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}
