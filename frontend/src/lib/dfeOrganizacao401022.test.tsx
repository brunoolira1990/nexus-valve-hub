/** ERP 4.0.10.2.2 — conferência segura de CT-e importado. */
import { type ReactElement } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CTeEntrada from '@/pages/CTeEntrada';
import CTeHistoricoImportado from '@/pages/CTeHistoricoImportado';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { participantesCteFromDetalhe, formatComponentesFrete } from '@/lib/cteParticipanteFormat';

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

const paginatedEmpty = {
  items: [] as unknown[],
  count: 0,
  page: 1,
  pageSize: 20,
  totalPages: 0,
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
};

const cteProcessado = {
  id: 1,
  chave_acesso: '1'.repeat(44),
  numero: '100',
  serie: '1',
  dh_emissao: '2026-05-15T10:00:00',
  valor_total_servico: 1500,
  valor_receber: 1500,
  icms_base: 0,
  icms_aliquota: 0,
  icms_valor: 0,
  modal: '01',
  tipo_servico: '0',
  municipio_inicio: 'SP',
  uf_inicio: 'SP',
  municipio_fim: 'RJ',
  uf_fim: 'RJ',
  cstat: '100',
  protocolo: '1',
  transportadora: null,
  transportadora_nome: 'Transp Teste',
  empresa_tomadora: null,
  empresa_tomadora_nome: 'Tomador Teste',
  empresa_destinataria: null,
  empresa_recebedora: null,
  fornecedor_remetente: null,
  fornecedor_remetente_nome: '',
  empresa_id: null,
  empresa_nome: '',
  papel_empresa: '',
  papel_empresa_no_documento: '',
  cancelado: false,
  status_documento: 'AUTORIZADO',
  data_cancelamento: null,
  protocolo_cancelamento: '',
  motivo_cancelamento: '',
  status_visual: 'autorizado',
  cstat_visual: '100',
  motivo_visual: '',
  nome_arquivo: 'cte.xml',
  importado_em: '2026-05-15T12:00:00',
  importado: true,
  origem_externa: true,
  historico: true,
  status_conferencia: 'PROCESSADO',
  apto_operacional: false,
  classificacao_dfe: {
    categoria: 'BASE_DFE_IMPORTADA',
    badges: ['base_importada', 'producao', 'apura'],
    pode_entrar_apuracao: true,
    pode_alimentar_precificacao: true,
    pode_gerar_efeito_operacional: false,
  },
};

const detalheMock = {
  ...cteProcessado,
  modelo: '57',
  tp_amb: '1',
  nat_op: 'PREST',
  cfop: '5353',
  versao_layout: '4.00',
  xmotivo: 'Autorizado',
  componentes_frete_json: [{ xNome: 'Frete', vComp: '100' }],
  emit_json: { xNome: 'Transp Teste', CNPJ: '11222333000181' },
  rem_json: {},
  dest_json: {},
  exped_json: {},
  receb_json: {},
  tomador_json: { xNome: 'Tomador Teste', CNPJ: '11444777000161' },
  totais_json: {},
  imposto_json: {},
  prot_json: {},
  reforma_e_outros_json: {},
  chaves_nfe_vinculadas: [],
  documentos_vinculados_resumo: [],
  eventos: [],
  checklist_conferencia_json: {},
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: vi.fn(() => paginatedEmpty),
}));

vi.mock('@/services/api/cteHistoricoImportado', () => ({
  cteHistoricoImportadoService: {
    listPaginated: vi.fn(),
    importarXmls: vi.fn(),
    getById: vi.fn(),
    conferir: vi.fn(),
    marcarDivergente: vi.fn(),
    ignorarOperacional: vi.fn(),
    resumoGerencial: vi.fn().mockResolvedValue({
      totais: { valor_total_fretes: 0, quantidade_ctes: 0, frete_medio: 0 },
      indicadores_gerenciais: {
        peso_frete_sobre_faturamento_pct: 0,
        peso_frete_sobre_compras_pct: 0,
        frete_medio_observado: 0,
      },
      base_comparativa: { faturamento: 0, compras: 0 },
    }),
    transportadorasGerencial: vi.fn().mockResolvedValue({ transportadoras: [] }),
    serieMensalGerencial: vi.fn().mockResolvedValue({ meses: [] }),
    serieTrimestralGerencial: vi.fn().mockResolvedValue({ trimestres: [] }),
  },
}));

