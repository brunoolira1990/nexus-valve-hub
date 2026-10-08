import { useEffect, useState } from 'react';
import { Clock3 } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { ErrorState } from '@/components/list/ListStates';
import { crmService, type CrmHistoricoLead } from '@/services/api/crm';
import { apiErrorMessage } from '@/services/api/config';

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const CRMLeadHistoricoModal = ({
  leadId,
  leadName,
  isOpen,
  onClose,
}: {
  leadId: number | null;
  leadName?: string;
  isOpen: boolean;
  onClose: () => void;
}) => {
  const [items, setItems] = useState<CrmHistoricoLead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !leadId) return undefined;
    let active = true;
    setLoading(true);
    setError(null);
    crmService.historicoLeads
      .listPaginated({ lead_id: leadId, limit: 100 })
      .then((response) => {
        if (active) setItems(response.results || []);
      })
      .catch((err) => {
        if (active) setError(apiErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isOpen, leadId]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Histórico${leadName ? ` — ${leadName}` : ''}`} size="lg">
      {loading ? <p className="py-6 text-center text-sm text-muted-foreground">Carregando histórico...</p> : null}
      {error ? <ErrorState onRetry={() => undefined} /> : null}
      {!loading && !error && items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
          <Clock3 className="h-8 w-8 opacity-50" />
          <p>Nenhum evento registrado para este Lead.</p>
        </div>
      ) : null}
      {!loading && !error && items.length > 0 ? (
        <ol className="relative space-y-5 border-l border-border pl-5">
          {items.map((item) => (
            <li key={item.id} className="relative">
              <span className="absolute -left-[1.58rem] top-1 h-3 w-3 rounded-full border-2 border-background bg-primary" />
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                <div>
                  <p className="font-medium">{item.titulo}</p>
                  <p className="text-xs text-muted-foreground">{item.evento.replaceAll('_', ' ')}</p>
                </div>
                <time className="shrink-0 text-xs text-muted-foreground">{formatDateTime(item.criado_em)}</time>
              </div>
              {item.descricao ? <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{item.descricao}</p> : null}
              {item.realizado_por_nome ? <p className="mt-1 text-xs text-muted-foreground">Por {item.realizado_por_nome}</p> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </Modal>
  );
};

export default CRMLeadHistoricoModal;
