/**
 * Tarefa A1 — corridas adicionais com os mesmos dados técnicos no Certificado de Fornecedor.
 * Cobre: nomenclatura/texto explicativo/aviso de herança na UI, soma visível e derivada da
 * principal, bloqueio de soma excedida e duplicidade, compatibilidade com registros antigos
 * sem quantidade e aplicação da corrida realmente encontrada na busca (dados herdados).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import CertificadosFornecedor from '@/pages/CertificadosFornecedor';
import {
  AVISO_DADOS_HERDADOS_CORRIDA_CF,
  MSG_CORRIDA_LOTE_DUPLICADA_CF,
  MSG_CORRIDA_OBRIGATORIA_LINHA_ADICIONAL_CF,
  MSG_DISTRIBUICAO_INCOMPLETA_CF,
  MSG_PRINCIPAL_SEM_QUANTIDADE_CF,
  MSG_QUANTIDADE_OBRIGATORIA_NOVA_CORRIDA_CF,
  MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF,
  TEXTO_EXPLICATIVO_CORRIDAS_ADICIONAIS_CF,
  TITULO_CORRIDAS_ADICIONAIS_CF,
  avisosCorridasAdicionaisItemCf,
  chaveCorridaLoteNormalizada,
  errosCorridasAdicionaisItemCf,
  resumoQuantidadesCorridasItemCf,
} from '@/lib/cfCorridasAdicionaisUi';
import { corridaLoteEfetivosResultadoFornecedor } from '@/services/api/certificadosFornecedor';
import type {
  CertificadoFornecedorEntrada,
  DadosTecnicosFornecedorResultado,
  ItemCertificadoFornecedorEntrada,
} from '@/types';

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

const updateMock = vi.fn();

vi.mock('@/services/api/certificadosFornecedor', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/services/api/certificadosFornecedor')>();
  return {
    ...mod,
    certificadosFornecedorService: {
      ...mod.certificadosFornecedorService,
      listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }),
      update: (...args: unknown[]) => updateMock(...args),
      create: vi.fn().mockResolvedValue({}),
    },
  };
});

vi.mock('@/services/api/fiscal', () => ({
  nfeEntradasService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/nfeEntradaHistoricaImportada', () => ({
  nfeEntradaHistoricaImportadaService: { list: vi.fn().mockResolvedValue([]) },
}));

const itemBase = (over: Partial<ItemCertificadoFornecedorEntrada> = {}): ItemCertificadoFornecedorEntrada => ({
  ordem: 1,
  codigo_produto: 'P-001',
  descricao_material: 'Flange A105',
  quantidade: 14,
  unidade: 'PC',
  corrida: '3242',
  lote: '',
  norma: 'ASTM A105',
  tipo_dados_tecnicos: 'PADRAO_ITEM',
  composicao_json: {},
  ensaio_tracao_json: {},
  ensaio_impacto_json: {},
  ativo: true,
  componentes: [],
  corridas_adicionais: [],
  ...over,
});

const certificadoBase = (itens: ItemCertificadoFornecedorEntrada[]): CertificadoFornecedorEntrada => ({
  id: 42,
  numero_certificado_fornecedor: 'CF-42',
  fornecedor: null,
  fornecedor_nome_snapshot: 'Fornecedor Teste',
  fornecedor_cnpj_snapshot: '',
  numero_nf_entrada: '123',
  serie_nf_entrada: '1',
  data_nf_entrada: '2026-01-10',
  status: 'rascunho',
  observacoes: '',
  criado_em: '2026-01-10T00:00:00Z',
  atualizado_em: '2026-01-10T00:00:00Z',
  itens,
} as CertificadoFornecedorEntrada);

describe('CF A1 — resumo de quantidades (principal derivada, sem redistribuição automática)', () => {
  it('deriva a principal como total menos adicionais (14 = 8 + 6) sem aviso de incompletude', () => {
    const resumo = resumoQuantidadesCorridasItemCf(itemBase({
      corridas_adicionais: [{ ordem: 1, corrida: 'AB337', lote: '', quantidade: 6 }],
    }));
    expect(resumo.quantidadeItem).toBe(14);
    expect(resumo.somaAdicionais).toBe(6);
    expect(resumo.principalDerivada).toBe(8);
    expect(resumo.excedeQuantidadeItem).toBe(false);
    expect(resumo.principalSemQuantidade).toBe(false);
    // Soma menor que o total é a distribuição normal: a principal recebe o saldo.
    expect(resumo.distribuicaoIncompleta).toBe(false);
    expect(avisosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ ordem: 1, corrida: 'AB337', lote: '', quantidade: 6 }],
    }))).toEqual([]);
  });

  it('duas adicionais (6 + 3) derivam principal 5 sem aviso de incompletude', () => {
    const resumo = resumoQuantidadesCorridasItemCf(itemBase({
      corridas_adicionais: [
        { ordem: 1, corrida: 'AB337', lote: '', quantidade: 6 },
        { ordem: 2, corrida: 'CC001', lote: '', quantidade: 3 },
      ],
    }));
    expect(resumo.principalDerivada).toBe(5);
    expect(resumo.distribuicaoIncompleta).toBe(false);
    expect(resumo.principalSemQuantidade).toBe(false);
  });

  it('soma igual ao total deixa a principal sem quantidade (14 = 14 + 0)', () => {
    const resumo = resumoQuantidadesCorridasItemCf(itemBase({
      corridas_adicionais: [{ ordem: 1, corrida: 'AB337', lote: '', quantidade: 14 }],
    }));
    expect(resumo.principalSemQuantidade).toBe(true);
    expect(resumo.excedeQuantidadeItem).toBe(false);
    expect(resumo.principalDerivada).toBe(0);
  });

  it('marca excedente quando adicionais ultrapassam o total do item', () => {
    const resumo = resumoQuantidadesCorridasItemCf(itemBase({
      corridas_adicionais: [
        { ordem: 1, corrida: 'AB337', lote: '', quantidade: 8 },
        { ordem: 2, corrida: 'CC001', lote: '', quantidade: 7 },
      ],
    }));
    expect(resumo.excedeQuantidadeItem).toBe(true);
    expect(resumo.principalSemQuantidade).toBe(false);
    expect(resumo.principalDerivada).toBe(-1);
  });

  it('distribuição incompleta quando linha antiga não tem quantidade (sem inventar valores)', () => {
    const resumo = resumoQuantidadesCorridasItemCf(itemBase({
      corridas_adicionais: [{ id: 9, ordem: 1, corrida: 'AB337', lote: '', quantidade: null }],
    }));
    expect(resumo.distribuicaoIncompleta).toBe(true);
    expect(resumo.principalDerivada).toBeNull();
    expect(avisosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ id: 9, ordem: 1, corrida: 'AB337', lote: '', quantidade: null }],
    }))).toEqual([MSG_DISTRIBUICAO_INCOMPLETA_CF]);
  });
});

describe('CF A1 — erros bloqueantes das corridas adicionais', () => {
  it('sem adicionais não gera erro (item só com principal segue funcionando)', () => {
    expect(errosCorridasAdicionaisItemCf(itemBase())).toEqual([]);
  });

  it('soma maior que a quantidade do item bloqueia', () => {
    const erros = errosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [
        { ordem: 1, corrida: 'AB337', lote: '', quantidade: 8 },
        { ordem: 2, corrida: 'CC001', lote: '', quantidade: 7 },
      ],
    }));
    expect(erros).toContain(MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF);
    expect(erros).not.toContain(MSG_PRINCIPAL_SEM_QUANTIDADE_CF);
  });

  it('soma igual ao total bloqueia com mensagem de principal sem quantidade (uma única vez)', () => {
    const item = itemBase({
      corridas_adicionais: [
        { ordem: 1, corrida: 'AB337', lote: '', quantidade: 8 },
        { ordem: 2, corrida: 'CC001', lote: '', quantidade: 6 },
      ],
    });
    const erros = errosCorridasAdicionaisItemCf(item);
    expect(erros.filter((m) => m === MSG_PRINCIPAL_SEM_QUANTIDADE_CF)).toHaveLength(1);
    expect(erros).not.toContain(MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF);
    expect(avisosCorridasAdicionaisItemCf(item)).toEqual([]);
  });

  it('duplicidade corrida+lote normalizada bloqueia (inclui a principal) sem repetir a mensagem', () => {
    const erros = errosCorridasAdicionaisItemCf(itemBase({
      corrida: 'AB 337',
      lote: 'L1',
      corridas_adicionais: [
        { ordem: 1, corrida: 'ab  337', lote: 'l1', quantidade: 3 },
        { ordem: 2, corrida: 'AB337X', lote: 'L1', quantidade: 3 },
        { ordem: 3, corrida: 'AB337X', lote: 'L1', quantidade: 2 },
      ],
    }));
    expect(erros.filter((m) => m === MSG_CORRIDA_LOTE_DUPLICADA_CF)).toHaveLength(1);
  });

  it('nova linha exige quantidade > 0; linha antiga sem quantidade não bloqueia (histórico)', () => {
    const nova = errosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ ordem: 1, corrida: 'AB337', lote: '', quantidade: null }],
    }));
    expect(nova).toContain(MSG_QUANTIDADE_OBRIGATORIA_NOVA_CORRIDA_CF);

    const antiga = errosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ id: 7, ordem: 1, corrida: 'AB337', lote: '', quantidade: null }],
    }));
    expect(antiga).toEqual([]);
  });

  it('quantidade zero ou negativa bloqueia mesmo em linha antiga', () => {
    const erros = errosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ id: 7, ordem: 1, corrida: 'AB337', lote: '', quantidade: 0 }],
    }));
    expect(erros).toContain(MSG_QUANTIDADE_OBRIGATORIA_NOVA_CORRIDA_CF);
  });

  it('linha totalmente vazia pede corrida ou remoção', () => {
    const erros = errosCorridasAdicionaisItemCf(itemBase({
      corridas_adicionais: [{ ordem: 1, corrida: '', lote: '', quantidade: null }],
    }));
    expect(erros).toContain(MSG_CORRIDA_OBRIGATORIA_LINHA_ADICIONAL_CF);
  });

  it('chave normalizada trata caixa e espaços triviais', () => {
    expect(chaveCorridaLoteNormalizada(' ab  337 ', ' l1 ')).toBe(chaveCorridaLoteNormalizada('AB 337', 'L1'));
    expect(chaveCorridaLoteNormalizada('', '')).toBe('');
  });
});

describe('CF A1 — busca: corrida encontrada prevalece quando dados são herdados', () => {
  it('aplica a corrida adicional encontrada, não a principal do outro item', () => {
    const resultado = {
      id: 1,
      certificado_fornecedor_id: 2,
      codigo_produto: 'P-001',
      descricao_material: 'Flange',
      corrida: '3242',
      lote: '',
      dados_tecnicos_herdados: true,
      corrida_encontrada: 'AB337',
      lote_encontrado: 'LB1',
      tipo_dados_tecnicos: 'PADRAO_ITEM',
    } as DadosTecnicosFornecedorResultado;
    expect(corridaLoteEfetivosResultadoFornecedor(resultado)).toEqual({ corrida: 'AB337', lote: 'LB1' });
  });

  it('sem herança mantém comportamento atual (corrida do item)', () => {
    const resultado = {
      id: 1,
      certificado_fornecedor_id: 2,
      codigo_produto: 'P-001',
      descricao_material: 'Flange',
      corrida: '3242',
      lote: 'L9',
      tipo_dados_tecnicos: 'PADRAO_ITEM',
    } as DadosTecnicosFornecedorResultado;
    expect(corridaLoteEfetivosResultadoFornecedor(resultado)).toEqual({ corrida: '3242', lote: 'L9' });
  });
});

describe('CF A1 — apresentação na página CertificadosFornecedor', () => {
  beforeEach(() => {
    paginated.items = [];
    paginated.count = 0;
    updateMock.mockReset();
  });

  const abrirEdicao = () => {
    render(<CertificadosFornecedor />);
    fireEvent.click(screen.getByTitle('Abrir cadastro do certificado de fornecedor'));
  };

  it('exibe título, texto explicativo, aviso de herança e soma visível', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [{ id: 5, ordem: 1, corrida: 'AB337', lote: '', quantidade: 6 }],
    })])];
    paginated.count = 1;
    abrirEdicao();
    expect(screen.getByText(TITULO_CORRIDAS_ADICIONAIS_CF)).toBeInTheDocument();
    expect(screen.getByText(TEXTO_EXPLICATIVO_CORRIDAS_ADICIONAIS_CF)).toBeInTheDocument();
    expect(screen.getByText(AVISO_DADOS_HERDADOS_CORRIDA_CF)).toBeInTheDocument();
    expect(screen.getByText(/Corrida principal \(calculada\):\s*8/)).toBeInTheDocument();
    // Principal com saldo é distribuição completa — nenhum aviso de incompletude.
    expect(screen.queryByText(MSG_DISTRIBUICAO_INCOMPLETA_CF)).not.toBeInTheDocument();
    expect(screen.queryByText(/origem física confirmada/i)).not.toBeInTheDocument();
  });

  it('bloqueia salvar quando a soma iguala o total (principal ficaria sem quantidade)', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [
        { id: 5, ordem: 1, corrida: 'AB337', lote: '', quantidade: 8 },
        { id: 6, ordem: 2, corrida: 'CC001', lote: '', quantidade: 6 },
      ],
    })])];
    paginated.count = 1;
    abrirEdicao();
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }));
    expect(screen.getByText(`- Item 1: ${MSG_PRINCIPAL_SEM_QUANTIDADE_CF}`)).toBeInTheDocument();
    expect(updateMock).not.toHaveBeenCalled();
  });

  it('adiciona e remove linha adicional sem redistribuir quantidades', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [{ id: 5, ordem: 1, corrida: 'AB337', lote: '', quantidade: 6 }],
    })])];
    paginated.count = 1;
    abrirEdicao();
    fireEvent.click(screen.getByRole('button', { name: /\+ Adicionar corrida/ }));
    expect(screen.getAllByPlaceholderText('Corrida')).toHaveLength(2);
    // A quantidade existente permanece 6 (nenhuma divisão igualitária).
    expect(screen.getByDisplayValue('6')).toBeInTheDocument();
    const removeButtons = screen.getAllByTitle('Remover corrida adicional');
    fireEvent.click(removeButtons[removeButtons.length - 1]);
    expect(screen.getAllByPlaceholderText('Corrida')).toHaveLength(1);
  });

  it('bloqueia salvar quando a soma excede a quantidade do item, sem chamar a API', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [
        { id: 5, ordem: 1, corrida: 'AB337', lote: '', quantidade: 8 },
        { id: 6, ordem: 2, corrida: 'CC001', lote: '', quantidade: 7 },
      ],
    })])];
    paginated.count = 1;
    abrirEdicao();
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }));
    expect(screen.getAllByText(new RegExp(MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF)).length).toBeGreaterThan(0);
    expect(updateMock).not.toHaveBeenCalled();
  });

  it('bloqueia salvar com corrida/lote duplicada e mostra mensagem específica uma única vez no topo', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [
        { id: 5, ordem: 1, corrida: 'AB337', lote: 'L1', quantidade: 3 },
        { id: 6, ordem: 2, corrida: 'ab 337', lote: 'l1', quantidade: 3 },
      ],
    })])];
    paginated.count = 1;
    abrirEdicao();
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }));
    expect(screen.getByText(`- Item 1: ${MSG_CORRIDA_LOTE_DUPLICADA_CF}`)).toBeInTheDocument();
    expect(updateMock).not.toHaveBeenCalled();
  });

  it('CF histórico sem quantidade continua editável: aviso de parcialidade e salvar segue permitido', () => {
    paginated.items = [certificadoBase([itemBase({
      corridas_adicionais: [{ id: 5, ordem: 1, corrida: 'AB337', lote: '', quantidade: null }],
    })])];
    paginated.count = 1;
    abrirEdicao();
    expect(screen.getByText(MSG_DISTRIBUICAO_INCOMPLETA_CF)).toBeInTheDocument();
    updateMock.mockResolvedValueOnce({});
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }));
    expect(updateMock).toHaveBeenCalledTimes(1);
  });
});
