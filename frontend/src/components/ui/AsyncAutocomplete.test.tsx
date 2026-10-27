import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';

type Opcao = { id: number; nome: string };

const OPCOES: Opcao[] = [
  { id: 1, nome: 'NPT' },
  { id: 2, nome: 'BSP' },
];

function renderBusca(args: { value: number | null; selectedOption: Opcao | null } = { value: null, selectedOption: null }) {
  const onChange = vi.fn();
  const search = vi.fn(async (term: string) =>
    OPCOES.filter((o) => o.nome.toLowerCase().includes(term.toLowerCase())),
  );
  render(
    <AsyncAutocomplete<Opcao>
      value={args.value}
      selectedOption={args.selectedOption}
      search={search}
      getOptionValue={(o) => o.id}
      getOptionLabel={(o) => o.nome}
      onChange={onChange}
    />,
  );
  const input = screen.getByRole('textbox');
  return { input, onChange, search };
}

describe('AsyncAutocomplete — foco e saída sem escolha', () => {
  it('mantém o rótulo salvo enquanto o operador não digita', () => {
    const { input } = renderBusca({ value: 1, selectedOption: OPCOES[0] });
    expect(input).toHaveValue('NPT');
  });

  it('ao perder o foco sem escolher opção, fecha o painel e restaura o rótulo salvo', () => {
    const { input, onChange } = renderBusca({ value: 1, selectedOption: OPCOES[0] });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'BS' } });
    expect(screen.queryByText('Digite ao menos 2 caracteres para buscar.')).toBeNull();

    fireEvent.blur(input);

    expect(input).toHaveValue('NPT');
    expect(screen.queryByText('BSP')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Escape também fecha o painel e restaura o rótulo', () => {
    const { input } = renderBusca({ value: 1, selectedOption: OPCOES[0] });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'BSP' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(input).toHaveValue('NPT');
  });

  it('campo vazio volta ao placeholder ao perder o foco', () => {
    const { input } = renderBusca();
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'NP' } });
    fireEvent.blur(input);
    expect(input).toHaveValue('');
    expect(input).toHaveAttribute('placeholder', 'Digite para buscar...');
  });
});
