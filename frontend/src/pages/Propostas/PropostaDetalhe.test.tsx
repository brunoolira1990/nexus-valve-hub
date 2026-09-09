import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import PropostaDetalhe from './PropostaDetalhe';
import { propostasService } from '@/services/api/comercial';
import type { Proposta } from '@/types';
vi.mock('@/services/api/comercial', () => ({ propostasService: { getById: vi.fn() } }));
vi.mock('../Propostas', () => ({ default: ({ proposta }: { proposta?: Proposta }) => <div>Formulario {proposta?.id ?? 'novo'}</div> }));
function open(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Link to="/propostas/43">Outra proposta</Link><Link to="/propostas/nova">Nova</Link><Routes>
    <Route path="/propostas/nova" element={<PropostaDetalhe />} />
    <Route path="/propostas/:id" element={<PropostaDetalhe />} />
    <Route path="/propostas" element={<div>Listagem</div>} />
  </Routes></MemoryRouter>);
}
describe('pagina dedicada', () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(cleanup);
  it('abre nova sem consultar ID', () => {
    open('/propostas/nova');
    expect(screen.getByText('Formulario novo')).toBeInTheDocument();
    expect(propostasService.getById).not.toHaveBeenCalled();
  });
  it('carrega a proposta antes de abrir o formulario', async () => {
    vi.mocked(propostasService.getById).mockResolvedValue({ id: 42 } as Proposta);
    open('/propostas/42');
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(await screen.findByText('Formulario 42')).toBeInTheDocument();
    expect(propostasService.getById).toHaveBeenCalledWith(42);
  });
  it('bloqueia ID invalido', () => {
    open('/propostas/invalido');
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(propostasService.getById).not.toHaveBeenCalled();
    expect(screen.queryByText('Formulario novo')).not.toBeInTheDocument();
  });
  it('permite tentar novamente', async () => {
    vi.mocked(propostasService.getById).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ id: 42 } as Proposta);
    open('/propostas/42');
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Tentar novamente'));
    expect(await screen.findByText('Formulario 42')).toBeInTheDocument();
  });
  it('ignora resposta antiga depois de trocar a rota', async () => {
    let resolveOld!: (proposta: Proposta) => void;
    vi.mocked(propostasService.getById).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ id: 43 } as Proposta);
    open('/propostas/42');
    fireEvent.click(screen.getByText('Outra proposta'));
    expect(await screen.findByText('Formulario 43')).toBeInTheDocument();
    resolveOld({ id: 42 } as Proposta);
    await Promise.resolve();
    expect(screen.queryByText('Formulario 42')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Nova'));
    expect(screen.getByText('Formulario novo')).toBeInTheDocument();
  });
  it('permite voltar depois de erro', async () => {
    vi.mocked(propostasService.getById).mockRejectedValue(new Error('offline'));
    open('/propostas/42');
    fireEvent.click(await screen.findByText('Voltar para listagem'));
    expect(screen.getByText('Listagem')).toBeInTheDocument();
  });
});
