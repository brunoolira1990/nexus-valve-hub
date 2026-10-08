import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NFeEnvioDanfeXmlModal } from '@/components/fiscal/NFeEnvioDanfeXmlModal';
import {
  adicionarDestinatarioManual,
  destinatariosSugeridosParaUi,
  emailsSelecionadosEnvio,
} from '@/lib/nfeEnvioDestinatarios';
import { nfeSaidasService } from '@/services/api/fiscal';

vi.mock('@/services/api/fiscal', () => ({
  nfeSaidasService: {
    envioEmailDados: vi.fn(),
    envioEmailEnviar: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const dadosBase = {
  ok: true,
  pode_enviar: true,
  motivo_bloqueio: '',
  ambiente: 'homologacao',
  ambiente_label: 'Homologação',
  homologacao: true,
  alerta_homologacao: 'NF-e emitida em ambiente de HOMOLOGAÇÃO — sem valor fiscal.',
  assunto_sugerido: 'HOMOLOGAÇÃO — NF-e 99/0 — Sem valor fiscal',
  mensagem_sugerida: 'Documento emitido em ambiente de homologação, sem valor fiscal.',
  anexos: { xml_autorizado: true, danfe_pdf: true },
  nfe: {
    id: 17,
    numero: '99',
    serie: '0',
    chave_acesso: '3526050399910200015055000000000991234567890',
    status: 'AUTORIZADA_HOMOLOGACAO',
    status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
    cliente_nome: 'Cliente Teste',
    protocolo_autorizacao: '135260000000099',
  },
  ultimo_envio: null,
  destinatario_sugerido: 'cliente@test.local',
  destinatarios_sugeridos: [
    {
      email: 'fiscal1@test.local',
      nome: 'Fiscal 1',
      origem: 'contato',
      contato_id: 1,
      selecionado: true,
    },
    {
      email: 'cliente@test.local',
      nome: 'E-mail NF (legado)',
      origem: 'email_nf',
      contato_id: null,
      selecionado: true,
    },
  ],
  cliente_sem_email: false,
  destinatario_origem: 'contato',
  aviso_sem_email_cliente: '',
};

describe('nfeEnvioDestinatarios helpers', () => {
  it('deduplica e lista selecionados', () => {
    const ui = destinatariosSugeridosParaUi([
      { email: 'A@test.local', nome: 'A', origem: 'contato', contato_id: 1, selecionado: true },
      { email: 'a@test.local', nome: 'dup', origem: 'email_nf', contato_id: null, selecionado: true },
    ]);
    expect(ui).toHaveLength(1);
    expect(emailsSelecionadosEnvio(ui)).toEqual(['A@test.local']);
  });

  it('adiciona e-mail manual sem duplicar', () => {
    const base = destinatariosSugeridosParaUi(dadosBase.destinatarios_sugeridos);
    const dup = adicionarDestinatarioManual(base, 'fiscal1@test.local');
    expect(dup.erro).toBeTruthy();
    const ok = adicionarDestinatarioManual(base, 'extra@test.local');
    expect(ok.erro).toBeNull();
    expect(ok.itens).toHaveLength(3);
  });
});

describe('NFeEnvioDanfeXmlModal multi-destinatários', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exibe checklist de destinatários sugeridos', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({ ...dadosBase });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);

    expect(await screen.findByText('fiscal1@test.local')).toBeTruthy();
    expect(screen.getByText('cliente@test.local')).toBeTruthy();
    expect(screen.getByText(/e-mail individual/i)).toBeTruthy();
  });

  it('exibe aviso quando não há destinatários sugeridos', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({
      ...dadosBase,
      destinatario_sugerido: '',
      destinatarios_sugeridos: [],
      cliente_sem_email: true,
      destinatario_origem: '',
      aviso_sem_email_cliente:
        'Cliente sem destinatários fiscais cadastrados. Selecione ou informe o destinatário manualmente.',
    });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);

    expect(
      await screen.findByText(/sem destinatários fiscais cadastrados/i),
    ).toBeTruthy();
    expect(screen.getByLabelText('Incluir e-mail adicional')).toBeTruthy();
  });

  it('envia lista destinatarios selecionados e mostra resultado consolidado', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({ ...dadosBase });
    vi.mocked(nfeSaidasService.envioEmailEnviar).mockResolvedValue({
      ok: true,
      status_geral: 'SUCESSO',
      mensagem: 'E-mails enviados com sucesso para 2 destinatários.',
      total: 2,
      sucessos: 2,
      falhas: 0,
      resultados: [
        { email: 'fiscal1@test.local', status: 'SUCESSO', mensagem: 'E-mail enviado com sucesso.', envio_id: 1 },
        { email: 'cliente@test.local', status: 'SUCESSO', mensagem: 'E-mail enviado com sucesso.', envio_id: 2 },
      ],
    });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);

    await screen.findByText('fiscal1@test.local');
    fireEvent.click(screen.getByLabelText(/Confirmo o envio/i));
    fireEvent.click(screen.getByRole('button', { name: /Enviar e-mail/i }));

    await waitFor(() => {
      expect(nfeSaidasService.envioEmailEnviar).toHaveBeenCalledWith(
        17,
        expect.objectContaining({
          destinatarios: ['fiscal1@test.local', 'cliente@test.local'],
          confirmar_envio: true,
        }),
      );
    });

    expect(await screen.findByText(/enviados com sucesso para 2/i)).toBeTruthy();
    expect(screen.getByText(/não são expostos entre si/i)).toBeTruthy();
  });

  it('apresenta sucessos e falhas na resposta parcial', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({ ...dadosBase });
    vi.mocked(nfeSaidasService.envioEmailEnviar).mockResolvedValue({
      ok: true,
      status_geral: 'PARCIAL',
      mensagem: 'Envio parcial: 1 sucesso(s), 1 falha(s) de 2 destinatário(s).',
      total: 2,
      sucessos: 1,
      falhas: 1,
      resultados: [
        { email: 'fiscal1@test.local', status: 'SUCESSO', mensagem: 'E-mail enviado com sucesso.' },
        {
          email: 'cliente@test.local',
          status: 'ERRO',
          mensagem: 'Falha ao enviar e-mail. Verifique a configuração SMTP do ambiente.',
        },
      ],
    });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);
    await screen.findByText('fiscal1@test.local');
    fireEvent.click(screen.getByLabelText(/Confirmo o envio/i));
    fireEvent.click(screen.getByRole('button', { name: /Enviar e-mail/i }));

    expect(await screen.findByTestId('envio-resultados')).toBeTruthy();
    expect(screen.getByText(/Envio parcial/i)).toBeTruthy();
    expect(screen.getByText(/cliente@test.local/)).toBeTruthy();
  });

  it('clique duplo gera apenas uma requisição', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({ ...dadosBase });
    let resolveEnvio: (v: unknown) => void = () => undefined;
    vi.mocked(nfeSaidasService.envioEmailEnviar).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveEnvio = resolve;
        }) as ReturnType<typeof nfeSaidasService.envioEmailEnviar>,
    );

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);
    await screen.findByText('fiscal1@test.local');
    fireEvent.click(screen.getByLabelText(/Confirmo o envio/i));
    const btn = screen.getByRole('button', { name: /Enviar e-mail/i });
    fireEvent.click(btn);
    fireEvent.click(btn);
    fireEvent.click(btn);

    await waitFor(() => {
      expect(nfeSaidasService.envioEmailEnviar).toHaveBeenCalledTimes(1);
    });

    resolveEnvio({
      ok: true,
      status_geral: 'SUCESSO',
      mensagem: 'E-mail enviado com sucesso.',
      resultados: [{ email: 'fiscal1@test.local', status: 'SUCESSO', mensagem: 'ok' }],
    });
  });
});
