import { statusToneClasses, type StatusTone } from '@/design-system/tokens';
import { cn } from '@/lib/utils';

export interface StatusStep {
  key: string;
  label: string;
  tone?: StatusTone;
  clickable?: boolean;
  tooltip?: string;
}

export interface StatusPipelineProps {
  steps: StatusStep[];
  currentKey: string;
  onChange?: (key: string) => void;
  somenteLeitura?: boolean;
  variant?: 'chevron' | 'arrow' | 'pill';
}

const connectorGlyph: Record<'chevron' | 'arrow', string> = {
  chevron: '›',
  arrow: '→',
};

export function StatusPipeline({
  steps,
  currentKey,
  onChange,
  somenteLeitura = false,
  variant = 'chevron',
}: StatusPipelineProps) {
  const currentIndex = steps.findIndex((step) => step.key === currentKey);
  const interactive = !somenteLeitura && Boolean(onChange);

  return (
    <nav
      aria-label="Pipeline de status"
      data-testid="status-pipeline"
      data-variant={variant}
      className="flex flex-col items-start gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:flex-nowrap"
    >
      {steps.map((step, index) => {
        const isCurrent = index === currentIndex;
        const isDone = currentIndex >= 0 && index < currentIndex;
        const isCancelled = step.tone === 'danger';
        const canClick = interactive && !isCancelled && !isCurrent && step.clickable !== false;

        const stateClasses = isCancelled
          ? 'bg-red-50 text-red-700 ring-1 ring-red-200 line-through'
          : isCurrent
            ? 'bg-nexus-orange text-white'
            : isDone
              ? 'bg-nexus-blue text-white'
              : step.tone
                ? statusToneClasses[step.tone].soft
                : 'bg-slate-100 text-slate-600';

        const shapeClasses =
          variant === 'pill' ? 'rounded-full px-4' : 'rounded-sm px-3 sm:px-4';

        const content = (
          <>
            {step.label}
            {isCurrent && !isCancelled && (
              <span
                data-testid="status-pipeline-atual"
                className={cn(
                  'ml-1 rounded-full bg-white/25 px-1.5 py-0.5 text-[10px] font-bold not-italic tracking-wide',
                  'no-underline',
                )}
              >
                ATUAL
              </span>
            )}
          </>
        );

        return (
          <span key={step.key} className="flex items-center gap-1 sm:inline-flex">
            {variant !== 'pill' && index > 0 && (
              <span
                data-testid="status-pipeline-connector"
                aria-hidden="true"
                className="rotate-90 px-0.5 text-sm text-slate-400 sm:rotate-0"
              >
                {connectorGlyph[variant]}
              </span>
            )}
            <button
              type="button"
              data-testid={`status-pipeline-step-${step.key}`}
              disabled={!canClick}
              title={step.tooltip}
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`Estágio ${step.label}${isCurrent ? ' (atual)' : ''}`}
              onClick={() => {
                if (canClick) onChange?.(step.key);
              }}
              className={cn(
                'inline-flex items-center whitespace-nowrap py-1.5 text-xs font-semibold transition-shadow',
                shapeClasses,
                stateClasses,
                canClick ? 'cursor-pointer hover:brightness-110' : 'cursor-default',
              )}
            >
              {content}
            </button>
          </span>
        );
      })}
    </nav>
  );
}
