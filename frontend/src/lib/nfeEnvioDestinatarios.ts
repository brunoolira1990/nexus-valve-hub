/**
 * Helpers do envio manual DANFE/XML — seleção e dedupe de destinatários.
 */

import { emailOperacionalValido } from '@/lib/validacaoSenha';
import type { NFeEnvioDestinatarioSugerido } from '@/services/api/fiscal';

export type DestinatarioEnvioUi = {
  key: string;
  email: string;
  nome: string;
  origem: string;
  contato_id: number | null;
  selecionado: boolean;
  manual?: boolean;
};

export function chaveEmailEnvio(email: string): string {
  return email.trim().toLowerCase();
}

export function destinatariosSugeridosParaUi(
  sugeridos: NFeEnvioDestinatarioSugerido[] | undefined | null,
): DestinatarioEnvioUi[] {
  const out: DestinatarioEnvioUi[] = [];
  const vistos = new Set<string>();
  for (const item of sugeridos ?? []) {
    const email = (item.email || '').trim();
    if (!email || !emailOperacionalValido(email)) continue;
    const chave = chaveEmailEnvio(email);
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    out.push({
      key: item.contato_id != null ? `contato-${item.contato_id}` : `sug-${chave}`,
      email,
      nome: (item.nome || '').trim(),
      origem: item.origem || '',
      contato_id: item.contato_id ?? null,
      selecionado: item.selecionado !== false,
      manual: false,
    });
  }
  return out;
}

export function emailsSelecionadosEnvio(itens: DestinatarioEnvioUi[]): string[] {
  const out: string[] = [];
  const vistos = new Set<string>();
  for (const item of itens) {
    if (!item.selecionado) continue;
    const email = item.email.trim();
    if (!email || !emailOperacionalValido(email)) continue;
    const chave = chaveEmailEnvio(email);
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    out.push(email);
  }
  return out;
}

export function adicionarDestinatarioManual(
  itens: DestinatarioEnvioUi[],
  emailBruto: string,
): { itens: DestinatarioEnvioUi[]; erro: string | null } {
  const email = emailBruto.trim();
  if (!email) {
    return { itens, erro: 'Informe um e-mail válido.' };
  }
  if (!emailOperacionalValido(email)) {
    return { itens, erro: 'Informe um e-mail válido.' };
  }
  const chave = chaveEmailEnvio(email);
  if (itens.some((i) => chaveEmailEnvio(i.email) === chave)) {
    return { itens, erro: 'Este e-mail já está na lista de destinatários.' };
  }
  return {
    itens: [
      ...itens,
      {
        key: `manual-${chave}-${itens.length}`,
        email,
        nome: 'Informado manualmente',
        origem: 'manual',
        contato_id: null,
        selecionado: true,
        manual: true,
      },
    ],
    erro: null,
  };
}

export function rotuloOrigemDestinatario(origem: string): string {
  switch (origem) {
    case 'contato':
      return 'Contato fiscal';
    case 'email_nf':
      return 'E-mail NF (legado)';
    case 'email':
      return 'E-mail principal (legado)';
    case 'manual':
      return 'Manual';
    default:
      return origem || 'Cadastro';
  }
}
