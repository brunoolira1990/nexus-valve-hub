import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AdvancedSupportSection } from '@/components/nexus/AdvancedSupportSection';
import { OperationalMessage } from '@/components/nexus/OperationalMessage';
import { labelTipoComposicao, labelTipoEquivalencia } from '@/lib/conferenciaEquivalencia';
import {
  ACTION_LABELS,
  friendlyOperationalMessage,
  labelNfeStatusConferenciaOperacional,
  labelNfeStatusOperacional,
  labelPedidoStatusOperacional,
  PRODUTO_UI_LABELS,
  TECHNICAL_DOWNLOAD_LABELS,
} from '@/lib/operationalUi';

describe('operationalUi 4.0.13.8', () => {
  it('ACTION_LABELS usa verbos operacionais', () => {
    expect(ACTION_LABELS.verDanfe).toBe('Ver DANFE');
    expect(ACTION_LABELS.baixarXml).toBe('Baixar XML');
    expect(ACTION_LABELS.emitirNfe).toBe('Emitir NF-e');
    expect(ACTION_LABELS.prepararEmissao).toBe('Preparar emissão');
  });

  it('labels técnicos XML ficam separados dos operacionais', () => {
    expect(TECHNICAL_DOWNLOAD_LABELS.xmlPreliminar).toContain('XML preliminar');
    expect(ACTION_LABELS.baixarXml).not.toContain('assinado');
  });

  it('status NF-e em linguagem de negócio', () => {
    expect(labelNfeStatusOperacional('AUTORIZADA_HOMOLOGACAO')).toBe('NF-e autorizada');
    expect(labelNfeStatusOperacional('REJEITADA_HOMOLOGACAO')).toBe('NF-e rejeitada');
    expect(labelNfeStatusConferenciaOperacional('', 'PRONTA_PARA_EMISSAO')).toBe('Pronta para emissão');
    expect(labelNfeStatusConferenciaOperacional(undefined, 'EM_CONFERENCIA')).toBe('Em conferência');
    expect(labelNfeStatusConferenciaOperacional('ENVIADA_PRODUCAO', 'PRONTA_PARA_EMISSAO')).toBe(
      labelNfeStatusOperacional('ENVIADA_PRODUCAO'),
    );
  });

  it('status pedido operacional', () => {
    expect(labelPedidoStatusOperacional('EM_FATURAMENTO')).toBe('Pendente de faturamento');
    expect(labelPedidoStatusOperacional('FATURADO')).toBe('Faturado');
  });

  it('traduz mensagem técnica para amigável', () => {
    expect(friendlyOperationalMessage('ValidationError: item.snapshot_fiscal is null')).toContain(
      'dados fiscais',
    );
    expect(friendlyOperationalMessage('XML de transmissão sem chave válida')).toContain(
      'preparar a NF-e',
    );
    expect(friendlyOperationalMessage('BFR render failed')).toContain('DANFE');
  });

  it('produtos usa modelo de medidas', () => {
    expect(PRODUTO_UI_LABELS.tipoDimensional).toBe('Modelo de medidas');
    expect(PRODUTO_UI_LABELS.regraCodigo).toBe('Como o código será formado');
  });

  it('enum composição aparece amigável', () => {
    expect(labelTipoComposicao('MONTAGEM_ROSCADA')).toBe('Montagem roscada');
    expect(labelTipoEquivalencia('equivalencia_composta')).toBe('Itens do fornecedor agrupados');
  });
});

describe('AdvancedSupportSection', () => {
  it('fechado por padrão e abre ao clicar', () => {
    render(
      <AdvancedSupportSection title="Avançado / Suporte técnico">
        <p>Conteúdo técnico XML</p>
      </AdvancedSupportSection>,
    );
    expect(screen.queryByText('Conteúdo técnico XML')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Avançado/i }));
    expect(screen.getByText('Conteúdo técnico XML')).toBeInTheDocument();
  });
});

describe('OperationalMessage', () => {
  it('renderiza mensagem amigável', () => {
    render(<OperationalMessage title="Atenção" message="Erro payload ReceitaWS" />);
    expect(screen.getByText(/CNPJ/i)).toBeInTheDocument();
  });
});
