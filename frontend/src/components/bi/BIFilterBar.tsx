import { useEffect, useState } from 'react';
import { Filter } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { empresasService } from '@/services/api/empresas';
import type { Empresa } from '@/types';
import type { DashboardBIFilters } from '@/hooks/useDashboardBI';

const PERIODO_OPCOES = [
  { value: 'hoje', label: 'Hoje' },
  { value: 'ultimos_7_dias', label: 'Últimos 7 dias' },
  { value: 'ultimos_30_dias', label: 'Últimos 30 dias' },
  { value: 'mes_atual', label: 'Mês atual' },
  { value: 'mes_anterior', label: 'Mês anterior' },
  { value: 'ano_atual', label: 'Ano atual' },
] as const;

type BIFilterBarProps = {
  filters: DashboardBIFilters;
  onApply: (filters: DashboardBIFilters) => void;
  onClear: () => void;
  showEmpresa?: boolean;
};

export function BIFilterBar({ filters, onApply, onClear, showEmpresa = true }: BIFilterBarProps) {
  const [draft, setDraft] = useState<DashboardBIFilters>(filters);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);

  useEffect(() => {
    setDraft(filters);
  }, [filters]);

  useEffect(() => {
    if (!showEmpresa) return;
    void empresasService.getAll({ limit: 100 }).then(setEmpresas).catch(() => setEmpresas([]));
  }, [showEmpresa]);

  return (
    <div className="erp-card p-4 flex flex-col sm:flex-row flex-wrap items-end gap-3 min-w-[280px]">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground w-full sm:w-auto">
        <Filter className="h-3.5 w-3.5" />
        Filtros
      </div>
      <div className="flex-1 min-w-[140px]">
        <label className="text-xs text-muted-foreground mb-1 block">Período</label>
        <Select
          value={draft.periodo}
          onValueChange={(v) => setDraft((f) => ({ ...f, periodo: v }))}
        >
          <SelectTrigger className="h-9">
            <SelectValue placeholder="Período" />
          </SelectTrigger>
          <SelectContent>
            {PERIODO_OPCOES.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {showEmpresa ? (
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-muted-foreground mb-1 block">Empresa</label>
          <Select
            value={draft.empresa_id || '__all__'}
            onValueChange={(v) =>
              setDraft((f) => ({ ...f, empresa_id: v === '__all__' ? '' : v }))
            }
          >
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Todas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Todas as empresas</SelectItem>
              {empresas.map((e) => (
                <SelectItem key={e.id} value={String(e.id)}>
                  {e.razao_social || e.nome_fantasia || `Empresa #${e.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      <div className="flex gap-2 w-full sm:w-auto">
        <button type="button" className="erp-btn-primary erp-btn-sm flex-1 sm:flex-none" onClick={() => onApply(draft)}>
          Aplicar
        </button>
        <button type="button" className="erp-btn-outline erp-btn-sm flex-1 sm:flex-none" onClick={onClear}>
          Limpar
        </button>
      </div>
    </div>
  );
}
