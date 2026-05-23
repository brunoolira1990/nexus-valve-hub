import {
  AVISO_RECOMENDACOES_NFE,
  RECOMENDACOES_NFE_OPCOES,
  type RecomendacoesNfeForm,
} from '@/lib/recomendacoesNfeSaida';

type Props = {
  recomendacoes: RecomendacoesNfeForm;
  onChange: (recomendacoes: RecomendacoesNfeForm) => void;
};

export const RecomendacoesNfeSaidaEditor = ({ recomendacoes, onChange }: Props) => {
  const f = (key: keyof RecomendacoesNfeForm, checked: boolean) =>
    onChange({ ...recomendacoes, [key]: checked });

  return (
    <section>
      <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">Recomendações NF-e/DANFE</h3>
      <p className="text-[10px] text-muted-foreground border border-border/60 rounded px-2 py-1.5 mb-3 bg-muted/20">
        {AVISO_RECOMENDACOES_NFE}
      </p>
      <div className="space-y-2">
        {RECOMENDACOES_NFE_OPCOES.map(({ key, label }) => (
          <label key={key} className="flex items-start gap-2 text-xs">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={recomendacoes[key]}
              onChange={(e) => f(key, e.target.checked)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
    </section>
  );
};
