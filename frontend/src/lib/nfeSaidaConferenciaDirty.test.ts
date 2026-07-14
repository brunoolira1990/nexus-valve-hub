import { describe, expect, it } from 'vitest';

import type { NFeSaidaConferenciaPayload } from '@/services/api/fiscal';
import {
  conferenciaTemAlteracoesNaoSalvas,
  montarPayloadSalvarConferencia,
  snapshotConferenciaDirty,
  transporteTemDadosPreenchidos,
} from './nfeSaidaConferenciaDirty';

const baseConf = (): NFeSaidaConferenciaPayload =>
  ({
    nfe: { pedido_cliente_numero: '', pedido_cliente_observacao: '' },
    observacoes: {
      observacoes_nfe: '',
      informacoes_adicionais: '',
      informacoes_fisco: '',
      observacoes_internas: '',
    },
    transporte: {
      modalidade_frete: '9',
      transportadora_id: null,
      valor_frete: 0,
      quantidade_volumes: 0,
      especie_volumes: '',
      marca_volumes: '',
      numeracao_volumes: '',
      peso_bruto: 0,
      peso_liquido: 0,
      placa_veiculo: '',
      uf_veiculo: '',
    },
    itens: [],
  }) as NFeSaidaConferenciaPayload;

describe('nfeSaidaConferenciaDirty', () => {
  it('detecta alteração de modalidade do frete', () => {
    const baseline = snapshotConferenciaDirty(baseConf());
    const editado = {
      ...baseConf(),
      transporte: { ...baseConf().transporte, modalidade_frete: '0' },
    };
    expect(conferenciaTemAlteracoesNaoSalvas(editado, baseline)).toBe(true);
  });

  it('detecta alteração de transportadora', () => {
    const baseline = snapshotConferenciaDirty(baseConf());
    const editado = {
      ...baseConf(),
      transporte: { ...baseConf().transporte, transportadora_id: 42 },
    };
    expect(conferenciaTemAlteracoesNaoSalvas(editado, baseline)).toBe(true);
  });

  it('detecta alteração de volumes e peso', () => {
    const baseline = snapshotConferenciaDirty(baseConf());
    const editado = {
      ...baseConf(),
      transporte: {
        ...baseConf().transporte,
        quantidade_volumes: 1,
        peso_bruto: 500,
        peso_liquido: 500,
      },
    };
    expect(conferenciaTemAlteracoesNaoSalvas(editado, baseline)).toBe(true);
  });

  it('transporteTemDadosPreenchidos reconhece transportadora e volumes', () => {
    expect(transporteTemDadosPreenchidos({ transportadora_id: 1 })).toBe(true);
    expect(transporteTemDadosPreenchidos({ quantidade_volumes: 1 })).toBe(true);
    expect(transporteTemDadosPreenchidos({ modalidade_frete: '9' })).toBe(false);
  });

  it('montarPayloadSalvarConferencia inclui transporte completo', () => {
    const conf = {
      ...baseConf(),
      transporte: {
        modalidade_frete: '0',
        transportadora_id: 5,
        valor_frete: 99,
        quantidade_volumes: 2,
        peso_bruto: 100,
        peso_liquido: 90,
        especie_volumes: 'CAIXA',
        marca_volumes: 'M1',
        numeracao_volumes: '1-2',
        placa_veiculo: 'ABC1D23',
        uf_veiculo: 'SP',
      },
    };
    const payload = montarPayloadSalvarConferencia(conf, false);
    expect(payload.modalidade_frete).toBe('0');
    expect(payload.transportadora_id).toBe(5);
    expect(payload.quantidade_volumes).toBe(2);
    expect(payload.peso_bruto).toBe(100);
    expect(payload.placa_veiculo).toBe('ABC1D23');
    expect(payload.numeracao_volumes).toBe('1-2');
  });

  it('salvar preserva numeração manual compacta do PV sem recalcular', () => {
    const conf = {
      ...baseConf(),
      transporte: {
        ...baseConf().transporte,
        numeracao_volumes: 'VOL-MANUAL-99',
      },
    };
    const payload = montarPayloadSalvarConferencia(conf, false);
    expect(payload.numeracao_volumes).toBe('VOL-MANUAL-99');
  });
});
