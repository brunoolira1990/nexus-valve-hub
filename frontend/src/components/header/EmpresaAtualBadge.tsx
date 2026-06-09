import { Link } from 'react-router-dom';
import { Building2 } from 'lucide-react';
import { formatCnpjDisplay } from '@/lib/cnpj';
import type { AppContextoEmpresa } from '@/services/api/appContexto';

type Props = {
  empresa: AppContextoEmpresa | null;
};

export function EmpresaAtualBadge({ empresa }: Props) {
  if (!empresa) {
    return (
      <span
        className="hidden sm:inline-flex items-center gap-1.5 text-xs text-amber-800 dark:text-amber-200 min-w-0 truncate"
        title="Empresa não configurada"
      >
        <Building2 className="h-3.5 w-3.5 shrink-0" />
        Empresa não configurada
      </span>
    );
  }

  const tooltip = `${empresa.razao_social} · CNPJ ${formatCnpjDisplay(empresa.cnpj)}`;

  return (
    <Link
      to="/empresas"
      className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-foreground/90 hover:text-primary min-w-0 max-w-[28vw] md:max-w-[36vw] lg:max-w-[42vw] xl:max-w-none transition-colors"
      title={tooltip}
      aria-label="Ver empresa atual"
    >
      <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{empresa.nome_exibicao}</span>
    </Link>
  );
}
