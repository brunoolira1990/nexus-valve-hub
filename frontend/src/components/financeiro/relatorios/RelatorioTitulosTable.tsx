import { Eye, Wallet } from 'lucide-react';
import { NexusButton } from '@/components/nexus';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/money';
import { labelTipoLancamentoPagar } from '@/lib/financeiroUi';
import type { RelatorioLinhaTitulo } from '@/services/api/financeiro';

function formatVencimentoLinha(ln: RelatorioLinhaTitulo): string {
  if (ln.vencimento_ausente) return ln.vencimento_ausente;
  const raw = ln.vencimento_exibicao || ln.vencimento;
  const fmt = formatDateBr(raw);
  if (ln.vencimento_label && fmt) {
    const m = ln.vencimento_label.match(/^Próx\.:\s*(\d{4}-\d{2}-\d{2})/);
    if (m) return formatDateBr(m[1]);
  }
  return fmt || '—';
}

type Props = {
  linhas: RelatorioLinhaTitulo[];
  modo: 'RECEBER' | 'PAGAR';
  onAbrir: (id: number) => void;
  onBaixar?: (linha: RelatorioLinhaTitulo) => void;
};

export function RelatorioTitulosTable({ linhas, modo, onAbrir, onBaixar }: Props) {
  if (!linhas.length) return null;
  return (
    <div className="erp-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-3 font-medium">Vencimento</th>
            <th className="p-3 font-medium">{modo === 'RECEBER' ? 'Cliente' : 'Fornecedor / descrição'}</th>
            {modo === 'PAGAR' ? <th className="p-3 font-medium">Tipo</th> : null}
            <th className="p-3 font-medium">Documento</th>
            <th className="p-3 font-medium">Origem</th>
            <th className="p-3 font-medium text-right">Original</th>
            <th className="p-3 font-medium text-right">{modo === 'RECEBER' ? 'Recebido' : 'Pago'}</th>
            <th className="p-3 font-medium text-right">Saldo</th>
            <th className="p-3 font-medium">Status</th>
            <th className="p-3 font-medium">Categoria</th>
            <th className="p-3 font-medium w-[120px]">Ações</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((ln) => (
            <tr key={ln.id} className="border-b border-border/50 hover:bg-muted/30">
              <td className="p-3 whitespace-nowrap">{formatVencimentoLinha(ln)}</td>
              <td className="p-3">
                {modo === 'RECEBER'
                  ? ln.cliente_nome || '—'
                  : ln.fornecedor_nome || ln.descricao || '—'}
              </td>
              {modo === 'PAGAR' ? (
                <td className="p-3 text-xs">
                  {labelTipoLancamentoPagar(ln.tipo_lancamento, ln.tipo_lancamento_label)}
                </td>
              ) : null}
              <td className="p-3">{ln.documento}</td>
              <td className="p-3">
                <span className="line-clamp-2">{ln.origem}</span>
                {ln.origem_fiscal_cancelada ? (
                  <span className="text-xs text-amber-700 dark:text-amber-400 block mt-0.5">
                    Origem cancelada
                  </span>
                ) : null}
              </td>
              <td className="p-3 text-right tabular-nums">{formatMoneyBRL(ln.valor_original)}</td>
              <td className="p-3 text-right tabular-nums">{formatMoneyBRL(ln.valor_baixado)}</td>
              <td className="p-3 text-right tabular-nums font-medium">{formatMoneyBRL(ln.saldo)}</td>
              <td className="p-3">
                <StatusBadge status={ln.status_label || ln.status} />
              </td>
              <td className="p-3 text-xs text-muted-foreground">
                {ln.categoria_nome || '—'}
                {ln.centro_custo_nome ? (
                  <span className="block">{ln.centro_custo_nome}</span>
                ) : null}
              </td>
              <td className="p-3">
                <div className="flex flex-wrap gap-1">
                  <NexusButton variant="ghost" size="sm" onClick={() => onAbrir(ln.id)} title="Abrir título">
                    <Eye className="h-4 w-4" />
                  </NexusButton>
                  {ln.pode_baixar && onBaixar ? (
                    <NexusButton variant="ghost" size="sm" onClick={() => onBaixar(ln)} title="Baixar">
                      <Wallet className="h-4 w-4" />
                    </NexusButton>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