vi.mock('@/services/api/fiscal', () => ({
  cteEntradasService: { listPaginated: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
}));

vi.mock('@/services/api/empresas', () => ({
  empresasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/transportadoras', () => ({
  transportadorasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

import { usePaginatedList } from '@/hooks/usePaginatedList';
import { cteHistoricoImportadoService } from '@/services/api/cteHistoricoImportado';
import { cteEntradasService } from '@/services/api/fiscal';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ERP 4.0.10.2.2 CT-e conferência', () => {
  it('participantes em cards a partir do JSON', () => {
    const cards = participantesCteFromDetalhe(detalheMock as never);
    expect(cards.some((c) => c.papel.includes('Transportadora'))).toBe(true);
    expect(cards.some((c) => c.razaoSocial.includes('Tomador'))).toBe(true);
  });

  it('componentes de frete formatados', () => {
    const comps = formatComponentesFrete(detalheMock.componentes_frete_json);
    expect(comps.length).toBeGreaterThan(0);
    expect(comps[0].nome).toBeTruthy();
  });

  it('modal exibe título Detalhes do CT-e importado', async () => {
    vi.mocked(cteHistoricoImportadoService.getById).mockResolvedValue(detalheMock as never);
    renderWithRouter(
      <CTeHistoricoDetalheModal open cteId={1} listRow={cteProcessado as never} onClose={() => undefined} />,
    );
    await waitFor(() => {
      expect(screen.getByText(/Detalhes do CT-e importado/i)).toBeTruthy();
    });
  });

  it('aba Conferência mostra aviso sem financeiro', async () => {
    vi.mocked(cteHistoricoImportadoService.getById).mockResolvedValue(detalheMock as never);
    renderWithRouter(
      <CTeHistoricoDetalheModal open cteId={1} abaInicial="conferencia" onClose={() => undefined} />,
    );
    await waitFor(() => {
      expect(screen.getByText(/Não gera contas a pagar/i)).toBeTruthy();
    });
    expect(screen.getByText(/Marcar como conferido/i)).toBeTruthy();
  });

  it('base importada mostra botão Conferir para processado', async () => {
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedEmpty,
      items: [cteProcessado],
      count: 1,
    } as never);
    renderWithRouter(<CTeHistoricoImportado />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Conferir/i })).toBeTruthy();
    });
  });

  it('CT-e Entrada descreve hub operacional sem efeito financeiro automático', () => {
    vi.mocked(usePaginatedList).mockReturnValue({ ...paginatedEmpty } as never);
    renderWithRouter(<CTeEntrada />);
    expect(screen.getByText(/não gera financeiro/i)).toBeTruthy();
  });

  it('CT-e Entrada lista conferido com badges', async () => {
    const conferido = {
      id: 1,
      numero: '100',
      serie: '1',
      transportadora_nome: 'Transp',
      tomador_nome: 'Tomador',
      valor_frete: 1500,
      data: '2026-05-15',
      status_conferencia: 'CONFERIDO',
      qtd_nfe_referenciadas: 2,
      impostos: {
        icms_base: 1500,
        icms_aliquota: 12,
        icms_valor: 180,
        cbs_valor: 0,
        ibs_valor: 0,
        tem_reforma_ibscbs: false,
      },
      classificacao_dfe: {
        categoria: 'BASE_DFE_IMPORTADA',
        badges: ['conferido', 'sem_financeiro_automatico', 'sem_expedicao_automatica'],
        pode_entrar_apuracao: true,
        pode_alimentar_precificacao: true,
        pode_gerar_efeito_operacional: false,
      },
    };
    vi.mocked(usePaginatedList).mockReturnValue({
      ...paginatedEmpty,
      items: [conferido],
      count: 1,
    } as never);
    renderWithRouter(<CTeEntrada />);
    expect(screen.getByText('Transp')).toBeTruthy();
    expect(screen.getAllByText(/Conferido/i).length).toBeGreaterThan(0);
    expect(screen.getByText('ICMS')).toBeTruthy();
    expect(screen.getByText('R$ 180.00')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Detalhes' })).toBeTruthy();
  });

  it('marcar divergente exige motivo no modal', async () => {
    vi.mocked(cteHistoricoImportadoService.getById).mockResolvedValue(detalheMock as never);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderWithRouter(
      <CTeHistoricoDetalheModal open cteId={1} abaInicial="conferencia" onClose={() => undefined} />,
    );
    await waitFor(() => screen.getByText(/Marcar como divergente/i));
    fireEvent.click(screen.getByRole('button', { name: /Marcar como divergente/i }));
    await waitFor(() => {
      expect(screen.getByText(/motivo da divergência/i)).toBeTruthy();
    });
    confirmSpy.mockRestore();
  });
});
