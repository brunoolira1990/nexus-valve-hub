import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { PageHeader, type BreadcrumbItem } from '@/components/PageHeader';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

type WorkspaceLayoutProps = {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  onSave?: () => void;
  onClose?: () => void;
  saving?: boolean;
  saveLabel?: string;
  closeLabel?: string;
  error?: string | null;
  meta?: { label: string; value: ReactNode; className?: string }[];
  tabs: {
    value: string;
    label: string;
    icon?: LucideIcon;
    content: ReactNode;
  }[];
  defaultTab?: string;
  activeTab?: string;
  onTabChange?: (value: string) => void;
  className?: string;
};

export function WorkspaceLayout({
  title,
  subtitle,
  breadcrumbs,
  actions,
  onSave,
  onClose,
  saving = false,
  saveLabel = 'Salvar',
  closeLabel = 'Voltar',
  error,
  meta,
  tabs,
  defaultTab,
  activeTab,
  onTabChange,
  className,
}: WorkspaceLayoutProps) {
  return (
    <div className={`px-4 pb-5 sm:px-5 sm:pb-6 space-y-3 ${className ?? ''}`}>
      <PageHeader
        title={title}
        description={subtitle}
        breadcrumbs={breadcrumbs}
        actions={
          <div className="flex items-center gap-2">
            {actions}
            {onClose && (
              <button type="button" className="erp-btn-outline" onClick={onClose}>
                {closeLabel}
              </button>
            )}
            {onSave && (
              <button type="button" className="erp-btn-primary" onClick={onSave} disabled={saving}>
                {saving ? 'Salvando…' : saveLabel}
              </button>
            )}
          </div>
        }
      />

      {error && (
        <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2">
          {error}
        </p>
      )}

      {meta && meta.length > 0 && (
        <div className="grid grid-cols-2 gap-x-3.5 gap-y-1.5 rounded-lg border border-border bg-muted/15 px-2.5 py-1.5 text-sm sm:grid-cols-2 lg:grid-cols-4 lg:gap-x-3 lg:gap-y-1.5">
          {meta.map((item, idx) => (
            <div key={idx} className={item.className}>
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground/80 block">{item.label}</span>
              <span className="font-semibold text-foreground truncate block">{item.value}</span>
            </div>
          ))}
        </div>
      )}

      <Tabs
        value={activeTab}
        defaultValue={activeTab ? undefined : (defaultTab ?? tabs[0]?.value)}
        onValueChange={onTabChange}
        className="flex flex-col min-h-0"
      >
        <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value} className="inline-flex items-center gap-2">
              {t.icon && <t.icon className="h-4 w-4" />}
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="border border-border border-t-0 rounded-b-lg bg-card px-4 py-3.5 sm:px-5 sm:py-4 min-h-0 flex-1">
          {tabs.map((t) => (
            <TabsContent key={t.value} value={t.value} className="mt-0">
              {t.content}
            </TabsContent>
          ))}
        </div>
      </Tabs>
    </div>
  );
}
