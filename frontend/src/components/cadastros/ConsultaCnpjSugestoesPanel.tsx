import { CadastroButton } from '@/components/ui/cadastro';
import type { CampoSugestaoCnpj } from '@/lib/consultaCnpjCadastro';

type Props<TCampo extends string> = {
  sugestoes: CampoSugestaoCnpj<TCampo>[];
  onAplicarCampo: (campo: TCampo, valor: string) => void;
  onAplicarTodas: () => void;
};

export function ConsultaCnpjSugestoesPanel<TCampo extends string>({
  sugestoes,
  onAplicarCampo,
  onAplicarTodas,
}: Props<TCampo>) {
  if (!sugestoes.length) return null;

  return (
    <div
      className="md:col-span-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-3 py-3 text-sm space-y-3"
      data-testid="consulta-cnpj-sugestoes"
    >
      <div className="space-y-1">
        <p className="font-medium text-foreground">Sugestões da consulta de CNPJ</p>
        <p className="text-xs text-muted-foreground">
          Valores já preenchidos não foram alterados automaticamente. Revise e aplique o que desejar.
        </p>
      </div>
      <div className="space-y-2">
        {sugestoes.map((item) => (
          <div
            key={item.campo}
            className="flex flex-col gap-2 rounded border border-border/70 bg-background/70 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">{item.label}</p>
              <p className="text-xs">
                <span className="text-muted-foreground">Atual:</span> {item.atual || '—'}
              </p>
              <p className="text-xs">
                <span className="text-muted-foreground">Encontrado:</span> {item.sugerido}
              </p>
            </div>
            <CadastroButton
              type="button"
              variant="outline"
              className="shrink-0"
              onClick={() => onAplicarCampo(item.campo, item.sugerido)}
            >
              Aplicar
            </CadastroButton>
          </div>
        ))}
      </div>
      <CadastroButton type="button" variant="secondary" onClick={onAplicarTodas}>
        Aplicar todas as sugestões
      </CadastroButton>
    </div>
  );
}
