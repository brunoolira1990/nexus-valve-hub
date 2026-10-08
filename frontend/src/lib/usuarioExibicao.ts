/** Nome exibido do usuário — ERP 4.0.14.9.4.1 */

export type UsuarioNomeExibicaoInput = {
  nome_exibicao?: string | null;
  colaborador_nome?: string | null;
  colaborador_id?: number | null;
  first_name?: string | null;
  last_name?: string | null;
  name?: string | null;
  nome?: string | null;
  nome_curto?: string | null;
  username?: string | null;
};

function trim(val?: string | null): string {
  return (val || '').trim();
}

/** Prioridade: nome_exibicao → colaborador_nome → first+last → name → nome → username. */
export function getUsuarioNomeExibicao(usuario?: UsuarioNomeExibicaoInput | null): string {
  if (!usuario) return 'Usuário';

  const username = trim(usuario.username);
  const colaboradorNome = trim(usuario.colaborador_nome);
  const candidatos = [
    trim(usuario.nome_exibicao),
    colaboradorNome,
    `${usuario.first_name || ''} ${usuario.last_name || ''}`.trim(),
    trim(usuario.name),
    trim(usuario.nome),
  ].filter(Boolean);

  for (const candidato of candidatos) {
    if (!username || candidato !== username) return candidato;
  }

  if (colaboradorNome) return colaboradorNome;
  if (username) return username;
  return 'Usuário';
}

/** Nome compacto para header em telas estreitas. */
export function getUsuarioNomeCurto(usuario?: UsuarioNomeExibicaoInput | null, maxLen = 18): string {
  const curto = trim(usuario?.nome_curto);
  if (curto) return curto;

  const completo = getUsuarioNomeExibicao(usuario);
  const partes = completo.split(/\s+/).filter(Boolean);
  if (!partes.length) return 'Usuário';
  if (partes.length === 1) return partes[0].slice(0, maxLen);
  const abreviado = `${partes[0]} ${partes[partes.length - 1][0]}.`;
  return abreviado.slice(0, maxLen);
}

/** Cache/contexto antigo pode trazer username como nome quando há colaborador vinculado. */
export function contextoUsuarioNomePareceStale(usuario?: UsuarioNomeExibicaoInput | null): boolean {
  if (!usuario?.colaborador_id && !trim(usuario?.colaborador_nome)) return false;
  const exibido = trim(usuario?.nome_exibicao) || trim(usuario?.nome);
  const username = trim(usuario?.username);
  if (!exibido) return true;
  return Boolean(username && exibido === username);
}
