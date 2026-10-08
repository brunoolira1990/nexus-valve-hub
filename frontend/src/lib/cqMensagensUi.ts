/**
 * Helpers puros para mensagens operacionais do Certificado de Qualidade.
 * Deduplicação por conteúdo (identificador estável), sem depender da posição
 * no array — corrige o acúmulo de mensagens repetidas na tela do CQ.
 */

export const MSG_SEM_CORRIDAS_IRMAS =
  'Não há outras corridas irmãs deste certificado para adicionar.';

/** Acrescenta apenas mensagens inéditas; preserva a referência quando nada muda. */
export function mesclarMensagensUnicas(atuais: string[], novas: string | string[]): string[] {
  const lista = Array.isArray(novas) ? novas : [novas];
  const ineditas = lista.filter(
    (msg, i) => msg && !atuais.includes(msg) && lista.indexOf(msg) === i,
  );
  return ineditas.length ? [...atuais, ...ineditas] : atuais;
}

/** Remove mensagens específicas sem tocar nas demais; preserva a referência quando nada muda. */
export function removerMensagens(atuais: string[], remover: string | string[]): string[] {
  const alvo = new Set(Array.isArray(remover) ? remover : [remover]);
  const restantes = atuais.filter((m) => !alvo.has(m));
  return restantes.length === atuais.length ? atuais : restantes;
}
