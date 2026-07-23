import type { ReactNode } from 'react';
import { Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { NexusButton } from '@/components/nexus';
import { SearchInput } from '@/components/nexus/inputs';
import { Badge } from '@/components/nexus/Badge';
import { cn } from '@/lib/utils';

export interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  /** Slot para ações customizadas (prioridade sobre onAdd). */
  actions?: ReactNode;
  badges?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** Compatibilidade legada */
  onAdd?: () => void;
  addLabel?: string;
  searchValue?: string;
  onSearch?: (val: string) => void;
  searchPlaceholder?: string;
}

export const PageHeader = ({
  title,
  description,
  breadcrumbs,
  actions,
  badges,
  meta,
  children,
  className,
  onAdd,
  addLabel = 'Novo',
  searchValue,
  onSearch,
  searchPlaceholder,
}: PageHeaderProps) => {
  const defaultActions = (
    <>
      {onSearch ? (
        <SearchInput
          value={searchValue}
          onChange={onSearch}
          placeholder={searchPlaceholder}
          className={searchPlaceholder ? 'sm:min-w-[18rem] sm:w-80' : undefined}
        />
      ) : null}
      {onAdd ? (
        <NexusButton type="button" onClick={onAdd}>
          <Plus className="h-4 w-4" />
          {addLabel}
        </NexusButton>
      ) : null}
    </>
  );

  return (
    <header className={cn('mb-[var(--section-gap)] space-y-3', className)}>
      {breadcrumbs?.length ? (
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
          {breadcrumbs.map((bc, i) => (
            <span key={`${bc.label}-${i}`} className="inline-flex items-center gap-1">
              {i > 0 ? <span className="opacity-50">/</span> : null}
              {bc.path ? (
                <Link to={bc.path} className="hover:text-foreground transition-colors">
                  {bc.label}
                </Link>
              ) : (
                <span className="text-foreground/80">{bc.label}</span>
              )}
            </span>
          ))}
        </nav>
      ) : null}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="nexus-heading-lg">{title}</h1>
            {badges}
          </div>
          {description ? <p className="text-sm text-muted-foreground max-w-3xl">{description}</p> : null}
          {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions ?? defaultActions}</div>
      </div>
      {children}
    </header>
  );
};

export { Badge as PageHeaderBadge };
