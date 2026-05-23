/** NF-e Saída 3.5.3 — status de prontidão da conferência (separado do status fiscal). */

export type StatusConferenciaNFe =
  | 'EM_CONFERENCIA'
  | 'COM_PENDENCIAS'
  | 'CONFERIDA'
  | 'PRONTA_PARA_EMISSAO'
  | string;

export type NFeSaidaProntidaoPayload = {
  nfe_saida_id?: number;
  status?: string;
  status_conferencia: StatusConferenciaNFe;
  status_conferencia_display: string;
  pode_validar: boolean;
  pode_marcar_pronta: boolean;
  total_pendencias: number;
  total_alertas: number;
  mensagens?: string[];
  ultima_validacao_em?: string | null;
  marcada_pronta_em?: string | null;
  conferencia_ultima_mensagem?: string;
};

export function badgeStatusConferenciaNFe(
  status: StatusConferenciaNFe | undefined,
): { label: string; className: string } {
  const st = (status || 'EM_CONFERENCIA').toUpperCase();
  switch (st) {
    case 'PRONTA_PARA_EMISSAO':
      return { label: 'Pronta para emissão', className: 'erp-badge-success' };
    case 'CONFERIDA':
      return { label: 'Conferida', className: 'erp-badge-success opacity-90' };
    case 'COM_PENDENCIAS':
      return { label: 'Com pendências', className: 'erp-badge-danger' };
    case 'EM_CONFERENCIA':
    default:
      return { label: 'Em conferência', className: 'erp-badge-warning' };
  }
}

export function mensagemOrientacaoProntidao(status: StatusConferenciaNFe | undefined): string | null {
  const st = (status || '').toUpperCase();
  if (st === 'COM_PENDENCIAS') {
    return 'Existem pendências bloqueantes. Corrija os itens abaixo e valide novamente.';
  }
  if (st === 'CONFERIDA') {
    return 'Conferência validada sem pendências bloqueantes. Você pode marcar a NF-e como pronta para emissão.';
  }
  if (st === 'PRONTA_PARA_EMISSAO') {
    return 'NF-e pronta para emissão futura. Esta fase ainda não transmite para SEFAZ. Próxima etapa futura: transmitir para SEFAZ.';
  }
  return 'Salve os dados complementares e use «Validar conferência» para atualizar o status.';
}

export function podeExibirBotaoMarcarPronta(prontidao: NFeSaidaProntidaoPayload | undefined): boolean {
  return Boolean(prontidao?.pode_marcar_pronta);
}
