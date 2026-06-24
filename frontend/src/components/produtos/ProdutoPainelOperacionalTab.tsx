import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import type {
  ProdutoPainelFiscalNfEntrada,
  ProdutoPainelHistoricoCompra,
  ProdutoPainelHistoricoVenda,
  ProdutoPainelInteligenciaCompras,
  ProdutoPainelInteligenciaVendas,
  ProdutoPainelQualidadeCertificado,
  ProdutoPainelQualidadeCorrida,
  ProdutoPainelResumo,
} from '@/types';

type Props = {
  produtoId?: number;
  active?: boolean;
};

function PainelCard({ titulo, children, className }: { titulo: string; children: ReactNode; className?: string }) {
  return (
    <article className={`rounded-lg border border-border bg-card p-4 shadow-sm ${className || ''}`}>
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

function PainelTabela({ headers, children, vazio }: { headers: string[]; children: ReactNode; vazio?: boolean }) {
  if (vazio) {
    return <p className="text-sm text-muted-foreground py-4">{PAINEL_SEM_HISTORICO}</p>;
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

function InteligenciaComprasCards({ dados }: { dados: ProdutoPainelInteligenciaCompras | null }) {
  if (!dados) {
    return <p className="text-sm text-muted-foreground">{PAINEL_SEM_HISTORICO}</p>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <PainelCard titulo="Menor preço">
        <p className="text-xl font-semibold tabular-nums">{dados.menor_preco}</p>
        <p className="text-xs text-muted-foreground">{painelValorExibicao(dados.fornecedor_menor_preco)}</p>
      </PainelCard>
      <PainelCard titulo="Maior preço">
        <p className="text-xl font-semibold tabular-nums">{dados.maior_preco}</p>
        <p className="text-xs text-muted-foreground">{painelValorExibicao(dados.fornecedor_maior_preco)}</p>
      </PainelCard>
      <PainelCard titulo="Preço médio">
        <p className="text-xl font-semibold tabular-nums">{dados.preco_medio}</p>
        <p className="text-xs text-muted-foreground">{dados.quantidade_registros} registro(s)</p>
      </PainelCard>
      <PainelCard titulo="Último preço">
        <p className="text-xl font-semibold tabular-nums">{dados.ultimo_preco}</p>
        <p className="text-xs text-muted-foreground">
          {painelValorExibicao(dados.fornecedor_ultimo_preco)} · {formatDateBr(dados.data_ultimo_preco) || '—'}
        </p>
      </PainelCard>
    </div>
  );
}

function InteligenciaVendasCards({ dados }: { dados: ProdutoPainelInteligenciaVendas | null }) {
  if (!dados) {
    return <p className="text-sm text-muted-foreground">{PAINEL_SEM_HISTORICO}</p>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <PainelCard titulo="Menor preço">
        <p className="text-xl font-semibold tabular-nums">{dados.menor_preco}</p>
        <p className="text-xs text-muted-foreground">{painelValorExibicao(dados.cliente_menor_preco)}</p>
      </PainelCard>
      <PainelCard titulo="Maior preço">
        <p className="text-xl font-semibold tabular-nums">{dados.maior_preco}</p>
        <p className="text-xs text-muted-foreground">{painelValorExibicao(dados.cliente_maior_preco)}</p>
      </PainelCard>
      <PainelCard titulo="Preço médio">
        <p className="text-xl font-semibold tabular-nums">{dados.preco_medio}</p>
        <p className="text-xs text-muted-foreground">{dados.quantidade_registros} registro(s)</p>
      </PainelCard>
      <PainelCard titulo="Último preço">
        <p className="text-xl font-semibold tabular-nums">{dados.ultimo_preco}</p>
        <p className="text-xs text-muted-foreground">
          {painelValorExibicao(dados.cliente_ultimo_preco)} · {formatDateBr(dados.data_ultimo_preco) || '—'}
        </p>
      </PainelCard>
    </div>
  );
}

function linksCompraHistorico(row: ProdutoPainelHistoricoCompra) {
  return buildPainelCompraLinks({
    origem: row.origem,
    fornecedor: row.fornecedor,
    fornecedor_id: row.fornecedor_id,
    data: row.data,
    valor_unitario: row.valor_unitario,
    pedido_compra_id: row.pedido_compra_id,
    pedido_compra_numero: row.pedido_compra_numero,
    nf_entrada_id: row.nf_entrada_id,
    nf_entrada_numero: row.nf,
    nf_entrada_historica_id: row.nf_entrada_historica_id,
    conferencia_id: row.conferencia_id,
  });
}

function linksVendaHistorico(row: ProdutoPainelHistoricoVenda) {
  return buildPainelVendaLinks({
    origem: row.origem,
    cliente: row.cliente,
    cliente_id: row.cliente_id,
    pedido_id: row.pedido_id,
    pedido_numero: row.pedido_numero,
    nf: row.nf,
    nf_id: row.nf_id,
    data: row.data,
  });
}

function linksNfEntradaFiscal(row: ProdutoPainelFiscalNfEntrada) {
  return buildPainelNfEntradaLinks({
    origem: row.origem,
    numero: row.numero,
    nf_entrada_id: row.nf_entrada_id,
    nf_entrada_historica_id: row.nf_entrada_historica_id,
    conferencia_id: row.conferencia_id,
    fornecedor: row.fornecedor,
    data: row.data,
    quantidade: row.quantidade,
    valor_unitario: row.valor_unitario,
  });
}

function SecaoResumo({ resumo }: { resumo: ProdutoPainelResumo }) {
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

      <PainelGrupo titulo="Últimos movimentos">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
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
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_venda?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última NF-e entrada">
            <PainelBlocoHistorico
              vazio={!resumo.ultima_nf_entrada}
              links={buildPainelNfEntradaLinks(resumo.ultima_nf_entrada)}
            >
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_entrada?.numero)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_nf_entrada?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última NF-e saída">
            <PainelBlocoHistorico vazio={!resumo.ultima_nf_saida} links={buildPainelNfSaidaLinks(resumo.ultima_nf_saida)}>
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultima_nf_saida?.numero)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultima_nf_saida?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Último CQ">
            <PainelBlocoHistorico vazio={!resumo.ultimo_cq} links={buildPainelCqLinks(resumo.ultimo_cq)}>
              <PainelCampo label="Número" value={painelValorExibicao(resumo.ultimo_cq?.numero)} />
              <PainelCampo label="Data" value={formatDateBr(resumo.ultimo_cq?.data) || '—'} />
            </PainelBlocoHistorico>
          </PainelCard>
          <PainelCard titulo="Última corrida">
            <PainelBlocoHistorico vazio={!resumo.ultima_corrida} links={buildPainelCorridaLinks(resumo.ultima_corrida)}>
              <PainelCampo label="Corrida" value={painelValorExibicao(resumo.ultima_corrida?.corrida)} />
              <PainelCampo label="Saldo" value={painelValorExibicao(resumo.ultima_corrida?.saldo_atual)} />
            </PainelBlocoHistorico>
          </PainelCard>
        </div>
      </PainelGrupo>
    </div>
  );
}

export function ProdutoPainelOperacionalTab({ produtoId, active = true }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ProdutoPainelResumo | null>(null);
  const [painelSecao, setPainelSecao] = useState('resumo');

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

  useEffect(() => {
    if (active) setPainelSecao('resumo');
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
        <span>Carregando centro de informações…</span>
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

  const historicoCompras = resumo.historico_compras ?? [];
  const historicoVendas = resumo.historico_vendas ?? [];
  const qualidade = resumo.qualidade ?? { certificados: [], corridas: [] };
  const fiscal = resumo.fiscal ?? { nf_entrada: [], nf_saida: [] };

  return (
    <Tabs value={painelSecao} onValueChange={setPainelSecao} className="w-full">
      <TabsList className="flex flex-wrap h-auto gap-1 mb-4 w-full justify-start">
        <TabsTrigger value="resumo">Resumo</TabsTrigger>
        <TabsTrigger value="compras">Compras</TabsTrigger>
        <TabsTrigger value="vendas">Vendas</TabsTrigger>
        <TabsTrigger value="qualidade">Qualidade</TabsTrigger>
        <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
      </TabsList>

      <TabsContent value="resumo" className="mt-0">
        <SecaoResumo resumo={resumo} />
      </TabsContent>

      <TabsContent value="compras" className="mt-0 space-y-6">
        <PainelGrupo titulo="Inteligência de compras">
          <InteligenciaComprasCards dados={resumo.inteligencia_compras ?? null} />
        </PainelGrupo>
        <PainelGrupo titulo="Histórico de compras">
          <PainelTabela
            headers={['Data', 'Fornecedor', 'NF', 'Qtd.', 'V. unit.', 'V. total', '']}
            vazio={historicoCompras.length === 0}
          >
            {historicoCompras.map((row, idx) => (
              <tr key={`${row.origem}-${row.data}-${idx}`}>
                <td>{formatDateBr(row.data) || '—'}</td>
                <td>{painelValorExibicao(row.fornecedor)}</td>
                <td>{painelValorExibicao(row.nf)}</td>
                <td className="tabular-nums">{row.quantidade}</td>
                <td className="tabular-nums">{row.valor_unitario}</td>
                <td className="tabular-nums">{row.valor_total}</td>
                <td>
                  <PainelLinks links={linksCompraHistorico(row)} />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
      </TabsContent>

      <TabsContent value="vendas" className="mt-0 space-y-6">
        <PainelGrupo titulo="Inteligência de vendas">
          <InteligenciaVendasCards dados={resumo.inteligencia_vendas ?? null} />
        </PainelGrupo>
        <PainelGrupo titulo="Histórico de vendas">
          <PainelTabela
            headers={['Data', 'Cliente', 'Pedido', 'Qtd.', 'V. unit.', 'V. total', '']}
            vazio={historicoVendas.length === 0}
          >
            {historicoVendas.map((row, idx) => (
              <tr key={`${row.origem}-${row.data}-${idx}`}>
                <td>{formatDateBr(row.data) || '—'}</td>
                <td>{painelValorExibicao(row.cliente)}</td>
                <td>{painelValorExibicao(row.pedido_numero || row.nf)}</td>
                <td className="tabular-nums">{row.quantidade}</td>
                <td className="tabular-nums">{row.valor_unitario}</td>
                <td className="tabular-nums">{row.valor_total}</td>
                <td>
                  <PainelLinks links={linksVendaHistorico(row)} />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
      </TabsContent>

      <TabsContent value="qualidade" className="mt-0 space-y-6">
        <PainelGrupo titulo="Certificados de qualidade">
          <PainelTabela headers={['Número', 'Cliente', 'Data', 'Status', '']} vazio={qualidade.certificados.length === 0}>
            {qualidade.certificados.map((cq: ProdutoPainelQualidadeCertificado) => (
              <tr key={cq.certificado_qualidade_id}>
                <td>{cq.numero}</td>
                <td>{painelValorExibicao(cq.cliente)}</td>
                <td>{formatDateBr(cq.data) || '—'}</td>
                <td>{painelValorExibicao(cq.status)}</td>
                <td>
                  <PainelLinks
                    links={buildPainelCqLinks({
                      numero: cq.numero,
                      certificado_qualidade_id: cq.certificado_qualidade_id,
                      cliente: cq.cliente,
                      data: cq.data,
                      status: cq.status,
                    })}
                  />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
        <PainelGrupo titulo="Corridas vinculadas">
          <PainelTabela headers={['Corrida', 'Fornecedor', 'Recebimento', 'Saldo', 'NF entrada', '']} vazio={qualidade.corridas.length === 0}>
            {qualidade.corridas.map((c: ProdutoPainelQualidadeCorrida) => (
              <tr key={c.corrida_id}>
                <td className="font-mono">{c.corrida}</td>
                <td>{painelValorExibicao(c.fornecedor)}</td>
                <td>{formatDateBr(c.data_recebimento) || '—'}</td>
                <td className="tabular-nums">{c.saldo_atual}</td>
                <td>{painelValorExibicao(c.nf_entrada)}</td>
                <td>
                  <PainelLinks
                    links={buildPainelCorridaLinks({
                      corrida: c.corrida,
                      corrida_id: c.corrida_id,
                      fornecedor: c.fornecedor,
                      saldo_atual: c.saldo_atual,
                      data_recebimento: c.data_recebimento,
                    })}
                  />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
      </TabsContent>

      <TabsContent value="fiscal" className="mt-0 space-y-6">
        <PainelGrupo titulo="NF-e entrada">
          <PainelTabela
            headers={['Data', 'Número', 'Fornecedor', 'Qtd.', 'V. unit.', 'V. total', '']}
            vazio={fiscal.nf_entrada.length === 0}
          >
            {fiscal.nf_entrada.map((row, idx) => (
              <tr key={`${row.origem}-${row.numero}-${idx}`}>
                <td>{formatDateBr(row.data) || '—'}</td>
                <td>{row.numero}</td>
                <td>{painelValorExibicao(row.fornecedor)}</td>
                <td className="tabular-nums">{row.quantidade}</td>
                <td className="tabular-nums">{row.valor_unitario}</td>
                <td className="tabular-nums">{row.valor_total}</td>
                <td>
                  <PainelLinks links={linksNfEntradaFiscal(row)} />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
        <PainelGrupo titulo="NF-e saída">
          <PainelTabela
            headers={['Data', 'Número', 'Cliente', 'Qtd.', 'V. unit.', 'V. total', '']}
            vazio={fiscal.nf_saida.length === 0}
          >
            {fiscal.nf_saida.map((row) => (
              <tr key={row.nf_id}>
                <td>{formatDateBr(row.data) || '—'}</td>
                <td>{row.numero}</td>
                <td>{painelValorExibicao(row.cliente)}</td>
                <td className="tabular-nums">{row.quantidade}</td>
                <td className="tabular-nums">{row.valor_unitario}</td>
                <td className="tabular-nums">{row.valor_total}</td>
                <td>
                  <PainelLinks
                    links={buildPainelNfSaidaLinks({
                      numero: row.numero,
                      nf_id: row.nf_id,
                      cliente: row.cliente,
                      data: row.data,
                      quantidade: row.quantidade,
                      valor_unitario: row.valor_unitario,
                    })}
                  />
                </td>
              </tr>
            ))}
          </PainelTabela>
        </PainelGrupo>
      </TabsContent>
    </Tabs>
  );
}
