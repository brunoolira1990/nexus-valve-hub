import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  APP_SWITCHER_OTHER_SECTIONS,
  APP_SWITCHER_PRIMARY_SECTIONS,
  buildAppSwitcherModules,
  type AppSwitcherModule,
} from '@/components/layout/AppSwitcher';
import { useAppContexto } from '@/hooks/useAppContexto';

interface GradeModulosProps {
  modulos: AppSwitcherModule[];
}

/**
 * Cartões maiores que os do modal: em tela cheia o card é o destino, não uma opção de
 * menu, então o ícone e a descrição sobem de tamanho e o grid respira em 4 colunas.
 */
const GradeModulos = ({ modulos }: GradeModulosProps) => (
  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
    {modulos.map((modulo) => (
      <Link
        key={`${modulo.label}-${modulo.path}`}
        to={modulo.path}
        className="flex flex-col items-start gap-4 rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-colors hover:border-primary/40 hover:bg-muted/40"
      >
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <modulo.icon className="h-6 w-6" />
        </span>
        <span className="min-w-0">
          <span className="block text-base font-semibold text-foreground">{modulo.label}</span>
          <span className="mt-1 block line-clamp-2 text-sm text-muted-foreground">{modulo.descricao}</span>
        </span>
      </Link>
    ))}
  </div>
);

export const AppsHome = () => {
  const { contexto } = useAppContexto();
  const modulos = useMemo(
    () => buildAppSwitcherModules([...APP_SWITCHER_PRIMARY_SECTIONS, ...APP_SWITCHER_OTHER_SECTIONS]),
    [],
  );
  const nome = contexto.usuario.nome_exibicao || contexto.usuario.nome;

  return (
    <div className="mx-auto w-full max-w-6xl py-6 sm:py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {nome ? `Bem-vindo, ${nome}.` : 'Bem-vindo.'}
        </h1>
      </header>

      <GradeModulos modulos={modulos} />
    </div>
  );
};

export default AppsHome;
