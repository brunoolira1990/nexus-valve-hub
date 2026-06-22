import { describe, expect, it } from 'vitest';
import {
  classificarNfeResumoPedido,
  faturamentoIndicaNfeGerada,
  formatNFePedidoDisplay,
  formatNFeTitulo,
  getFaturamentoStatusLabel,
  getNFeFiscalBadgeTokens,
  getPedidoModalFooterActions,
  getStatusItemLabel,
  isPedidoTabEditable,
  mensagemNfeFaturamentoInconsistencia,
  pedidoFaturadoSemAtendimento,
  tituloResumoNfePedido,
} from '@/lib/pedidoVendaModalUi';

const linhaHomolog = {
  faturamento_id: 1,
  status: 'GERADO_NFE',
  observacao: '',
  criado_em: '',
  itens_count: 1,
  nfe_saida_id: 2,
  nfe_saida_numero: 'RASCUNHO-FAT-2',
  nfe_saida_status: 'AUTORIZADA_HOMOLOGACAO',
  nfe_titulo_exibicao: 'NF-e Homologação nº 000000002 — Série 0',
  nfe_numero_fiscal: '000000002',
  nfe_serie_fiscal: '0',
  nfe_status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
  nfe_cstat: '100',
};

describe('pedidoVendaModalUi', () => {
  it('NF-e autorizada em homologação não aparece como rascunho no título', () => {
    expect(tituloResumoNfePedido(linhaHomolog)).toBe('NF-e Homologação nº 000000002 — Série 0');
    expect(tituloResumoNfePedido(linhaHomolog)).not.toMatch(/rascunho/i);
    expect(classificarNfeResumoPedido(linhaHomolog)).toBe('autorizada_homolog');
  });

  it('formatNFeTitulo usa título amigável de homologação', () => {
    expect(formatNFeTitulo(linhaHomolog)).toContain('NF-e Homologação');
    expect(formatNFeTitulo(linhaHomolog)).toContain('000000002');
  });

  it('badges de homologação incluem sem valor fiscal e fora da apuração', () => {
    const badges = getNFeFiscalBadgeTokens(linhaHomolog);
    expect(badges).toContain('homologacao');
    expect(badges).toContain('sem_valor_fiscal');
    expect(badges).toContain('fora_apuracao');
  });

  it('GERADO_NFE não aparece cru no label amigável', () => {
    expect(getFaturamentoStatusLabel('GERADO_NFE')).toBe('NF-e gerada');
    expect(getFaturamentoStatusLabel('GERADO_NFE')).not.toBe('GERADO_NFE');
  });

  it('AUTORIZADA_HOMOLOGACAO não é label principal de faturamento', () => {
    expect(getFaturamentoStatusLabel('AUTORIZADA_HOMOLOGACAO')).not.toBe('AUTORIZADA_HOMOLOGACAO');
  });

  it('GERADO_NFE sem NF-e vinculada retorna alerta de inconsistência', () => {
    const msg = mensagemNfeFaturamentoInconsistencia({
      ...linhaHomolog,
      nfe_saida_id: null,
      nfe_titulo_exibicao: undefined,
    });
    expect(msg).toMatch(/indica NF-e gerada/i);
    expect(faturamentoIndicaNfeGerada('GERADO_NFE')).toBe(true);
  });

  it('rodapé fiscal usa Fechar em vez de Salvar', () => {
    const cfg = getPedidoModalFooterActions('fiscal', {
      pedidoId: 2,
      pedidoStatus: 'FATURADO',
      isNovoPedido: false,
    });
    expect(cfg.primaryLabel).toBe('Fechar');
    expect(cfg.primaryKind).toBe('close');
  });

  it('aba observações usa Salvar observações', () => {
    const cfg = getPedidoModalFooterActions('historico', {
      pedidoId: 2,
      pedidoStatus: 'FATURADO',
      isNovoPedido: false,
    });
    expect(cfg.primaryLabel).toBe('Salvar observações');
    expect(cfg.primaryKind).toBe('save');
  });

  it('aba consulta faturado não é editável', () => {
    expect(isPedidoTabEditable('faturamento', 'FATURADO', false)).toBe(false);
    expect(getPedidoModalFooterActions('resumo', { pedidoId: 2, pedidoStatus: 'FATURADO', isNovoPedido: false }).primaryLabel).toBe(
      'Fechar',
    );
  });

  it('pedido faturado sem atendimento detecta ausência de alocação', () => {
    expect(
      pedidoFaturadoSemAtendimento('FATURADO', {
        tem_alocacao: false,
        badges: [],
        mensagem: '',
      } as never),
    ).toBe(true);
  });

  it('rodapé inclui PDF do pedido quando há id', () => {
    expect(
      getPedidoModalFooterActions('fiscal', { pedidoId: 2, pedidoStatus: 'ABERTO', isNovoPedido: false }).showPedidoPdf,
    ).toBe(true);
  });

  it('formatNFePedidoDisplay retorna identidade homologação', () => {
    const d = formatNFePedidoDisplay(linhaHomolog);
    expect(d.titulo).toContain('Homologação');
    expect(d.referenciaInterna).toBe('RASCUNHO-FAT-2');
    expect(d.badges).toContain('Sem valor fiscal');
  });

  it('getStatusItemLabel não retorna enum cru', () => {
    expect(getStatusItemLabel('FATURADO')).toBe('Faturado');
    expect(getStatusItemLabel('FATURADO')).not.toBe('FATURADO');
  });

  it('NF-e cancelada SEFAZ não aparece como autorizada em produção', () => {
    const linhaCancelada = {
      ...linhaHomolog,
      nfe_saida_status: 'CANCELADA_PRODUCAO',
      nfe_status_emissao_sefaz: 'AUTORIZADA_PRODUCAO',
      nfe_titulo_exibicao: undefined,
    };
    expect(classificarNfeResumoPedido(linhaCancelada)).toBe('cancelada');
    expect(getNFeFiscalBadgeTokens(linhaCancelada)).toEqual(['cancelada']);
    expect(formatNFeTitulo(linhaCancelada)).toMatch(/cancelada/i);
    expect(formatNFeTitulo(linhaCancelada)).not.toMatch(/autorizada/i);
  });
});
