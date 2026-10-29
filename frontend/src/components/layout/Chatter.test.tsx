import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Chatter } from '@/components/layout/Chatter';
import { chatterNotasService, type NotaChatter } from '@/services/api/chatterNotas';
import { auditoriaService } from '@/services/api/auditoria';

vi.mock('@/services/api/chatterNotas', () => ({
  chatterNotasService: {
    listar: vi.fn(),
    criar: vi.fn(),
    atualizar: vi.fn(),
    excluir: vi.fn(),
  },
}));

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: vi.fn(),
    capacidade: vi.fn(),
  },
}));

function nota(id: number, texto: string, autor_nome = 'Bruno Lira'): NotaChatter {
  return {
    id,
    entity_type: 'familia',
    entity_id: 13,
    texto,
    autor: 1,
    autor_nome,
    criado_em: '2026-10-29T10:00:00Z',
    atualizado_em: '2026-10-29T10:00:00Z',
  };
}

function vazio(): { count: number; next: null; previous: null; results: NotaChatter[] } {
  return { count: 0, next: null, previous: null, results: [] };
}

/** Radix ativa a aba no mouseDown; o click cobre a ativação por teclado/mouse manual. */
function abrirAba(nome: string) {
  const aba = screen.getByRole('tab', { name: nome });
  fireEvent.mouseDown(aba);
  fireEvent.click(aba);
}

describe('Chatter', () => {
  beforeEach(() => {
    vi.mocked(chatterNotasService.listar).mockReset();
    vi.mocked(chatterNotasService.criar).mockReset();
    vi.mocked(auditoriaService.historicoObjeto).mockReset();
  });

  it('sem entityId orienta a salvar o registro primeiro e não monta as abas', () => {
    render(<Chatter entityType="familia" entityId={null} />);
    expect(screen.getByTestId('chatter-sem-registro')).toHaveTextContent(
      'Salve o registro primeiro para ver o histórico e adicionar notas.',
    );
    expect(screen.queryByRole('tab', { name: 'Notas internas' })).not.toBeInTheDocument();
    expect(chatterNotasService.listar).not.toHaveBeenCalled();
  });

  it('renderiza as 3 abas e carrega o histórico com o modelName do backend', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });

    render(<Chatter entityType="familia" entityId={13} />);

    expect(screen.getAllByRole('tab')).toHaveLength(3);
    await waitFor(() =>
      expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith(
        'produtos',
        'familiaproduto',
        13,
        { page_size: 50 },
      ),
    );
    expect(await screen.findByTestId('auditoria-historico-vazio')).toBeInTheDocument();

    abrirAba('Notas internas');
    expect(await screen.findByTestId('chatter-notas-vazio')).toBeInTheDocument();
  });

  it('lista notas internas com autor e texto', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [nota(2, 'Conferir certificado da FCMP'), nota(1, 'Família usada no pedido 4421')],
    });

    render(<Chatter entityType="familia" entityId={13} />);
    abrirAba('Notas internas');

    expect(await screen.findByTestId('chatter-nota-2')).toHaveTextContent(
      'Conferir certificado da FCMP',
    );
    expect(screen.getByTestId('chatter-nota-2')).toHaveTextContent('Bruno Lira');
    expect(screen.getByTestId('chatter-nota-1')).toHaveTextContent('Família usada no pedido 4421');
    expect(chatterNotasService.listar).toHaveBeenCalledWith('familia', 13, { page_size: 50 });
  });

  it('composer envia a nota e a lista atualiza sem recarregar', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [nota(1, 'Nota antiga')],
    });
    vi.mocked(chatterNotasService.criar).mockResolvedValue(nota(9, 'Nota nova'));

    render(<Chatter entityType="familia" entityId={13} />);
    abrirAba('Notas internas');
    expect(await screen.findByTestId('chatter-nota-1')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Nova nota interna'), {
      target: { value: 'Nota nova' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    await waitFor(() =>
      expect(chatterNotasService.criar).toHaveBeenCalledWith({
        entity_type: 'familia',
        entity_id: 13,
        texto: 'Nota nova',
      }),
    );
    expect(await screen.findByTestId('chatter-nota-9')).toHaveTextContent('Nota nova');
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Nova nota interna')).toHaveValue('');
  });

  it('mostra erro legível quando a API recusa a nota e mantém o texto digitado', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());
    vi.mocked(chatterNotasService.criar).mockRejectedValue(
      Object.assign(new Error('Request failed with status code 400'), {
        response: { status: 400, data: { texto: ['A nota não pode ficar vazia.'] } },
      }),
    );

    render(<Chatter entityType="familia" entityId={13} />);
    abrirAba('Notas internas');

    fireEvent.change(screen.getByLabelText('Nova nota interna'), {
      target: { value: 'Nota recusada' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('A nota não pode ficar vazia.');
    expect(screen.getByLabelText('Nova nota interna')).toHaveValue('Nota recusada');
    expect(screen.queryByTestId('chatter-nota-9')).not.toBeInTheDocument();
  });

  it('aba Atividades anuncia a Sprint 3.15', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());

    render(<Chatter entityType="familia" entityId={13} />);
    abrirAba('Atividades');

    expect(await screen.findByTestId('chatter-atividades-breve')).toHaveTextContent(
      'Em breve (Sprint 3.15)',
    );
  });
});
