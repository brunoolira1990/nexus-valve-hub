import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import { AlocacaoAtendimentoVinculosForm } from '@/components/comercial/AlocacaoAtendimentoVinculosForm';
import { AlocacaoVinculosLinha } from '@/components/comercial/AlocacaoVinculosLinha';

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: {
    opcoesFornecedores: vi.fn(async () => [
      { id: 7, label: 'FORNECEDOR XYZ', cnpj: '00.000.000/0001-00', cidade: 'SP', uf: 'SP' },
    ]),
    opcoesPedidosCompra: vi.fn(async () => []),
    opcoesPedidosCompraItens: vi.fn(async () => []),
    opcoesNfeEntradaImportada: vi.fn(async () => []),
    opcoesNfeEntradaImportadaItens: vi.fn(async () => []),
    opcoesCteConferido: vi.fn(async () => []),
  },
}));

const baseProps = {
  produtoId: 45,
  values: {
    fornecedor_id: null,
    pedido_compra_item_id: null,
    nf_entrada_historica_item_id: null,
    cte_historico_importado_id: null,
  },
  fornecedor: null,
  pedidoCompra: null,
  pedidoCompraItem: null,
  nfeEntrada: null,
  nfeEntradaItem: null,
  cte: null,
  onChange: vi.fn(),
  onSelectFornecedor: vi.fn(),
  onSelectPedidoCompra: vi.fn(),
  onSelectPedidoCompraItem: vi.fn(),
  onSelectNfeEntrada: vi.fn(),
  onSelectNfeEntradaItem: vi.fn(),
  onSelectCte: vi.fn(),
};

describe('ERP 4.0.13 — vínculo assistido alocação', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('formulário de vínculos mostra aviso sem financeiro/estoque', () => {
    render(<AlocacaoAtendimentoVinculosForm {...baseProps} />);
    expect(screen.getByText(/não gera financeiro, estoque, expedição/i)).toBeInTheDocument();
  });

  it('formulário mostra autocomplete de fornecedor', () => {
    render(<AlocacaoAtendimentoVinculosForm {...baseProps} />);
    expect(screen.getByText(/Fornecedor \(opcional\)/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Buscar por nome ou CNPJ/i)).toBeInTheDocument();
  });

  it('lista exibe nomes de vínculos, não apenas IDs', () => {
    render(
      <AlocacaoVinculosLinha
        vinculos={{
          fornecedor_label: 'FORNECEDOR XYZ',
          pedido_compra_label: 'PC-20260524-0001',
          pedido_compra_id: 10,
          nfe_entrada_label: null,
          nfe_entrada_status_conferencia: null,
          cte_label: 'CT-e 15708883/1 — Conferido',
          cte_status_conferencia: 'CONFERIDO',
          tem_compra_vinculada: true,
          tem_nfe_entrada_vinculada: false,
          tem_cte_vinculado: true,
          alertas_vinculo: [],
        }}
      />,
    );
    expect(screen.getByText(/FORNECEDOR XYZ/)).toBeInTheDocument();
    expect(screen.getByText(/PC-20260524-0001/)).toBeInTheDocument();
    expect(screen.getByText(/CT-e 15708883/)).toBeInTheDocument();
    expect(screen.queryByText(/#123/)).not.toBeInTheDocument();
  });
});
