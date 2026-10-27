import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DecimalPtBrInput } from '@/components/produtos/DecimalPtBrInput';

function Campo({ inicial, onValue }: { inicial: number | null; onValue?: (v: number | null) => void }) {
  const [valor, setValor] = useState<number | null>(inicial);
  return (
    <DecimalPtBrInput
      value={valor}
      onChange={(v) => {
        setValor(v);
        onValue?.(v);
      }}
    />
  );
}

describe('DecimalPtBrInput — vírgula pt-BR', () => {
  it('exibe o número salvo com vírgula', () => {
    render(<Campo inicial={12.5} />);
    expect(screen.getByRole('textbox')).toHaveValue('12,5');
  });

  it('grava 12.5 no estado quando o operador digita 12,50', () => {
    const onValue = vi.fn();
    render(<Campo inicial={null} onValue={onValue} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '12,50' } });
    expect(input).toHaveValue('12,50');
    expect(onValue).toHaveBeenLastCalledWith(12.5);
  });

  it('não zera o campo enquanto a vírgula é o último caractere digitado', () => {
    const onValue = vi.fn();
    render(<Campo inicial={7} onValue={onValue} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '12,' } });
    expect(input).toHaveValue('12,');
    expect(onValue).toHaveBeenLastCalledWith(12);
    fireEvent.change(input, { target: { value: '12,75' } });
    expect(input).toHaveValue('12,75');
    expect(onValue).toHaveBeenLastCalledWith(12.75);
  });

  it('esvaziar devolve null', () => {
    const onValue = vi.fn();
    render(<Campo inicial={3} onValue={onValue} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '' } });
    expect(onValue).toHaveBeenLastCalledWith(null);
    expect(input).toHaveValue('');
  });

  it('texto que não é decimal não chega no estado e o valor volta no blur', () => {
    const onValue = vi.fn();
    render(<Campo inicial={4} onValue={onValue} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'abc' } });
    expect(onValue).not.toHaveBeenCalled();
    fireEvent.blur(input);
    expect(input).toHaveValue('4');
  });
});
