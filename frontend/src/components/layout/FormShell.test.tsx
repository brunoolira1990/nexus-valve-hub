import { fireEvent, render, screen, within } from '@testing-library/react';
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

  it('rodapé mobile replica a ação principal e dispara o mesmo onClick', () => {
    const salvar = vi.fn();
    renderShell(
      <FormShell
        titulo="Teste"
        acoesPrincipais={[{ ...SALVAR, onClick: salvar }]}
        rail={<div>rail</div>}
      >
        <div>form</div>
      </FormShell>,
    );

    const rodape = screen.getByTestId('form-shell-rodape-mobile');
    const acao = within(rodape).getByRole('button', { name: 'Salvar' });
    expect(acao.className).toContain('w-full');
    fireEvent.click(acao);
    // Cabeçalho e rodapé apontam para a mesma ação: um clique aqui, uma chamada.
    expect(salvar).toHaveBeenCalledTimes(1);
  });

  it('sem ação principal não há rodapé e o botão Painel sobe para não colidir', () => {
    renderShell(
      <FormShell titulo="Teste" rail={<div>rail</div>}>
        <div>form</div>
      </FormShell>,
    );

    expect(screen.queryByTestId('form-shell-rodape-mobile')).toBeNull();
    expect(screen.getByTestId('form-shell-rail-toggle').className).toContain('bottom-24');
  });

  it('somenteLeitura esconde também o rodapé mobile', () => {
    renderShell(
      <FormShell titulo="Teste" acoesPrincipais={[SALVAR]} rail={<div>rail</div>} somenteLeitura>
        <div>form</div>
      </FormShell>,
    );

    expect(screen.queryByTestId('form-shell-rodape-mobile')).toBeNull();
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

  it('pipeline.somenteLeitura congela o estágio sem esconder as ações do cabeçalho (Sprint 3.18)', () => {
    const onChange = vi.fn();
    const salvar = vi.fn();
    const atualizar = vi.fn();
    renderShell(
      <FormShell
        titulo="CF-20260831-0007"
        acoesPrincipais={[{ ...SALVAR, onClick: salvar }]}
        acoesSecundarias={[{ label: 'Atualizar', onClick: atualizar }]}
        pipeline={{
          steps: [
            { key: 'rascunho', label: 'Rascunho' },
            { key: 'em_cotacao', label: 'Em cotação' },
            { key: 'concluida', label: 'Concluída' },
          ],
          currentKey: 'rascunho',
          onChange,
          somenteLeitura: true,
        }}
      >
        <div>abas do documento</div>
      </FormShell>,
    );

    // O pipeline é exibição: nenhum estágio é clicável mesmo com onChange passado.
    fireEvent.click(screen.getByTestId('status-pipeline-step-em_cotacao'));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId('status-pipeline-step-concluida')).toBeDisabled();

    // ...e a tela continua escrevendo: as duas faixas de ação seguem na tela.
    fireEvent.click(within(screen.getByTestId('form-shell-header')).getByRole('button', { name: 'Salvar' }));
    fireEvent.click(within(screen.getByTestId('form-shell-header')).getByRole('button', { name: 'Atualizar' }));
    expect(salvar).toHaveBeenCalledTimes(1);
    expect(atualizar).toHaveBeenCalledTimes(1);
  });

  it('campo omitido preserva o comportamento atual: o pipeline herda o somenteLeitura do shell', () => {
    const onChange = vi.fn();
    const interativo = renderShell(
      <FormShell
        titulo="Teste"
        pipeline={{
          steps: [
            { key: 'rascunho', label: 'Rascunho' },
            { key: 'pronta', label: 'Pronta' },
          ],
          currentKey: 'rascunho',
          onChange,
        }}
      >
        <div>form</div>
      </FormShell>,
    );
    fireEvent.click(screen.getByTestId('status-pipeline-step-pronta'));
    expect(onChange).toHaveBeenCalledWith('pronta');
    expect(screen.getByTestId('status-pipeline-step-pronta')).toBeEnabled();
    interativo.unmount();

    onChange.mockClear();
    const somenteLeitura = renderShell(
      <FormShell
        titulo="Teste"
        somenteLeitura
        pipeline={{
          steps: [
            { key: 'rascunho', label: 'Rascunho' },
            { key: 'pronta', label: 'Pronta' },
          ],
          currentKey: 'rascunho',
          onChange,
        }}
      >
        <div>form</div>
      </FormShell>,
    );
    fireEvent.click(screen.getByTestId('status-pipeline-step-pronta'));
    // Com o campo omitido, o shell em leitura continua congelando o pipeline (0 chamadas).
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId('status-pipeline-step-pronta')).toBeDisabled();
    somenteLeitura.unmount();
  });
});
