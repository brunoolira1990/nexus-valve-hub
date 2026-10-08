export interface BadgeAtendimentoOperacional {
  label: string;
  status: string;
  variant: string;
}

export interface ResumoAtendimentoOperacional {
  tem_alocacao: boolean;
  tipo_atendimento?: string;
  tipo_atendimento_label?: string;
  status_entrada_fiscal?: string;
  status_entrada_fiscal_label?: string;
  origem_fisica?: string;
  origem_fisica_label?: string;
  destino_fisico?: string;
  destino_fisico_label?: string;
  tem_compra_vinculada?: boolean;
  tem_nfe_entrada_vinculada?: boolean;
  tem_cte_vinculado?: boolean;
  itens_total?: number;
  itens_com_entrada_pendente?: number;
  itens_com_entrada_conciliada?: number;
  itens_entrega_direta?: number;
  itens_retirada_fornecedor?: number;
  alertas?: string[];
  tipo_principal?: string;
  status_entrada_principal?: string;
  origem_fisica_principal?: string;
  destino_fisico_principal?: string;
  quantidade_itens?: number;
  quantidade_pendente?: string;
  quantidade_conciliada?: string;
  possui_entrada_pendente?: boolean;
  possui_entrada_conciliada?: boolean;
  possui_divergencia?: boolean;
  possui_retirada_fornecedor?: boolean;
  possui_entrega_direta?: boolean;
  atendimento_misto?: boolean;
  badges: BadgeAtendimentoOperacional[];
  mensagem?: string;
}
