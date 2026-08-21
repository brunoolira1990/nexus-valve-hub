import { Bell, Check, ExternalLink, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { NexusButton } from '@/components/nexus';
import { notificacoesService, type Notificacao } from '@/services/api/notificacoes';

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const prioridadeClasses: Record<string, string> = {
  CRITICA: 'bg-destructive/10 text-destructive',
  ALTA: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  NORMAL: 'bg-primary/10 text-primary',
  BAIXA: 'bg-muted text-muted-foreground',
};

export const NotificacoesSino = () => {
  const navigate = useNavigate();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<Notificacao[]>([]);
  const [loading, setLoading] = useState(false);
  const [position, setPosition] = useState({ top: 0, right: 12 });

  const refreshCount = useCallback(async () => {
    try {
      setCount(await notificacoesService.countNaoLidas());
    } catch {
      // O sino não pode bloquear o cabeçalho quando a sessão ou a rede falhar.
    }
  }, []);

  const refreshPreview = useCallback(async () => {
    setLoading(true);
    try {
      const response = await notificacoesService.listPaginated({
        page: 1,
        page_size: 10,
        ordering: '-criado_em',
      });
      setItems(response.results);
      void refreshCount();
    } catch {
      // A central completa continuará mostrando o erro detalhado da API.
    } finally {
      setLoading(false);
    }
  }, [refreshCount]);

  useEffect(() => {
    void refreshCount();
    const intervalId = window.setInterval(() => void refreshCount(), 60_000);
    return () => window.clearInterval(intervalId);
  }, [refreshCount]);

  useEffect(() => {
    if (!open) return;
    void refreshPreview();
    const updatePosition = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPosition({
        top: rect.bottom + 8,
        right: Math.max(12, window.innerWidth - rect.right),
      });
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, refreshPreview]);

  useEffect(() => {
    if (!open) return;
    const handleOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !panelRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const openNotification = async (item: Notificacao) => {
    if (!item.lida) {
      try {
        await notificacoesService.marcarLida(item.id);
      } catch {
        // A navegação continua mesmo se a marcação falhar.
      }
    }
    setItems((previous) => previous.map((current) => current.id === item.id ? { ...current, lida: true } : current));
    setCount((previous) => item.lida ? previous : Math.max(0, previous - 1));
    setOpen(false);
    navigate(item.url_destino || '/notificacoes');
  };

  const openCenter = () => {
    setOpen(false);
    navigate('/notificacoes');
  };

  const panel = open ? createPortal(
    <div
      ref={panelRef}
      className="fixed z-[80] w-[min(24rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      style={{ top: position.top, right: position.right }}
      role="dialog"
      aria-label="Notificações recentes"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-foreground">Notificações</p>
          <p className="text-xs text-muted-foreground">Atualização automática a cada minuto</p>
        </div>
        <button type="button" className="text-xs font-medium text-primary hover:underline" onClick={openCenter}>
          Ver central
        </button>
      </div>
      <div className="max-h-[min(28rem,70vh)] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Carregando notificações...
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Você não tem notificações recentes.
          </div>
        ) : (
          items.map((item) => (
            <button
              type="button"
              key={item.id}
              className={`flex w-full gap-3 border-b border-border px-4 py-3 text-left transition-colors hover:bg-muted/60 ${item.lida ? '' : 'bg-primary/[0.04]'}`}
              onClick={() => void openNotification(item)}
            >
              <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${item.lida ? 'bg-muted' : 'bg-primary'}`} aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                  <span className="truncate text-sm font-medium text-foreground">{item.titulo}</span>
                  <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${prioridadeClasses[item.prioridade] || prioridadeClasses.NORMAL}`}>
                    {item.prioridade_label}
                  </span>
                </span>
                <span className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.mensagem}</span>
                <span className="mt-2 block text-[11px] text-muted-foreground">{formatDateTime(item.criado_em)}</span>
              </span>
            </button>
          ))
        )}
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-border bg-muted/20 px-4 py-2.5">
        <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground" onClick={() => { void notificacoesService.marcarTodasLidas().then(refreshCount); setItems((previous) => previous.map((item) => ({ ...item, lida: true }))); }}>
          <Check className="h-3.5 w-3.5" /> Marcar todas como lidas
        </button>
        <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline" onClick={openCenter}>
          Abrir central <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>,
    document.body,
  ) : null;

  return (
    <>
      <NexusButton
        ref={triggerRef}
        type="button"
        variant="ghost"
        size="icon"
        className="relative shrink-0"
        title={count > 0 ? `${count} notificações não lidas` : 'Notificações'}
        aria-label={count > 0 ? `${count} notificações não lidas` : 'Notificações'}
        aria-expanded={open}
        onClick={() => setOpen((previous) => !previous)}
      >
        <Bell className={`h-4 w-4 ${count > 0 ? 'text-primary' : ''}`} />
        {count > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-destructive px-1 text-center text-[10px] font-bold leading-4 text-destructive-foreground">
            {count > 99 ? '99+' : count}
          </span>
        ) : null}
      </NexusButton>
      {panel}
    </>
  );
};

export default NotificacoesSino;
