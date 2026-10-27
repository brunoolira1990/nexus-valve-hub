/**
 * Listas do card "Classificação técnica" da Família (Sprint 3.7).
 * Os valores continuam gravados nos CharFields tipo_peca / material_vedacao,
 * então a lista é apenas o vocabulário sugerido — o que já está no banco fora
 * dela continua visível no Select (ver `garantirOpcaoSalva`).
 */
export const OPCOES_TIPO_PECA_FAMILIA = [
  'Válvula',
  'Tubo',
  'Bucha',
  'Flange',
  'Niple',
  'Conexão',
  'Manômetro',
  'Junta',
  'Cap',
  'Tê',
  'Curva',
  'Outro',
] as const;

export const OPCOES_MATERIAL_VEDACAO_FAMILIA = [
  'PTFE',
  'NBR',
  'EPDM',
  'Viton',
  'Fibra',
  'Metal',
  'Silicone',
  'Outro',
] as const;

/**
 * O Radix não aceita value="", e um valor salvo fora da lista (família antiga com
 * 'Gaxeta', por exemplo) precisa continuar aparecendo — senão a tela mostraria a
 * primeira opção e gravaria por cima do que já existe.
 */
export function opcoesComValorSalvo(
  opcoes: readonly string[],
  valorSalvo: string,
  sentinelaVazio: string,
): string[] {
  const valor = valorSalvo.trim();
  if (!valor || opcoes.includes(valor)) return [...opcoes];
  return [valor, ...opcoes];
}
