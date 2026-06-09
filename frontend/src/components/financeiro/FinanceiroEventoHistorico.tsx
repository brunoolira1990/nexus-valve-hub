import {
  humanizarDescricaoFinanceira,
  linhasDetalheHistoricoFinanceiro,
  type FinanceiroHistoricoEvento,
} from '@/lib/financeiroUi';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';

type Props = {
  eventos: FinanceiroHistoricoEvento[];
  className?: string;
};

export function FinanceiroEventoHistorico({ eventos, className = '' }: Props) {
  if (!eventos.length) return null;

  return (
    <ul className={`space-y-3 ${className}`}>
      {eventos.map((ev) => {
        const detalhes = linhasDetalheHistoricoFinanceiro(ev);
        const titulo = humanizarDescricaoFinanceira(ev.descricao, ev.valor);
        const tituloSemMotivo = titulo.replace(/\.\s*Motivo:.*$/i, '.').trim();

        return (
          <li
            key={'id' in ev && ev.id != null ? String(ev.id) : `${ev.criado_em}-${ev.descricao}`}
            className="rounded-lg border border-border bg-muted/20 px-3 py-2.5 text-sm"
          >
            <p className="text-xs text-muted-foreground mb-1">
              {formatDateTimeBr(ev.criado_em)}
              {ev.usuario_nome ? ` · ${ev.usuario_nome}` : ''}
            </p>
            <p className="font-medium leading-snug">{tituloSemMotivo}</p>
            {detalhes.length > 0 ? (
              <ul className="mt-1.5 space-y-0.5 text-muted-foreground">
                {detalhes.map((linha) => (
                  <li key={linha}>{linha}</li>
                ))}
              </ul>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
