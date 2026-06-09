import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { usePaginatedList } from '@/hooks/usePaginatedList';

describe('usePaginatedList', () => {
  it('carrega página e expõe total', async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      count: 40,
      page: 1,
      page_size: 20,
      total_pages: 2,
      next: null,
      previous: null,
      results: [{ id: 1 }],
    });

    const { result } = renderHook(() => usePaginatedList({ fetchPage, debounceMs: 0 }));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.count).toBe(40);
    expect(result.current.items).toHaveLength(1);
    expect(fetchPage).toHaveBeenCalled();
  });
});
