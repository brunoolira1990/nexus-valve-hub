import { useEffect, useState, type ReactNode, type RefObject } from 'react';

export type MobileTableMode = 'auto' | 'scroll' | 'cards';

/**
 * Converte tabelas semânticas em cartões somente em telas compactas.
 * A conversão exige cabeçalho: sem ele, a tabela permanece com rolagem
 * horizontal para não apresentar valores sem contexto.
 */
export function useMobileTableLabels(
  tableRef: RefObject<HTMLTableElement>,
  mobileMode: MobileTableMode,
  content: ReactNode,
) {
  const [resolvedMobileMode, setResolvedMobileMode] = useState<MobileTableMode>('scroll');

  useEffect(() => {
    const table = tableRef.current;
    const headerRow = table?.tHead?.rows.item((table.tHead?.rows.length ?? 1) - 1);

    if (mobileMode === 'scroll' || !table || !headerRow) {
      setResolvedMobileMode('scroll');
      return;
    }

    const labels = Array.from(headerRow.cells).map(
      (header) => header.textContent?.replace(/\s+/g, ' ').trim() || 'Detalhe',
    );

    Array.from(table.tBodies).forEach((body) => {
      Array.from(body.rows).forEach((row) => {
        Array.from(row.cells).forEach((cell, index) => {
          if (cell.colSpan > 1 || cell.dataset.label) return;
          cell.dataset.label = labels[index] || 'Detalhe';
        });
      });
    });

    setResolvedMobileMode('cards');
  }, [content, mobileMode, tableRef]);

  return resolvedMobileMode;
}
