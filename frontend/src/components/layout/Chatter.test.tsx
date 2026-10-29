import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Chatter } from '@/components/layout/Chatter';
import {
  chatterNotasService,
  type AnexoChatter,
  type NotaChatter,
} from '@/services/api/chatterNotas';
import { auditoriaService } from '@/services/api/auditoria';

vi.mock('@/services/api/chatterNotas', () => ({
  chatterNotasService: {
    listar: vi.fn(),
    criar: vi.fn(),
    atualizar: vi.fn(),
    excluir: vi.fn(),
    uploadAnexo: vi.fn(),
    excluirAnexo: vi.fn(),
  },
}));

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: vi.fn(),
    capacidade: vi.fn(),
  },
}));

// O Chatter decide o botão de excluir pelo usuário do contexto; o estado é mutável
// por teste para cobrir autor, terceiro e superuser.
const quemSou = vi.hoisted(() => ({ atual: { id: 1, is_superuser: false } }));

vi.mock('@/hooks/useAppContexto', () => ({
  useAppContexto: () => ({
    contexto: {
      empresa: null,
      usuario: {
        id: quemSou.atual.id,
        nome: 'Bruno Lira',
        nome_exibicao: 'Bruno Lira',
        email: 'bruno@nexus.test',
        username: 'bruno',
        perfil: 'admin',
        perfil_label: 'Administrador',
        is_admin: true,
        is_superuser: quemSou.atual.is_superuser,
      },
      colaborador: null,
      ambiente: 'homologacao',
      ambiente_label: 'Homologação',
    },
    loading: false,
    refresh: vi.fn(),
  }),
}));

function anexo(id: number, nome: string, tamanho_bytes = 2048): AnexoChatter {
  return {
    id,
    nota: 1,
    nome_original: nome,
    tamanho_bytes,
    criado_em: '2026-10-29T10:00:00Z',
    arquivo_url: `/media/chatter/anexos/2026/10/${nome}`,
  };
}

function nota(id: number, texto: string, autor_nome = 'Bruno Lira', anexos: AnexoChatter[] = []): NotaChatter {
  return {
    id,
    entity_type: 'familia',
    entity_id: 94,
    texto,
    autor: 1,
    autor_nome,
    anexos,
    criado_em: '2026-10-29T10:00:00Z',
    atualizado_em: '2026-10-29T10:00:00Z',
  };
}

function lista(...notas: NotaChatter[]) {
  return { count: notas.length, next: null, previous: null, results: notas };
}

const vazio = () => lista();

/** Radix ativa a aba no mouseDown; o click cobre a ativação por teclado/mouse manual. */
function abrirAba(nome: string) {
  const aba = screen.getByRole('tab', { name: nome });
  fireEvent.mouseDown(aba);
  fireEvent.click(aba);
}

function arquivo(name: string, conteudo = '%PDF-1.4 teste') {
  return new File([conteudo], name, { type: 'application/pdf' });
}

function selecionarArquivos(...files: File[]) {
  fireEvent.change(screen.getByLabelText('Selecionar anexos da nota'), {
    target: { files },
  });
}

/** O X só abre a confirmação; a chamada à API acontece no "Excluir" do diálogo. */
async function abrirConfirmacaoExcluirAnexo(anexoId: number) {
  fireEvent.click(await screen.findByTestId(`chatter-anexo-excluir-${anexoId}`));
  const dialogo = await screen.findByTestId('chatter-confirmar-anexo');
  return { dialogo, excluir: within(dialogo).getByRole('button', { name: 'Excluir' }) };
}

