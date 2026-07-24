/**
 * Helpers de validação de contatos adicionais do Cliente (e-mails fiscais).
 * Sem dependência de Axios — mensagens amigáveis para a UI.
 */

import type { ContatoCliente } from '@/types';

export const MSG_EMAIL_FISCAL_OBRIGATORIO =
  'Informe um e-mail para o contato que recebe documentos fiscais.';
export const MSG_EMAIL_DUPLICADO = 'Este e-mail já está cadastrado nos contatos deste cliente.';
export const MSG_EMAIL_INVALIDO = 'Informe um endereço de e-mail válido.';
export const MSG_AUXILIAR_CONTATOS_FISCAIS =
  'Contatos ativos marcados para documentos fiscais poderão ser selecionados no envio manual de DANFE e XML.';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizarEmailContato(email: string | undefined | null): string {
  return (email ?? '').trim();
}

export function chaveEmailContato(email: string | undefined | null): string {
  return normalizarEmailContato(email).toLowerCase();
}

export function emailContatoValido(email: string | undefined | null): boolean {
  const n = normalizarEmailContato(email);
  if (!n) return false;
  return EMAIL_RE.test(n);
}

export type ContatoClienteErro = {
  email?: string;
};

/**
 * Valida lista de contatos (duplicidade CI, fiscal exige e-mail, formato).
 * Retorna um erro por índice; `null` = sem erro naquele contato.
 */
export function validarContatosCliente(contatos: ContatoCliente[]): Array<ContatoClienteErro | null> {
  const erros: Array<ContatoClienteErro | null> = contatos.map(() => null);
  const visto = new Map<string, number>();

  contatos.forEach((item, i) => {
    const email = normalizarEmailContato(item.email);
    const recebe = Boolean(item.recebe_documentos_fiscais);

    if (recebe && !email) {
      erros[i] = { ...erros[i], email: MSG_EMAIL_FISCAL_OBRIGATORIO };
      return;
    }
    if (email && !emailContatoValido(email)) {
      erros[i] = { ...erros[i], email: MSG_EMAIL_INVALIDO };
      return;
    }
    if (!email) return;

    const chave = chaveEmailContato(email);
    const primeiro = visto.get(chave);
    if (primeiro !== undefined) {
      erros[i] = { ...erros[i], email: MSG_EMAIL_DUPLICADO };
      if (!erros[primeiro]?.email) {
        erros[primeiro] = { ...erros[primeiro], email: MSG_EMAIL_DUPLICADO };
      }
    } else {
      visto.set(chave, i);
    }
  });

  return erros;
}

export function contatosClienteTemErro(erros: Array<ContatoClienteErro | null>): boolean {
  return erros.some((e) => Boolean(e?.email));
}

export function contatoVazioCliente(): ContatoCliente {
  return {
    tipo: 'COMERCIAL',
    nome: '',
    telefone: '',
    celular: '',
    email: '',
    principal: false,
    ativo: true,
    recebe_documentos_fiscais: false,
  };
}
