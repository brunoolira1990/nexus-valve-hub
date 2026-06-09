import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type CardVariant = 'default' | 'kpi' | 'alert' | 'info' | 'action' | 'preparation';

const variantClasses: Record<CardVariant, string> = {
  default: 'nexus-card',
  kpi: 'nexus-card border-primary/15 bg-gradient-to-br from-card to-primary/5',
  alert: 'nexus-card border-warning/30 bg-warning/5',
  info: 'nexus-card border-info/30 bg-info/5',
  action: 'nexus-card border-dashed',
  preparation: 'nexus-card border-violet-200 bg-violet-50/40',
};

interface NexusCardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  variant?: CardVariant;
  clickable?: boolean;
  onClick?: () => void;
  className?: string;
}

export function NexusCard({
  title,
  subtitle,
  actions,
  footer,
  children,
  variant = 'default',
  clickable,
  onClick,
  className,
}: NexusCardProps) {
  const body = (
    <>
      {(title || subtitle || actions) && (
        <div className="flex items-start justify-between gap-3 px-[var(--card-padding)] pt-[var(--card-padding)]">
          <div>
            {title ? <h3 className="nexus-heading-md">{title}</h3> : null}
            {subtitle ? <p className="nexus-caption mt-1">{subtitle}</p> : null}
          </div>
          {actions ? <div className="shrink-0 flex items-center gap-2">{actions}</div> : null}
        </div>
      )}
      {children ? (
        <div
          className={cn(
            'px-[var(--card-padding)]',
            title || subtitle || actions ? 'pt-3 pb-[var(--card-padding)]' : 'py-[var(--card-padding)]',
          )}
        >
          {children}
        </div>
      ) : null}
      {footer ? (
        <div className="border-t border-border/60 mt-1 pt-3 mx-[var(--card-padding)] mb-[var(--card-padding)]">
          {footer}
        </div>
      ) : null}
    </>
  );

  if (clickable) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(variantClasses[variant], 'nexus-card-clickable text-left w-full', className)}
      >
        {body}
      </button>
    );
  }

  return <div className={cn(variantClasses[variant], className)}>{body}</div>;
}
