import { useState } from 'react';
import { ChevronDown, ChevronUp, X } from 'lucide-react';

export type TituloFiltrosState = {
  status: string;
  vencimento: string;
  origem_tipo: string;
  tipo_lancamento: string;
  categoria: string;
  centro_custo: string;
  conta_prevista: string;
  origem_fiscal_cancelada: string;
  com_saldo_aberto: string;
  sem_categoria: string;
  sem_conta_prevista: string;
};

const EMPTY: TituloFiltrosState = {
  status: '',
  vencimento: '',
  origem_tipo: '',
  tipo_lancamento: '',
  categoria: '',
  centro_custo: '',
  conta_prevista: '',
  origem_fiscal_cancelada: '',
  com_saldo_aberto: '',
  sem_categoria: '',
  sem_conta_prevista: '',
};

type Props = {
  modo: 'RECEBER' | 'PAGAR';
  filtros: TituloFiltrosState;
  onChange: (next: TituloFiltrosState) => void;
  categorias: { id: number; nome: string }[];
  centros: { id: number; nome: string }[];
  contas: { id: number; nome: string }[];
};

export function tituloFiltrosFromSearchParams(sp: URLSearchParams): TituloFiltrosState {
  const keys = Object.keys(EMPTY) as (keyof TituloFiltrosState)[];
  const out = { ...EMPTY };
  keys.forEach((k) => {
    const v = sp.get(k);
    if (v) out[k] = v;
  });
  return out;
}

export function tituloFiltrosToQuery(f: TituloFiltrosState): Record<string, string> {
  const q: Record<string, string> = {};
  (Object.keys(f) as (keyof TituloFiltrosState)[]).forEach((k) => {
    if (f[k]) q[k] = f[k];
  });
  return q;
}

export function TituloFinanceiroFiltrosPanel({
  modo,
  filtros,
  onChange,
  categorias,
  centros,
  contas,
}: Props) {
  const [aberto, setAberto] = useState(false);
  const patch = (key: keyof TituloFiltrosState, value: string) =>
    onChange({ ...filtros, [key]: value });

  const temFiltro = Object.values(filtros).some(Boolean);

  return (
    <div className="erp-card p-3 mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          className="text-sm font-medium flex items-center gap-1"
          onClick={() => setAberto((v) => !v)}
        >
          Filtros avançados
          {aberto ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {temFiltro ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm text-xs"
            onClick={() => onChange({ ...EMPTY })}
          >
            <X className="h-3 w-3 mr-1" />
            Limpar filtros
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          className="erp-input erp-input-sm min-w-[140px]"
          value={filtros.vencimento}
          onChange={(e) => patch('vencimento', e.target.value)}
        >
          <option value="">Vencimento</option>
          <option value="hoje">Hoje</option>
          <option value="vencidos">Vencidos</option>
          <option value="proximos_7">Próximos 7 dias</option>
          <option value="proximos_30">Próximos 30 dias</option>
          <option value="mes">Este mês</option>
        </select>
        <select
          className="erp-input erp-input-sm min-w-[140px]"
          value={filtros.status}
          onChange={(e) => patch('status', e.target.value)}
        >
          <option value="">Status</option>
          <option value="EM_ABERTO">Em aberto</option>
          <option value="VENCIDO">Vencido</option>
          {modo === 'RECEBER' ? (
            <>
              <option value="PARCIALMENTE_RECEBIDO">Parcialmente recebido</option>
              <option value="RECEBIDO">Recebido</option>
            </>
          ) : (
            <>
              <option value="PARCIALMENTE_PAGO">Parcialmente pago</option>
              <option value="PAGO">Pago</option>
            </>
          )}
          <option value="CANCELADO">Cancelado</option>
        </select>
        <select
          className="erp-input erp-input-sm min-w-[120px]"
          value={filtros.origem_tipo}
          onChange={(e) => patch('origem_tipo', e.target.value)}
        >
          <option value="">Origem</option>
          <option value="MANUAL">Manual</option>
          {modo === 'RECEBER' ? (
            <>
              <option value="NFE_SAIDA">NF-e Saída</option>
              <option value="FATURAMENTO">Faturamento</option>
              <option value="PEDIDO_VENDA">Pedido de Venda</option>
            </>
          ) : (
            <>
              <option value="NFE_ENTRADA">NF-e Entrada</option>
              <option value="PEDIDO_COMPRA">Pedido de Compra</option>
              <option value="SERVICO">Serviço</option>
            </>
          )}
        </select>
      </div>

      {aberto ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-2 border-t border-border/60">
          {modo === 'PAGAR' ? (
            <select
              className="erp-input erp-input-sm"
              value={filtros.tipo_lancamento}
              onChange={(e) => patch('tipo_lancamento', e.target.value)}
            >
              <option value="">Tipo</option>
              <option value="FORNECEDOR">Fornecedor</option>
              <option value="DESPESA_OPERACIONAL">Despesa operacional</option>
              <option value="SERVICO">Serviço</option>
              <option value="TRIBUTO_IMPOSTO">Tributo / Imposto</option>
              <option value="OUTROS">Outros</option>
            </select>
          ) : null}
          <select
            className="erp-input erp-input-sm"
            value={filtros.categoria}
            onChange={(e) => patch('categoria', e.target.value)}
          >
            <option value="">Categoria</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
          <select
            className="erp-input erp-input-sm"
            value={filtros.centro_custo}
            onChange={(e) => patch('centro_custo', e.target.value)}
          >
            <option value="">Centro de custo</option>
            {centros.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
          <select
            className="erp-input erp-input-sm"
            value={filtros.conta_prevista}
            onChange={(e) => patch('conta_prevista', e.target.value)}
          >
            <option value="">Conta / caixa prevista</option>
            {contas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-xs col-span-full sm:col-span-2">
            <input
              type="checkbox"
              checked={filtros.com_saldo_aberto === '1'}
              onChange={(e) => patch('com_saldo_aberto', e.target.checked ? '1' : '')}
            />
            Com saldo em aberto
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={filtros.origem_fiscal_cancelada === '1'}
              onChange={(e) => patch('origem_fiscal_cancelada', e.target.checked ? '1' : '')}
            />
            Origem fiscal cancelada
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={filtros.sem_categoria === '1'}
              onChange={(e) => patch('sem_categoria', e.target.checked ? '1' : '')}
            />
            Sem categoria
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={filtros.sem_conta_prevista === '1'}
              onChange={(e) => patch('sem_conta_prevista', e.target.checked ? '1' : '')}
            />
            Sem conta prevista
          </label>
        </div>
      ) : null}
    </div>
  );
}
