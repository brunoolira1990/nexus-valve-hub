import { describe, expect, it } from 'vitest';
import {
  MODALIDADE_FRETE_OPCOES,
  alertasTransporteLocal,
  diagnosticoReformaExibicao,
  labelModalidadeFrete,
  labelTransportadoraSelecionada,
  transportadoraStub,
} from './nfeSaidaConferenciaUx';

describe('nfeSaidaConferenciaUx', () => {
  it('labelTransportadoraSelecionada', () => {
    const t = transportadoraStub(1, 'Transp XYZ', '12345678000199');
    expect(labelTransportadoraSelecionada(t)).toMatch(/TRANSP XYZ/);
    expect(labelTransportadoraSelecionada(t)).toMatch(/12\.345\.678/);
  });

  it('labelModalidadeFrete', () => {
    expect(labelModalidadeFrete('9')).toContain('Sem ocorrência');
    expect(MODALIDADE_FRETE_OPCOES.length).toBeGreaterThanOrEqual(6);
  });

  it('alertasTransporteLocal modalidade 9 limpa', () => {
    const a = alertasTransporteLocal({ modalidade_frete: '9', transportadora_id: null });
    expect(a.some((m) => m.includes('Sem ocorrência'))).toBe(true);
  });

  it('alertasTransporteLocal modalidade 9 com transportadora', () => {
    const a = alertasTransporteLocal({
      modalidade_frete: '9',
      transportadora_id: 1,
      quantidade_volumes: 1,
    });
    expect(a.some((m) => m.includes('Modalidade 9'))).toBe(true);
  });

  it('alertasTransporteLocal modalidade 9 com volume', () => {
    const a = alertasTransporteLocal({
      modalidade_frete: '9',
      transportadora_id: null,
      quantidade_volumes: 1,
    });
    expect(a.some((m) => m.includes('Modalidade 9'))).toBe(true);
  });

  it('alertasTransporteLocal placa sem UF', () => {
    const a = alertasTransporteLocal({
      modalidade_frete: '0',
      transportadora_id: 1,
      placa_veiculo: 'ABC1D23',
    });
    expect(a.some((m) => m.includes('UF do veículo'))).toBe(true);
  });

  it('alertasTransporteLocal exige transportadora', () => {
    const a = alertasTransporteLocal({ modalidade_frete: '0', transportadora_id: null });
    expect(a.some((m) => m.toLowerCase().includes('transportadora'))).toBe(true);
  });

  it('diagnosticoReformaExibicao', () => {
    expect(diagnosticoReformaExibicao('CST ausente', 'PENDENTE')).toBe('CST ausente');
    expect(diagnosticoReformaExibicao('', 'NAO_CONFIGURADA')).toContain('não configurada');
  });
});
