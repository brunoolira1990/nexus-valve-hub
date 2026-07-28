import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AVISO_COBERTURA_PROTESTO,
  SecaoProtestosCartorio,
  URL_PESQUISA_PROTESTO,
} from '@/components/financeiro/SecaoProtestosCartorio';
import type { ProtestoManualRegistro } from '@/services/api/analiseFinanceira';

const listMock = vi.fn();
const registrarMock = vi.fn();

vi.mock('@/services/api/analiseFinanceira', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/analiseFinanceira')>(
    '@/services/api/analiseFinanceira',
  );
  return {
    ...actual,
    analiseFinanceiraService: {
      ...actual.analiseFinanceiraService,
      listProtestosManuais: (...args: unknown[]) => listMock(...args),
      registrarProtestoManual: (...args: unknown[]) => registrarMock(...args),
    },
  };
});

function registro(partial: Partial<ProtestoManualRegistro> = {}): ProtestoManualRegistro {
  return {
    id: 10,
    tipo: 'PROTESTO_MANUAL',
    status: 'CONCLUIDA',
    solicitada_em: '2026-07-27T12:00:00Z',
    resultado_normalizado: {
      origem: 'PESQUISA_PROTESTO_MANUAL',
      registro_manual: true,
      resultado: 'SEM_PROTESTOS_INFORMADOS',
      quantidade_informada: null,
      ufs_informadas: [],
      cartorios_informados: null,
      observacao: null,
      consultado_em: '2026-07-27T11:00:00Z',
      registrado_em: '2026-07-27T12:00:00Z',
      registrado_por: { id: '1', nome_exibicao: 'Financeiro Teste' },
      corrige_registro_id: null,
      motivo_correcao: null,
      aviso: 'manual',
    },
    ...partial,
  };
}

