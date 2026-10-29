import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { StatusPipeline, type StatusStep } from '@/components/layout/StatusPipeline';

const tresSteps: StatusStep[] = [
  { key: 'cotacao', label: 'Cotação' },
  { key: 'enviada', label: 'Cotação Enviada' },
  { key: 'pedido', label: 'Pedido de Venda' },
];

describe('StatusPipeline', () => {
  it('renderiza 3 steps com o segundo ativo (badge ATUAL)', () => {
    render(<StatusPipeline steps={tresSteps} currentKey="enviada" />);

    expect(screen.getByTestId('status-pipeline-step-cotacao')).toBeInTheDocument();
    expect(screen.getByTestId('status-pipeline-step-pedido')).toBeInTheDocument();

    const atual = screen.getByTestId('status-pipeline-step-enviada');
    expect(atual).toHaveAttribute('aria-current', 'step');
    expect(atual.className).toContain('bg-nexus-orange');
    expect(screen.getByTestId('status-pipeline-atual')).toHaveTextContent('ATUAL');
    expect(screen.getByTestId('status-pipeline-step-cotacao').className).toContain('bg-nexus-blue');
    expect(screen.getByTestId('status-pipeline-step-pedido').className).toContain('bg-slate-100');
  });

  it('clique em step anterior dispara onChange com a key do step', () => {
    const onChange = vi.fn();
    render(<StatusPipeline steps={tresSteps} currentKey="enviada" onChange={onChange} />);

    fireEvent.click(screen.getByTestId('status-pipeline-step-cotacao'));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('cotacao');
  });

  it('somenteLeitura=true desabilita todos os cliques', () => {
    const onChange = vi.fn();
    render(
      <StatusPipeline steps={tresSteps} currentKey="enviada" onChange={onChange} somenteLeitura />,
    );

    for (const step of tresSteps) {
      const el = screen.getByTestId(`status-pipeline-step-${step.key}`);
      expect(el).toBeDisabled();
      fireEvent.click(el);
    }
    expect(onChange).not.toHaveBeenCalled();
  });

  it('step cancelado (tone danger) aparece riscado em vermelho', () => {
    const cancelados: StatusStep[] = [
      tresSteps[0],
      { ...tresSteps[1], tone: 'danger', tooltip: 'Proposta cancelada' },
      tresSteps[2],
    ];
    render(<StatusPipeline steps={cancelados} currentKey="enviada" />);

    const step = screen.getByTestId('status-pipeline-step-enviada');
    expect(step.className).toContain('line-through');
    expect(step.className).toContain('bg-red-50');
    expect(step.className).not.toContain('bg-nexus-orange');
    expect(screen.queryByTestId('status-pipeline-atual')).not.toBeInTheDocument();
  });

  it('variante pill renderiza sem conectores e com chips arredondados', () => {
    const { rerender } = render(<StatusPipeline steps={tresSteps} currentKey="enviada" variant="pill" />);
    expect(screen.queryAllByTestId('status-pipeline-connector')).toHaveLength(0);
    expect(screen.getByTestId('status-pipeline-step-cotacao').className).toContain('rounded-full');

    rerender(<StatusPipeline steps={tresSteps} currentKey="enviada" variant="chevron" />);
    expect(screen.queryAllByTestId('status-pipeline-connector')).toHaveLength(2);
    expect(screen.getByTestId('status-pipeline-step-cotacao').className).toContain('rounded-sm');
  });
});
