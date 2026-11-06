import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DevolucaoEntradaBloco,
  type DevolucaoEntradaBlocoHandle,
} from '@/components/fiscal/DevolucaoEntradaBloco';
import type {
  ItemConferenciaNFeEntrada,
  ResultadoGerarSaidaDevolucaoCompra,
} from '@/types';

const api = vi.hoisted(() => ({ gerarSaidaDevolucaoCompra: vi.fn() }));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: api,
}));

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }));
vi.mock('sonner', () => ({ toast }));

const item: ItemConferenciaNFeEntrada = {
  id: 5,
  item_nfe_historico: 1,
  produto_nome: 'Válvula esfera 2"',
  status: 'CONFERIDO',
  unidade_nf: 'UN',
  quantidade_nf: 10,
  valor_unitario_nf: 5,
  valor_total_nf: 50,
  quantidade_estoque_calculada: 4,
};

const resultado: ResultadoGerarSaidaDevolucaoCompra = {
  ok: true,
  nf_saida_id: 77,
  numero: 'DEV-001',
  valor_total: '180.00',
  itens_criados: 1,
  cfop: '5202',
  mensagem: 'ok',
};

async function abrirEGerar(ref: React.RefObject<DevolucaoEntradaBlocoHandle>) {
  ref.current?.abrir();
  const gerar = await screen.findByRole('button', { name: 'Gerar rascunho' });
  fireEvent.click(gerar);
}

describe('DevolucaoEntradaBloco', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.gerarSaidaDevolucaoCompra.mockResolvedValue(resultado);
  });

  afterEach(cleanup);

  it('não renderiza o modal até o handle abrir()', () => {
    const ref = createRef<DevolucaoEntradaBlocoHandle>();
    render(
      <DevolucaoEntradaBloco
        ref={ref}
        nfeHistoricaId={10}
        itensConferencia={[item]}
        onDevolucaoGerada={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Gerar rascunho' })).toBeNull();
  });

  it('gera pelo modal aberto pelo handle, fecha, toasta o texto do painel e delega o recarregamento', async () => {
    const ref = createRef<DevolucaoEntradaBlocoHandle>();
    const onDevolucaoGerada = vi.fn();
    render(
      <DevolucaoEntradaBloco
        ref={ref}
        nfeHistoricaId={10}
        itensConferencia={[item]}
        onDevolucaoGerada={onDevolucaoGerada}
      />,
    );

    await abrirEGerar(ref);

    await waitFor(() => {
      expect(api.gerarSaidaDevolucaoCompra).toHaveBeenCalledWith(10, {
        itens: [{ item_conferencia_id: 5, quantidade: '4' }],
        motivo: 'NAO_CONFORME',
        observacao: undefined,
      });
      expect(toast.success).toHaveBeenCalledWith(
        'Rascunho DEV-001 criado (R$ 180.00). NF-e de saída #77.',
      );
      expect(onDevolucaoGerada).toHaveBeenCalledTimes(1);
    });
    // O onSuccess do disco fechava o modal antes do toast; aqui o open é interno.
    expect(screen.queryByRole('button', { name: 'Gerar rascunho' })).toBeNull();
  });

  it('cancelar fecha sem chamar a API nem delegar recarregamento', async () => {
    const ref = createRef<DevolucaoEntradaBlocoHandle>();
    const onDevolucaoGerada = vi.fn();
    render(
      <DevolucaoEntradaBloco
        ref={ref}
        nfeHistoricaId={10}
        itensConferencia={[item]}
        onDevolucaoGerada={onDevolucaoGerada}
      />,
    );

    ref.current?.abrir();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByRole('button', { name: 'Gerar rascunho' })).toBeNull();
    expect(api.gerarSaidaDevolucaoCompra).not.toHaveBeenCalled();
    expect(onDevolucaoGerada).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
});
