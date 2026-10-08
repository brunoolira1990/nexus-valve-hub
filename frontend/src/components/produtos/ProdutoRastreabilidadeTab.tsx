import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { formatDateBr } from '@/lib/dateBr';
import {
  buildRastreabilidadeCfLink,
  buildRastreabilidadeCorridaLink,
  buildRastreabilidadeCqLink,
  buildRastreabilidadeNfEntradaLink,
  buildRastreabilidadeNfSaidaLink,
  painelValorExibicao,
  RASTREABILIDADE_SEM_REGISTRO,
} from '@/lib/produtoPainelOperacional';
import { produtosService } from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import type { ProdutoRastreabilidade } from '@/types';

type Props = {
  produtoId?: number;
  active?: boolean;
};

function RastreabilidadeLinks({ links }: { links: { label: string; to: string }[] }) {
  if (!links.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
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

function RastreabilidadeTabela({
  headers,
  children,
  vazio,
}: {
  headers: string[];
  children: ReactNode;
  vazio?: boolean;
}) {
  if (vazio) {
    return <p className="text-sm text-muted-foreground py-2">{RASTREABILIDADE_SEM_REGISTRO}</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="erp-table w-full text-sm">
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} className="whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function RastreabilidadeSkeleton() {
  return (
    <div className="space-y-3 py-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-10 rounded-md bg-muted/60 animate-pulse" />
      ))}
    </div>
  );
}

