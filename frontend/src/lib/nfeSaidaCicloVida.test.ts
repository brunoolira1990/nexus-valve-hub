import { describe, expect, it } from 'vitest';
import { nfePodeDescartarRascunho } from './nfeSaidaUi';

describe('nfePodeDescartarRascunho', () => {
  it('permite rascunho sem protocolo', () => {
    expect(nfePodeDescartarRascunho({ status: 'RASCUNHO' }).pode).toBe(true);
  });

  it('bloqueia autorizada homologação', () => {
    const r = nfePodeDescartarRascunho({
      status: 'AUTORIZADA_HOMOLOGACAO',
      status_emissao_sefaz: 'AUTORIZADA_HOMOLOGACAO',
    });
    expect(r.pode).toBe(false);
  });

  it('bloqueia com protocolo', () => {
    expect(nfePodeDescartarRascunho({ status: 'RASCUNHO', protocolo_autorizacao: '123' }).pode).toBe(false);
  });
});
