import { useCallback } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { FornecedorOpcaoField } from '@/components/comercial/FornecedorOpcaoField';
import { alocacaoAtendimentoService } from '@/services/api/alocacaoAtendimento';
import type {
  OpcaoCteConferido,
  OpcaoFornecedor,
  OpcaoNfeEntradaImportada,
  OpcaoNfeEntradaImportadaItem,
  OpcaoPedidoCompra,
  OpcaoPedidoCompraItem,
} from '@/types/alocacaoAtendimentoOpcoes';

export const AVISO_VINCULO_DFE =
  'Vincular documentos nesta tela não gera financeiro, estoque, expedição ou rateio automático. O vínculo serve apenas para rastreabilidade operacional.';

export type VinculosFormValues = {
  fornecedor_id: number | null;
  pedido_compra_item_id: number | null;
  nf_entrada_historica_item_id: number | null;
  cte_historico_importado_id: number | null;
};

type Props = {
  produtoId: number | null;
  values: VinculosFormValues;
  fornecedor: OpcaoFornecedor | null;
  pedidoCompra: OpcaoPedidoCompra | null;
  pedidoCompraItem: OpcaoPedidoCompraItem | null;
  nfeEntrada: OpcaoNfeEntradaImportada | null;
  nfeEntradaItem: OpcaoNfeEntradaImportadaItem | null;
  cte: OpcaoCteConferido | null;
  onChange: (patch: Partial<VinculosFormValues>) => void;
  onSelectFornecedor: (opt: OpcaoFornecedor | null) => void;
  onSelectPedidoCompra: (opt: OpcaoPedidoCompra | null) => void;
  onSelectPedidoCompraItem: (opt: OpcaoPedidoCompraItem | null) => void;
  onSelectNfeEntrada: (opt: OpcaoNfeEntradaImportada | null) => void;
  onSelectNfeEntradaItem: (opt: OpcaoNfeEntradaImportadaItem | null) => void;
  onSelectCte: (opt: OpcaoCteConferido | null) => void;
};

