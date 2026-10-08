import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';

// As regras e o conteúdo permanecem em Propostas.tsx, fonte única do formulário.
export default function PropostaForm({ isOpen, title, onCancel, children }: {
  isOpen: boolean;
  title: string;
  onCancel: () => void;
  children: ReactNode;
}) {
  if (!isOpen) return null;
  return (
    <section className="min-w-0 space-y-4">
      <PageHeader title={title} description="Dados da proposta comercial" actions={
        <button type="button" onClick={onCancel} className="erp-btn-outline">
          <ArrowLeft className="mr-2 h-4 w-4" />Voltar para listagem
        </button>
      } />
      {children}
    </section>
  );
}
