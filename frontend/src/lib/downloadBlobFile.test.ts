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

  it('cria link com atributo download', () => {
    const click = vi.fn();
    const anchor = { href: '', download: '', rel: '', click, remove: vi.fn() } as unknown as HTMLAnchorElement;
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
  const replace = vi.fn();

  beforeEach(() => {
    close.mockClear();
    replace.mockClear();
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:pdf-mock'),
      revokeObjectURL: vi.fn(),
    });
    vi.stubGlobal('window', {
      open: vi.fn(() => ({ close, location: { replace } })),
      setTimeout: (fn: () => void) => {
        fn();
        return 0;
      },
    } as unknown as Window & typeof globalThis);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('abre about:blank e carrega blob pdf na aba', async () => {
    await visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' }));

    expect(window.open).toHaveBeenCalledWith('about:blank', '_blank', 'noopener,noreferrer');
    expect(replace).toHaveBeenCalledWith('blob:pdf-mock');
    expect(close).not.toHaveBeenCalled();
  });

  it('fecha aba e propaga erro quando fetch falha', async () => {
    await expect(
      visualizarPdfEmNovaAba(async () => {
        throw new Error('falha backend');
      }),
    ).rejects.toThrow('falha backend');
    expect(close).toHaveBeenCalled();
  });

  it('lança PopupBlockedError quando pop-up é bloqueado', async () => {
  vi.mocked(window.open).mockReturnValueOnce(null);
    await expect(
      visualizarPdfEmNovaAba(async () => new Blob(['%PDF'], { type: 'application/pdf' })),
    ).rejects.toBeInstanceOf(PopupBlockedError);
  });
});
