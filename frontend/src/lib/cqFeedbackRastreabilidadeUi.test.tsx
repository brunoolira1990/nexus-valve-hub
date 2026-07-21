/**
 * Fase 1 — feedback visual de rastreabilidade no Certificado de Qualidade.
 * Cobre: deduplicação de mensagens (corridas irmãs), banner «Origem manual»
 * restrito a origem realmente manual e separação entre prontidão técnica e
 * origem documental na apresentação (sem afirmar origem física).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import Certificados from '@/pages/Certificados';
import {
  itemCqTemOrigemDocumental,
  origemFisicaCqBadge,
  origemFisicaCqItem,
  origemFisicaCqResumo,
} from '@/lib/certificadoStatusUi';
import {
  MSG_SEM_CORRIDAS_IRMAS,
  mesclarMensagensUnicas,
  removerMensagens,
} from '@/lib/cqMensagensUi';
import type { CertificadoQualidade, ItemCertificadoQualidade } from '@/types';

const paginated = {
  items: [] as unknown[],
  count: 0,
  page: 1,
  pageSize: 20,
  totalPages: 0,
  search: '',
  setSearch: vi.fn(),
  setPage: vi.fn(),
  setPageSize: vi.fn(),
  filters: {},
  setFilter: vi.fn(),
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock('@/hooks/usePaginatedList', () => ({
  usePaginatedList: () => paginated,
}));

vi.mock('@/services/api/qualidade', () => ({
  certificadosQualidadeService: {
    listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }),
    obterNfeOpcao: vi.fn().mockResolvedValue(null),
    corridasDisponiveisPorProduto: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('@/services/api/certificadosFornecedor', () => ({
  certificadosFornecedorService: {
    listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }),
  },
  corridaLoteEfetivosResultadoFornecedor: vi.fn(),
  mensagemPrincipalBuscaDadosTecnicosFornecedor: vi.fn(),
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: { search: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/nfeHistoricaImportada', () => ({
  nfeHistoricaImportadaService: { list: vi.fn().mockResolvedValue([]) },
}));

const itemBase = (over: Partial<ItemCertificadoQualidade> = {}): ItemCertificadoQualidade => ({
  ordem: 1,
  codigo_produto: 'P-001',
  descricao_material: 'Barra redonda',
  quantidade: 10,
  unidade: 'KG',
  norma: '',
  corrida: '',
  lote: '',
  incluir_no_certificado: true,
  ...over,
});

const certificadoBase = (itens: ItemCertificadoQualidade[]): CertificadoQualidade => ({
  id: 77,
  numero: '77',
  serie: '1',
  numero_formatado: 'CQ-77',
  cliente_nome_snapshot: 'Cliente Teste',
  nota_fiscal_numero: '',
  status: 'rascunho',
  tipo_certificado: 'PADRAO_POR_NFE',
  criado_em: '2026-01-01T00:00:00Z',
  atualizado_em: '2026-01-01T00:00:00Z',
  itens,
});

describe('CQ — deduplicação de mensagens operacionais', () => {
  it('mensagem de corridas irmãs não duplica em tentativas repetidas', () => {
    let mensagens: string[] = [];
    mensagens = mesclarMensagensUnicas(mensagens, MSG_SEM_CORRIDAS_IRMAS);
    mensagens = mesclarMensagensUnicas(mensagens, MSG_SEM_CORRIDAS_IRMAS);
    mensagens = mesclarMensagensUnicas(mensagens, MSG_SEM_CORRIDAS_IRMAS);
    expect(mensagens).toEqual([MSG_SEM_CORRIDAS_IRMAS]);
  });

  it('mensagens diferentes coexistem e lote com duplicatas internas é deduplicado', () => {
    let mensagens = ['Alerta de NCM divergente.'];
    mensagens = mesclarMensagensUnicas(mensagens, [
      MSG_SEM_CORRIDAS_IRMAS,
      MSG_SEM_CORRIDAS_IRMAS,
      'Outro aviso.',
    ]);
    expect(mensagens).toEqual([
      'Alerta de NCM divergente.',
      MSG_SEM_CORRIDAS_IRMAS,
      'Outro aviso.',
    ]);
  });

  it('sucesso posterior remove o aviso de ausência sem tocar nas demais mensagens', () => {
    const antes = ['Alerta de NCM divergente.', MSG_SEM_CORRIDAS_IRMAS];
    const depois = mesclarMensagensUnicas(
      removerMensagens(antes, MSG_SEM_CORRIDAS_IRMAS),
      'Linha adicionada com corrida C-100 do mesmo certificado fornecedor.',
    );
    expect(depois).toEqual([
      'Alerta de NCM divergente.',
      'Linha adicionada com corrida C-100 do mesmo certificado fornecedor.',
    ]);
  });

  it('sem novas mensagens, preserva a referência do array (evita re-render inútil)', () => {
    const atuais = [MSG_SEM_CORRIDAS_IRMAS];
    expect(mesclarMensagensUnicas(atuais, MSG_SEM_CORRIDAS_IRMAS)).toBe(atuais);
    expect(removerMensagens(atuais, 'Mensagem inexistente')).toBe(atuais);
  });
});

describe('CQ — classificação da origem documental (somente payload existente)', () => {
  it('corrida digitada manualmente não gera origem documental confirmada', () => {
    const item = itemBase({ corrida: 'C-DIGITADA' });
    expect(origemFisicaCqItem(item)).toBe('MANUAL');
    expect(origemFisicaCqBadge(origemFisicaCqItem(item)).label).not.toBe('Origem documental confirmada');
  });

  it('item vazio sem origem documental fica como não confirmada', () => {
    expect(origemFisicaCqItem(itemBase())).toBe('NAO_CONFIRMADA');
  });

  it('CF vinculado com corrida/lote da origem e sem avisos é origem documental confirmada', () => {
    const item = itemBase({
      certificado_fornecedor_origem_id: 5,
      item_certificado_fornecedor_origem_id: 9,
      corrida: 'C-100',
      corrida_snapshot: 'C-100',
      lote_snapshot: 'L-1',
    });
    expect(origemFisicaCqItem(item)).toBe('CONFIRMADA');
    expect(origemFisicaCqBadge('CONFIRMADA').label).toBe('Origem documental confirmada');
  });

  it('CF vinculado sem corrida/lote identificado na origem é parcial, não manual', () => {
    const item = itemBase({ certificado_fornecedor_origem_id: 5, corrida: 'C-100' });
    expect(origemFisicaCqItem(item)).toBe('PARCIAL');
    expect(itemCqTemOrigemDocumental(item)).toBe(true);
  });

  it('CF vinculado com avisos pendentes é parcial', () => {
    const item = itemBase({
      certificado_fornecedor_origem_id: 5,
      corrida_snapshot: 'C-100',
      rastreabilidade_avisos: ['Rastreabilidade física não vinculada. Isso não impede a emissão do certificado.'],
    });
    expect(origemFisicaCqItem(item)).toBe('PARCIAL');
  });

  it('motivo CF_NAO_VINCULADO_MANUAL prevalece como origem manual', () => {
    const item = itemBase({
      corrida: 'C-100',
      rastreabilidade_motivos: ['CF_NAO_VINCULADO_MANUAL'],
    });
    expect(origemFisicaCqItem(item)).toBe('MANUAL');
  });

  it('resumo agrega de forma conservadora', () => {
    const confirmado = itemBase({ certificado_fornecedor_origem_id: 5, corrida_snapshot: 'C-1' });
    const manual = itemBase({ corrida: 'C-DIGITADA' });
    expect(origemFisicaCqResumo([confirmado])).toBe('CONFIRMADA');
    expect(origemFisicaCqResumo([confirmado, manual])).toBe('PARCIAL');
    expect(origemFisicaCqResumo([manual])).toBe('MANUAL');
    expect(origemFisicaCqResumo([])).toBe('NAO_CONFIRMADA');
    expect(origemFisicaCqResumo([itemBase({ incluir_no_certificado: false, corrida: 'X' })])).toBe('NAO_CONFIRMADA');
  });
});

describe('CQ — apresentação no modal (prontidão técnica × origem documental)', () => {
  beforeEach(() => {
    paginated.items = [];
    paginated.count = 0;
  });

  it('novo certificado exibe blocos separados e não exibe banner de origem manual sem itens', () => {
    render(<Certificados />);
    fireEvent.click(screen.getAllByRole('button', { name: /Novo certificado/i })[0]);
    expect(screen.getByText('Prontidão técnica')).toBeInTheDocument();
    expect(screen.getByText('Origem documental')).toBeInTheDocument();
    expect(screen.getByText('Origem documental não confirmada')).toBeInTheDocument();
    expect(screen.queryByText(/Origem física/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/não comprova, nesta fase, a origem física da quantidade consumida no estoque ou na alocação da venda/i),
    ).toBeInTheDocument();
    expect(screen.queryByText('Origem manual dos dados técnicos')).not.toBeInTheDocument();
  });

  it('item sem CF vinculado exibe banner de origem manual e badge manual no item', () => {
    paginated.items = [certificadoBase([itemBase({ corrida: 'C-MANUAL' })])];
    paginated.count = 1;
    render(<Certificados />);
    fireEvent.click(screen.getByTitle('Editar certificado'));
    expect(screen.getByText('Origem manual dos dados técnicos')).toBeInTheDocument();
    expect(screen.getAllByText('Origem manual').length).toBeGreaterThan(0);
    expect(screen.queryByText('Origem documental confirmada')).not.toBeInTheDocument();
  });

  it('aviso físico com CF vinculado não dispara banner de origem manual', () => {
    paginated.items = [certificadoBase([
      itemBase({
        certificado_fornecedor_origem_id: 5,
        item_certificado_fornecedor_origem_id: 9,
        tem_certificado_fornecedor: true,
        corrida: 'C-100',
        corrida_snapshot: 'C-100',
        rastreabilidade_avisos: [
          'Rastreabilidade física não vinculada. Isso não impede a emissão do certificado.',
        ],
        rastreabilidade_motivos: ['RASTREABILIDADE_FISICA_OPCIONAL'],
      }),
    ])];
    paginated.count = 1;
    render(<Certificados />);
    fireEvent.click(screen.getByTitle('Editar certificado'));
    expect(screen.queryByText('Origem manual dos dados técnicos')).not.toBeInTheDocument();
    expect(screen.getAllByText('Origem documental parcial').length).toBeGreaterThan(0);
  });

  it('CF vinculado sem corrida/lote da origem exibe aviso específico de rastreabilidade incompleta', () => {
    paginated.items = [certificadoBase([
      itemBase({
        certificado_fornecedor_origem_id: 5,
        tem_certificado_fornecedor: true,
        corrida: 'C-100',
      }),
    ])];
    paginated.count = 1;
    render(<Certificados />);
    fireEvent.click(screen.getByTitle('Editar certificado'));
    expect(screen.getByText('Rastreabilidade incompleta na origem vinculada')).toBeInTheDocument();
    expect(screen.queryByText('Origem manual dos dados técnicos')).not.toBeInTheDocument();
    expect(screen.queryByText('Origem documental confirmada')).not.toBeInTheDocument();
  });
});
