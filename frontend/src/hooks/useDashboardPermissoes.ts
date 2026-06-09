import { useEffect, useState } from 'react';
import { dashboardService, type DashboardPermissoes } from '@/services/api/dashboard';
import {
  EMPTY_DASHBOARD_PERMISSOES,
  clearDashboardPermissoesCache,
  getDashboardPermissoesCached,
  getDashboardPermissoesInflight,
  setDashboardPermissoesCached,
  setDashboardPermissoesInflight,
} from '@/services/api/dashboardPermissoesCache';
import {
  SESSION_EXPIRED_MESSAGE,
  apiErrorMessage,
  isApiUnauthorized,
} from '@/services/api/config';

export { clearDashboardPermissoesCache };

async function fetchPermissoes(): Promise<DashboardPermissoes> {
  const cached = getDashboardPermissoesCached();
  if (cached) return cached;

  const inflight = getDashboardPermissoesInflight();
  if (inflight) return inflight;

  const promise = dashboardService
    .getPermissoes()
    .then((p) => {
      setDashboardPermissoesCached(p);
      setDashboardPermissoesInflight(null);
      return p;
    })
    .catch((err) => {
      setDashboardPermissoesInflight(null);
      throw err;
    });

  setDashboardPermissoesInflight(promise);
  return promise;
}

export function useDashboardPermissoes() {
  const [permissoes, setPermissoes] = useState<DashboardPermissoes | null>(
    getDashboardPermissoesCached(),
  );
  const [loading, setLoading] = useState(!getDashboardPermissoesCached());
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchPermissoes()
      .then((p) => {
        if (cancelled) return;
        setPermissoes(p);
        setError(null);
        setUnauthorized(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setPermissoes(EMPTY_DASHBOARD_PERMISSOES);
        if (isApiUnauthorized(err)) {
          setUnauthorized(true);
          setError(SESSION_EXPIRED_MESSAGE);
        } else {
          setUnauthorized(false);
          setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar permissões do dashboard.' }));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { permissoes: permissoes ?? EMPTY_DASHBOARD_PERMISSOES, loading, error, unauthorized };
}
