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

/**
 * Toolbar de filtros no padrão Odoo: uma linha de 36px, fundo transparente e
 * alinhada à direita, logo acima da barra de abas. Os `<label>` empilhados da
 * versão antiga sumiram junto com o card — o nome de cada campo passa a vir de
 * `aria-label`, que é o que leitores de tela leem num controle de toolbar.
 */
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
    <div className="flex flex-wrap items-center justify-end gap-2 sm:h-10 sm:flex-nowrap">
      <span className="mr-auto flex items-center gap-1.5 text-xs font-medium text-muted-foreground sm:mr-0">
        <Filter className="h-3.5 w-3.5" aria-hidden />
        Filtrar
      </span>
      <Select value={draft.periodo} onValueChange={(v) => setDraft((f) => ({ ...f, periodo: v }))}>
        <SelectTrigger
          aria-label="Período"
          className="h-9 w-auto min-w-[9.5rem] text-sm"
        >
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
      {showEmpresa ? (
        <Select
          value={draft.empresa_id || '__all__'}
          onValueChange={(v) => setDraft((f) => ({ ...f, empresa_id: v === '__all__' ? '' : v }))}
        >
          <SelectTrigger
            aria-label="Empresa"
            className="h-9 w-auto min-w-[12rem] text-sm"
          >
            <SelectValue placeholder="Todas as empresas" />
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
      ) : null}
      <button
        type="button"
        onClick={() => onApply(draft)}
        className="h-9 shrink-0 rounded-md bg-nexus-blue px-3 text-sm font-medium text-white transition-colors hover:bg-nexus-blue-strong"
      >
        Aplicar
      </button>
      <button
        type="button"
        onClick={onClear}
        className="h-9 shrink-0 rounded-md px-3 text-sm text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
      >
        Limpar
      </button>
    </div>
  );
}
