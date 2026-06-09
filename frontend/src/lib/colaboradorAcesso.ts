/** Perfis de acesso ao sistema (Django Groups) — ERP 4.0.14.9.1 / 4.0.14.10.2 */

export const PERFIS_ACESSO = [
  { value: 'administrador', label: 'Administrador' },
  { value: 'financeiro', label: 'Financeiro' },
  { value: 'fiscal', label: 'Fiscal' },
  { value: 'compras', label: 'Compras' },
  { value: 'comercial', label: 'Comercial' },
  { value: 'estoque', label: 'Estoque' },
  { value: 'produtos', label: 'Produtos' },
  { value: 'consulta', label: 'Consulta' },
] as const;

export type AcessoStatusColaborador =
  | 'SEM_USUARIO'
  | 'USUARIO_ATIVO'
  | 'USUARIO_INATIVO'
  | 'SEM_PERFIL'
  | 'SUPERUSUARIO';

export type ColaboradorAcessoCampos = {
  acesso_status?: string | null;
  acesso_status_label?: string | null;
  badge_acesso?: string | null;
  perfil_acesso?: string | null;
  perfil_acesso_label?: string | null;
  usuario_login?: string | null;
  usuario_email?: string | null;
  usuario_ativo?: boolean;
  usuario_is_staff?: boolean;
  usuario_is_superuser?: boolean;
  usuario_grupos?: string[];
  sem_perfil?: boolean;
  email_tecnico?: boolean;
};

export function badgeAcessoVariant(
  c: ColaboradorAcessoCampos,
): 'default' | 'warning' | 'destructive' | 'muted' {
  if (c.acesso_status === 'SEM_PERFIL' || c.sem_perfil) return 'destructive';
  if (c.acesso_status === 'SEM_USUARIO') return 'muted';
  if (c.acesso_status === 'USUARIO_INATIVO') return 'warning';
  if (c.email_tecnico) return 'warning';
  return 'default';
}

export function badgeAcessoListagem(c: ColaboradorAcessoCampos): string {
  if (c.badge_acesso) return c.badge_acesso;
  if (c.acesso_status === 'SEM_USUARIO') return 'Sem acesso';
  if (c.acesso_status === 'USUARIO_INATIVO') return 'Acesso inativo';
  if (c.acesso_status === 'SUPERUSUARIO') return 'Superusuário';
  if (c.acesso_status === 'SEM_PERFIL' || c.sem_perfil) return 'Sem perfil';
  if (c.acesso_status === 'USUARIO_ATIVO') return c.perfil_acesso_label || 'Usuário ativo';
  return c.acesso_status_label || 'Sem acesso';
}

export function labelAcessoComPerfil(c: ColaboradorAcessoCampos): string {
  return badgeAcessoListagem(c);
}

export function acessoColaboradorTooltip(c: ColaboradorAcessoCampos): string | undefined {
  if (!c.usuario_login && !c.usuario_email && c.acesso_status === 'SEM_USUARIO') return undefined;
  const linhas: string[] = [badgeAcessoListagem(c)];
  if (c.usuario_login) linhas.push(`Login: ${c.usuario_login}`);
  if (c.usuario_email) linhas.push(`E-mail: ${c.usuario_email}`);
  linhas.push(`Status: ${c.usuario_ativo ? 'Ativo' : 'Inativo'}`);
  const grupos =
    c.usuario_grupos?.filter((g) => g !== 'superusuario').join(', ') ||
    (c.usuario_is_superuser ? '—' : 'nenhum');
  linhas.push(`Grupos: ${grupos}`);
  linhas.push(`Superusuário: ${c.usuario_is_superuser ? 'Sim' : 'Não'}`);
  return linhas.join('\n');
}

export function perfilInicialSugerido(c: {
  perfil_sugerido?: string | null;
  perfil_acesso?: string | null;
  eh_administrador?: boolean;
  eh_responsavel_financeiro?: boolean;
}): string {
  if (c.perfil_acesso && c.perfil_acesso !== 'superusuario') return c.perfil_acesso;
  if (c.perfil_sugerido) return c.perfil_sugerido;
  if (c.eh_administrador) return 'administrador';
  if (c.eh_responsavel_financeiro) return 'financeiro';
  return 'consulta';
}

export function tipoUsuarioLabel(c: ColaboradorAcessoCampos): string {
  if (c.usuario_is_superuser) return 'Superusuário';
  if (c.usuario_is_staff) return 'Staff';
  return 'Usuário comum';
}
