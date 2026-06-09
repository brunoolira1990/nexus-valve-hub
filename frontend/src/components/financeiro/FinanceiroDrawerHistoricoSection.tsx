import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { FinanceiroEventoHistorico } from '@/components/financeiro/FinanceiroEventoHistorico';
import { FINANCEIRO_ACTION_LABELS } from '@/lib/financeiroUi';
import type { FinanceiroHistoricoEvento } from '@/lib/financeiroUi';

type Props = {
  eventos: FinanceiroHistoricoEvento[];
  possuiMovimentoAtivo?: boolean;
  resumoMovimento?: string;
  className?: string;
};

export function FinanceiroDrawerHistoricoSection({
  eventos,
  possuiMovimentoAtivo = false,
  resumoMovimento,
  className = '',
}: Props) {
  const [aberto, setAberto] = useState(false);

  if (!eventos.length) return null;

  return (
    <section className={className}>
      <Collapsible open={aberto} onOpenChange={setAberto}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Movimentos e histórico</h3>
            {possuiMovimentoAtivo ? (
              <p className="text-xs text-amber-700 mt-1">
                {resumoMovimento || 'Este registro possui movimentos financeiros ativos.'}
              </p>
            ) : null}
          </div>
          <CollapsibleTrigger asChild>
            <button type="button" className="erp-btn-ghost erp-btn-sm shrink-0 inline-flex items-center gap-1">
              {aberto ? 'Recolher' : FINANCEIRO_ACTION_LABELS.verHistorico}
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${aberto ? 'rotate-180' : ''}`} />
            </button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="mt-3">
          <FinanceiroEventoHistorico eventos={eventos} />
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
