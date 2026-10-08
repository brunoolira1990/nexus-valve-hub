import { CadastroButton } from '@/components/ui/cadastro';
import type { InscricaoEstadualSefazItem } from '@/services/api/consulta';
import type { SugestaoIeCampo } from '@/lib/consultaIeCadastro';

type Props = {
  sugestao?: SugestaoIeCampo | null;
  opcoes?: InscricaoEstadualSefazItem[];
  onAplicarIe: (valor: string) => void;
};

export function ConsultaIeSefazPanel({ sugestao, opcoes = [], onAplicarIe }: Props) {
  if (opcoes.length >= 1) {
    return (
      <div
        className="md:col-span-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-3 py-3 text-sm space-y-3"
        data-testid="consulta-ie-sefaz-opcoes"
      >
        <div className="space-y-1">
          <p className="font-medium text-foreground">Inscrições Estaduais encontradas na SEFAZ</p>
          <p className="text-xs text-muted-foreground">Escolha qual IE deseja aplicar no cadastro.</p>
        </div>
        <div className="space-y-2">
          {opcoes.map((item) => (
            <div
              key={`${item.uf}-${item.inscricao_estadual}`}
              className="flex flex-col gap-2 rounded border border-border/70 bg-background/70 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="text-xs font-medium">{item.inscricao_estadual}</p>
                <p className="text-xs text-muted-foreground">
                  UF {item.uf} · {item.situacao_ie || 'Situação não informada'}
                </p>
              </div>
              <CadastroButton type="button" variant="outline" onClick={() => onAplicarIe(item.inscricao_estadual)}>
                Aplicar
              </CadastroButton>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!sugestao) return null;

  return (
    <div
      className="md:col-span-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-3 py-3 text-sm space-y-3"
      data-testid="consulta-ie-sefaz-sugestao"
    >
      <div className="space-y-1">
        <p className="font-medium text-foreground">Sugestão da consulta IE na SEFAZ</p>
        <p className="text-xs text-muted-foreground">
          O valor cadastrado não foi alterado automaticamente. Revise e aplique se desejar.
        </p>
      </div>
      <div className="space-y-1 text-xs">
        <p>
          <span className="text-muted-foreground">Atual:</span> {sugestao.atual || '—'}
        </p>
        <p>
          <span className="text-muted-foreground">Encontrado:</span> {sugestao.sugerido}
          {sugestao.situacao_ie ? ` (${sugestao.situacao_ie})` : ''}
        </p>
      </div>
      <CadastroButton type="button" variant="outline" onClick={() => onAplicarIe(sugestao.sugerido)}>
        Aplicar IE sugerida
      </CadastroButton>
    </div>
  );
}
