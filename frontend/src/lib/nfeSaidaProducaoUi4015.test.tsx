/** Testes UI — emissão NF-e Saída produção SEFAZ (Fase 3C). */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { NFeSaidaEmissaoProducaoPanel } from '@/components/fiscal/NFeSaidaEmissaoProducaoPanel';
import { nfeSaidasService } from '@/services/api/fiscal';
import {
  avisoProducaoDesabilitada,
  botaoEmitirProducaoHabilitado,
  confirmacaoProducaoValida,
  feedbackFinanceiroPosAutorizacaoProducao,
  montarPayloadEmitirProducao,
  podeExibirBotaoEmitirProducao,
  TEXTO_CONFIRMACAO_PRODUCAO,
} from '@/lib/nfeSaidaEmissaoProducao';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), message: vi.fn() },
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeSaidasService: {
    emitirProducao: vi.fn(),
    validarEmissaoProducao: vi.fn(),
    downloadXmlAutorizado: vi.fn(),
    downloadXmlAutorizadoBlob: vi.fn(),
  },
}));

const permDesligada = {
  producao_habilitada: false,
  usuario_pode_emitir_producao: false,
  pode_emitir_producao: false,
  pode_tentar_emitir_producao: false,
};

const permHomologOnly = {
  producao_habilitada: true,
  usuario_pode_emitir_producao: false,
  pode_emitir_producao: false,
  pode_tentar_emitir_producao: false,
  pode_emitir_homologacao: true,
  pode_tentar_emitir_homologacao: true,
};

const permHabilitadaAdmin = {
  producao_habilitada: true,
  usuario_pode_emitir_producao: true,
  pode_emitir_producao: true,
  pode_tentar_emitir_producao: true,
};

const emissaoPronta = {
  habilitada: true,
  pronta: true,
  ambiente_emissao_nfe: 'producao',
  emitente: { nome: 'Emitente Teste' },
  destinatario: { nome: 'Cliente Teste' },
  valor_total: 1500,
  ambiente_label: 'Produção SEFAZ',
  status_producao_label: 'Aguardando emissão produção',
  numeracao_producao: { serie: '1', proximo_numero: 42 },
  pendencias: [],
  alertas: [],
};

describe('nfeSaidaProducaoUi4015 helpers', () => {
  it('produção desabilitada — aviso claro', () => {
    expect(avisoProducaoDesabilitada(permDesligada)).toContain('desabilitada');
  });

  it('botão não aparece sem produção habilitada', () => {
    expect(podeExibirBotaoEmitirProducao(emissaoPronta, permDesligada)).toBe(false);
  });

  it('homologação habilitada não libera produção', () => {
    expect(podeExibirBotaoEmitirProducao(emissaoPronta, permHomologOnly)).toBe(false);
    expect(botaoEmitirProducaoHabilitado(emissaoPronta, permHomologOnly)).toBe(false);
  });

  it('botão aparece com flag e permissão produção', () => {
    expect(podeExibirBotaoEmitirProducao(emissaoPronta, permHabilitadaAdmin)).toBe(true);
    expect(botaoEmitirProducaoHabilitado(emissaoPronta, permHabilitadaAdmin, { pronta: true })).toBe(true);
  });

  it('pendências bloqueantes desabilitam emissão', () => {
    expect(
      botaoEmitirProducaoHabilitado(emissaoPronta, permHabilitadaAdmin, { pronta: false }),
    ).toBe(false);
  });

  it('confirmação exige checkbox e texto PRODUCAO SEFAZ', () => {
    expect(confirmacaoProducaoValida(false, TEXTO_CONFIRMACAO_PRODUCAO)).toBe(false);
    expect(confirmacaoProducaoValida(true, 'errado')).toBe(false);
    expect(confirmacaoProducaoValida(true, TEXTO_CONFIRMACAO_PRODUCAO)).toBe(true);
  });

  it('payload correto', () => {
    expect(montarPayloadEmitirProducao()).toEqual({
      confirmar_emissao_producao: true,
      confirmar_ambiente: 'PRODUCAO_SEFAZ',
    });
  });
});

