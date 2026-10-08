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

/**
 * Cabeçalho de página padronizado do Nexus ERP.
 *
 * Anatomia consistente:
 * 1. Breadcrumb (quando fornecido) — contexto de navegação.
 * 2. Bloco de título: título + badges de contexto (ex.: ambiente fiscal),
 *    descrição e meta, no mesmo fluxo visual.
 * 3. Barra de ações (busca + botão primário) alinhada à direita em desktop,
 *    ancorada na linha do título em vez de flutuar isolada.
 * 4. `children` — área reservada para filtros de listagem integrados abaixo
 *    do título (padrão recomendado em vez de selects soltos no topo).
 */
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
          className={cn(
            // Largura controlada pelo container: mobile 100%, desktop ≥320px sem comprimir.
            'w-full min-w-0 max-w-full',
            'sm:min-w-[20rem] sm:w-[22rem] md:w-96 md:max-w-md',
            'grow basis-full sm:basis-auto sm:grow-0',
          )}
        />
      ) : null}
      {onAdd ? (
        <NexusButton type="button" onClick={onAdd} className="shrink-0">
          <Plus className="h-4 w-4" />
          {addLabel}
        </NexusButton>
      ) : null}
    </>
  );

  const hasToolbar = !!(actions ?? (onSearch || onAdd));

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

      {/* Bloco de título com ações ancoradas na mesma linha (desktop) */}
      <div className={cn('flex flex-col gap-4', hasToolbar ? 'lg:flex-row lg:items-center lg:justify-between' : '')}>
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="nexus-heading-lg">{title}</h1>
            {badges}
          </div>
          {description ? <p className="text-sm text-muted-foreground max-w-3xl">{description}</p> : null}
          {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
        </div>

        {hasToolbar ? (
          <div
            className={cn(
              'flex flex-wrap items-center gap-2',
              'w-full lg:w-auto lg:max-w-[min(100%,28rem)] xl:max-w-none',
              'lg:justify-end lg:shrink-0',
            )}
          >
            {actions ?? defaultActions}
          </div>
        ) : null}
      </div>

      {/* Filtros integrados abaixo do título — fluxo natural da página */}
      {children}
    </header>
  );
};

export { Badge as PageHeaderBadge };
