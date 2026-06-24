import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { formatDateBr } from '@/lib/dateBr';
import { buildPainelCorridaLinks, painelValorExibicao } from '@/lib/produtoPainelOperacional';
import { produtosService } from '@/services/api/produtos';
import type { ProdutoPainelResumoUltimaCorrida } from '@/types';

type Props = {
  produtoId?: number;
  active?: boolean;
};

export function ProdutoRastreabilidadeTab({ produtoId, active = true }: Props) {
  const [loading, setLoading] = useState(false);
  const [ultimaCorrida, setUltimaCorrida] = useState<ProdutoPainelResumoUltimaCorrida | null>(null);

  useEffect(() => {
    if (!active || !produtoId) {
      if (!produtoId) setUltimaCorrida(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    produtosService
      .getPainelResumo(produtoId)
      .then((data) => {
        if (!cancelled) setUltimaCorrida(data.ultima_corrida);
      })
      .catch(() => {
        if (!cancelled) setUltimaCorrida(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [active, produtoId]);

  if (!produtoId) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        Salve o produto para visualizar informações de rastreabilidade.
      </p>
    );
  }

  const corridaLinks = buildPainelCorridaLinks(ultimaCorrida);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        Rastreabilidade detalhada será implementada em fase futura.
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando dados de corrida…
        </div>
      ) : null}

      {!loading && ultimaCorrida ? (
        <article className="rounded-lg border border-border bg-card p-4 shadow-sm max-w-xl">
          <h4 className="text-sm font-semibold text-foreground mb-3">Última corrida conhecida</h4>
          <div className="space-y-2 text-sm">
            <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
              <span className="text-muted-foreground sm:w-28">Corrida</span>
              <span className="font-medium">{painelValorExibicao(ultimaCorrida.corrida)}</span>
            </div>
            <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
              <span className="text-muted-foreground sm:w-28">Fornecedor</span>
              <span className="font-medium">{painelValorExibicao(ultimaCorrida.fornecedor)}</span>
            </div>
            <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
              <span className="text-muted-foreground sm:w-28">Saldo atual</span>
              <span className="font-medium">{painelValorExibicao(ultimaCorrida.saldo_atual)}</span>
            </div>
            {ultimaCorrida.data_recebimento ? (
              <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                <span className="text-muted-foreground sm:w-28">Recebimento</span>
                <span className="font-medium">{formatDateBr(ultimaCorrida.data_recebimento) || '—'}</span>
              </div>
            ) : null}
          </div>
          {corridaLinks.length ? (
            <div className="flex flex-wrap gap-2 pt-3 mt-3 border-t border-border/60">
              {corridaLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className="text-xs text-primary underline-offset-2 hover:underline"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