export function AlocacaoAtendimentoVinculosForm({
  produtoId,
  values,
  fornecedor,
  pedidoCompra,
  pedidoCompraItem,
  nfeEntrada,
  nfeEntradaItem,
  cte,
  onChange,
  onSelectFornecedor,
  onSelectPedidoCompra,
  onSelectPedidoCompraItem,
  onSelectNfeEntrada,
  onSelectNfeEntradaItem,
  onSelectCte,
}: Props) {
  const fornecedorId = values.fornecedor_id;
  const pedidoCompraId = pedidoCompra?.id ?? pedidoCompraItem?.pedido_compra_id ?? null;
  const nfeId = nfeEntrada?.id ?? nfeEntradaItem?.nfe_entrada_historica_id ?? null;

  const buscaPc = useCallback(
    (term: string) =>
      alocacaoAtendimentoService.opcoesPedidosCompra(term, {
        fornecedor_id: fornecedorId ?? undefined,
      }),
    [fornecedorId],
  );
  const buscaPcItem = useCallback(
    (term: string) =>
      alocacaoAtendimentoService.opcoesPedidosCompraItens(term, {
        pedido_compra_id: pedidoCompraId ?? undefined,
        fornecedor_id: fornecedorId ?? undefined,
        produto_id: produtoId ?? undefined,
      }),
    [pedidoCompraId, fornecedorId, produtoId],
  );
  const buscaNfe = useCallback(
    (term: string) =>
      alocacaoAtendimentoService.opcoesNfeEntradaImportada(term, {
        fornecedor_id: fornecedorId ?? undefined,
        produto_id: produtoId ?? undefined,
      }),
    [fornecedorId, produtoId],
  );
  const buscaNfeItem = useCallback(
    (term: string) =>
      alocacaoAtendimentoService.opcoesNfeEntradaImportadaItens(term, {
        nfe_entrada_historica_id: nfeId ?? undefined,
        fornecedor_id: fornecedorId ?? undefined,
        produto_id: produtoId ?? undefined,
      }),
    [nfeId, fornecedorId, produtoId],
  );
  const buscaCte = useCallback(
    (term: string) => alocacaoAtendimentoService.opcoesCteConferido(term),
    [],
  );

  return (
    <div className="space-y-3 border-t border-border pt-3">
      <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md bg-amber-500/10 px-2 py-1.5">
        {AVISO_VINCULO_DFE}
      </p>

      <div>
        <label className="erp-label">Fornecedor (opcional)</label>
        <FornecedorOpcaoField
          valueId={values.fornecedor_id}
          selectedOption={fornecedor}
          onSelect={(opt) => {
            onChange({ fornecedor_id: opt?.id ?? null });
            onSelectFornecedor(opt);
          }}
        />
      </div>

      <div>
        <label className="erp-label">Pedido de compra (opcional)</label>
        <AsyncAutocomplete<OpcaoPedidoCompra>
          value={pedidoCompraId}
          selectedOption={pedidoCompra}
          placeholder="Buscar PC por número ou fornecedor…"
          search={buscaPc}
          getOptionValue={(o) => o.id}
          getOptionLabel={(o) => o.label}
          onChange={(_id, opt) => {
            onSelectPedidoCompra(opt ?? null);
            onChange({ pedido_compra_item_id: null });
            onSelectPedidoCompraItem(null);
          }}
        />
      </div>

      <div>
        <label className="erp-label">Item do pedido de compra (opcional)</label>
        <AsyncAutocomplete<OpcaoPedidoCompraItem>
          value={values.pedido_compra_item_id}
          selectedOption={pedidoCompraItem}
          placeholder={pedidoCompraId ? 'Buscar item do PC…' : 'Selecione um pedido de compra antes'}
          disabled={!pedidoCompraId && !fornecedorId}
          search={buscaPcItem}
          getOptionValue={(o) => o.id}
          getOptionLabel={(o) => o.label}
          onChange={(id, opt) => {
            onChange({ pedido_compra_item_id: id != null ? Number(id) : null });
            onSelectPedidoCompraItem(opt ?? null);
            if (opt?.pedido_compra_id && !pedidoCompra) {
              onSelectPedidoCompra({
                id: opt.pedido_compra_id,
                numero: '',
                fornecedor: '',
                fornecedor_id: fornecedorId,
                data: '',
                status: '',
                valor_total: '',
                label: `PC #${opt.pedido_compra_id}`,
              });
            }
          }}
        />
      </div>

      <div>
        <label className="erp-label">NF-e entrada importada (opcional)</label>
        <AsyncAutocomplete<OpcaoNfeEntradaImportada>
          value={nfeId}
          selectedOption={nfeEntrada}
          placeholder="Buscar NF-e por número, chave ou fornecedor…"
          search={buscaNfe}
          getOptionValue={(o) => o.id}
          getOptionLabel={(o) => o.label}
          onChange={(_id, opt) => {
            onSelectNfeEntrada(opt ?? null);
            onChange({ nf_entrada_historica_item_id: null });
            onSelectNfeEntradaItem(null);
          }}
        />
      </div>

      <div>
        <label className="erp-label">Item da NF-e entrada (opcional)</label>
        <AsyncAutocomplete<OpcaoNfeEntradaImportadaItem>
          value={values.nf_entrada_historica_item_id}
          selectedOption={nfeEntradaItem}
          placeholder={nfeId ? 'Buscar item da NF-e…' : 'Selecione a NF-e entrada antes'}
          disabled={!nfeId}
          search={buscaNfeItem}
          getOptionValue={(o) => o.id}
          getOptionLabel={(o) => o.label}
          onChange={(id, opt) => {
            onChange({ nf_entrada_historica_item_id: id != null ? Number(id) : null });
            onSelectNfeEntradaItem(opt ?? null);
          }}
        />
      </div>

      <div>
        <label className="erp-label">CT-e conferido (opcional)</label>
        <AsyncAutocomplete<OpcaoCteConferido>
          value={values.cte_historico_importado_id}
          selectedOption={cte}
          placeholder="Buscar CT-e por número ou transportadora…"
          search={buscaCte}
          getOptionValue={(o) => o.id}
          getOptionLabel={(o) => o.label}
          onChange={(id, opt) => {
            onChange({ cte_historico_importado_id: id != null ? Number(id) : null });
            onSelectCte(opt ?? null);
          }}
        />
      </div>
    </div>
  );
}
