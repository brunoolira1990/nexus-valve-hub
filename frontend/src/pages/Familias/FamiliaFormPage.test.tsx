import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  familiaVariacoesService,
  familiasProdutoService,
  ncmApiService,
  polegadasService,
  roscasConexaoService,
  schedulesEspessuraService,
} from '@/services/api/produtos';
import { materiaisService } from '@/services/api/materiais';
import type { FamiliaProduto } from '@/types';
import FamiliaFormPage from './FamiliaFormPage';

vi.mock('@/services/api/produtos', () => ({
  familiasProdutoService: {
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  ncmApiService: { search: vi.fn().mockResolvedValue([]) },
  roscasConexaoService: { getAll: vi.fn() },
  schedulesEspessuraService: { getAll: vi.fn() },
  polegadasService: { getAll: vi.fn() },
  familiaVariacoesService: {
    listRoscasPermitidas: vi.fn(),
    listSchedulesPermitidos: vi.fn(),
    listPolegadasPermitidas: vi.fn(),
    addRoscaPermitida: vi.fn(),
    addSchedulePermitido: vi.fn(),
    addPolegadaPermitida: vi.fn(),
    patchRoscaPermitida: vi.fn(),
    patchSchedulePermitido: vi.fn(),
    removeRoscaPermitida: vi.fn(),
    removeSchedulePermitido: vi.fn(),
    removePolegadaPermitida: vi.fn(),
  },
}));

vi.mock('@/services/api/materiais', () => ({
  materiaisService: { getAll: vi.fn() },
}));

/** Família no estado em que a tela a recebe: NCM preenchido e classificação técnica escrita. */
const FAMILIA: Partial<FamiliaProduto> = {
  id: 7,
  codigo_figura: '0007',
  descricao_base: 'VÁLVULA DE ESFERA INOX 316L 2 POL',
  ativo: true,
  tipo_regra_codigo: 'BASE_POLEGADA',
  tipo_dimensional: 'NPS',
  categoria_produto: 'PRODUTO_TECNICO',
  separador_base_medidas: '.',
  ncm_padrao: 55,
  ncm_padrao_info: { id: 55, codigo: '84818011', descricao: 'TORNEIRAS PARA CANAL' },
  unidade_padrao: 'UN',
  unidade_estoque_padrao: 'PC',
  tipo_fisico: 'PECA',
  tipo_controle_unidade: 'PECA',
  tipo_composicao_fisica: 'BARRA_M',
  usa_conversao_dimensional: false,
  controla_composicao_fisica: false,
  exige_certificado_qualidade: false,
  tipo_peca: 'Válvula',
  material_vedacao: 'PTFE',
  norma_base: 'ANSI B16.34',
  pressao_base: '150 lbs',
  conexao_base: 'Solda BW',
};

function renderEdicao() {
  return render(
    <MemoryRouter initialEntries={['/familias/7/editar']}>
      <Routes>
        <Route path="/familias/:id/editar" element={<FamiliaFormPage />} />
        <Route path="/familias" element={<div>listagem</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('FamiliaFormPage (redesenho Sprint 3.7)', () => {
  beforeEach(() => {
    // Os mocks são compartilhados entre os testes do arquivo: sem limpar, a contagem de
    // chamadas de um teste vaza para o próximo e o teste do NCM veria o update anterior.
    vi.clearAllMocks();
    vi.mocked(ncmApiService.search).mockResolvedValue([]);
    vi.mocked(materiaisService.getAll).mockResolvedValue([] as never);
    vi.mocked(roscasConexaoService.getAll).mockResolvedValue([] as never);
    vi.mocked(schedulesEspessuraService.getAll).mockResolvedValue([] as never);
    vi.mocked(polegadasService.getAll).mockResolvedValue([] as never);
    vi.mocked(familiaVariacoesService.listRoscasPermitidas).mockResolvedValue([]);
    vi.mocked(familiaVariacoesService.listSchedulesPermitidos).mockResolvedValue([]);
    vi.mocked(familiaVariacoesService.listPolegadasPermitidas).mockResolvedValue([]);
    vi.mocked(familiasProdutoService.update).mockResolvedValue(FAMILIA as FamiliaProduto);
    vi.mocked(familiasProdutoService.getById).mockResolvedValue(FAMILIA as FamiliaProduto);
  });

  it('esconde os pesos até uma das flags de conversão ligar', async () => {
    renderEdicao();
    await screen.findByDisplayValue('0007');

    expect(screen.queryByText('Peso por metro (kg/m)')).toBeNull();

    fireEvent.click(screen.getByRole('switch', { name: 'Converter medida em estoque' }));

    expect(screen.getByText('Peso por metro (kg/m)')).toBeInTheDocument();
    expect(screen.getByText('Densidade do material (g/cm³)')).toBeInTheDocument();
  });

  it('removeu o campo morto: unidade padrão não aparece e não vai no payload', async () => {
    renderEdicao();
    await screen.findByDisplayValue('0007');
    expect(screen.queryByText('Unidade padrão')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /^Salvar$/ }));

    const [, payload] = await waitFor(() => {
      expect(familiasProdutoService.update).toHaveBeenCalled();
      return vi.mocked(familiasProdutoService.update).mock.calls[0];
    });
    expect(payload).not.toHaveProperty('unidade_padrao');
  });

  it('grava a classificação técnica herdada (norma, pressão e conexão)', async () => {
    renderEdicao();
    await screen.findByDisplayValue('ANSI B16.34');

    fireEvent.click(screen.getByRole('button', { name: /^Salvar$/ }));

    const [, payload] = await waitFor(() => {
      expect(familiasProdutoService.update).toHaveBeenCalled();
      return vi.mocked(familiasProdutoService.update).mock.calls[0];
    });
    expect(payload).toMatchObject({
      ncm_padrao: 55,
      norma_base: 'ANSI B16.34',
      pressao_base: '150 lbs',
      conexao_base: 'Solda BW',
      tipo_peca: 'Válvula',
      material_vedacao: 'PTFE',
    });
  });

  it('bloqueia o salvar quando a família não tem NCM', async () => {
    vi.mocked(familiasProdutoService.getById).mockResolvedValue({
      ...FAMILIA,
      ncm_padrao: null,
      ncm_padrao_info: null,
    } as FamiliaProduto);

    renderEdicao();
    await screen.findByDisplayValue('0007');

    fireEvent.click(screen.getByRole('button', { name: /^Salvar$/ }));

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('NCM é obrigatório para esta família.');
    expect(familiasProdutoService.update).not.toHaveBeenCalled();
  });

  it('o domínio perdeu o botão próprio e é salvo pelo Salvar da tela', async () => {
    renderEdicao();
    await screen.findByDisplayValue('0007');

    expect(screen.queryByRole('button', { name: /Salvar domínio/ })).toBeNull();
    expect(screen.getByText('Medidas, roscas e espessuras desta família')).toBeInTheDocument();
    expect(screen.getByText(/salvas junto com a família/)).toBeInTheDocument();
  });

  it('mostra o aviso quando a regra usa medidas e nenhuma está marcada', async () => {
    renderEdicao();
    await screen.findByDisplayValue('0007');

    expect(
      await screen.findByText(/A regra do código desta família usa rosca, espessura/),
    ).toBeInTheDocument();
  });
});
