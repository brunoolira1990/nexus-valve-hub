import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NFeChecklistHomologacaoModal } from '@/components/fiscal/NFeChecklistHomologacaoModal';
import { NFeSaidaDetalheDrawer } from '@/components/fiscal/NFeSaidaDetalheDrawer';
import { nfeSaidasService } from '@/services/api/fiscal';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('@/components/comercial/AtendimentoOperacionalResumo', () => ({
  AtendimentoOperacionalResumo: () => <div>Atendimento mock</div>,
}));

vi.mock('@/components/fiscal/NFeReformaTributariaResumo', () => ({
  NFeReformaTributariaResumo: () => <div>Reforma mock</div>,
}));

vi.mock('@/components/ui/drawer', () => ({
  Drawer: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="drawer">{children}</div> : null,
  DrawerContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DrawerHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DrawerTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DrawerFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DrawerClose: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/services/api/fiscal', () => ({
  nfeSaidasService: {
    getById: vi.fn(),
    previewDanfeBlob: vi.fn(),
    previewXmlPreliminar: vi.fn(),
    checklistHomologacao: vi.fn(),
    checklistHomologacaoGeral: vi.fn(),
  },
}));

const respostaAprovada = {
  apto: true,
  status: 'aprovado' as const,
  bloqueios: [],
  alertas: [],
  mensagem: 'Checklist aprovado. O sistema está pronto para um novo teste de NF-e em homologação.',
  itens: [
    {
      codigo: 'duplicatas_nfe',
      label: 'Duplicatas da NF-e',
      status: 'ok' as const,
      mensagem: '1 duplicata(s) preparada(s): 001',
      secao: 'duplicatas',
    },
    {
      codigo: 'reforma_tributaria',
      label: 'Reforma Tributária',
      status: 'alerta' as const,
      mensagem: 'Estrutura em pesquisa/preparação. XML e DANFE seguem layout atual.',
      secao: 'reforma_tributaria',
    },
    {
      codigo: 'sem_financeiro',
      label: 'Sem financeiro automático',
      status: 'ok' as const,
      mensagem: 'Checklist não gera Contas a Receber/Pagar nem títulos financeiros.',
      secao: 'financeiro',
    },
  ],
  aviso_fixo: 'Esta validação não transmite NF-e...',
};

const respostaAprovadaComAlertas = {
  apto: true,
  status: 'aprovado_com_alertas' as const,
  bloqueios: [],
  alertas: ['Homologação sem valor fiscal real.', 'Reforma Tributária em preparação.'],
  mensagem: 'Checklist aprovado com alertas. Revise os pontos antes de prosseguir.',
  itens: [
    {
      codigo: 'duplicatas_nfe',
      label: 'Duplicatas da NF-e',
      status: 'ok' as const,
      mensagem: '1 duplicata(s) preparada(s): 001',
      secao: 'duplicatas',
    },
    {
      codigo: 'reforma_tributaria',
      label: 'Reforma Tributária',
      status: 'alerta' as const,
      mensagem: 'Estrutura em pesquisa/preparação. XML e DANFE seguem layout atual.',
      secao: 'reforma_tributaria',
    },
    {
      codigo: 'sem_financeiro',
      label: 'Sem financeiro automático',
      status: 'ok' as const,
      mensagem: 'Checklist não gera Contas a Receber/Pagar nem títulos financeiros.',
      secao: 'financeiro',
    },
  ],
  aviso_fixo: 'Esta validação não transmite NF-e...',
};

const respostaDanfeOk = {
  apto: true,
  status: 'aprovado_com_alertas' as const,
  bloqueios: [],
  alertas: ['Reforma Tributária em preparação.'],
  mensagem: 'Checklist aprovado com alertas. Revise os pontos antes de prosseguir.',
  itens: [
    {
      codigo: 'danfe_render',
      label: 'DANFE',
      status: 'ok' as const,
      mensagem: 'DANFE renderizado com sucesso (xml_autorizado_procNFe).',
      secao: 'danfe',
    },
    {
      codigo: 'danfe_duplicatas',
      label: 'Duplicatas no DANFE',
      status: 'ok' as const,
      mensagem: 'Duplicata 001, vencimento 05/07/2026, valor R$ 5.000,00.',
      secao: 'danfe',
    },
  ],
};

const respostaDanfeFalha = {
  apto: false,
  status: 'bloqueado' as const,
  bloqueios: [
    'DANFE não pôde ser renderizado. Corrija os dados fiscais antes de nova homologação.',
  ],
  alertas: [],
  mensagem: 'Checklist bloqueado. Corrija os itens críticos antes de gerar uma nova NF-e de homologação.',
  itens: [
    {
      codigo: 'danfe_render',
      label: 'DANFE',
      status: 'bloqueado' as const,
      mensagem:
        'DANFE não pôde ser renderizado. Corrija os dados fiscais antes de nova homologação. (ValueError: PDF vazio)',
      secao: 'danfe',
    },
  ],
};

const respostaBloqueada = {
  apto: false,
  status: 'bloqueado' as const,
  bloqueios: ['Pagamento a prazo sem duplicatas/vencimento calculável.'],
  alertas: [],
  mensagem: 'Checklist bloqueado. Corrija os itens críticos antes de gerar uma nova NF-e de homologação.',
  itens: [
    {
      codigo: 'duplicatas_nfe',
      label: 'Duplicatas da NF-e',
      status: 'bloqueado' as const,
      mensagem: 'Pagamento a prazo sem duplicatas/vencimento calculável.',
      secao: 'duplicatas',
    },
  ],
};

