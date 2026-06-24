import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { formatDateBr } from '@/lib/dateBr';
import {
  buildPainelCompraLinks,
  buildPainelCorridaLinks,
  buildPainelCqLinks,
  buildPainelNfEntradaLinks,
  buildPainelNfSaidaLinks,
  buildPainelVendaLinks,
  PAINEL_SEM_HISTORICO,
  painelValorExibicao,
} from '@/lib/produtoPainelOperacional';
import { produtosService } from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import type { ProdutoPainelResumo } from '@/types';

type Props = {
  produtoId?: number;
  active?: boolean;
};

function PainelCard({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <h4 className="text-sm font-semibold text-foreground mb-3">{titulo}</h4>
      <div className="space-y-2">{children}</div>
    </article>
  );
}

function PainelGrupo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titulo}</h3>
      {children}
    </section>
  );
}

function PainelCampo({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3 sm:items-baseline text-sm">
      <span className="text-muted-foreground shrink-0 sm:w-28">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  );
}

function PainelLinks({ links }: { links: { label: string; to: string }[] }) {
  if (!links.length) return null;
  return (
    <div className="flex flex-wrap gap-2 pt-2 border-t border-border/60 mt-2">
      {links.map((link) => (
        <Link
          key={`${link.to}-${link.label}`}
          to={link.to}
          className="text-xs text-primary underline-offset-2 hover:underline"
        >
          {link.label}
        </Link>
      ))}
    </div>
  );
}

function PainelBlocoHistorico({
  vazio,
  children,
  links,
}: {
  vazio: boolean;
  children: ReactNode;
  links: { label: string; to: string }[];
}) {
  if (vazio) {
    return <p className="text-sm text-muted-foreground">{PAINEL_SEM_HISTORICO}</p>;
  }
  return (
    <>
      {children}
      <PainelLinks links={links} />
    </>
  );
}

export function ProdutoPainelOperacionalTab({ produtoId, active = true }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ProdutoPainelResumo | null>(null);

  useEffect(() => {
    if (!active || !produtoId) {
      if (!produtoId) {
        setResumo(null);
        setError(null);
      }
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    produtosService
      .getPainelResumo(produtoId)
      .then((data) => {
        if (!cancelled) setResumo(data);
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err, 'Não foi possível carregar o painel operacional.'));
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
        Salve o produto para visualizar o painel operacional.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Carregando resumo operacional…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-sm text-destructive text-center" role="alert">
        {error}
      </div>
    );
  }

  if (!resumo) return null;

  return (
    <div className="space-y-6">
      <PainelGrupo titulo="Estoque">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <PainelCard titulo="Saldo físico">
            <p className="text-2xl font-semibold tabular-nums">{painelValorExibicao(resumo.estoque.saldo_fisico)}</p>
          </PainelCard>
          <PainelCard titulo="Reservado">
            <p className="text-2xl font-semibold tabular-nums">{painelValorExibicao(resumo.estoque.reservado)}</p>
          </PainelCard>
          <PainelCard titulo="Disponível">
            <p className="text-2xl font-semibold tabular-nums">{painelValorExibicao(resumo.estoque.disponivel)}</p>
          </PainelCard>
        </div>
      </PainelGrupo>

      <PainelGrupo titulo="Movimentação">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PainelCard titulo="Última compra">
            <PainelBlocoHistorico vazio={!resumo.ultima_compra} links={buildPainelCompraLinks(resumo.ultima_compra)}>
              <PainelCampo label="Fornecedor" value={painelValorExibicao(resumo.ultima_compra?.fornecedor)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_compra?.data) || '—'} />
              <PainelCampo label="Valor unit." value={painelValorExibicao(resumo.ultima_compra?.valor_unitario)} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última venda">
            <PainelBlocoHistorico vazio={!resumo.ultima_venda} links={buildPainelVendaLinks(resumo.ultima_venda)}>
              <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultima_venda?.cliente)} />
              <PainelCampo label="Pedido" value={painelValorExibicao(resumo.ultima_venda?.pedido_numero)} />
              <PainelCampo label="NF" value={painelValorExibicao(resumo.ultima_venda?.nf)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_venda?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
        </div>
      </PainelGrupo>

      <PainelGrupo titulo="Fiscal">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PainelCard titulo="Última NF-e entrada">
            <PainelBlocoHistorico
              vazio={!resumo.ultima_nf_entrada}
              links={buildPainelNfEntradaLinks(resumo.ultima_nf_entrada)}
            >
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_entrada?.numero)} />
              <PainelCampo label="Fornecedor" value={painelValorExibicao(resumo.ultima_nf_entrada?.fornecedor)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_nf_entrada?.data) || '—'} />
              <PainelCampo label="Qtd." value={painelValorExibicao(resumo.ultima_nf_entrada?.quantidade)} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última NF-e saída">
            <PainelBlocoHistorico vazio={!resumo.ultima_nf_saida} links={buildPainelNfSaidaLinks(resumo.ultima_nf_saida)}>
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_saida?.numero)} />
              <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultima_nf_saida?.cliente)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_nf_saida?.data) || '—'} />
              <PainelCampo label="Qtd." value={painelValorExibicao(resumo.ultima_nf_saida?.quantidade)} />
            </PainelBlocoHistorico>
          </PainelCard>
        </div>
      </PainelGrupo>

      <PainelGrupo titulo="Qualidade">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PainelCard titulo="Último CQ">
            <PainelBlocoHistorico vazio={!resumo.ultimo_cq} links={buildPainelCqLinks(resumo.ultimo_cq)}>
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultimo_cq?.numero)} />
              <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultimo_cq?.cliente)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultimo_cq?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última corrida">
            <PainelBlocoHistorico vazio={!resumo.ultima_corrida} links={buildPainelCorridaLinks(resumo.ultima_corrida)}>
              <PainelCampo label="Corrida" value={painelValorExibicao(resumo.ultima_corrida?.corrida)} />
              <PainelCampo label="Fornecedor" value={painelValorExibicao(resumo.ultima_corrida?.fornecedor)} />
              <PainelCampo label="Saldo atual" value={painelValorExibicao(resumo.ultima_corrida?.saldo_atual)} />
            </PainelBlocoHistorico>
          </PainelCard>
        </div>
      </PainelGrupo>
    </div>
  );
}
