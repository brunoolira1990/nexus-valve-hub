import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { NFeEntradaRevisaoDrawer } from '@/components/fiscal/NFeEntradaRevisaoDrawer';
import { nfeEntradasService } from '@/services/api/fiscal';

const itemXml = {
  n_item: 1,
  prod: {
    cProd: '001',
    xProd: 'Válvula gaveta 2"',
    NCM: '84818095',
    CFOP: '1202',
    uCom: 'UN',
    qCom: '2.5000',
    vUnCom: '1500.00',
    vProd: '3750.00',
  },
};

const entradaPropria: import('@/types').NFeEntrada = {
  id: 42,
  numero: '1001',
  serie: '1',
  chave_acesso: '35250612345678901234567890123456789012345678',
  fornecedor_nome: 'Empresa Nexus Ltda',
  destinatario_nome: 'Cliente ABC',
  data: '2025-06-01',
  valor_total: 1234.56,
  tipo_origem: 'ENTRADA_PROPRIA_IMPORTADA',
  tipo_origem_label: 'Entrada própria',
  status_operacional: 'IMPORTADA_PENDENTE_CONFERENCIA',
  status_operacional_label: 'Importada — pendente conferência',
  importado_em: '2025-06-02T10:30:00',
  itens: [],
  itens_json: [itemXml],
};

const entradaSemItensXml: import('@/types').NFeEntrada = {
  ...entradaPropria,
  itens_json: [],
};

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: {
    getById: vi.fn(),
  },
}));

describe('NFeEntradaRevisaoDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(nfeEntradasService.getById).mockResolvedValue(entradaPropria);
  });

  it('exibe aviso explícito de somente leitura e sem efeitos', async () => {
    render(<NFeEntradaRevisaoDrawer nfeId={42} open onClose={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Revisão somente leitura/i);
    expect(screen.getByRole('alert')).toHaveTextContent(
      /Não altera XML, estoque, financeiro ou finalização da conferência/i,
    );
    await waitFor(() => {
      expect(screen.getByText('Revisão da NF-e de entrada')).toBeInTheDocument();
    });
  });

  it('exibe itens de itens_json com formatação BR e metadados fiscais', async () => {
    render(<NFeEntradaRevisaoDrawer nfeId={42} open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('Itens do XML — somente leitura')).toBeInTheDocument();
      expect(
        screen.getByText(/Nenhum item operacional vinculado\. Os itens abaixo vêm do XML importado/i),
      ).toBeInTheDocument();
      expect(screen.getByText('Válvula gaveta 2"')).toBeInTheDocument();
      expect(screen.getByText('84818095')).toBeInTheDocument();
      expect(screen.getByText('1202')).toBeInTheDocument();
      expect(screen.getByText('UN')).toBeInTheDocument();
      expect(screen.getByText(/R\$\s*1\.500,00/)).toBeInTheDocument();
      expect(screen.getByText(/R\$\s*3\.750,00/)).toBeInTheDocument();
      expect(screen.getByText('2,5')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Nenhum item cadastrado nesta NF-e/i)).not.toBeInTheDocument();
  });

  it('exibe mensagem quando não há itens no XML', async () => {
    vi.mocked(nfeEntradasService.getById).mockResolvedValue(entradaSemItensXml);
    render(<NFeEntradaRevisaoDrawer nfeId={42} open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('Itens')).toBeInTheDocument();
      expect(screen.getByText('Nenhum item encontrado no XML importado.')).toBeInTheDocument();
    });
    expect(screen.queryByText('Itens do XML — somente leitura')).not.toBeInTheDocument();
  });

  it('exibe seções de checklist da revisão', async () => {
    render(<NFeEntradaRevisaoDrawer nfeId={42} open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('Identificação da NF-e')).toBeInTheDocument();
      expect(screen.getByText('Emitente / Destinatário')).toBeInTheDocument();
      expect(screen.getByText('Chave de acesso')).toBeInTheDocument();
      expect(screen.getByText('Valores')).toBeInTheDocument();
      expect(screen.getByText('Status operacional')).toBeInTheDocument();
    });
  });
});