export function ProdutoRastreabilidadeTab({ produtoId, active = true }: Props) {
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [dados, setDados] = useState<ProdutoRastreabilidade | null>(null);

  useEffect(() => {
    if (!active || !produtoId) {
      if (!produtoId) {
        setDados(null);
        setErro(null);
      }
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErro(null);
    produtosService
      .getPainelRastreabilidade(produtoId)
      .then((data) => {
        if (!cancelled) setDados(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setDados(null);
          setErro(apiErrorMessage(err, 'Não foi possível carregar a rastreabilidade.'));
        }
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
        Salve o produto para visualizar a rastreabilidade.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Carregando rastreabilidade…</span>
        <RastreabilidadeSkeleton />
      </div>
    );
  }

  if (erro) {
    return (
      <p className="text-sm text-destructive py-8 text-center">{erro}</p>
    );
  }

  const corridas = dados?.corridas ?? [];
  const certificadosQualidade = dados?.certificados_qualidade ?? [];
  const certificadosFornecedor = dados?.certificados_fornecedor ?? [];
  const nfsEntrada = dados?.nfs_entrada ?? [];
  const nfsSaida = dados?.nfs_saida ?? [];

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Rastreabilidade por corrida/lote — somente leitura, consolidada a partir de estoque, qualidade e fiscal.
      </p>

      <Accordion type="multiple" defaultValue={['corridas']} className="w-full">
        <AccordionItem value="corridas">
          <AccordionTrigger className="text-sm font-semibold">
            Corridas ({corridas.length})
          </AccordionTrigger>
          <AccordionContent>
            <RastreabilidadeTabela
              vazio={!corridas.length}
              headers={['Código', 'Lote', 'Saldo', 'Fornecedor', 'Origem', 'NF entrada', 'CF', '']}
            >
              {corridas.map((c) => {
                const link = buildRastreabilidadeCorridaLink(c.codigo);
                return (
                  <tr key={c.id}>
                    <td className="font-medium">{painelValorExibicao(c.codigo)}</td>
                    <td>{painelValorExibicao(c.lote)}</td>
                    <td>{c.saldo.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</td>
                    <td>{painelValorExibicao(c.fornecedor_nome)}</td>
                    <td>{painelValorExibicao(c.origem_tecnica)}</td>
                    <td>{painelValorExibicao(c.nf_entrada_numero)}</td>
                    <td>{c.possui_cf ? 'Sim' : 'Não'}</td>
                    <td>
                      <RastreabilidadeLinks links={[link]} />
                    </td>
                  </tr>
                );
              })}
            </RastreabilidadeTabela>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="certificados-qualidade">
          <AccordionTrigger className="text-sm font-semibold">
            Certificados de Qualidade ({certificadosQualidade.length})
          </AccordionTrigger>
          <AccordionContent>
            <RastreabilidadeTabela
              vazio={!certificadosQualidade.length}
              headers={['Número', 'Cliente', 'Emissão', 'Status', 'Corridas', '']}
            >
              {certificadosQualidade.map((cq) => (
                <tr key={cq.id}>
                  <td className="font-medium">{painelValorExibicao(cq.numero)}</td>
                  <td>{painelValorExibicao(cq.cliente_nome)}</td>
                  <td>{formatDateBr(cq.data_emissao) || '—'}</td>
                  <td>{painelValorExibicao(cq.status)}</td>
                  <td>
                    {cq.corridas.length
                      ? cq.corridas.map((c) => c.codigo).join(', ')
                      : '—'}
                  </td>
                  <td>
                    <RastreabilidadeLinks links={[buildRastreabilidadeCqLink(cq.id, cq.numero)]} />
                  </td>
                </tr>
              ))}
            </RastreabilidadeTabela>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="certificados-fornecedor">
          <AccordionTrigger className="text-sm font-semibold">
            Certificados de Fornecedor ({certificadosFornecedor.length})
          </AccordionTrigger>
          <AccordionContent>
            <RastreabilidadeTabela
              vazio={!certificadosFornecedor.length}
              headers={['Número', 'Fornecedor', 'Emissão', 'NF entrada', 'Corridas', '']}
            >
              {certificadosFornecedor.map((cf) => (
                <tr key={cf.id}>
                  <td className="font-medium">{painelValorExibicao(cf.numero)}</td>
                  <td>{painelValorExibicao(cf.fornecedor_nome)}</td>
                  <td>{formatDateBr(cf.data_emissao) || '—'}</td>
                  <td>{painelValorExibicao(cf.nf_entrada_referencia)}</td>
                  <td>
                    {cf.corridas.length
                      ? cf.corridas.map((c) => c.codigo).join(', ')
                      : '—'}
                  </td>
                  <td>
                    <RastreabilidadeLinks links={[buildRastreabilidadeCfLink(cf.id, cf.numero)]} />
                  </td>
                </tr>
              ))}
            </RastreabilidadeTabela>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="nfs-entrada">
          <AccordionTrigger className="text-sm font-semibold">
            NF-e Entrada ({nfsEntrada.length})
          </AccordionTrigger>
          <AccordionContent>
            <RastreabilidadeTabela
              vazio={!nfsEntrada.length}
              headers={['Número', 'Fornecedor', 'Entrada', 'Corrida', 'Status', '']}
            >
              {nfsEntrada.map((nf) => (
                <tr key={`nf-ent-${nf.id}-${nf.numero}`}>
                  <td className="font-medium">{painelValorExibicao(nf.numero)}</td>
                  <td>{painelValorExibicao(nf.fornecedor_nome)}</td>
                  <td>{formatDateBr(nf.data_entrada) || '—'}</td>
                  <td>{painelValorExibicao(nf.corrida_codigo)}</td>
                  <td>{painelValorExibicao(nf.status)}</td>
                  <td>
                    <RastreabilidadeLinks links={[buildRastreabilidadeNfEntradaLink(nf.id, nf.numero)]} />
                  </td>
                </tr>
              ))}
            </RastreabilidadeTabela>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="nfs-saida">
          <AccordionTrigger className="text-sm font-semibold">
            NF-e Saída ({nfsSaida.length})
          </AccordionTrigger>
          <AccordionContent>
            <RastreabilidadeTabela
              vazio={!nfsSaida.length}
              headers={['Número', 'Cliente', 'Emissão', 'Pedido', 'Corrida', '']}
            >
              {nfsSaida.map((nf) => (
                <tr key={nf.id}>
                  <td className="font-medium">{painelValorExibicao(nf.numero)}</td>
                  <td>{painelValorExibicao(nf.cliente_nome)}</td>
                  <td>{formatDateBr(nf.data_emissao) || '—'}</td>
                  <td>{painelValorExibicao(nf.pedido_numero)}</td>
                  <td>{painelValorExibicao(nf.corrida_codigo)}</td>
                  <td>
                    <RastreabilidadeLinks links={[buildRastreabilidadeNfSaidaLink(nf.id, nf.numero)]} />
                  </td>
                </tr>
              ))}
            </RastreabilidadeTabela>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
