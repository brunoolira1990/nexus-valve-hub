import { useState, type ReactNode } from 'react';

type ItemConferenciaCompactoProps = {
  className?: string;
  resumo: ReactNode;
  children: ReactNode;
};

export function ItemConferenciaCompacto({ className, resumo, children }: ItemConferenciaCompactoProps) {
  const [aberto, setAberto] = useState(false);

  return (
    <details className={className} onToggle={(e) => setAberto(e.currentTarget.open)}>
      <summary className="flex cursor-pointer flex-wrap items-center gap-3 p-4">
        {resumo}
        <span className="ml-auto text-xs">{aberto ? 'Recolher detalhes' : 'Expandir detalhes'}</span>
      </summary>
      {children}
    </details>
  );
}
