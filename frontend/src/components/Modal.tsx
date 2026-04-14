import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Modal = ({ isOpen, onClose, title, children, size = 'md' }: ModalProps) => {
  if (!isOpen) return null;
  const sizeClass = { sm: 'max-w-md', md: 'max-w-2xl', lg: 'max-w-4xl', xl: 'max-w-6xl' }[size];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-10 px-4">
      <div className="fixed inset-0 bg-foreground/40" onClick={onClose} />
      <div className={`relative bg-card rounded-lg shadow-xl w-full ${sizeClass} max-h-[85vh] flex flex-col`}>
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
};
