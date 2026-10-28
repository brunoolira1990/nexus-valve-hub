import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import { polegadasService } from '@/services/api/produtos';
import type { Polegada } from '@/types';

vi.mock('@/services/api/produtos', () => ({
  polegadasService: {
    getById: vi.fn(),
    search: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
  },
}));

const NPS_MEIA: Polegada = {
  id: 130,
  codigo: '05',
  codigo_oficial: '1/2',
  descricao: '1/2"',
  valor_decimal: '0.5',
  valor_mm: '12.7',
  tipo_medida: 'NPS',
  ativo: true,
};

describe('PolegadaAutocomplete — saída sem escolha', () => {
  beforeEach(() => {
    vi.mocked(polegadasService.getById).mockResolvedValue(NPS_MEIA);
    vi.mocked(polegadasService.search).mockResolvedValue([]);
  });

  it('resolve a polegada salva pelo id mostrando só a polegada, sem o rótulo técnico', async () => {
    render(<PolegadaAutocomplete value={130} tipoMedida="NPS" onChange={vi.fn()} />);
    expect(await screen.findByDisplayValue('1/2"')).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/NPS|12,7 mm/)).toBeNull();
  });

  it('mantém o rótulo completo (código, descrição e mm) nas opções da busca', async () => {
    vi.mocked(polegadasService.search).mockResolvedValueOnce([
      { ...NPS_MEIA, id: 131, codigo: '06', codigo_oficial: '3/4', descricao: '3/4"', valor_mm: '19.05' },
    ]);
    render(<PolegadaAutocomplete value={null} tipoMedida="NPS" onChange={vi.fn()} />);
    const input = screen.getByRole('textbox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '3/4' } });

    expect(await screen.findByRole('button', { name: '3/4 — 3/4" — 19,05 mm' })).toBeInTheDocument();
  });

  it('ao perder o foco sem escolher, fecha o painel e restaura a polegada salva', async () => {
    render(<PolegadaAutocomplete value={130} tipoMedida="NPS" onChange={vi.fn()} />);
    const input = await screen.findByDisplayValue('1/2"');

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '3/4' } });
    fireEvent.blur(input);

    expect(input).toHaveValue('1/2"');
    expect(screen.queryByText('Nenhuma polegada encontrada.')).toBeNull();
  });

  it('campo vazio continua vazio depois de digitar e sair', () => {
    render(<PolegadaAutocomplete value={null} onChange={vi.fn()} />);
    const input = screen.getByRole('textbox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '1' } });
    fireEvent.blur(input);
    expect(input).toHaveValue('');
  });

  it('Escape fecha o painel sem alterar a seleção', async () => {
    render(<PolegadaAutocomplete value={130} tipoMedida="NPS" onChange={vi.fn()} />);
    const input = await screen.findByDisplayValue('1/2"');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: '3/4' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(input).toHaveValue('1/2"');
  });
});
