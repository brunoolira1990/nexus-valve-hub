import { describe, expect, it } from 'vitest';
import { formatMoneyBRL } from '@/lib/money';
import { formatQuantityBR } from '@/lib/numberFields';
import {
  mapItemNfeEntradaJson,
  mapItensNfeEntradaJson,
  temItensXmlNfeEntrada,
} from '@/lib/nfeEntradaItensJson';

describe('nfeEntradaItensJson', () => {
  const itemXml = {
    n_item: 1,
    prod: {
      cProd: '001',
      xProd: 'Válvula gaveta 2"',
      NCM: '84818095',
      CFOP: '1202',
      uCom: 'UN',
      qCom: '2.5000',
      vUnCom: '1500.00',
      vProd: '3750.00',
    },
  };

  it('mapeia campos principais do item XML', () => {
    const item = mapItemNfeEntradaJson(itemXml, 0);
    expect(item.numeroItem).toBe('1');
    expect(item.codigoProduto).toBe('001');
    expect(item.descricao).toBe('Válvula gaveta 2"');
    expect(item.ncm).toBe('84818095');
    expect(item.cfop).toBe('1202');
    expect(item.unidade).toBe('UN');
    expect(item.quantidade).toBe(2.5);
    expect(item.valorUnitario).toBe(1500);
    expect(item.valorTotal).toBe(3750);
  });

  it('formata valores e quantidades em pt-BR', () => {
    const item = mapItemNfeEntradaJson(itemXml, 0);
    expect(formatMoneyBRL(item.valorUnitario)).toMatch(/R\$\s*1\.500,00/);
    expect(formatMoneyBRL(item.valorTotal)).toMatch(/R\$\s*3\.750,00/);
    expect(formatQuantityBR(item.quantidade, item.unidade)).toBe('2,5 UN');
  });

  it('tolera chaves ausentes', () => {
    const item = mapItemNfeEntradaJson({ prod: { xProd: 'Só descrição' } }, 2);
    expect(item.numeroItem).toBe('3');
    expect(item.descricao).toBe('Só descrição');
    expect(item.ncm).toBe('');
    expect(item.cfop).toBe('');
  });

  it('detecta presença de itens_json', () => {
    expect(temItensXmlNfeEntrada({ itens: [], itens_json: [itemXml] })).toBe(true);
    expect(temItensXmlNfeEntrada({ itens: [], itens_json: [] })).toBe(false);
    expect(mapItensNfeEntradaJson(undefined)).toEqual([]);
  });
});
