import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NFeEnvioDanfeXmlModal } from '@/components/fiscal/NFeEnvioDanfeXmlModal';
import { nfeSaidasService } from '@/services/api/fiscal';

vi.mock('@/services/api/fiscal', () => ({
  nfeSaidasService: {
    envioEmailDados: vi.fn(),
    envioEmailEnviar: vi.fn(),
  },
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
};

describe('NFeEnvioDanfeXmlModal destinatário sugerido', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('pré-preenche Para com e-mail do cliente e permite editar', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({
      ...dadosBase,
      destinatario_sugerido: 'cliente@test.local',
      cliente_sem_email: false,
      destinatario_origem: 'email_nf',
      aviso_sem_email_cliente: '',
    });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);

    const campoPara = await screen.findByLabelText('Para');
    await waitFor(() => {
      expect(campoPara).toHaveValue('cliente@test.local');
    });

    fireEvent.change(campoPara, { target: { value: 'outro@test.local' } });
    expect(campoPara).toHaveValue('outro@test.local');
  });

  it('mantém Para vazio e exibe aviso quando cliente não tem e-mail', async () => {
    vi.mocked(nfeSaidasService.envioEmailDados).mockResolvedValue({
      ...dadosBase,
      destinatario_sugerido: '',
      cliente_sem_email: true,
      destinatario_origem: '',
      aviso_sem_email_cliente: 'Cliente sem e-mail cadastrado. Informe o destinatário manualmente.',
    });

    render(<NFeEnvioDanfeXmlModal open nfeId={17} onClose={() => undefined} />);

    const campoPara = await screen.findByLabelText('Para');
    await waitFor(() => {
      expect(campoPara).toHaveValue('');
    });
    expect(
      screen.getByText('Cliente sem e-mail cadastrado. Informe o destinatário manualmente.'),
    ).toBeInTheDocument();
  });
});
