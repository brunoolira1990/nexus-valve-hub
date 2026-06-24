import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, X } from 'lucide-react';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
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
import type { Produto, ProdutoPainelResumo } from '@/types';

type Props = {
  produto: Produto | null;
  open: boolean;
  onClose: () => void;
};

function PainelSecao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="border-b border-border py-4 last:border-b-0">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">{titulo}</h3>
      {children}
    </section>
  );
}

function PainelCampo({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,7rem)_1fr] gap-2 text-sm py-1">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  );
}

function PainelLinks({ links }: { links: { label: string; to: string }[] }) {
  if (!links.length) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
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

export function ProdutoPainelOperacionalDrawer({ produto, open, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ProdutoPainelResumo | null>(null);

  useEffect(() => {
    if (!open || !produto?.id) {
      setResumo(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    produtosService
      .getPainelResumo(produto.id)
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
  }, [open, produto?.id]);

  const titulo = produto ? `Painel — ${produto.codigo_completo}` : 'Painel operacional';

  return (
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="inset-y-0 right-0 left-auto top-0 mt-0 h-full w-full max-w-md rounded-none rounded-l-lg border-l flex flex-col max-h-[100vh]">
        <DrawerHeader className="text-left border-b border-border shrink-0 flex flex-row items-start justify-between gap-2">
          <div>
            <DrawerTitle className="text-base">{titulo}</DrawerTitle>
            {produto ? <p className="text-sm text-muted-foreground mt-1">{produto.descricao}</p> : null}
          </div>
          <DrawerClose className="erp-btn-ghost erp-btn-sm shrink-0" aria-label="Fechar painel">
            <X className="h-4 w-4" />
          </DrawerClose>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto px-4 pb-6">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Carregando resumo operacional…</span>
            </div>
          ) : null}

          {!loading && error ? (
            <div className="py-8 text-sm text-destructive" role="alert">
              {error}
            </div>
          ) : null}

          {!loading && !error && resumo ? (
            <>
              <PainelSecao titulo="Produto">
                <PainelCampo label="Código" value={painelValorExibicao(resumo.produto.codigo)} />
                <PainelCampo label="Descrição" value={painelValorExibicao(resumo.produto.descricao)} />
                <PainelCampo label="Material" value={painelValorExibicao(resumo.produto.material)} />
                <PainelCampo label="Norma" value={painelValorExibicao(resumo.produto.norma)} />
                <PainelCampo label="Polegada" value={painelValorExibicao(resumo.produto.polegada)} />
                <PainelCampo label="NCM" value={painelValorExibicao(resumo.produto.ncm)} />
              </PainelSecao>

              <PainelSecao titulo="Estoque atual">
                <PainelCampo label="Saldo físico" value={painelValorExibicao(resumo.estoque.saldo_fisico)} />
                <PainelCampo label="Reservado" value={painelValorExibicao(resumo.estoque.reservado)} />
                <PainelCampo label="Disponível" value={painelValorExibicao(resumo.estoque.disponivel)} />
              </PainelSecao>

              <PainelSecao titulo="Última compra">
                <PainelBlocoHistorico
                  vazio={!resumo.ultima_compra}
                  links={buildPainelCompraLinks(resumo.ultima_compra)}
                >
                  <PainelCampo label="Fornecedor" value={painelValorExibicao(resumo.ultima_compra?.fornecedor)} />
                  <PainelCampo
                    label="Data"
                    value={formatDateBr(resumo.ultima_compra?.data) || '—'}
                  />
                  <PainelCampo
                    label="Valor unit."
                    value={painelValorExibicao(resumo.ultima_compra?.valor_unitario)}
                  />
                </PainelBlocoHistorico>
              </PainelSecao>

              <PainelSecao titulo="Última venda">
                <PainelBlocoHistorico
                  vazio={!resumo.ultima_venda}
                  links={buildPainelVendaLinks(resumo.ultima_venda)}
                >
                  <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultima_venda?.cliente)} />
                  <PainelCampo
                    label="Pedido"
                    value={painelValorExibicao(resumo.ultima_venda?.pedido_numero)}
                  />
                  <PainelCampo label="NF" value={painelValorExibicao(resumo.ultima_venda?.nf)} />
                  <PainelCampo
                    label="Data"
                    value={formatDateBr(resumo.ultima_venda?.data) || '—'}
                  />
                </PainelBlocoHistorico>
              </PainelSecao>

              <PainelSecao titulo="Última NF entrada">
                <PainelBlocoHistorico
                  vazio={!resumo.ultima_nf_entrada}
                  links={buildPainelNfEntradaLinks(resumo.ultima_nf_entrada)}
                >
                  <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_entrada?.numero)} />
                  <PainelCampo
                    label="Fornecedor"
                    value={painelValorExibicao(resumo.ultima_nf_entrada?.fornecedor)}
                  />
                  <PainelCampo
                    label="Data"
                    value={formatDateBr(resumo.ultima_nf_entrada?.data) || '—'}
                  />
                  <PainelCampo
                    label="Qtd."
                    value={painelValorExibicao(resumo.ultima_nf_entrada?.quantidade)}
                  />
                </PainelBlocoHistorico>
              </PainelSecao>

              <PainelSecao titulo="Última NF saída">
                <PainelBlocoHistorico
                  vazio={!resumo.ultima_nf_saida}
                  links={buildPainelNfSaidaLinks(resumo.ultima_nf_saida)}
                >
                  <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_saida?.numero)} />
                  <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultima_nf_saida?.cliente)} />
                  <PainelCampo
                    label="Data"
                    value={formatDateBr(resumo.ultima_nf_saida?.data) || '—'}
                  />
                  <PainelCampo
                    label="Qtd."
                    value={painelValorExibicao(resumo.ultima_nf_saida?.quantidade)}
                  />
                </PainelBlocoHistorico>
              </PainelSecao>

              <PainelSecao titulo="Último CQ">
                <PainelBlocoHistorico vazio={!resumo.ultimo_cq} links={buildPainelCqLinks(resumo.ultimo_cq)}>
                  <PainelCampo label="Número" value={painelValorExibicao(resumo.ultimo_cq?.numero)} />
                  <PainelCampo label="Cliente" value={painelValorExibicao(resumo.ultimo_cq?.cliente)} />
                  <PainelCampo label="Data" value={formatDateBr(resumo.ultimo_cq?.data) || '—'} />
                </PainelBlocoHistorico>
              </PainelSecao>

              <PainelSecao titulo="Última corrida">
                <PainelBlocoHistorico
                  vazio={!resumo.ultima_corrida}
                  links={buildPainelCorridaLinks(resumo.ultima_corrida)}
                >
                  <PainelCampo label="Corrida" value={painelValorExibicao(resumo.ultima_corrida?.corrida)} />
                  <PainelCampo
                    label="Fornecedor"
                    value={painelValorExibicao(resumo.ultima_corrida?.fornecedor)}
                  />
                  <PainelCampo
                    label="Saldo atual"
                    value={painelValorExibicao(resumo.ultima_corrida?.saldo_atual)}
                  />
                </PainelBlocoHistorico>
              </PainelSecao>
            </>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
