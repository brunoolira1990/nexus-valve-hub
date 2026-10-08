import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ChecklistFiscalMinimo } from '@/components/fiscal/ChecklistFiscalMinimo';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import { prepararEstoqueErrorMessage } from '@/lib/conferenciaNfePreparar';

describe('ChecklistFiscalMinimo 4014101', () => {
  beforeEach(() => {
    vi.spyOn(regrasFiscaisService, 'checklistProducao').mockResolvedValue({
      checklist_saida: [
        { item: 'Regra fiscal de venda ativa', ok: true, nota: '' },
        { item: 'CST/CSOSN de saída configurado', ok: true, nota: '' },
      ],
      checklist_entrada: [
        { item: 'Regra fiscal de entrada ativa', ok: true, nota: '' },
        { item: 'CST/CSOSN de entrada configurado', ok: false, nota: 'Obrigatório ao finalizar NF-e Entrada fiscal.' },
      ],
      avisos_entrada: [
        {
          mensagem:
            'Regra fiscal de entrada "Configuração" incompleta (Falta CST/CSOSN.). Corrija antes de finalizar entradas fiscais de NF-e.',
        },
      ],
      criticos: [],
    });
  });

  it('mostra bloco Pronto para venda/saída', async () => {
    render(<ChecklistFiscalMinimo />);
    await waitFor(() => {
      expect(screen.getByText(/Pronto para venda\/saída/i)).toBeInTheDocument();
      expect(screen.getByText(/Regra fiscal de venda ativa/i)).toBeInTheDocument();
    });
  });

  it('mostra bloco Pendente para entrada fiscal', async () => {
    render(<ChecklistFiscalMinimo />);
    await waitFor(() => {
      expect(screen.getByText(/Pendente para entrada fiscal/i)).toBeInTheDocument();
      expect(screen.getByText(/CST\/CSOSN de entrada configurado/i)).toBeInTheDocument();
    });
  });

  it('regra de entrada incompleta aparece como aviso', async () => {
    render(<ChecklistFiscalMinimo />);
    await waitFor(() => {
      expect(screen.getByText(/Configuração/i)).toBeInTheDocument();
      expect(screen.getByText(/Falta CST\/CSOSN/i)).toBeInTheDocument();
    });
  });

  it('críticos de saída aparecem em destaque', async () => {
    vi.spyOn(regrasFiscaisService, 'checklistProducao').mockResolvedValue({
      checklist_saida: [{ item: 'Regra fiscal de venda ativa', ok: false, nota: '' }],
      checklist_entrada: [],
      criticos: [{ mensagem: 'Regra fiscal de saída "Venda" ativa sem CST/CSOSN de ICMS.' }],
    });
    render(<ChecklistFiscalMinimo />);
    await waitFor(() => {
      expect(screen.getByText(/sem CST\/CSOSN/i)).toBeInTheDocument();
    });
  });
});

describe('prepararEstoqueErrorMessage 4014101', () => {
  it('bloqueio de configuração de entrada fiscal', () => {
    const err = {
      isAxiosError: true,
      response: {
        data: {
          bloqueio_fiscal: true,
          pendencias: ['Não é possível finalizar a entrada fiscal sem regra fiscal de entrada válida.'],
        },
      },
    };
    const msg = prepararEstoqueErrorMessage(err);
    expect(msg).toMatch(/Cadastre regra fiscal de entrada antes de finalizar/i);
    expect(msg).toMatch(/CFOP, natureza e CST\/CSOSN/i);
  });

  it('bloqueio por item mantém mensagem operacional', () => {
    const err = {
      isAxiosError: true,
      response: {
        data: {
          bloqueio_fiscal: true,
          pendencias: ['Item 1: CFOP bloqueado por regra fiscal.'],
        },
      },
    };
    const msg = prepararEstoqueErrorMessage(err);
    expect(msg).toMatch(/itens bloqueados por regra fiscal/i);
  });
});

describe('labelStatusConfiguracao 4014101', () => {
  it('INCOMPLETO exibe Incompleta', async () => {
    const { labelStatusConfiguracao } = await import('@/lib/regrasFiscaisEntradaHelpers');
    expect(labelStatusConfiguracao('INCOMPLETO')).toBe('Incompleta');
  });
});
