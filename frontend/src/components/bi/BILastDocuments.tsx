import { Link } from 'react-router-dom';
import type { BIUltimo } from '@/services/api/dashboard';
import { formatBiMoeda, formatBiNumero } from './biFormat';
import { BIEmptyState } from './BIEmptyState';

function formatUltimoValor(doc: BIUltimo) {
  if (!doc.valor) return '—';
  const t = doc.tipo.toLowerCase();
  if (t.includes('pedido') || t.includes('nfe') || t.includes('proposta')) {
    return formatBiMoeda(doc.valor);
  }
  const n = Number(doc.valor);
  if (!Number.isNaN(n)) return formatBiNumero(n);
  return doc.valor;
}

function formatData(iso: string) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('pt-BR');
  } catch {
    return iso;
  }
}

export function BILastDocuments({
  itens,
  title = 'Últimos registros',
}: {
  itens: BIUltimo[];
  title?: string;
}) {
  return (
    <div className="erp-card p-5 overflow-hidden">
      <h3 className="text-sm font-semibold text-foreground mb-4">{title}</h3>
      {itens.length === 0 ? (
        <BIEmptyState message="Nenhum registro recente." />
      ) : (
        <div className="overflow-x-auto">
          <table className="erp-table text-sm w-full" data-mobile-table-mode="cards">
            <thead>
              <tr>
                <th>Documento</th>
                <th>Detalhe</th>
                <th>Valor</th>
                <th>Status</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((doc, i) => (
                <tr key={`${doc.tipo}-${doc.titulo}-${i}`}>
                  <td>
                    {doc.link ? (
                      <Link to={doc.link} className="text-primary font-medium hover:underline">
                        {doc.titulo}
                      </Link>
                    ) : (
                      doc.titulo
                    )}
                  </td>
                  <td className="text-muted-foreground max-w-[180px] truncate">{doc.subtitulo || '—'}</td>
                  <td className="tabular-nums">{formatUltimoValor(doc)}</td>
                  <td>{doc.status || '—'}</td>
                  <td className="text-muted-foreground whitespace-nowrap">{formatData(doc.data)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
