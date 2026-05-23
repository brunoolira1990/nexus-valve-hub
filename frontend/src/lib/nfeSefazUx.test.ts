import { describe, expect, it } from 'vitest';
import {
  cStatExibicao,
  consultaFalhou,
  consultaOk,
  erroHistoricoResumo,
  motivoExibicao,
  resultadoHistoricoLabel,
  tituloUltimoRetorno,
} from '@/lib/nfeSefazUx';

describe('nfeSefazUx', () => {
  it('último retorno com ok=false mostra título de falha', () => {
    expect(tituloUltimoRetorno({ ok: false, motivo: 'Erro parse' })).toBe('Consulta não concluída');
  });

  it('cStat vazio em falha não mostra só traço no motivo', () => {
    expect(motivoExibicao({ ok: false, c_stat: '', erro_tecnico: 'sem cStat' })).toBe('sem cStat');
    expect(cStatExibicao({ ok: false, c_stat: '' })).toBe('');
  });

  it('falha sem campos usa mensagem padrão', () => {
    expect(motivoExibicao({ ok: false })).toBe('Falha sem retorno SEFAZ');
  });

  it('consulta ok com cStat 107', () => {
    expect(consultaOk({ ok: true, cstat: '107' })).toBe(true);
    expect(cStatExibicao({ cstat: '107' })).toBe('107');
    expect(resultadoHistoricoLabel({ ok: true })).toBe('OK');
  });

  it('histórico falha com tipo_erro e resumo', () => {
    expect(consultaFalhou({ ok: false, tipo_erro: 'PARSE_ERROR' })).toBe(true);
    expect(resultadoHistoricoLabel({ ok: false, tipo_erro: 'PARSE_ERROR' })).toBe('PARSE_ERROR');
    expect(erroHistoricoResumo({ ok: false, erro_tecnico: 'x'.repeat(80) }).length).toBeLessThanOrEqual(60);
  });

  it('certificado válido — motivo da SEFAZ', () => {
    expect(motivoExibicao({ ok: true, motivo: 'Servico em Operacao' })).toBe('Servico em Operacao');
  });
});
