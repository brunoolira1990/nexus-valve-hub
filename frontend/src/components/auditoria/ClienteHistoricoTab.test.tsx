import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClienteForm, type ClienteFormInput } from '@/pages/Clientes/ClienteForm';
import { auditoriaService } from '@/services/api/auditoria';

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    capacidade: vi.fn(),
    historicoObjeto: vi.fn(),
  },
}));

vi.mock('@/services/api/consulta', () => ({
  consultaCnpj: vi.fn(),
  consultaCep: vi.fn(),
}));

const defaults: ClienteFormInput = {
  razao_social: 'Cliente Teste',
  nome_fantasia: '',
  cnpj: '11.222.333/0001-81',
  ddd: '',
  ie: '',
  ie_isento: false,
  inscricao_municipal: '',
  suframa: '',
  cep: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: '',
  cidade: '',
  uf: '',
  telefone: '',
  telefone_alternativo: '',
  celular: '',
  email: '',
  email_nf: '',
  contato_responsavel: '',
  banco: '',
  agencia: '',
  conta: '',
  tipo_conta: '',
  cnae: '',
  regime_tributario: '',
  integracao_texto: '',
  limite_credito: 0,
  condicao_pagamento_texto: '',
  transportadora_padrao_id: '',
  vendedor_padrao: '',
  bloqueado: false,
  ativo: true,
  observacoes: '',
  informacoes_complementares_nfe: '',
};

describe('ClienteForm — aba Histórico', () => {
  beforeEach(() => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('oculta aba Histórico sem permissão', () => {
    render(
      <ClienteForm
        defaultValues={defaults}
        transportadoras={[]}
        onSubmit={async () => undefined}
        onCancel={() => undefined}
        clienteId={42}
        podeVerHistorico={false}
      />,
    );
    expect(screen.getByRole('button', { name: 'Dados Gerais' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Histórico' })).not.toBeInTheDocument();
    expect(auditoriaService.historicoObjeto).not.toHaveBeenCalled();
  });

  it('exibe aba Histórico com permissão e só carrega ao abrir', async () => {
    render(
      <ClienteForm
        defaultValues={defaults}
        transportadoras={[]}
        onSubmit={async () => undefined}
        onCancel={() => undefined}
        clienteId={42}
        podeVerHistorico
      />,
    );
    const tab = screen.getByRole('button', { name: 'Histórico' });
    expect(auditoriaService.historicoObjeto).not.toHaveBeenCalled();
    fireEvent.click(tab);
    await waitFor(() => expect(auditoriaService.historicoObjeto).toHaveBeenCalledTimes(1));
    expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith(
      'cadastros',
      'cliente',
      42,
      expect.any(Object),
    );
  });
});