describe('SecaoProtestosCartorio', () => {
  beforeEach(() => {
    listMock.mockReset();
    registrarMock.mockReset();
    listMock.mockResolvedValue([]);
    registrarMock.mockResolvedValue(registro());
  });

  it('botão abre URL pública fixa em nova aba com noopener', () => {
    render(
      <SecaoProtestosCartorio
        analiseId={1}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    const link = screen.getByTestId('dossie-btn-abrir-pesquisa-protesto');
    expect(link).toHaveAttribute('href', URL_PESQUISA_PROTESTO);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link.getAttribute('href')).not.toMatch(/cnpj|token|analise/i);
    expect(URL_PESQUISA_PROTESTO).not.toMatch(/\?/);
  });

  it('exibe aviso de cobertura e estado vazio', () => {
    render(
      <SecaoProtestosCartorio
        analiseId={1}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    expect(screen.getByTestId('dossie-protestos-aviso-cobertura')).toHaveTextContent(AVISO_COBERTURA_PROTESTO);
    expect(screen.getByTestId('dossie-protestos-vazio')).toBeInTheDocument();
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/recomendação automática/i)).not.toBeInTheDocument();
  });

  it('sem permissão de ver não renderiza seção', () => {
    const { container } = render(
      <SecaoProtestosCartorio analiseId={1} podeVer={false} podeRegistrar={false} carregarHistorico={false} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('sem permissão de registrar não mostra ação', () => {
    render(
      <SecaoProtestosCartorio
        analiseId={1}
        podeVer
        podeRegistrar={false}
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    expect(screen.queryByTestId('dossie-btn-registrar-protesto')).not.toBeInTheDocument();
    expect(screen.getByTestId('dossie-btn-abrir-pesquisa-protesto')).toBeInTheDocument();
  });

  it('exibe registro mais recente e histórico', () => {
    const recente = registro({
      id: 2,
      resultado_normalizado: {
        ...registro().resultado_normalizado!,
        resultado: 'COM_PROTESTOS_INFORMADOS',
        quantidade_informada: 2,
        ufs_informadas: ['SP'],
        motivo_correcao: 'Atualização',
      },
    });
    const antigo = registro({ id: 1 });
    render(
      <SecaoProtestosCartorio
        analiseId={1}
        podeVer
        podeRegistrar
        historicoInicial={[recente, antigo]}
        carregarHistorico={false}
      />,
    );
    expect(screen.getByTestId('dossie-protestos-recente-status')).toHaveTextContent('Com protestos informados');
    expect(screen.getByTestId('dossie-protestos-quantidade')).toHaveTextContent('2');
    fireEvent.click(screen.getByTestId('dossie-protestos-toggle-historico'));
    expect(screen.getByTestId('dossie-protestos-historico')).toBeInTheDocument();
  });

  it('salva sem protestos', async () => {
    render(
      <SecaoProtestosCartorio
        analiseId={7}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    fireEvent.click(screen.getByTestId('dossie-btn-registrar-protesto'));
    fireEvent.click(screen.getByTestId('dossie-protestos-salvar'));
    await waitFor(() => expect(registrarMock).toHaveBeenCalled());
    expect(registrarMock.mock.calls[0][0]).toBe(7);
    expect(registrarMock.mock.calls[0][1].resultado).toBe('SEM_PROTESTOS_INFORMADOS');
  });

  it('salva inconclusiva com observação', async () => {
    render(
      <SecaoProtestosCartorio
        analiseId={7}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    fireEvent.click(screen.getByTestId('dossie-btn-registrar-protesto'));
    fireEvent.change(screen.getByTestId('dossie-protestos-campo-resultado'), {
      target: { value: 'CONSULTA_INCONCLUSIVA' },
    });
    fireEvent.change(screen.getByTestId('dossie-protestos-campo-observacao'), {
      target: { value: 'Portal fora do ar' },
    });
    fireEvent.click(screen.getByTestId('dossie-protestos-salvar'));
    await waitFor(() => expect(registrarMock).toHaveBeenCalled());
    expect(registrarMock.mock.calls[0][1].resultado).toBe('CONSULTA_INCONCLUSIVA');
  });

  it('valida quantidade zero com protestos', async () => {
    render(
      <SecaoProtestosCartorio
        analiseId={7}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    fireEvent.click(screen.getByTestId('dossie-btn-registrar-protesto'));
    fireEvent.change(screen.getByTestId('dossie-protestos-campo-resultado'), {
      target: { value: 'COM_PROTESTOS_INFORMADOS' },
    });
    fireEvent.change(screen.getByTestId('dossie-protestos-campo-quantidade'), { target: { value: '0' } });
    fireEvent.click(screen.getByTestId('dossie-protestos-salvar'));
    expect(await screen.findByTestId('dossie-protestos-form-erro')).toBeInTheDocument();
    expect(registrarMock).not.toHaveBeenCalled();
  });

  it('erro da API não vira sem protestos', async () => {
    registrarMock.mockRejectedValueOnce({ response: { data: { detail: 'Falha Nexus' } } });
    render(
      <SecaoProtestosCartorio
        analiseId={7}
        podeVer
        podeRegistrar
        historicoInicial={[]}
        carregarHistorico={false}
      />,
    );
    fireEvent.click(screen.getByTestId('dossie-btn-registrar-protesto'));
    fireEvent.click(screen.getByTestId('dossie-protestos-salvar'));
    const alerta = await screen.findByTestId('dossie-protestos-form-erro');
    expect(alerta.textContent || '').not.toMatch(/sem protestos/i);
  });

  it('correção envia registro_anterior_id e motivo', async () => {
    const recente = registro({ id: 44 });
    render(
      <SecaoProtestosCartorio
        analiseId={7}
        podeVer
        podeRegistrar
        historicoInicial={[recente]}
        carregarHistorico={false}
      />,
    );
    fireEvent.click(screen.getByTestId('dossie-btn-registrar-protesto'));
    fireEvent.click(screen.getByTestId('dossie-protestos-campo-corrigir'));
    fireEvent.change(screen.getByTestId('dossie-protestos-campo-motivo-correcao'), {
      target: { value: 'Novo resultado no portal' },
    });
    fireEvent.click(screen.getByTestId('dossie-protestos-salvar'));
    await waitFor(() => expect(registrarMock).toHaveBeenCalled());
    expect(registrarMock.mock.calls[0][1].registro_anterior_id).toBe(44);
    expect(registrarMock.mock.calls[0][1].motivo_correcao).toBe('Novo resultado no portal');
  });
});
