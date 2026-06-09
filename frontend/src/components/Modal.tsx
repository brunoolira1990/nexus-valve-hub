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
}

export const Modal = ({ isOpen, onClose, title, children, footer, size = 'md', stacked = false }: ModalProps) => {
  if (!isOpen) return null;
  const sizeClass = {
    sm: 'max-w-md',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-6xl',
    '2xl': 'max-w-[1200px]',
    focus: 'max-w-[1100px]',
  }[size];

  const zClass = stacked ? 'z-[70]' : 'z-50';
  const overlayClass = stacked ? 'bg-foreground/55' : 'bg-foreground/40';

  const modal = (
    <div className={`fixed inset-0 ${zClass} flex items-start justify-center pt-4 pb-4 px-3 sm:pt-8 sm:px-4`}>
      <div className={`fixed inset-0 ${overlayClass}`} onClick={onClose} aria-hidden />
      <div
        className={`relative bg-card rounded-lg nexus-modal-shadow w-full ${sizeClass} max-h-[85vh] flex flex-col min-h-0`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="flex shrink-0 items-center justify-between p-4 border-b border-border bg-card sticky top-0 z-10 rounded-t-lg">
          <h2 id="modal-title" className="text-lg font-semibold pr-2">
            {title}
          </h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground shrink-0">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto p-4">{children}</div>
        {footer ? (
          <div className="shrink-0 border-t border-border bg-card sticky bottom-0 z-10 rounded-b-lg">{footer}</div>
        ) : null}
      </div>
    </div>
  );

  if (stacked && typeof document !== 'undefined') {
    return createPortal(modal, document.body);
  }
  return modal;
};