describe('Chatter', () => {
  beforeEach(() => {
    quemSou.atual = { id: 1, is_superuser: false };
    vi.mocked(chatterNotasService.listar).mockReset();
    vi.mocked(chatterNotasService.criar).mockReset();
    vi.mocked(chatterNotasService.uploadAnexo).mockReset();
    vi.mocked(chatterNotasService.excluirAnexo).mockReset();
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

    render(<Chatter entityType="familia" entityId={94} />);

    expect(screen.getAllByRole('tab')).toHaveLength(3);
    await waitFor(() =>
      expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith(
        'produtos',
        'familiaproduto',
        94,
        { page_size: 50 },
      ),
    );
    expect(await screen.findByTestId('auditoria-historico-vazio')).toBeInTheDocument();

    abrirAba('Notas internas');
    expect(await screen.findByTestId('chatter-notas-vazio')).toBeInTheDocument();
  });

  it('lista notas internas com autor, texto e link de download do anexo', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(
      lista(
        nota(2, 'Laudo do lote 2026-10', 'Bruno Lira', [anexo(77, 'laudo-lote-2026-10.pdf')]),
        nota(1, 'Família usada no pedido 4421'),
      ),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    const nota2 = await screen.findByTestId('chatter-nota-2');
    expect(nota2).toHaveTextContent('Laudo do lote 2026-10');
    expect(nota2).toHaveTextContent('Bruno Lira');

    const link = within(nota2).getByTestId('chatter-anexo-77');
    expect(link).toHaveAttribute('href', '/media/chatter/anexos/2026/10/laudo-lote-2026-10.pdf');
    expect(link).toHaveAttribute('download', 'laudo-lote-2026-10.pdf');
    expect(link).toHaveTextContent('2 KB');

    expect(screen.getByTestId('chatter-nota-1')).toHaveTextContent('Família usada no pedido 4421');
    expect(within(screen.getByTestId('chatter-nota-1')).queryAllByTestId(/^chatter-anexo-/)).toHaveLength(0);
    expect(chatterNotasService.listar).toHaveBeenCalledWith('familia', 94, { page_size: 50 });
  });

  it('autor da nota exclui anexo gravado e a lista recarrega sem o arquivo', async () => {
    vi.mocked(chatterNotasService.listar)
      .mockResolvedValueOnce(lista(nota(2, 'Laudo do lote', 'Bruno Lira', [anexo(77, 'laudo.pdf')])))
      .mockResolvedValue(lista(nota(2, 'Laudo do lote', 'Bruno Lira', [])));

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    // O nome acessível identifica o arquivo, não é uma X anônima.
    expect(await screen.findByRole('button', { name: 'Excluir laudo.pdf' })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('chatter-anexo-excluir-77'));

    // O clique pede confirmação: nada vai à API antes do "Excluir" do diálogo.
    const dialogo = await screen.findByTestId('chatter-confirmar-anexo');
    expect(within(dialogo).getByRole('heading', { name: 'Excluir anexo?' })).toBeInTheDocument();
    expect(dialogo).toHaveTextContent('O arquivo "laudo.pdf" será removido permanentemente.');
    expect(chatterNotasService.excluirAnexo).not.toHaveBeenCalled();

    fireEvent.click(within(dialogo).getByRole('button', { name: 'Excluir' }));

    await waitFor(() => expect(chatterNotasService.excluirAnexo).toHaveBeenCalledWith(77));
    await waitFor(() => expect(screen.queryByTestId('chatter-confirmar-anexo')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByTestId('chatter-anexo-77')).not.toBeInTheDocument());
    // Delete + refetch: a lista vem da API, não de corte otimista no estado local.
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(2);
  });

  it('cancelar no diálogo de confirmação não toca na API nem remove o anexo', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(
      lista(nota(2, 'Laudo do lote', 'Bruno Lira', [anexo(77, 'laudo.pdf')])),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    const { dialogo } = await abrirConfirmacaoExcluirAnexo(77);
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }));

    await waitFor(() => expect(screen.queryByTestId('chatter-confirmar-anexo')).not.toBeInTheDocument());
    expect(chatterNotasService.excluirAnexo).not.toHaveBeenCalled();
    expect(screen.getByTestId('chatter-anexo-77')).toBeInTheDocument();
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(1);

    // Depois de cancelar dá para repetir o fluxo — nada ficou travado.
    const segundo = await abrirConfirmacaoExcluirAnexo(77);
    fireEvent.click(within(segundo.dialogo).getByRole('button', { name: 'Excluir' }));
    await waitFor(() => expect(chatterNotasService.excluirAnexo).toHaveBeenCalledWith(77));
  });

  it('quem não é autor nem superuser não vê o botão de excluir', async () => {
    quemSou.atual = { id: 99, is_superuser: false };
    vi.mocked(chatterNotasService.listar).mockResolvedValue(
      lista(nota(2, 'Nota do Bruno', 'Bruno Lira', [anexo(77, 'laudo.pdf')])),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    const notaEl = await screen.findByTestId('chatter-nota-2');
    expect(within(notaEl).getByTestId('chatter-anexo-77')).toBeInTheDocument();
    expect(within(notaEl).queryByTestId('chatter-anexo-excluir-77')).not.toBeInTheDocument();
  });

  it('superuser exclui anexo de nota de outro autor', async () => {
    quemSou.atual = { id: 99, is_superuser: true };
    vi.mocked(chatterNotasService.listar).mockResolvedValue(
      lista(nota(2, 'Nota do Bruno', 'Bruno Lira', [anexo(77, 'laudo.pdf')])),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    const { dialogo } = await abrirConfirmacaoExcluirAnexo(77);
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Excluir' }));
    await waitFor(() => expect(chatterNotasService.excluirAnexo).toHaveBeenCalledWith(77));
  });

  it('recusa da API mantém o anexo na tela e nomeia o arquivo no papel de erro', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(
      lista(nota(2, 'Laudo do lote', 'Bruno Lira', [anexo(77, 'laudo.pdf')])),
    );
    vi.mocked(chatterNotasService.excluirAnexo).mockRejectedValue(
      Object.assign(new Error('Request failed with status code 403'), {
        response: { status: 403, data: { detail: 'Só o autor da nota pode excluir o anexo.' } },
      }),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    const { dialogo, excluir } = await abrirConfirmacaoExcluirAnexo(77);
    fireEvent.click(excluir);

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('Não foi possível excluir laudo.pdf');
    expect(screen.getByTestId('chatter-anexo-77')).toBeInTheDocument();
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(1);
    // Botão volta a habilitar: falha não deixa o chatter travado.
    expect(screen.getByTestId('chatter-anexo-excluir-77')).toBeEnabled();
  });

  it('composer envia a nota e a lista atualiza sem recarregar', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(lista(nota(1, 'Nota antiga')));
    vi.mocked(chatterNotasService.criar).mockResolvedValue(nota(9, 'Nota nova'));

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');
    expect(await screen.findByTestId('chatter-nota-1')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Nova nota interna'), {
      target: { value: 'Nota nova' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    await waitFor(() =>
      expect(chatterNotasService.criar).toHaveBeenCalledWith({
        entity_type: 'familia',
        entity_id: 94,
        texto: 'Nota nova',
      }),
    );
    expect(await screen.findByTestId('chatter-nota-9')).toHaveTextContent('Nota nova');
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(1);
    expect(chatterNotasService.uploadAnexo).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Nova nota interna')).toHaveValue('');
  });

  it('mostra o anexo pendente com nome, tamanho e contador, e remove pela X', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    expect(screen.getByRole('button', { name: 'Anexar' })).toBeInTheDocument();
    expect(screen.queryByTestId('chatter-anexo-contador')).not.toBeInTheDocument();

    selecionarArquivos(arquivo('laudo.pdf'), arquivo('anexo-grande.pdf'));

    const pendentes = await screen.findByTestId('chatter-anexos-pendentes');
    expect(within(pendentes).getAllByRole('button', { name: /^Remover/ })).toHaveLength(2);
    expect(within(pendentes).getByTestId('chatter-anexo-pendente-0')).toHaveTextContent('laudo.pdf');
    expect(within(pendentes).getByTestId('chatter-anexo-pendente-0')).toHaveTextContent('14 B');
    expect(screen.getByTestId('chatter-anexo-contador')).toHaveTextContent('2 anexos');

    fireEvent.click(within(pendentes).getByRole('button', { name: 'Remover laudo.pdf' }));
    await waitFor(() =>
      expect(screen.getByTestId('chatter-anexo-contador')).toHaveTextContent('1 anexo'),
    );
  });

  it('enviar nota sobe cada anexo depois de criar a nota e recarrega a lista', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());
    vi.mocked(chatterNotasService.criar).mockResolvedValue(nota(9, 'Com anexos'));
    vi.mocked(chatterNotasService.uploadAnexo).mockResolvedValue(anexo(1, 'um.pdf'));

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    fireEvent.change(screen.getByLabelText('Nova nota interna'), {
      target: { value: 'Com anexos' },
    });
    selecionarArquivos(arquivo('um.pdf'), arquivo('dois.pdf'));

    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    await waitFor(() => expect(chatterNotasService.uploadAnexo).toHaveBeenCalledTimes(2));
    expect(chatterNotasService.uploadAnexo).toHaveBeenNthCalledWith(1, 9, expect.objectContaining({ name: 'um.pdf' }));
    expect(chatterNotasService.uploadAnexo).toHaveBeenNthCalledWith(2, 9, expect.objectContaining({ name: 'dois.pdf' }));
    // Ordem importa: o anexo só pode apontar para uma nota que já existe.
    const ordemCriar = vi.mocked(chatterNotasService.criar).mock.invocationCallOrder[0];
    const ordemUpload = vi.mocked(chatterNotasService.uploadAnexo).mock.invocationCallOrder[0];
    expect(ordemCriar).toBeLessThan(ordemUpload);
    expect(chatterNotasService.listar).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId('chatter-anexos-pendentes')).not.toBeInTheDocument();
  });

  it('falha no anexo mantém a nota salva e avisa em papel de erro', async () => {
    vi.mocked(chatterNotasService.listar)
      .mockResolvedValueOnce(vazio())
      .mockResolvedValue(lista(nota(9, 'Nota com anexo recusado')));
    vi.mocked(chatterNotasService.criar).mockResolvedValue(nota(9, 'Nota com anexo recusado'));
    vi.mocked(chatterNotasService.uploadAnexo).mockRejectedValue(
      Object.assign(new Error('Request failed with status code 400'), {
        response: { status: 400, data: { arquivo: ['Tipo de arquivo não permitido.'] } },
      }),
    );

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Notas internas');

    fireEvent.change(screen.getByLabelText('Nova nota interna'), {
      target: { value: 'Nota com anexo recusado' },
    });
    selecionarArquivos(arquivo('proibido.pdf.exe'));

    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('A nota foi salva, mas o anexo não');
    expect(alerta).toHaveTextContent('Tipo de arquivo não permitido.');
    expect(screen.getByTestId('chatter-nota-9')).toBeInTheDocument();
  });

  it('mostra erro legível quando a API recusa a nota e mantém o texto digitado', async () => {
    vi.mocked(chatterNotasService.listar).mockResolvedValue(vazio());
    vi.mocked(chatterNotasService.criar).mockRejectedValue(
      Object.assign(new Error('Request failed with status code 400'), {
        response: { status: 400, data: { texto: ['A nota não pode ficar vazia.'] } },
      }),
    );

    render(<Chatter entityType="familia" entityId={94} />);
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

    render(<Chatter entityType="familia" entityId={94} />);
    abrirAba('Atividades');

    expect(await screen.findByTestId('chatter-atividades-breve')).toHaveTextContent(
      'Em breve (Sprint 3.15)',
    );
  });
});
