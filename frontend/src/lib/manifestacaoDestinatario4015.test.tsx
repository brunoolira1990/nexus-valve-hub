/** ERP 4.0.15 — Manifestação Destinatário (redirect legado). */
import { describe, expect, it, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ManifestacaoDestinatario from '@/pages/ManifestacaoDestinatario';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

describe('ManifestacaoDestinatario', () => {
  afterEach(() => cleanup());

  it('redireciona rota legada para Inbox Fiscal (/central-dfe)', () => {
    render(
      <MemoryRouter initialEntries={['/manifestacao-destinatario']} future={routerFuture}>
        <Routes>
          <Route path="/manifestacao-destinatario" element={<ManifestacaoDestinatario />} />
          <Route path="/central-dfe" element={<div data-testid="inbox-fiscal">Inbox Fiscal</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('inbox-fiscal')).toBeInTheDocument();
    expect(screen.getByText('Inbox Fiscal')).toBeInTheDocument();
  });
});
