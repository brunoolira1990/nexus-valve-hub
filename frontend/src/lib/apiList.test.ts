import { describe, expect, it } from 'vitest';
import { formatPageRange, isPaginatedResponse, unwrapListResults } from '@/lib/apiList';

describe('apiList', () => {
  it('identifica resposta paginada', () => {
    expect(isPaginatedResponse({ count: 1, results: [] })).toBe(true);
    expect(isPaginatedResponse([])).toBe(false);
  });

  it('formata intervalo de paginação', () => {
    expect(formatPageRange(1, 20, 156)).toBe('Exibindo 1–20 de 156');
    expect(formatPageRange(1, 20, 0)).toBe('Exibindo 0 de 0');
  });

  it('unwrap aceita array ou paginado', () => {
    expect(unwrapListResults([{ id: 1 }])).toEqual([{ id: 1 }]);
    expect(unwrapListResults({ count: 1, results: [{ id: 2 }] } as never)).toEqual([{ id: 2 }]);
  });
});