const nfeMock = {
  id: 1,
  numero: 'RASCUNHO-FAT-2',
  cliente_id: 1,
  cliente_nome: 'Cliente Teste',
  data: '2026-05-22',
  valor_total: 5000,
  status: 'AUTORIZADA_HOMOLOGACAO',
  status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
  listagem_resumo: {
    titulo: 'NF-e Homologação nº 000000002 — Série 0',
    subtitulo: 'FAT-1 · PV-1',
    fiscal_resumo: {
      badge: 'Homologação autorizada',
      variant: 'warning',
      subtexto: 'cStat 100 · Fora da apuração',
    },
    atendimento_resumo: { badges: [], ocultos: 0, vazio_label: 'Atendimento não definido' },
    tem_duplicatas: true,
    reforma_tributaria_status: 'nao_preparada',
  },
  apresentacao: {
    titulo_exibicao: 'NF-e Homologação nº 000000002 — Série 0',
    subtitulo_exibicao: 'Faturamento: FAT-1 · Pedido de venda: PV-1',
    numero_fiscal: '000000002',
    serie_fiscal: '0',
    ambiente_emissao: 'homologacao',
  },
  duplicatas_nfe: [
    {
      numero: '001',
      vencimento: '2026-07-05',
      vencimento_formatado: '05/07/2026',
      valor: '5000.00',
      valor_formatado: 'R$ 5.000,00',
    },
  ],
  resumo_atendimento_operacional: { badges: [], vazio_label: 'Atendimento não definido' },
  reforma_tributaria: { status: 'nao_preparada', status_label: 'Em preparação' },
};

describe('NFeChecklistHomologacaoModal', () => {
  it('mostra aviso de que não transmite NF-e', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovada);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/não transmite NF-e/i)).toBeInTheDocument();
    });
  });

  it('mostra itens OK e Reforma em preparação', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovada);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/Duplicatas da NF-e/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Reforma Tributária/).length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(/Estrutura em pesquisa\/preparação\. XML e DANFE seguem layout atual\./),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Alerta').length).toBeGreaterThanOrEqual(1);
  });

  it('mostra mensagem de aprovado', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovada);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/Pronto para novo teste de homologação/i)).toBeInTheDocument();
    });
  });

  it('mostra mensagem de aprovado com alertas', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovadaComAlertas);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/Checklist aprovado com alertas/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Validação prévia sem transmissão/i)).toBeInTheDocument();
    expect(screen.getByText(/não gera financeiro/i)).toBeInTheDocument();
  });

  it('mostra seção Financeiro', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovadaComAlertas);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText('Financeiro')).toBeInTheDocument();
    });
  });

  it('mostra seção DANFE como OK quando backend aprovar', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaDanfeOk);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/DANFE renderizado com sucesso/i)).toBeInTheDocument();
      expect(screen.getByText(/Duplicata 001/i)).toBeInTheDocument();
    });
  });

  it('mostra erro amigável quando DANFE falha', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaDanfeFalha);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getAllByText(/DANFE não pôde ser renderizado/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/1 bloqueio/i)).toBeInTheDocument();
    });
  });

  it('mostra resumo geral com contadores', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovadaComAlertas);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/bloqueio\(s\)/i)).toBeInTheDocument();
      expect(screen.getByText(/alerta\(s\)/i)).toBeInTheDocument();
      expect(screen.getByText(/itens OK/i)).toBeInTheDocument();
    });
  });

  it('mostra bloqueios', async () => {
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaBloqueada);
    render(<NFeChecklistHomologacaoModal open nfeSaidaId={1} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText(/Checklist bloqueado/i)).toBeInTheDocument();
      expect(screen.getByText(/Bloqueado/)).toBeInTheDocument();
    });
  });
});

describe('NFeSaidaDetalheDrawer checklist', () => {
  beforeEach(() => {
    vi.mocked(nfeSaidasService.getById).mockResolvedValue(nfeMock as never);
    vi.mocked(nfeSaidasService.checklistHomologacao).mockResolvedValue(respostaAprovadaComAlertas);
  });

  it('mostra botão Validar', async () => {
    render(<NFeSaidaDetalheDrawer nfeId={1} open onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Validar pré-homologação' })).toBeInTheDocument();
    });
  });

  it('clique em Validar chama endpoint e exibe badge no drawer', async () => {
    render(<NFeSaidaDetalheDrawer nfeId={1} open onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Validar pré-homologação' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Validar pré-homologação' }));
    await waitFor(() => {
      expect(nfeSaidasService.checklistHomologacao).toHaveBeenCalledWith(1);
      expect(screen.getByText('Checklist fiscal de homologação')).toBeInTheDocument();
    });
    const fecharModal = screen.getAllByRole('button', { name: 'Fechar' }).pop();
    expect(fecharModal).toBeDefined();
    fireEvent.click(fecharModal!);
    await waitFor(() => {
      expect(screen.getByText('Pré-homologação validada')).toBeInTheDocument();
    });
  });
});
