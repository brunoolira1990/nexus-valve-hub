import { useState } from 'react';
import { ChevronDown, ChevronUp, X } from 'lucide-react';
import type { RelatorioFiltrosState } from '@/lib/relatorioFinanceiro';

type Props = {
  modo: 'RECEBER' | 'PAGAR' | 'FLUXO' | 'CATEGORIAS' | 'CLIENTES' | 'FORNECEDORES';
  filtros: RelatorioFiltrosState;
  onChange: (next: RelatorioFiltrosState) => void;
  categorias: { id: number; nome: string }[];
  centros: { id: number; nome: string }[];
  contas: { id: number; nome: string }[];
  showAgrupamento?: boolean;
};

const EMPTY_FILTROS: RelatorioFiltrosState = {
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
  periodo: '',
  periodo_emissao: '',
  periodo_baixa: '',
  agrupamento: '',
  cliente: '',
  fornecedor: '',
  data_inicio: '',
  data_fim: '',
  emissao_de: '',
  emissao_ate: '',
  incluir_quitados: '',
  incluir_cancelados: '',
  incluir_sem_saldo: '',
};

export function RelatorioFiltrosPanel({
  modo,
  filtros,
  onChange,
  categorias,
  centros,
  contas,
  showAgrupamento,
}: Props) {
  const [maisOpen, setMaisOpen] = useState(false);
  const patch = (key: keyof RelatorioFiltrosState, value: string) =>
    onChange({ ...filtros, [key]: value });
  const toggle = (key: 'incluir_quitados' | 'incluir_cancelados' | 'incluir_sem_saldo') => {
    onChange({ ...filtros, [key]: filtros[key] === '1' ? '' : '1' });
  };

  const temFiltro = Object.values(filtros).some(Boolean);
  const showVencimento = modo !== 'FLUXO' && modo !== 'CATEGORIAS';
  const showStatusCrCp =
    modo === 'RECEBER' || modo === 'PAGAR' || modo === 'CLIENTES' || modo === 'FORNECEDORES';

  const statusOpts =
    modo === 'PAGAR' || modo === 'FORNECEDORES'
      ? [
          { v: 'EM_ABERTO', l: 'Em aberto' },
          { v: 'VENCIDO', l: 'Vencido' },
          { v: 'PARCIALMENTE_PAGO', l: 'Parcialmente pago' },
          { v: 'PAGO', l: 'Pago' },
          { v: 'CANCELADO', l: 'Cancelado' },
        ]
      : [
          { v: 'EM_ABERTO', l: 'Em aberto' },
          { v: 'VENCIDO', l: 'Vencido' },
          { v: 'PARCIALMENTE_RECEBIDO', l: 'Parcialmente recebido' },
          { v: 'RECEBIDO', l: 'Recebido' },
          { v: 'CANCELADO', l: 'Cancelado' },
        ];

  const origemOpts =
    modo === 'PAGAR' || modo === 'FORNECEDORES'
      ? [
          { v: 'MANUAL', l: 'Manual' },
          { v: 'NFE_ENTRADA', l: 'NF-e Entrada' },
          { v: 'PEDIDO_COMPRA', l: 'Pedido de Compra' },
          { v: 'SERVICO', l: 'Serviço' },
          { v: 'APURACAO_FISCAL', l: 'Apuração fiscal' },
        ]
      : [
          { v: 'MANUAL', l: 'Manual' },
          { v: 'NFE_SAIDA', l: 'NF-e Saída' },
          { v: 'FATURAMENTO', l: 'Faturamento' },
          { v: 'PEDIDO_VENDA', l: 'Pedido de Venda' },
        ];

  const agrupamentoOpts =
    modo === 'RECEBER'
      ? [
          { v: '', l: 'Sem agrupamento' },
          { v: 'cliente', l: 'Por cliente' },
          { v: 'categoria', l: 'Por categoria' },
          { v: 'origem', l: 'Por origem' },
          { v: 'vencimento_mes', l: 'Por vencimento (mês)' },
        ]
      : modo === 'PAGAR'
        ? [
            { v: '', l: 'Sem agrupamento' },
            { v: 'fornecedor', l: 'Por fornecedor' },
            { v: 'categoria', l: 'Por categoria' },
            { v: 'tipo', l: 'Por tipo' },
            { v: 'origem', l: 'Por origem' },
            { v: 'vencimento_mes', l: 'Por vencimento (mês)' },
          ]
        : [];

  return (
    <div className="erp-card p-3 mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold">Filtros</span>
        {temFiltro ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm text-xs"
            onClick={() => onChange({ ...EMPTY_FILTROS })}
          >
            <X className="h-3 w-3 mr-1" />
            Limpar filtros
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        {modo === 'FLUXO' || modo === 'CATEGORIAS' ? (
          <select
            className="erp-input erp-input-sm min-w-[160px]"
            value={filtros.periodo || (modo === 'FLUXO' ? 'proximos_30' : 'mes')}
            onChange={(e) => patch('periodo', e.target.value)}
          >
            <option value="hoje">Hoje</option>
            <option value="proximos_7">Próximos 7 dias</option>
            <option value="proximos_15">Próximos 15 dias</option>
            <option value="proximos_30">Próximos 30 dias</option>
            <option value="mes">Este mês</option>
            <option value="proximo_mes">Próximo mês</option>
          </select>
        ) : (
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
        )}

        {showStatusCrCp ? (
          <select
            className="erp-input erp-input-sm min-w-[140px]"
            value={filtros.status}
            onChange={(e) => patch('status', e.target.value)}
          >
            <option value="">Status</option>
            {statusOpts.map((o) => (
              <option key={o.v} value={o.v}>
                {o.l}
              </option>
            ))}
          </select>
        ) : null}

        {modo !== 'CLIENTES' && modo !== 'FORNECEDORES' ? (
          <select
            className="erp-input erp-input-sm min-w-[140px]"
            value={filtros.origem_tipo}
            onChange={(e) => patch('origem_tipo', e.target.value)}
          >
            <option value="">Origem</option>
            {origemOpts.map((o) => (
              <option key={o.v} value={o.v}>
                {o.l}
              </option>
            ))}
          </select>
        ) : null}

        <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={filtros.incluir_quitados === '1'}
            onChange={() => toggle('incluir_quitados')}
          />
          Incluir quitados
        </label>
        <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={filtros.incluir_cancelados === '1'}
            onChange={() => toggle('incluir_cancelados')}
          />
          Incluir cancelados
        </label>
      </div>

      <div>
        <button
          type="button"
          className="text-sm text-muted-foreground flex items-center gap-1"
          onClick={() => setMaisOpen((v) => !v)}
        >
          Mais filtros
          {maisOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {maisOpen ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {(modo === 'CLIENTES' || modo === 'RECEBER') && (
              <input
                className="erp-input erp-input-sm min-w-[140px]"
                placeholder="ID do cliente"
                value={filtros.cliente}
                onChange={(e) => patch('cliente', e.target.value)}
              />
            )}
            {(modo === 'FORNECEDORES' || modo === 'PAGAR') && (
              <input
                className="erp-input erp-input-sm min-w-[140px]"
                placeholder="ID do fornecedor"
                value={filtros.fornecedor}
                onChange={(e) => patch('fornecedor', e.target.value)}
              />
            )}
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
                <option key={c.id} value={String(c.id)}>
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
                <option key={c.id} value={String(c.id)}>
                  {c.nome}
                </option>
              ))}
            </select>
            <select
              className="erp-input erp-input-sm"
              value={filtros.conta_prevista}
              onChange={(e) => patch('conta_prevista', e.target.value)}
            >
              <option value="">Conta/Caixa prevista</option>
              {contas.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.nome}
                </option>
              ))}
            </select>
            {showVencimento ? (
              <select
                className="erp-input erp-input-sm"
                value={filtros.periodo_emissao}
                onChange={(e) => patch('periodo_emissao', e.target.value)}
              >
                <option value="">Emissão</option>
                <option value="mes">Este mês</option>
                <option value="hoje">Hoje</option>
                <option value="proximos_30">Últimos 30 dias</option>
              </select>
            ) : null}
            {modo === 'CATEGORIAS' ? (
              <select
                className="erp-input erp-input-sm"
                value={filtros.periodo_baixa || filtros.periodo}
                onChange={(e) => patch('periodo_baixa', e.target.value)}
              >
                <option value="mes">Período de baixa — este mês</option>
                <option value="hoje">Hoje</option>
                <option value="proximos_30">Últimos 30 dias</option>
              </select>
            ) : null}
            {showAgrupamento && agrupamentoOpts.length ? (
              <select
                className="erp-input erp-input-sm"
                value={filtros.agrupamento}
                onChange={(e) => patch('agrupamento', e.target.value)}
              >
                {agrupamentoOpts.map((o) => (
                  <option key={o.v} value={o.v}>
                    {o.l}
                  </option>
                ))}
              </select>
            ) : null}
            <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={filtros.origem_fiscal_cancelada === '1'}
                onChange={() =>
                  patch(
                    'origem_fiscal_cancelada',
                    filtros.origem_fiscal_cancelada === '1' ? '' : '1',
                  )
                }
              />
              Origem fiscal cancelada
            </label>
            {(modo === 'CLIENTES' || modo === 'FORNECEDORES') && (
              <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={filtros.incluir_sem_saldo === '1'}
                  onChange={() => toggle('incluir_sem_saldo')}
                />
                Incluir registros sem saldo
              </label>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
