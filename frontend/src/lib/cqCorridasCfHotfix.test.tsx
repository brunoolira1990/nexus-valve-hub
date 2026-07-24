/**
 * Hotfix CQ — múltiplas corridas do CF exato como itens irmãos do CQ.
 * Cobre: helpers de distribuição (soma exata, bloqueios, duplicidade), criação de
 * itens irmãos com técnicos independentes (herdados × próprios), modal de seleção
 * e integração na página (botão, aplicação, erro de API visível, origem documental).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import Certificados from '@/pages/Certificados';
import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';
import {
  MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
  MSG_ORIGEM_DUPLICADA_CQ,
  MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ,
  MSG_QUANTIDADE_CORRIDA_OBRIGATORIA_CQ,
  MSG_SOMA_DIFERENTE_TOTAL_CQ,
  MSG_SOMA_EXCEDE_TOTAL_CQ,
  ORIGEM_STATUS_TECNICO_HERDADO_CF,
  ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES,
  TITULO_MODAL_CORRIDAS_CF_CQ,
  aplicarDistribuicaoCorridasCfCq,
  errosSelecaoCorridasCfCq,
  quantidadeTotalDistribuicaoCorridasCfCq,
  resumoDistribuicaoCorridasCfCq,
  selecoesExistentesCorridasCfCq,
  type CorridaCfParaCq,
  type CorridasCfParaCqResponse,
  type SelecaoCorridaCfCq,
} from '@/lib/cqCorridasCfUi';
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

const corridasCfMock = vi.fn();

vi.mock('@/services/api/qualidade', () => ({
  certificadosQualidadeService: {
    listPaginated: vi.fn().mockResolvedValue({ results: [], count: 0 }),
    obterNfeOpcao: vi.fn().mockResolvedValue(null),
    corridasDisponiveisPorProduto: vi.fn().mockResolvedValue([]),
    corridasCertificadoFornecedor: (...args: unknown[]) => corridasCfMock(...args),
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

const linhaCf = (over: Partial<CorridaCfParaCq> = {}): CorridaCfParaCq => ({
  chave_origem: 'certificado_fornecedor:9:3242:',
  tipo_linha: 'corrida_principal',
  corrida: '3242',
  lote: '',
  quantidade_no_certificado: '8.000',
  unidade: 'PC',
  origem_tecnica: 'dados_do_item_cf',
  origem_tecnica_label: 'Dados técnicos herdados do item principal do CF',
  dados_tecnicos_herdados: true,
  permite_preenchimento_manual: true,
  modo_dados_tecnicos_padrao: 'herdados',
  modos_dados_tecnicos_permitidos: ['herdados', 'manual'],
  certificado_fornecedor_id: 5,
  item_certificado_fornecedor_id: 9,
  codigo_produto: 'P-001',
  descricao_material: 'Flange A105',
  fornecedor_nome: 'Fornecedor X',
  numero_nf_entrada: '777',
  numero_certificado_fornecedor: 'CF-1',
  status_certificado_fornecedor: 'registrado',
  dados_tecnicos: {
    norma: 'ASTM A105',
    ncm: '84818099',
    tipo_dados_tecnicos: 'PADRAO_ITEM',
    composicao_json: { C: '0.20', Mn: '0.90' },
    ensaio_tracao_json: { limite_escoamento: '250' },
    ensaio_impacto_json: {},
  },
  ...over,
});

const linhaAdicionalAb337 = (over: Partial<CorridaCfParaCq> = {}): CorridaCfParaCq =>
  linhaCf({
    chave_origem: 'certificado_fornecedor:9:AB337:',
    tipo_linha: 'corrida_adicional',
    corrida: 'AB337',
    quantidade_no_certificado: '6.000',
    origem_tecnica: 'herdados_item_principal',
    origem_tecnica_label: 'Dados técnicos herdados do item principal',
    dados_tecnicos_herdados: true,
    ...over,
  });

const selecao = (
  linha: CorridaCfParaCq,
  quantidade: string,
  dadosTecnicos: SelecaoCorridaCfCq['dadosTecnicos'] = 'herdados',
): SelecaoCorridaCfCq => ({ linha, quantidade, dadosTecnicos });

const respostaCf = (): CorridasCfParaCqResponse => ({
  linhas: [linhaCf(), linhaAdicionalAb337()],
  avisos: [],
  mensagem_origem_fisica: MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
  limitacao_itens_independentes: 'Itens independentes sem vínculo inequívoco pertencem à A2.',
});

const itemCqBase = (over: Partial<ItemCertificadoQualidade> = {}): ItemCertificadoQualidade => ({
  id: 501,
  ordem: 1,
  codigo_produto: 'P-001',
  descricao_material: 'Flange A105',
  quantidade: 14,
  unidade: 'PC',
  norma: 'NORMA ORIGINAL',
  corrida: '3242',
  lote: '',
  produto: 12,
  tipo_dados_tecnicos: 'PADRAO_ITEM',
  incluir_no_certificado: true,
  composicao_json: { C: '0.99' },
  ensaio_tracao_json: {},
  ensaio_impacto_json: {},
  certificado_fornecedor_origem_id: 5,
  item_certificado_fornecedor_origem_id: 9,
  componentes: [],
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

describe('cqCorridasCfUi — distribuição de quantidades', () => {
  it('8 + 6 fecha o total 14 sem saldo', () => {
    const r = resumoDistribuicaoCorridasCfCq(14, [
      selecao(linhaCf(), '8'),
      selecao(linhaAdicionalAb337(), '6'),
    ]);
    expect(r.totalDistribuido).toBe(14);
    expect(r.saldoRestante).toBe(0);
    expect(
      errosSelecaoCorridasCfCq(14, [selecao(linhaCf(), '8'), selecao(linhaAdicionalAb337(), '6')]),
    ).toEqual([]);
  });

  it('sem seleção não permite aplicar', () => {
    expect(errosSelecaoCorridasCfCq(14, []).length).toBe(1);
  });

  it('quantidade vazia ou zero bloqueia (mensagem única, sem duplicar)', () => {
    const erros = errosSelecaoCorridasCfCq(14, [
      selecao(linhaCf(), ''),
      selecao(linhaAdicionalAb337(), '0'),
    ]);
    expect(erros.filter((e) => e === MSG_QUANTIDADE_CORRIDA_OBRIGATORIA_CQ)).toHaveLength(1);
  });

  it('soma maior que o total bloqueia; não divide em partes iguais automaticamente', () => {
    const erros = errosSelecaoCorridasCfCq(14, [
      selecao(linhaCf(), '14'),
      selecao(linhaAdicionalAb337(), '6'),
    ]);
    expect(erros).toContain(MSG_SOMA_EXCEDE_TOTAL_CQ);
  });

  it('soma menor que o total bloqueia a aplicação', () => {
    const erros = errosSelecaoCorridasCfCq(14, [
      selecao(linhaCf(), '8'),
      selecao(linhaAdicionalAb337(), '3'),
    ]);
    expect(erros).toContain(MSG_SOMA_DIFERENTE_TOTAL_CQ);
  });

  it('mesma corrida/origem duas vezes bloqueia', () => {
    const erros = errosSelecaoCorridasCfCq(14, [
      selecao(linhaCf(), '8'),
      selecao(linhaCf({ chave_origem: 'chave-cliente-nao-confiavel' }), '6'),
    ]);
    expect(erros).toContain(MSG_ORIGEM_DUPLICADA_CQ);
  });
});

describe('cqCorridasCfUi — criação de itens irmãos', () => {
  const selecoesPadrao = () => [
    selecao(linhaCf(), '8', 'herdados'),
    selecao(linhaAdicionalAb337(), '6', 'herdados'),
  ];

  it('primeira corrida reutiliza o item original; demais viram itens irmãos', () => {
    const itens = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()],
      0,
      respostaCf().linhas,
      selecoesPadrao(),
    );
    expect(itens).toHaveLength(2);
    expect(itens[0].id).toBe(501);
    expect(itens[0].quantidade).toBe(8);
    expect(itens[0].corrida).toBe('3242');
    expect(itens[0].certificado_fornecedor_origem_id).toBe(5);
    expect(itens[0].item_certificado_fornecedor_origem_id).toBe(9);

    const novo = itens[1];
    expect(novo.id).toBeUndefined();
    expect(novo.quantidade).toBe(6);
    expect(novo.corrida).toBe('AB337');
    expect(novo.codigo_produto).toBe('P-001');
    expect(novo.unidade).toBe('PC');
    expect(novo.fornecedor_nome_snapshot).toBe('Fornecedor X');
    expect(novo.nf_entrada_snapshot).toBe('777');
    expect(novo.origem_rastreabilidade_tipo).toBe('certificado_fornecedor');
  });

  it('herdados copia os dados técnicos da origem; editar um item não altera o outro', () => {
    const itens = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()], 0, respostaCf().linhas, selecoesPadrao(),
    );
    expect(itens[0].composicao_json).toEqual({ C: '0.20', Mn: '0.90' });
    expect(itens[0].origem_status_tecnico).toBe(ORIGEM_STATUS_TECNICO_HERDADO_CF);
    expect(itens[1].composicao_json).toEqual({ C: '0.20', Mn: '0.90' });

    (itens[1].composicao_json as Record<string, unknown>).C = '0.40';
    expect((itens[0].composicao_json as Record<string, unknown>).C).toBe('0.20');
  });

  it('dados próprios criam linha manual editável sem copiar técnicos da principal', () => {
    const itens = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()],
      0,
      respostaCf().linhas,
      [
        selecao(linhaCf(), '8', 'herdados'),
        selecao(linhaAdicionalAb337(), '6', 'proprios'),
      ],
    );
    const novo = itens[1];
    expect(novo.norma).toBe('');
    expect(novo.composicao_json).toEqual({});
    expect(novo.ensaio_tracao_json).toEqual({});
    expect(novo.ensaio_impacto_json).toEqual({});
    expect(novo.origem_status_tecnico).toBe(ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES);
    expect(novo.origem_observacoes).toContain('preenchidos manualmente');
    // Origem documental preservada mesmo com técnicos próprios.
    expect(novo.corrida).toBe('AB337');
    expect(novo.quantidade).toBe(6);
    expect(novo.certificado_fornecedor_origem_id).toBe(5);
  });

  it('aplicar duas vezes não duplica e preserva técnicos manuais já editados', () => {
    const primeira = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()], 0, respostaCf().linhas,
      [
        selecao(linhaCf(), '8', 'herdados'),
        selecao(linhaAdicionalAb337(), '6', 'proprios'),
      ],
    );
    primeira[1] = {
      ...primeira[1],
      norma: 'ASTM B',
      composicao_json: { C: '0.40' },
    };
    const segunda = aplicarDistribuicaoCorridasCfCq(
      primeira, 0, respostaCf().linhas,
      [
        selecao(linhaCf(), '8', 'herdados'),
        selecao(linhaAdicionalAb337(), '6', 'proprios'),
      ],
    );
    expect(segunda).toHaveLength(2);
    expect(segunda.map((item) => item.corrida)).toEqual(['3242', 'AB337']);
    expect(segunda[1].norma).toBe('ASTM B');
    expect(segunda[1].composicao_json).toEqual({ C: '0.40' });
  });

  it('save → reload (ids novos do servidor) → reaplicar não duplica nem troca dados', () => {
    const aplicados = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()], 0, respostaCf().linhas,
      [
        selecao(linhaCf(), '8', 'herdados'),
        selecao(linhaAdicionalAb337(), '6', 'proprios'),
      ],
    );
    // AB337 é editada manualmente antes do save (dados B).
    aplicados[1] = { ...aplicados[1], norma: 'ASTM A350 LF2', composicao_json: { C: '0.35', Cr: '1.10' } };

    // Simula reload da API: o _upsert_itens recria os itens com ids novos e o
    // backend normaliza campos operacionais para MAIÚSCULAS; a chave documental
    // (item do CF + corrida + lote) permanece estável.
    const recarregados = aplicados.map((item, idx) => ({
      ...item,
      id: 7000 + idx,
      origem_status_tecnico: (item.origem_status_tecnico || '').toUpperCase(),
    }));

    // Reabrir o modal reconstrói exatamente a divisão salva (8 herdados, 6 próprios).
    const selecoesRecuperadas = selecoesExistentesCorridasCfCq(respostaCf().linhas, recarregados);
    expect(selecoesRecuperadas.map((s) => [s.quantidade, s.dadosTecnicos]))
      .toEqual([['8', 'herdados'], ['6', 'proprios']]);

    const reaplicados = aplicarDistribuicaoCorridasCfCq(
      recarregados, 0, respostaCf().linhas, selecoesRecuperadas,
    );
    expect(reaplicados).toHaveLength(2);
    expect(reaplicados.map((item) => item.corrida)).toEqual(['3242', 'AB337']);
    // Ids do servidor preservados (identidade documental, não índice/ID temporário).
    expect(reaplicados.map((item) => item.id)).toEqual([7000, 7001]);
    // Dados A continuam na 3242 e dados B (manuais) na AB337, sem troca.
    // (a comparação de status é insensível a caixa: o backend salva em maiúsculas)
    expect(reaplicados[0].composicao_json).toEqual({ C: '0.20', Mn: '0.90' });
    expect((reaplicados[0].origem_status_tecnico || '').toLowerCase())
      .toBe(ORIGEM_STATUS_TECNICO_HERDADO_CF);
    expect(reaplicados[1].composicao_json).toEqual({ C: '0.35', Cr: '1.10' });
    expect(reaplicados[1].norma).toBe('ASTM A350 LF2');
    expect((reaplicados[1].origem_status_tecnico || '').toLowerCase())
      .toBe(ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES);
    expect(reaplicados[0].quantidade).toBe(8);
    expect(reaplicados[1].quantidade).toBe(6);
  });

  it('reabertura recupera divisão existente e total 14', () => {
    const itens = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase()], 0, respostaCf().linhas, selecoesPadrao(),
    );
    expect(selecoesExistentesCorridasCfCq(respostaCf().linhas, itens).map((s) => s.quantidade))
      .toEqual(['8', '6']);
    expect(quantidadeTotalDistribuicaoCorridasCfCq(respostaCf().linhas, itens, itens[0])).toBe(14);
  });

  it('itens não relacionados permanecem intactos e na mesma ordem relativa', () => {
    const outro = itemCqBase({
      id: 900,
      ordem: 2,
      produto: 99,
      codigo_produto: 'OUTRO',
      corrida: 'ZZ1',
      certificado_fornecedor_origem_id: null,
      item_certificado_fornecedor_origem_id: null,
      quantidade: 3,
    });
    const itens = aplicarDistribuicaoCorridasCfCq(
      [itemCqBase(), outro], 0, respostaCf().linhas, selecoesPadrao(),
    );
    expect(itens).toHaveLength(3);
    expect(itens[2].id).toBe(900);
    expect(itens[2].codigo_produto).toBe('OUTRO');
    expect(itens[2].quantidade).toBe(3);
  });
});

describe('ModalCorridasCertificadoFornecedor', () => {
  const renderModal = (over: Partial<Parameters<typeof ModalCorridasCertificadoFornecedor>[0]> = {}) => {
    const onAplicar = vi.fn().mockReturnValue(true);
    render(
      <ModalCorridasCertificadoFornecedor
        isOpen
        onClose={vi.fn()}
        dados={respostaCf()}
        carregando={false}
        erroCarregamento={null}
        quantidadeTotalItem={14}
        selecoesIniciais={[]}
        onAplicar={onAplicar}
        {...over}
      />,
    );
    return { onAplicar };
  };

  it('mostra colunas, corridas do CF exato e mensagem de origem documental', () => {
    renderModal();
    expect(screen.getByText(TITULO_MODAL_CORRIDAS_CF_CQ)).toBeInTheDocument();
    for (const col of ['Selecionar', 'Corrida', 'Lote', 'Quantidade registrada no CF', 'Origem técnica']) {
      expect(screen.getByText(col)).toBeInTheDocument();
    }
    expect(screen.queryByText(/disponível em estoque/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('Sugestão documental')).toHaveLength(2);
    expect(screen.getByText('3242')).toBeInTheDocument();
    expect(screen.getByText('AB337')).toBeInTheDocument();
    expect(screen.getAllByText('Dados técnicos herdados do item principal do CF').length).toBeGreaterThan(0);
    expect(screen.getByText(MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ)).toBeInTheDocument();
  });

  it('estado vazio amigável sem erro genérico e botão desabilitado', () => {
    const { onAplicar } = renderModal({
      dados: {
        linhas: [],
        avisos: ['Reaplique os dados do fornecedor neste item do CQ.'],
        mensagem_origem_fisica: MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
        limitacao_itens_independentes: '',
      },
    });
    expect(screen.getByText(MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ)).toBeInTheDocument();
    expect(screen.getByText('Reaplique os dados do fornecedor neste item do CQ.')).toBeInTheDocument();
    expect(screen.queryByText('Recurso não encontrado.')).not.toBeInTheDocument();
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    expect(aplicar).toBeDisabled();
    fireEvent.click(aplicar);
    expect(onAplicar).not.toHaveBeenCalled();
  });

  it('botão permanece desabilitado sem seleção válida', () => {
    const { onAplicar } = renderModal();
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    expect(aplicar).toBeDisabled();
    fireEvent.click(aplicar);
    expect(onAplicar).not.toHaveBeenCalled();
  });

  it('selecionar 3242 (8) + AB337 (6) libera aplicar com as seleções corretas', () => {
    const { onAplicar } = renderModal();
    fireEvent.click(screen.getByLabelText('Selecionar corrida 3242'));
    fireEvent.click(screen.getByLabelText('Selecionar corrida AB337'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('Quantidade da corrida AB337'), { target: { value: '6' } });
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    expect(aplicar).toBeEnabled();
    fireEvent.click(aplicar);
    expect(onAplicar).toHaveBeenCalledTimes(1);
    const selecoes = onAplicar.mock.calls[0][0] as SelecaoCorridaCfCq[];
    expect(selecoes.map((s) => [s.linha.corrida, s.quantidade, s.dadosTecnicos])).toEqual([
      ['3242', '8', 'herdados'],
      ['AB337', '6', 'herdados'],
    ]);
  });

  it('aplica uma única vez mesmo com cliques repetidos', () => {
    const onAplicarSync = vi.fn().mockReturnValue(true);
    render(
      <ModalCorridasCertificadoFornecedor
        isOpen
        onClose={vi.fn()}
        dados={respostaCf()}
        carregando={false}
        erroCarregamento={null}
        quantidadeTotalItem={14}
        selecoesIniciais={[]}
        onAplicar={onAplicarSync}
      />,
    );
    fireEvent.click(screen.getByLabelText('Selecionar corrida 3242'));
    fireEvent.click(screen.getByLabelText('Selecionar corrida AB337'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('Quantidade da corrida AB337'), { target: { value: '6' } });
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    fireEvent.click(aplicar);
    fireEvent.click(aplicar);
    expect(onAplicarSync).toHaveBeenCalledTimes(1);
  });

  it('recurso realmente inexistente exibe erro e desabilita aplicar', () => {
    const { onAplicar } = renderModal({
      dados: null,
      erroCarregamento: 'Certificado de Fornecedor não encontrado.',
    });
    expect(screen.getByRole('alert')).toHaveTextContent('Certificado de Fornecedor não encontrado.');
    expect(screen.queryByText(MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ)).not.toBeInTheDocument();
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    expect(aplicar).toBeDisabled();
    fireEvent.click(aplicar);
    expect(onAplicar).not.toHaveBeenCalled();
  });

  it('soma diferente do total desabilita aplicar e mostra o motivo uma única vez', () => {
    const { onAplicar } = renderModal();
    fireEvent.click(screen.getByLabelText('Selecionar corrida 3242'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '5' } });
    const aplicar = screen.getByRole('button', { name: 'Aplicar corridas selecionadas' });
    expect(aplicar).toBeDisabled();
    expect(screen.getAllByText(MSG_SOMA_DIFERENTE_TOTAL_CQ)).toHaveLength(1);
    fireEvent.click(aplicar);
    expect(onAplicar).not.toHaveBeenCalled();
  });

  it('permite marcar dados técnicos próprios por corrida', () => {
    const { onAplicar } = renderModal();
    fireEvent.click(screen.getByLabelText('Selecionar corrida 3242'));
    fireEvent.click(screen.getByLabelText('Selecionar corrida AB337'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('Quantidade da corrida AB337'), { target: { value: '6' } });
    const radiosProprios = screen.getAllByLabelText('Preencher dados técnicos próprios desta corrida');
    fireEvent.click(radiosProprios[1]);
    expect(screen.getByText(/dados técnicos desta linha serão preenchidos manualmente/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar corridas selecionadas' }));
    const selecoes = onAplicar.mock.calls[0][0] as SelecaoCorridaCfCq[];
    expect(selecoes[0].dadosTecnicos).toBe('herdados');
    expect(selecoes[1].dadosTecnicos).toBe('proprios');
  });

  it('reabrir recebe a divisão existente e cancelar não aplica alterações', () => {
    const onClose = vi.fn();
    const onAplicar = vi.fn().mockReturnValue(true);
    render(
      <ModalCorridasCertificadoFornecedor
        isOpen
        onClose={onClose}
        dados={respostaCf()}
        carregando={false}
        erroCarregamento={null}
        quantidadeTotalItem={14}
        selecoesIniciais={[
          selecao(linhaCf(), '8', 'herdados'),
          selecao(linhaAdicionalAb337(), '6', 'proprios'),
        ]}
        onAplicar={onAplicar}
      />,
    );
    expect(screen.getByLabelText('Quantidade da corrida 3242')).toHaveValue('8');
    expect(screen.getByLabelText('Quantidade da corrida AB337')).toHaveValue('6');
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onClose).toHaveBeenCalled();
    expect(onAplicar).not.toHaveBeenCalled();
  });

  it('erro de carregamento da API permanece visível', () => {
    renderModal({ dados: null, erroCarregamento: 'Falha ao consultar o Certificado de Fornecedor.' });
    expect(screen.getByRole('alert')).toHaveTextContent('Falha ao consultar o Certificado de Fornecedor.');
  });
});

describe('Certificados (página) — adicionar corridas do CF', () => {
  beforeEach(() => {
    window.confirm = vi.fn().mockReturnValue(true);
    paginated.items = [certificadoBase([itemCqBase()])];
    paginated.count = 1;
    corridasCfMock.mockReset();
  });

  const abrirEdicaoEClicarBotao = async () => {
    render(<Certificados />);
    fireEvent.click(screen.getByTitle('Editar certificado'));
    fireEvent.click(screen.getByRole('button', { name: TITULO_MODAL_CORRIDAS_CF_CQ }));
  };

  it('botão consulta o CF/item exatos e aplicar cria um item por corrida', async () => {
    corridasCfMock.mockResolvedValue(respostaCf());
    await abrirEdicaoEClicarBotao();
    expect(corridasCfMock).toHaveBeenCalledWith(5, 9);

    // A origem já presente (3242) reabre selecionada com a quantidade atual 14.
    expect(await screen.findByLabelText('Quantidade da corrida 3242')).toHaveValue('14');
    fireEvent.click(screen.getByLabelText('Selecionar corrida AB337'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('Quantidade da corrida AB337'), { target: { value: '6' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar corridas selecionadas' }));

    // Um item por corrida, com quantidade específica (8 e 6, total 14).
    await waitFor(() => {
      expect(screen.getByDisplayValue('AB337')).toBeInTheDocument();
    });
    expect(screen.getAllByDisplayValue('3242').length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue('8')).toBeInTheDocument();
    expect(screen.getByDisplayValue('6')).toBeInTheDocument();
    // Origem documental identificada, sem afirmar origem física.
    expect(screen.getAllByText(MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ).length).toBeGreaterThan(0);
  });

  it('erro da API permanece visível no modal', async () => {
    // Rejeição axios-like sem mensagem própria: deve exibir o fallback amigável.
    corridasCfMock.mockRejectedValue({ response: undefined });
    await abrirEdicaoEClicarBotao();
    expect(
      await screen.findByText('Não foi possível carregar as corridas do Certificado de Fornecedor.'),
    ).toBeInTheDocument();
  });

  it('404 real do certificado exibe detail da API e não mascara como lista vazia', async () => {
    corridasCfMock.mockRejectedValue({
      response: { status: 404, data: { detail: 'Certificado de Fornecedor não encontrado.' } },
    });
    await abrirEdicaoEClicarBotao();
    expect(await screen.findByText('Certificado de Fornecedor não encontrado.')).toBeInTheDocument();
    expect(screen.queryByText(MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar corridas selecionadas' })).toBeDisabled();
  });

  it('coleção vazia da API mostra estado vazio sem Recurso não encontrado', async () => {
    corridasCfMock.mockResolvedValue({
      linhas: [],
      avisos: ['O item do Certificado de Fornecedor vinculado a este CQ não foi encontrado ou está inativo.'],
      mensagem_origem_fisica: MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
      limitacao_itens_independentes: '',
    });
    await abrirEdicaoEClicarBotao();
    expect(await screen.findByText(MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ)).toBeInTheDocument();
    expect(screen.queryByText('Recurso não encontrado.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aplicar corridas selecionadas' })).toBeDisabled();
  });

  it('cancelar confirmação de substituição preserva o editor e mantém o modal aberto', async () => {
    corridasCfMock.mockResolvedValue(respostaCf());
    vi.mocked(window.confirm).mockReturnValue(false);
    await abrirEdicaoEClicarBotao();
    expect(await screen.findByLabelText('Quantidade da corrida 3242')).toHaveValue('14');
    fireEvent.click(screen.getByLabelText('Selecionar corrida AB337'));
    fireEvent.change(screen.getByLabelText('Quantidade da corrida 3242'), { target: { value: '8' } });
    fireEvent.change(screen.getByLabelText('Quantidade da corrida AB337'), { target: { value: '6' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar corridas selecionadas' }));

    expect(window.confirm).toHaveBeenCalled();
    expect(screen.getAllByText(TITULO_MODAL_CORRIDAS_CF_CQ).length).toBeGreaterThan(1);
    expect(screen.getByLabelText('Quantidade da corrida 3242')).toHaveValue('8');
    expect(screen.getByLabelText('Quantidade da corrida AB337')).toHaveValue('6');
    expect(screen.queryByDisplayValue('AB337')).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('14')).toBeInTheDocument();
  });
});
