import { useCallback, useEffect, useState } from 'react';
import { dashboardService, type DashboardHome as DashboardHomeData } from '@/services/api/dashboard';
import { useDashboardHomeFilters } from '@/hooks/useDashboardBI';
import { useDashboardPermissoes } from '@/hooks/useDashboardPermissoes';
import {
  SESSION_EXPIRED_MESSAGE,
  apiErrorMessage,
  isApiUnauthorized,
} from '@/services/api/config';
import { BIPageLayout } from '@/components/bi/BIPageLayout';
import { BIFilterBar } from '@/components/bi/BIFilterBar';
import { BIModuleCard } from '@/components/bi/BIModuleCard';
import { BIAlertList } from '@/components/bi/BIAlertList';
import { BIModuleNav } from '@/components/bi/BIModuleNav';
import { BILoadingState } from '@/components/bi/BILoadingState';
import { BIErrorState } from '@/components/bi/BIErrorState';
import { BIEmptyState } from '@/components/bi/BIEmptyState';

export default function DashboardHome() {
  const { permissoes } = useDashboardPermissoes();
  const { appliedFilters, applyFilters, clearFilters, queryParams } = useDashboardHomeFilters();
  const [data, setData] = useState<DashboardHomeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setUnauthorized(false);
    try {
      setData(await dashboardService.getHome(queryParams));
    } catch (err) {
      setData(null);
      if (isApiUnauthorized(err)) {
        setUnauthorized(true);
        setError(SESSION_EXPIRED_MESSAGE);
      } else {
        setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar o dashboard.' }));
      }
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  useEffect(() => {
    void load();
  }, [load]);

  const perms = data?.permissoes ?? permissoes;

  return (
    <BIPageLayout
      title="Dashboard"
      subtitle="Visão executiva dos módulos permitidos ao seu perfil"
      periodo={data?.periodo}
      nav={<BIModuleNav permissoes={perms} />}
      filters={
        <BIFilterBar
          filters={appliedFilters}
          onApply={applyFilters}
          onClear={clearFilters}
          showEmpresa={false}
        />
      }
    >
      {loading ? <BILoadingState message="Carregando dashboard…" /> : null}
      {!loading && error ? <BIErrorState message={error} onRetry={() => void load()} /> : null}
      {!loading && !error && data ? (
        <>
          {data.nenhum_modulo ? (
            <BIEmptyState message="Nenhum painel disponível para seu usuário. Solicite acesso ao administrador." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-5 mb-8 min-w-0">
              {(data.modulos ?? []).map((mod) => (
                <BIModuleCard key={mod.modulo} modulo={mod} />
              ))}
            </div>
          )}
          {(data.alertas ?? []).length > 0 ? (
            <BIAlertList alertas={data.alertas ?? []} title="Alertas operacionais" compact />
          ) : null}
          {data.gerado_em ? (
            <p className="text-xs text-muted-foreground mt-6 text-right">
              Atualizado em {new Date(data.gerado_em).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })}
            </p>
          ) : null}
        </>
      ) : null}
    </BIPageLayout>
  );
}
