import { useCallback, useEffect, useState } from 'react';
import { appContextoService, type AppContexto } from '@/services/api/appContexto';
import { contextoUsuarioNomePareceStale } from '@/lib/usuarioExibicao';

const EMPTY: AppContexto = {
  empresa: null,
  usuario: {
    id: 0,
    nome: '',
    nome_exibicao: '',
    email: '',
    username: '',
    perfil: '',
    perfil_label: '',
    is_admin: false,
  },
  colaborador: null,
  ambiente: 'homologacao',
  ambiente_label: 'Homologação',
};

let cache: AppContexto | null = null;
let inflight: Promise<AppContexto> | null = null;

function cacheValido(data: AppContexto | null): data is AppContexto {
  if (!data) return false;
  return !contextoUsuarioNomePareceStale(data.usuario);
}

const CACHE_INVALIDATED_EVENT = 'nexus:app-contexto-invalidated';

function dispatchCacheInvalidated() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(CACHE_INVALIDATED_EVENT));
  }
}

async function fetchContexto(force = false): Promise<AppContexto> {
  if (!force && cache && cacheValido(cache)) return cache;
  if (!force && inflight) return inflight;
  inflight = appContextoService
    .getContexto()
    .then((data) => {
      cache = data;
      inflight = null;
      return data;
    })
    .catch((err) => {
      inflight = null;
      throw err;
    });
  return inflight;
}

export function clearAppContextoCache() {
  cache = null;
  inflight = null;
  dispatchCacheInvalidated();
}

export function setAppContextoCache(data: AppContexto) {
  cache = data;
}

export function useAppContexto() {
  const [ctx, setCtx] = useState<AppContexto | null>(cacheValido(cache) ? cache : null);
  const [loading, setLoading] = useState(!cacheValido(cache));

  const refresh = useCallback(async () => {
    const data = await fetchContexto(true);
    setCtx(data);
    return data;
  }, []);

  useEffect(() => {
    let active = true;
    const force = cacheValido(cache) ? false : true;
    void fetchContexto(force)
      .then((data) => {
        if (active) setCtx(data);
      })
      .catch(() => {
        if (active) setCtx(EMPTY);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    const onInvalidate = () => {
      setLoading(true);
      void fetchContexto(true)
        .then((data) => {
          if (active) setCtx(data);
        })
        .catch(() => {
          if (active) setCtx(EMPTY);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    };
    window.addEventListener(CACHE_INVALIDATED_EVENT, onInvalidate);

    return () => {
      active = false;
      window.removeEventListener(CACHE_INVALIDATED_EVENT, onInvalidate);
    };
  }, []);

  return { contexto: ctx ?? EMPTY, loading, refresh };
}
