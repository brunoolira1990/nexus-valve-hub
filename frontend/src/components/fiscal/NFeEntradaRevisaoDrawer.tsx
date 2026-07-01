import { useEffect, useState, type ReactNode } from 'react';
import { AlertCircle, Check, Loader2, X } from 'lucide-react';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { formatQuantityBR } from '@/lib/numberFields';
import {
  mapItensNfeEntradaJson,
  temItensOperacionaisNfeEntrada,
} from '@/lib/nfeEntradaItensJson';
import {
  emitenteDestinatarioLabelNfeEntrada,
  labelStatusOperacionalNfeEntrada,
  labelTipoOrigemNfeEntrada,
} from '@/lib/nfeEntradaOperacionalLabels';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';
import { nfeEntradasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeEntrada } from '@/types';

type Props = {
  nfeId: number | null;
  open: boolean;
  onClose: () => void;
};

function RevisaoSecao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="border border-border rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 border-b border-border">
        <Check className="h-4 w-4 text-primary shrink-0" aria-hidden />
        <h3 className="text-sm font-medium">{titulo}</h3>
      </div>
      <div className="px-3 py-3 text-sm space-y-1">{children}</div>
    </section>
  );
}

function RevisaoSecaoItens({ nfe }: { nfe: NFeEntrada }) {
  const itensOperacionais = temItensOperacionaisNfeEntrada(nfe);
  const itensXml = mapItensNfeEntradaJson(nfe.itens_json);
  const temXml = itensXml.length > 0;

  if (!itensOperacionais && !temXml) {
    return (
      <RevisaoSecao titulo="Itens">
        <div
          role="status"
          className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sky-900 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
          <p>Nenhum item encontrado no XML importado.</p>
        </div>
      </RevisaoSecao>
    );
  }

  return (
    <RevisaoSecao titulo="Itens do XML — somente leitura">
      {!itensOperacionais && temXml ? (
        <p className="text-xs text-muted-foreground mb-3">
          Nenhum item operacional vinculado. Os itens abaixo vêm do XML importado e são somente leitura — não
          geram estoque, financeiro ou finalização da conferência.
        </p>
      ) : null}
      {itensOperacionais ? (
        <div className="mb-4">
          <p className="text-xs font-medium text-muted-foreground mb-2">Itens operacionais vinculados</p>
          <div className="border border-border rounded-md overflow-x-auto -mx-1">
            <table className="erp-table text-xs w-full">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th className="text-right">Qtd</th>
                  <th className="text-right">Valor unit.</th>
                  <th className="text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {nfe.itens.map((it) => (
                  <tr key={it.id}>
                    <td>{it.produto_nome || `Produto #${it.produto_id}`}</td>
                    <td className="text-right nexus-numeric">{it.quantidade}</td>
                    <td className="text-right nexus-numeric">{formatMoneyBRL(it.valor)}</td>
                    <td className="text-right nexus-numeric">
                      {formatMoneyBRL(Number(it.quantidade) * Number(it.valor))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {temXml ? (
        <div className="border border-border rounded-md overflow-x-auto -mx-1">
          <table className="erp-table text-xs w-full">
            <thead>
              <tr>
                <th>#</th>
                <th>Descrição</th>
                <th>Cód.</th>
                <th>NCM</th>
                <th>CFOP</th>
                <th className="text-right">Qtd</th>
                <th>Un.</th>
                <th className="text-right">V. unit.</th>
                <th className="text-right">V. total</th>
              </tr>
            </thead>
            <tbody>
              {itensXml.map((it) => (
                <tr key={`xml-${it.numeroItem}-${it.codigoProduto}`}>
                  <td className="nexus-numeric">{it.numeroItem}</td>
                  <td className="max-w-[12rem]">{it.descricao}</td>
                  <td className="font-mono">{it.codigoProduto || '—'}</td>
                  <td className="font-mono">{it.ncm || '—'}</td>
                  <td className="font-mono">{it.cfop || '—'}</td>
                  <td className="text-right nexus-numeric whitespace-nowrap">
                    {it.quantidade != null ? formatQuantityBR(it.quantidade) : '—'}
                  </td>
                  <td>{it.unidade || '—'}</td>
                  <td className="text-right nexus-numeric whitespace-nowrap">
                    {it.valorUnitario != null ? formatMoneyBRL(it.valorUnitario) : '—'}
                  </td>
                  <td className="text-right nexus-numeric whitespace-nowrap">
                    {it.valorTotal != null ? formatMoneyBRL(it.valorTotal) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </RevisaoSecao>
  );
}

export function NFeEntradaRevisaoDrawer({ nfeId, open, onClose }: Props) {
  const [nfe, setNfe] = useState<NFeEntrada | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !nfeId) {
      setNfe(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void nfeEntradasService
      .getById(nfeId)
      .then(setNfe)
      .catch((e) => {
        setNfe(null);
        setError(apiErrorMessage(e));
      })
      .finally(() => setLoading(false));
  }, [open, nfeId]);

  return (
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="max-h-[92vh]">
        <DrawerHeader className="border-b border-border pb-4">
          <div className="flex items-start justify-between gap-3">
            <DrawerTitle className="text-left">Revisão da NF-e de entrada</DrawerTitle>
            <DrawerClose className="rounded-md p-1 hover:bg-muted" aria-label="Fechar">
              <X className="h-4 w-4" />
            </DrawerClose>
          </div>
          <div
            role="alert"
            className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900 flex items-start gap-2"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
            <p>
              <strong>Revisão somente leitura.</strong> Não altera XML, estoque, financeiro ou finalização da conferência. Esta
              não é a conferência operacional completa da Base NF-e Entrada Importada.
            </p>
          </div>
        </DrawerHeader>

        <div className="overflow-y-auto px-4 py-4 space-y-3 text-sm">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Carregando…
            </div>
          ) : null}
          {error ? <p className="text-destructive">{error}</p> : null}
          {!loading && !error && nfe ? (
            <>
              <RevisaoSecao titulo="Identificação da NF-e">
                <p>
                  <span className="text-muted-foreground">Número / Série:</span>{' '}
                  <span className="font-medium">
                    {nfe.numero}
                    {nfe.serie ? ` / ${nfe.serie}` : ''}
                  </span>
                </p>
                <p>
                  <span className="text-muted-foreground">Emissão:</span> {nfe.data ? formatDateBr(nfe.data) : '—'}
                </p>
                {nfe.importado_em ? (
                  <p>
                    <span className="text-muted-foreground">Importado em:</span> {formatDateTimeBr(nfe.importado_em)}
                  </p>
                ) : null}
              </RevisaoSecao>

              <RevisaoSecao titulo="Emitente / Destinatário">
                <p>{emitenteDestinatarioLabelNfeEntrada(nfe)}</p>
                {nfe.fornecedor_cnpj ? (
                  <p className="font-mono text-xs text-muted-foreground">{nfe.fornecedor_cnpj}</p>
                ) : null}
              </RevisaoSecao>

              <RevisaoSecao titulo="Chave de acesso">
                <p className="font-mono text-xs break-all">{nfe.chave_acesso || '—'}</p>
              </RevisaoSecao>

              <RevisaoSecao titulo="Valores">
                <p className="font-semibold nexus-numeric">{formatMoneyBRL(nfe.valor_total)}</p>
              </RevisaoSecao>

              <RevisaoSecao titulo="Status operacional">
                <div className="flex flex-wrap gap-2 items-center">
                  <StatusBadge status={labelTipoOrigemNfeEntrada(nfe)} />
                  <StatusBadge
                    status={labelStatusOperacionalNfeEntrada(nfe.status_operacional, nfe.status_operacional_label)}
                  />
                </div>
              </RevisaoSecao>

              <RevisaoSecaoItens nfe={nfe} />
            </>
          ) : null}
        </div>

        <DrawerFooter className="border-t border-border">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={onClose}>
            Fechar revisão
          </button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
