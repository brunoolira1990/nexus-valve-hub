import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FormShell, type FormShellAction } from './FormShell';

const SALVAR: FormShellAction = { label: 'Salvar', onClick: vi.fn(), variant: 'primary' };
const DESCARTAR: FormShellAction = { label: 'Descartar', onClick: vi.fn() };

function renderShell(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('FormShell (Sprint 3.13)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('monta header com título, formulário como children e rail à direita', () => {
    renderShell(
      <FormShell
        titulo="0007 — VÁLVULA DE ESFERA"
        breadcrumbs={[{ label: 'Cadastros' }, { label: 'Famílias', path: '/familias' }]}
        acoesPrincipais={[SALVAR]}
        acoesSecundarias={[DESCARTAR]}
        onVoltar={vi.fn()}
        rail={<div>Chatter em breve (Sprint 3.14)</div>}
      >
        <div>corpo do formulário</div>
      </FormShell>,
    );

    expect(screen.getByRole('heading', { name: '0007 — VÁLVULA DE ESFERA' })).toBeInTheDocument();
    expect(screen.getByText('corpo do formulário')).toBeInTheDocument();
    expect(screen.getByTestId('form-shell-header')).toBeInTheDocument();
    // O rail renderiza no aside lg+ e dentro do drawer mobile (fechado por padrão).
    expect(screen.getAllByText('Chatter em breve (Sprint 3.14)').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('form-shell-rail')).toBeInTheDocument();
  });

  it('no mobile o rail some do fluxo e vira drawer pelo botão flutuante', () => {
    renderShell(
      <FormShell titulo="Teste" rail={<div>Chatter em breve (Sprint 3.14)</div>}>
        <div>form</div>
      </FormShell>,
    );

    // Regra do shell: o aside do rail é hidden abaixo de lg; quem aparece no mobile é o toggle.
    expect(screen.getByTestId('form-shell-rail').className).toContain('hidden');
    expect(screen.getByTestId('form-shell-rail').className).toContain('lg:block');
    expect(screen.queryByTestId('form-shell-rail-drawer')).toBeNull();

    fireEvent.click(screen.getByTestId('form-shell-rail-toggle'));

    const drawer = screen.getByTestId('form-shell-rail-drawer');
    expect(drawer).toBeInTheDocument();
    expect(drawer).toHaveTextContent('Chatter em breve (Sprint 3.14)');

    fireEvent.click(screen.getByRole('button', { name: 'Fechar painel' }));
    expect(screen.queryByTestId('form-shell-rail-drawer')).toBeNull();
  });

  it('somenteLeitura esconde as ações de escrita mas mantém o Voltar', () => {
    renderShell(
      <FormShell
        titulo="Teste"
        acoesPrincipais={[SALVAR]}
        acoesSecundarias={[DESCARTAR]}
        onVoltar={vi.fn()}
        somenteLeitura
      >
        <div>form</div>
      </FormShell>,
    );

    expect(screen.queryByRole('button', { name: 'Salvar' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Descartar' })).toBeNull();
    expect(screen.getByTestId('form-shell-voltar')).toBeInTheDocument();
  });

  it('sem onVoltar não renderiza o botão Voltar e sem rail não renderiza o aside', () => {
    renderShell(<FormShell titulo="Teste">{null}</FormShell>);

    expect(screen.queryByTestId('form-shell-voltar')).toBeNull();
    expect(screen.queryByTestId('form-shell-rail')).toBeNull();
    expect(screen.queryByTestId('form-shell-rail-toggle')).toBeNull();
    expect(screen.queryByTestId('form-shell-pipeline')).toBeNull();
  });

  it('renderiza a banda de pipeline e chama onChange ao clicar num estágio futuro', () => {
    const onVoltar = vi.fn();
    const onChange = vi.fn();
    renderShell(
      <FormShell
        titulo="Teste"
        onVoltar={onVoltar}
        pipeline={{
          steps: [
            { key: 'rascunho', label: 'Rascunho' },
            { key: 'pronta', label: 'Pronta' },
            { key: 'emitida', label: 'Emitida' },
          ],
          currentKey: 'rascunho',
          onChange,
        }}
      >
        <div>form</div>
      </FormShell>,
    );

    expect(screen.getByTestId('form-shell-pipeline')).toBeInTheDocument();
    expect(screen.getByTestId('status-pipeline')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('status-pipeline-step-pronta'));
    expect(onChange).toHaveBeenCalledWith('pronta');

    fireEvent.click(screen.getByTestId('form-shell-voltar'));
    expect(onVoltar).toHaveBeenCalled();
  });
});