function renderPanel(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('feedbackFinanceiroPosAutorizacaoProducao', () => {
  it('sucesso gerado', () => {
    expect(
      feedbackFinanceiroPosAutorizacaoProducao({ tentado: true, gerado: true, mensagem: 'Contas a receber gerado.' }),
    ).toEqual({ tipo: 'gerado', texto: 'Contas a receber gerado.' });
  });

  it('já existente', () => {
    expect(feedbackFinanceiroPosAutorizacaoProducao({ tentado: true, ja_existente: true }).tipo).toBe('ja_existente');
  });

  it('erro com regularização', () => {
    const r = feedbackFinanceiroPosAutorizacaoProducao({ tentado: true, erro: true });
    expect(r.tipo).toBe('erro');
    expect(r.texto).toMatch(/Gerar contas a receber/);
  });

  it('venda à vista — neutro sem erro de CR', () => {
    const r = feedbackFinanceiroPosAutorizacaoProducao({
      tentado: false,
      venda_integralmente_a_vista: true,
      mensagem: 'Venda à vista — não gera Contas a Receber.',
    });
    expect(r.tipo).toBe('a_vista');
    expect(r.texto).toMatch(/à vista/i);
    expect(r.texto).not.toMatch(/não foi possível gerar/i);
  });
});

describe('NFeSaidaEmissaoProducaoPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(nfeSaidasService.validarEmissaoProducao).mockResolvedValue({
      pronta: true,
      pendencias: [],
      alertas: [],
      producao_habilitada: true,
    });
  });

  it('exibe aviso quando produção desabilitada', () => {
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={1}
        emissaoProducao={{ habilitada: false }}
        permissoes={permDesligada}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    expect(screen.getByTestId('nfe-producao-desabilitada')).toHaveTextContent('desabilitada');
    expect(screen.queryByTestId('nfe-producao-btn-emitir')).toBeNull();
  });

  it('não exibe botão ativo sem permissão de usuário', () => {
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={1}
        emissaoProducao={{ ...emissaoPronta, habilitada: true }}
        permissoes={permHomologOnly}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    expect(screen.getByTestId('nfe-producao-sem-permissao')).toBeTruthy();
    expect(screen.queryByTestId('nfe-producao-btn-emitir')).toBeNull();
  });

  it('badge produção distinto e botão vermelho quando permitido', async () => {
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={7}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    expect(screen.getByText(/PRODUÇÃO SEFAZ — documento fiscal real/)).toBeTruthy();
    expect(screen.getByTestId('nfe-producao-panel')).toBeTruthy();
    const btn = screen.getByTestId('nfe-producao-btn-emitir');
    expect(btn).toHaveTextContent('Emitir em produção SEFAZ');
    await waitFor(() => {
      expect(nfeSaidasService.validarEmissaoProducao).toHaveBeenCalledWith(7);
    });
  });

  it('modal exige checkbox e texto antes de confirmar', async () => {
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={7}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    const confirmar = await screen.findByTestId('nfe-producao-confirmar');
    expect(confirmar).toBeDisabled();
    fireEvent.click(screen.getByTestId('nfe-producao-checkbox'));
    fireEvent.change(screen.getByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    expect(confirmar).not.toBeDisabled();
    expect(screen.getByText(/validade fiscal se autorizado/)).toBeTruthy();
  });

  it('pendências bloqueantes desabilitam botão emitir', async () => {
    vi.mocked(nfeSaidasService.validarEmissaoProducao).mockResolvedValue({
      pronta: false,
      pendencias: [{ mensagem: 'Certificado inválido' }],
      alertas: [],
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={8}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText('Certificado inválido')).toBeTruthy();
    });
    expect(screen.getByTestId('nfe-producao-btn-emitir')).toBeDisabled();
  });

  it('sucesso fiscal + financeiro', async () => {
    const onDone = vi.fn();
    vi.mocked(nfeSaidasService.emitirProducao).mockResolvedValue({
      ok: true,
      autorizado: true,
      cstat: '100',
      xmotivo: 'Autorizado',
      protocolo: '999',
      nfe: { cstat: '100', xmotivo: 'Autorizado', protocolo: '999' },
      financeiro: {
        tentado: true,
        gerado: true,
        mensagem: 'Contas a receber gerado.',
        titulo_id: 55,
      },
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={9}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={onDone}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    fireEvent.click(await screen.findByTestId('nfe-producao-checkbox'));
    fireEvent.change(await screen.findByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    fireEvent.click(screen.getByTestId('nfe-producao-confirmar'));
    await waitFor(() => {
      expect(nfeSaidasService.emitirProducao).toHaveBeenCalledWith(9, montarPayloadEmitirProducao());
    });
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/Contas a receber gerado/i));
  });

  it('CR já existente mostra feedback Ver contas a receber', async () => {
    vi.mocked(nfeSaidasService.emitirProducao).mockResolvedValue({
      ok: true,
      autorizado: true,
      cstat: '100',
      xmotivo: 'Autorizado',
      protocolo: '999',
      nfe: { cstat: '100', xmotivo: 'Autorizado', protocolo: '999' },
      financeiro: {
        tentado: true,
        ja_existente: true,
        mensagem: 'Contas a receber já gerado.',
        titulo_id: 77,
        financeiro_gerado: true,
      },
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={12}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    fireEvent.click(await screen.findByTestId('nfe-producao-checkbox'));
    fireEvent.change(await screen.findByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    fireEvent.click(screen.getByTestId('nfe-producao-confirmar'));
    await waitFor(() => expect(toast.message).toHaveBeenCalled());
    expect(feedbackFinanceiroPosAutorizacaoProducao({ tentado: true, ja_existente: true }).tipo).toBe(
      'ja_existente',
    );
  });

  it('falha automática mostra aviso e mantém regularização', async () => {
    const onAbrir = vi.fn();
    vi.mocked(nfeSaidasService.emitirProducao).mockResolvedValue({
      ok: true,
      autorizado: true,
      cstat: '100',
      xmotivo: 'Autorizado',
      protocolo: '999',
      nfe: { cstat: '100', xmotivo: 'Autorizado', protocolo: '999' },
      financeiro: {
        tentado: true,
        erro: true,
        mensagem:
          'NF-e autorizada, mas não foi possível gerar o Contas a Receber. Use a ação Gerar contas a receber para regularizar.',
      },
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={13}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
        onAbrirGerarContasReceber={onAbrir}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    fireEvent.click(await screen.findByTestId('nfe-producao-checkbox'));
    fireEvent.change(await screen.findByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    fireEvent.click(screen.getByTestId('nfe-producao-confirmar'));
    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(expect.stringMatching(/Gerar contas a receber/i));
    });
  });

  it('exibe rejeição com xMotivo sem marcar autorizada', async () => {
    vi.mocked(nfeSaidasService.emitirProducao).mockResolvedValue({
      ok: false,
      autorizado: false,
      cstat: '539',
      xmotivo: 'Rejeição teste',
      nfe: { cstat: '539', xmotivo: 'Rejeição teste' },
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={10}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    fireEvent.click(await screen.findByTestId('nfe-producao-checkbox'));
    fireEvent.change(await screen.findByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    fireEvent.click(screen.getByTestId('nfe-producao-confirmar'));
    await waitFor(() => {
      expect(screen.getByTestId('nfe-producao-resultado')).toHaveTextContent('539');
    });
    expect(screen.queryByTestId('nfe-producao-autorizada')).toBeNull();
  });

  it('erro técnico exibe mensagem amigável', async () => {
    vi.mocked(nfeSaidasService.emitirProducao).mockRejectedValue({
      response: { data: { mensagem: 'Erro técnico na transmissão.' } },
    });
    renderPanel(
      <NFeSaidaEmissaoProducaoPanel
        nfeId={11}
        emissaoProducao={emissaoPronta}
        permissoes={permHabilitadaAdmin}
        onEmissaoConcluida={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('nfe-producao-btn-emitir'));
    fireEvent.click(await screen.findByTestId('nfe-producao-checkbox'));
    fireEvent.change(await screen.findByTestId('nfe-producao-texto-confirmacao'), {
      target: { value: TEXTO_CONFIRMACAO_PRODUCAO },
    });
    fireEvent.click(screen.getByTestId('nfe-producao-confirmar'));
    await waitFor(() => {
      expect(screen.getByTestId('nfe-producao-resultado')).toHaveTextContent(/Erro técnico|transmissão/i);
    });
  });
});
