import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  PopupBlockedError,
  downloadBlobFile,
  ensurePdfBlob,
  visualizarPdfEmNovaAba,
} from '@/lib/downloadBlobFile';

describe('downloadBlobFile', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock'),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('Baixar DANFE: continua usando downloadBlobFile com atributo download', () => {
    const click = vi.fn();
    const anchor = {
      href: '',
      download: '',
      rel: '',
      click,
      remove: vi.fn(),
    } as unknown as HTMLAnchorElement;
    vi.spyOn(document, 'createElement').mockReturnValue(anchor);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => anchor);

    downloadBlobFile(new Blob(['pdf'], { type: 'application/pdf' }), 'danfe.pdf');

    expect(anchor.download).toBe('danfe.pdf');
    expect(click).toHaveBeenCalled();
  });
});

describe('ensurePdfBlob', () => {
  it('normaliza blob sem type para application/pdf', () => {
    const blob = ensurePdfBlob(new Blob(['x'], { type: '' }));
    expect(blob.type).toBe('application/pdf');
  });

  it('rejeita blob vazio', () => {
    expect(() => ensurePdfBlob(new Blob([]))).toThrow('vazio');
  });
});

describe('visualizarPdfEmNovaAba', () => {
  const close = vi.fn();
  const revokeObjectURL = vi.fn();
  let scheduled: Array<{ ms: number; fn: () => void }> = [];
  let openedTab: {
    close: typeof close;
    location: { href: string };
    document: { title: string; body: { textContent: string } };
  };

  beforeEach(() => {
    close.mockClear();
    revokeObjectURL.mockClear();
    scheduled = [];
    openedTab = {
      close,
      location: { href: '' },
      document: { title: '', body: { textContent: '' } },
    };
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:pdf-mock'),
      revokeObjectURL,
    });
    vi.stubGlobal(
      'window',
      {
        open: vi.fn(() => openedTab),
        setTimeout: (fn: () => void, ms?: number) => {
          scheduled.push({ ms: ms ?? 0, fn });
          return scheduled.length;
        },
      } as unknown as Window & typeof globalThis,
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('Visualizar abre window.open de forma síncrona com string vazia', async () => {
    const fetchBlob = vi.fn(async () => new Blob(['%PDF'], { type: 'application/pdf' }));
    const pending = visualizarPdfEmNovaAba(fetchBlob);

    expect(window.open).toHaveBeenCalledWith('', '_blank');
    expect(window.open).toHaveBeenCalledTimes(1);

    await pending;
    expect(fetchBlob).toHaveBeenCalled();
  });

  it('Visualizar atribui blob URL via location.href', async () => {
    await visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' }));

    expect(openedTab.location.href).toBe('blob:pdf-mock');
    expect(close).not.toHaveBeenCalled();
  });

  it('Visualizar não cria elemento com download', async () => {
    const createElement = vi.spyOn(document, 'createElement');
    await visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' }));
    expect(createElement).not.toHaveBeenCalledWith('a');
  });

  it('URL.revokeObjectURL não ocorre imediatamente', async () => {
    await visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' }));

    expect(revokeObjectURL).not.toHaveBeenCalled();
    expect(scheduled).toHaveLength(1);
    expect(scheduled[0].ms).toBe(60_000);

    scheduled[0].fn();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:pdf-mock');
  });

  it('Pop-up bloqueado mostra erro claro', async () => {
    vi.mocked(window.open).mockReturnValueOnce(null);
    await expect(
      visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' })),
    ).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(PopupBlockedError);
      expect((err as Error).message).toContain('bloqueou a nova aba');
      expect((err as Error).message).toContain('pop-ups');
      return true;
    });
  });

  it('fecha aba vazia quando a API falha', async () => {
    await expect(
      visualizarPdfEmNovaAba(async () => {
        throw new Error('falha backend');
      }),
    ).rejects.toThrow('falha backend');
    expect(close).toHaveBeenCalled();
    expect(revokeObjectURL).not.toHaveBeenCalled();
  });
});
