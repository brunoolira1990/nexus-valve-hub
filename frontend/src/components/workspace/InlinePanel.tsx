import type { ReactNode } from 'react';

type InlinePanelProps = {
  title: string;
  description?: string;
  onCancel: () => void;
  onSave: () => void;
  saving?: boolean;
  saveLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'destructive';
  error?: string | null;
  children: ReactNode;
};

export function InlinePanel({
  title,
  description,
  onCancel,
  onSave,
  saving = false,
  saveLabel = 'Salvar',
  cancelLabel = 'Cancelar',
  variant = 'default',
  error,
  children,
}: InlinePanelProps) {
  const accentClass = variant === 'destructive' ? 'border-l-destructive' : 'border-l-primary';
  const saveBtnClass = variant === 'destructive' ? 'erp-btn-destructive' : 'erp-btn-primary';

  return (
    <div className={`rounded-lg border border-border border-l-4 ${accentClass} bg-card p-4 sm:p-5`}>
      <header className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
          {description && (
            <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{description}</p>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-2">
          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={onCancel} disabled={saving}>
            {cancelLabel}
          </button>
          <button type="button" className={`${saveBtnClass} erp-btn-sm`} onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : saveLabel}
          </button>
        </div>
      </header>

      {error && (
        <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 mb-4">
          {error}
        </p>
      )}

      <div className="space-y-4">{children}</div>
    </div>
  );
}