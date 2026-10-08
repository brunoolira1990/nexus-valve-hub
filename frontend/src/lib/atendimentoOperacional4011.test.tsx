import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AtendimentoOperacionalBadge } from '@/components/comercial/AtendimentoOperacionalBadge';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { AtendimentoOperacionalInline } from '@/components/comercial/AtendimentoOperacionalInline';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

const resumoPendente: ResumoAtendimentoOperacional = {
  tem_alocacao: true,
  badges: [
    { label: 'Entrada pendente', status: 'entrada_pendente', variant: 'warning' },
    { label: 'Retirada fornecedor', status: 'retirada_fornecedor', variant: 'info' },
  ],
  mensagem: 'Atendimento com retirada no fornecedor e entrada fiscal pendente.',
};

const resumoConciliada: ResumoAtendimentoOperacional = {
  tem_alocacao: true,
  badges: [{ label: 'Entrada conciliada', status: 'entrada_conciliada', variant: 'success' }],
  mensagem: 'Entrada fiscal conciliada.',
};

const resumoSemAlocacao: ResumoAtendimentoOperacional = {
  tem_alocacao: false,
  badges: [{ label: 'Atendimento não definido', status: 'nao_definido', variant: 'neutral' }],
  mensagem:
    'Atendimento operacional ainda não definido. Use esta seção para informar retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada.',
};

describe('ERP 4.0.11 — atendimento operacional', () => {
  it('AtendimentoOperacionalBadge renderiza Entrada pendente', () => {
    render(<AtendimentoOperacionalBadge badge={resumoPendente.badges[0]} />);
    expect(screen.getByText('Entrada pendente')).toBeInTheDocument();
  });

  it('AtendimentoOperacionalBadge renderiza Entrada conciliada', () => {
    render(<AtendimentoOperacionalBadge badge={resumoConciliada.badges[0]} />);
    expect(screen.getByText('Entrada conciliada')).toBeInTheDocument();
  });

  it('AtendimentoOperacionalBadge renderiza Retirada fornecedor', () => {
    render(<AtendimentoOperacionalBadge badge={resumoPendente.badges[1]} />);
    expect(screen.getByText('Retirada fornecedor')).toBeInTheDocument();
  });

  it('AtendimentoOperacionalBadge renderiza Entrega direta', () => {
    render(
      <AtendimentoOperacionalBadge
        badge={{ label: 'Entrega direta', status: 'entrega_direta', variant: 'info' }}
      />,
    );
    expect(screen.getByText('Entrega direta')).toBeInTheDocument();
  });

  it('AtendimentoOperacionalResumo mostra mensagem sem alocação', () => {
    render(<AtendimentoOperacionalResumo resumo={resumoSemAlocacao} />);
    expect(screen.getByText(/ainda não definido/i)).toBeInTheDocument();
  });

  it('AtendimentoOperacionalInline oculta quando sem alocação (padrão)', () => {
    const { container } = render(<AtendimentoOperacionalInline resumo={resumoSemAlocacao} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('AtendimentoOperacionalInline exibe não definido na listagem PV', () => {
    render(<AtendimentoOperacionalInline resumo={resumoSemAlocacao} apenasComAlocacao={false} />);
    expect(screen.getByText(/Atendimento não definido/i)).toBeInTheDocument();
  });

  it('AtendimentoOperacionalBadges é alias do Inline', async () => {
    const { AtendimentoOperacionalBadges } = await import(
      '@/components/comercial/AtendimentoOperacionalInline'
    );
    render(<AtendimentoOperacionalBadges resumo={resumoPendente} />);
    expect(screen.getByText('Entrada pendente')).toBeInTheDocument();
  });

  it('AtendimentoOperacionalResumo exibe alertas informativos', () => {
    render(
      <AtendimentoOperacionalResumo
        resumo={{
          ...resumoPendente,
          alertas: ['Entrada fiscal ainda não conciliada. Operação permitida; sem bloqueio automático.'],
          tipo_atendimento_label: 'Retirada no fornecedor',
          status_entrada_fiscal_label: 'Entrada pendente',
        }}
      />,
    );
    expect(screen.getByText(/sem bloqueio automático/i)).toBeInTheDocument();
  });

  it('AtendimentoOperacionalInline exibe badges com alocação', () => {
    render(<AtendimentoOperacionalInline resumo={resumoPendente} />);
    expect(screen.getByText('Entrada pendente')).toBeInTheDocument();
    expect(screen.getByText('Retirada fornecedor')).toBeInTheDocument();
  });

  it('status fiscal e operacional são componentes distintos', () => {
    const { container } = render(
      <div>
        <StatusBadge status="autorizada_homologacao" />
        <AtendimentoOperacionalInline resumo={resumoPendente} />
      </div>,
    );
    expect(screen.getByText(/Autorizada homologação/i)).toBeInTheDocument();
    expect(screen.getByText('Entrada pendente')).toBeInTheDocument();
    expect(container.querySelectorAll('span').length).toBeGreaterThan(1);
  });

  it('não renderiza inline quando resumo é null', () => {
    const { container } = render(<AtendimentoOperacionalInline resumo={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
