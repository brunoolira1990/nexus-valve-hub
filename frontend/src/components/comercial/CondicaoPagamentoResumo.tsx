import { previewCondicaoPagamento } from '@/lib/condicaoPagamento';

type Props = {
  condicao: string;
  dataBaseIso: string;
};

export function CondicaoPagamentoResumo({ condicao, dataBaseIso }: Props) {
  const preview = previewCondicaoPagamento(condicao, dataBaseIso);

  if (preview.erro) {
    return <p className="text-xs text-destructive">{preview.erro}</p>;
  }

  if (!dataBaseIso) {
    return <p className="text-xs text-muted-foreground">Informe a data do documento para calcular os vencimentos.</p>;
  }

  return (
    <div className="space-y-2 text-xs">
      <p className="text-muted-foreground">{preview.resumo}</p>
      {preview.vencimentos.length > 0 ? (
        <ul className="space-y-1">
          {preview.vencimentos.map((v) => (
            <li key={`${v.dias}-${v.dataIso}`} className="flex flex-wrap gap-2 text-foreground">
              <span className="font-medium">{v.dias} dias</span>
              <span className="text-muted-foreground">—</span>
              <span>{v.dataBr}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground">Sem vencimentos calculados.</p>
      )}
    </div>
  );
}
