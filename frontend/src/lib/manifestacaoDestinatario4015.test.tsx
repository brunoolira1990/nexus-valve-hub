/** ERP 4.0.15 — Manifestação Destinatário (UI). */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ManifestacaoDestinatario from '@/pages/ManifestacaoDestinatario';

const { docPendente, paginatedWithData } = vi.hoisted(() => {
  const doc = {
    id: 1,
    empresa_id: 1,
    empresa_nome: 'Nexus Teste',
    chave_acesso: '3'.repeat(44),
    chave_resumida: '3333…3333',
    nsu: '100',
    cnpj_emitente: '22222222000122',
    razao_social_emitente: 'Fornecedor Manifest',
    dh_emissao: '2026-06-10T10:00:00',
    valor_nf: '1500.00',
    status_manifestacao: 'PENDENTE' as const,
    status_manifestacao_label: 'Pendente',
    status_xml: 'RESUMO' as const,
    status_xml_label: 'Resumo recebido',
    ambiente: '1',
    ambiente_label: 'Produção',
    classificacao_dfe: 'NFE_ENTRADA',
    ultimo_cstat: '',
    ultimo_xmotivo: '',
    nf_entrada_historica_id: null,
    manifestado_em: null,
    xml_baixado_em: null,
    consultado_em: '2026-06-10T12:00:00',
  };

  return {
    docPendente: doc,
    paginatedWithData: {
      items: [doc],
      count: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
      search: '',
      setSearch: vi.fn(),
      setPage: vi.fn(),
      setPageSize: vi.fn(),
      filters: {} as Record<string, string>,
      setFilter: vi.fn(),
      setFilters: vi.fn(),
      loading: false,
      error: null as string | null,
      reload: vi.fn(),
    },
  };
});

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

function renderWithRouter(ui: ReactElement) {
  return render(
    <MemoryRouter future={routerFuture}>
      {ui}
    </MemoryRouter>,
  );
}

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: { id: 1, nome_exibicao: 'Nexus Teste', cnpj: '11.111.111/0001-11' },
      usuario: { id: 1, nome: 'Admin' },
    },
    loading: false,
    refresh: vi.fn(),
  }),
}));

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: vi.fn(() => paginatedWithData),
}));

vi.mock('@/services/api/manifestacaoDestinatario', () => ({
  manifestacaoDestinatarioService: {
    fechamentoPreview: vi.fn().mockResolvedValue({
      empresa_id: 1,
      data_inicio: '',
      data_fim: '',
      total_documentos: 1,
      xml_baixados: 0,
      xml_pendentes: 1,
      sem_manifestacao: 1,
      erros: 0,
    }),
    get: vi.fn(),
    consultar: vi.fn(),
    manifestar: vi.fn(),
    baixarXml: vi.fn(),
  },
  DESCRICAO_EVENTO_MANIFESTACAO: {},
  LABEL_EVENTO_MANIFESTACAO: {
    CIENCIA_EMISSAO: 'Ciência da Emissão',
    CONFIRMACAO_OPERACAO: 'Confirmação da Operação',
    DESCONHECIMENTO: 'Desconhecimento da Operação',
    OPERACAO_NAO_REALIZADA: 'Operação não Realizada',
  },
}));

describe('ManifestacaoDestinatario', () => {
  afterEach(() => cleanup());

  it('renderiza título e documento pendente', async () => {
    renderWithRouter(<ManifestacaoDestinatario />);
    expect(screen.getByRole('heading', { name: /Manifestação Destinatário/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Consultar DF-e/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Fornecedor Manifest')).toBeInTheDocument();
      expect(screen.getByText(/Pendente/i)).toBeInTheDocument();
    });
  });

  it('estado vazio quando lista sem itens', async () => {
    const { usePaginatedList } = await import('@/hooks/usePaginatedList');
    vi.mocked(usePaginatedList).mockReturnValueOnce({
      ...paginatedWithData,
      items: [],
      count: 0,
      totalPages: 0,
    });
    renderWithRouter(<ManifestacaoDestinatario />);
    expect(screen.getByText(/Nenhuma NF-e destinada encontrada/i)).toBeInTheDocument();
  });
});
