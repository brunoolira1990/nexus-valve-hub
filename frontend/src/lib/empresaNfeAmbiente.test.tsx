import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { EmpresaNfeAmbienteSelector } from '@/components/cadastros/EmpresaNfeAmbienteSelector';
import { ALERTA_PRODUCAO_NFE } from '@/lib/empresaNfeAmbiente';

describe('EmpresaNfeAmbienteSelector', () => {
  it('exibe opções Homologação e Produção', () => {
    render(<EmpresaNfeAmbienteSelector value="homologacao" onChange={vi.fn()} />);
    expect(screen.getByTestId('nfe-ambiente-homologacao')).toBeInTheDocument();
    expect(screen.getByTestId('nfe-ambiente-producao')).toBeInTheDocument();
    expect(screen.getByText('Ambiente atual da NF-e')).toBeInTheDocument();
  });

  it('não mostra alerta em homologação', () => {
    render(<EmpresaNfeAmbienteSelector value="homologacao" onChange={vi.fn()} />);
    expect(screen.queryByTestId('alerta-producao-nfe')).not.toBeInTheDocument();
  });

  it('mostra alerta forte em produção e flag desligada', () => {
    render(<EmpresaNfeAmbienteSelector value="producao" producaoHabilitada={false} onChange={vi.fn()} />);
    expect(screen.getByTestId('alerta-producao-nfe')).toHaveTextContent(ALERTA_PRODUCAO_NFE);
    expect(screen.getByText(/NFE_PRODUCAO_HABILITADA=false/)).toBeInTheDocument();
  });

  it('altera seleção via clique', () => {
    const onChange = vi.fn();
    render(<EmpresaNfeAmbienteSelector value="homologacao" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('nfe-ambiente-producao'));
    expect(onChange).toHaveBeenCalledWith('producao');
  });
});
