import { formatAmbienteNfe } from '@/lib/nfeSaidaApresentacaoFormat';

export type NfeAmbienteEmpresa = 'homologacao' | 'producao';

export const NFE_AMBIENTE_OPCOES: { value: NfeAmbienteEmpresa; label: string; descricao: string }[] = [
  {
    value: 'homologacao',
    label: 'Homologação',
    descricao: 'Testes SEFAZ sem valor fiscal. Numeração independente da produção.',
  },
  {
    value: 'producao',
    label: 'Produção',
    descricao: 'Ambiente fiscal real. Emissão só ocorre com autorização e flag global habilitada.',
  },
];

export const ALERTA_PRODUCAO_NFE =
  'Produção fiscal selecionada. A emissão real só ocorrerá se NFE_PRODUCAO_HABILITADA=true e a NF-e estiver pronta.';

export function labelNfeAmbienteEmpresa(ambiente: string | null | undefined): string {
  return formatAmbienteNfe(ambiente);
}

export function isNfeAmbienteProducao(ambiente: string | null | undefined): boolean {
  return (ambiente || '').trim().toLowerCase() === 'producao';
}
