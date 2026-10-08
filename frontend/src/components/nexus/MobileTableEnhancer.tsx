import { useEffect } from 'react';

function hasUsableHeader(table: HTMLTableElement) {
  const headerRow = table.tHead?.rows.item((table.tHead?.rows.length ?? 1) - 1);
  return Boolean(headerRow && headerRow.cells.length);
}

function enhanceTable(table: HTMLTableElement) {
  if (table.dataset.mobileTableMode || table.closest('[data-mobile-table-mode]')) return;

  if (!hasUsableHeader(table)) {
    table.dataset.mobileTableMode = 'scroll';
    return;
  }

  const headerRow = table.tHead?.rows.item((table.tHead?.rows.length ?? 1) - 1);
  const labels = Array.from(headerRow?.cells ?? []).map(
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

  table.dataset.mobileTableMode = 'cards';
}

/**
 * Cobre tabelas HTML locais que ainda não usam DataTable ou Table.
 * Tabelas sem cabeçalho semântico ficam em modo de rolagem horizontal por segurança.
 */
export function MobileTableEnhancer() {
  useEffect(() => {
    let frameId = 0;

    const refresh = () => {
      frameId = 0;
      document.querySelectorAll<HTMLTableElement>('main table').forEach(enhanceTable);
    };

    const scheduleRefresh = () => {
      if (frameId) return;
      frameId = window.requestAnimationFrame(refresh);
    };

    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, { childList: true, subtree: true });
    scheduleRefresh();

    return () => {
      observer.disconnect();
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, []);

  return null;
}
