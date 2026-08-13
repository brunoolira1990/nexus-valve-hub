import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Conteúdo fixo no rodapé (ex.: resumo + botões), fora da área com scroll. */
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'focus';
  /** Sobrepõe outro modal (portal no body, z-index maior). */
  stacked?: boolean;
  /** Subtítulo ou identificador exibido abaixo do título (ex.: nº do pedido). */
  subtitle?: ReactNode;
  /** Badge de status ao lado do título (ex.: Rascunho). */
  badge?: ReactNode;
}

/**
 * Modal padronizado do Nexus ERP.
 *
 * Anatomia consistente:
 * - Cabeçalho fixo com título + (opcional) subtítulo/badge e botão de fechar.
 * - Corpo com scroll interno e padding uniforme (nunca cola nas bordas).
 * - Rodapé fixo com ações (Cancelar / Salvar), sempre visível e alinhado à direita —
 *   o scroll do corpo nunca esconde os botões.
 */
export const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  stacked = false,
  subtitle,
  badge,
}: ModalProps) => {
  if (isOpen === false) return null;
  const sizeClass = {
    sm: 'max-w-md',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-6xl',
    '2xl': 'max-w-[1200px]',
    focus: 'max-w-[1100px]',
  }[size];

  const zClass = stacked ? 'z-[70]' : 'z-50';
  const overlayClass = stacked ? 'bg-foreground/60' : 'bg-foreground/50';

  const modal = (
    <div
      className={`fixed inset-0 ${zClass} flex items-start justify-center px-3 py-6 sm:px-4 pointer-events-none`}
    >
      <div
        className={`fixed inset-0 ${overlayClass} backdrop-blur-[2px] pointer-events-auto`}
        onClick={onClose}
        aria-hidden
      />
      <div
        className={`relative z-10 pointer-events-auto bg-card rounded-lg shadow-2xl border border-border w-full ${sizeClass} max-h-[88vh] flex flex-col min-h-0`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Cabeçalho fixo */}
        <div className="shrink-0 flex items-start justify-between gap-3 px-5 pt-5 pb-4 border-b border-border">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 id="modal-title" className="text-lg font-semibold leading-tight truncate">
                {title}
              </h2>
              {badge}
            </div>
            {subtitle ? (
              <p className="text-sm text-muted-foreground mt-0.5 truncate">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Corpo com scroll — padding uniforme, sem colar nas bordas */}
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-5">{children}</div>

        {/* Rodapé fixo com ações — sempre visível */}
        {footer ? (
          <div className="shrink-0 flex items-center justify-end gap-2 px-5 py-4 border-t border-border bg-muted/40">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );

  if (stacked && typeof document !== 'undefined') {
    return createPortal(modal, document.body);
  }
  return modal;
};

/**
 * Botões padrão "Cancelar / Salvar" para o footer do Modal.
 */
export const ModalFooterActions = ({
  onCancel,
  onSave,
  saveLabel = 'Salvar',
  cancelLabel = 'Cancelar',
  saving = false,
}: {
  onCancel: () => void;
  onSave: () => void;
  saveLabel?: string;
  cancelLabel?: string;
  saving?: boolean;
}) => (
  <>
    <button
      type="button"
      onClick={onCancel}
      className="h-9 px-4 rounded-md border border-border bg-card text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
    >
      {cancelLabel}
    </button>
    <button
      type="button"
      onClick={onSave}
      disabled={saving}
      className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
    >
      {saving ? 'Salvando…' : saveLabel}
    </button>
  </>
);
