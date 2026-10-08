import { DrawerClose } from '@/components/ui/drawer';

export type FinanceiroDrawerAcao = {
  id: string;
  label: string;
  variant?: 'primary' | 'outline' | 'destructive';
  onClick: () => void;
};

type Props = {
  principal: FinanceiroDrawerAcao[];
  secundarias: FinanceiroDrawerAcao[];
  perigosas: FinanceiroDrawerAcao[];
};

function btnClass(variant?: FinanceiroDrawerAcao['variant']) {
  if (variant === 'primary') return 'erp-btn-primary';
  if (variant === 'destructive') return 'erp-btn-outline text-destructive';
  return 'erp-btn-outline';
}

export function FinanceiroDrawerFooterAcoes({ principal, secundarias, perigosas }: Props) {
  const renderGrupo = (acoes: FinanceiroDrawerAcao[], titulo?: string) => {
    if (!acoes.length) return null;
    return (
      <div className="flex flex-col gap-1.5 w-full sm:w-auto">
        {titulo ? <span className="text-[10px] uppercase tracking-wide text-muted-foreground px-0.5">{titulo}</span> : null}
        <div className="flex flex-wrap gap-2">
          {acoes.map((acao) => (
            <button
              key={acao.id}
              type="button"
              className={btnClass(acao.variant)}
              onClick={acao.onClick}
            >
              {acao.label}
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="border-t border-border px-4 py-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between w-full">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        {renderGrupo(principal, principal.length ? 'Principal' : undefined)}
        {renderGrupo(secundarias, secundarias.length ? 'Outras ações' : undefined)}
        {renderGrupo(perigosas, perigosas.length ? 'Ações sensíveis' : undefined)}
      </div>
      <DrawerClose asChild>
        <button type="button" className="erp-btn-outline sm:ml-auto">
          Fechar
        </button>
      </DrawerClose>
    </div>
  );
}
