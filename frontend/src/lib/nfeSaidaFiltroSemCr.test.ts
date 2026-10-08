import { describe, expect, it } from 'vitest';
import {
  NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR,
  paramsFiltroAPrazoSemContasReceber,
} from '@/lib/nfeSaidaListFilters';

describe('filtro NF-e a prazo sem Contas a Receber', () => {
  it('expõe chave e rótulo estáveis para a listagem', () => {
    expect(NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR.key).toBe('a_prazo_sem_contas_receber');
    expect(NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR.optionLabel).toBe(
      'Autorizadas a prazo sem Contas a Receber',
    );
    expect(NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR.optionValue).toBe('true');
  });

  it('envia o parâmetro somente quando ativo', () => {
    expect(paramsFiltroAPrazoSemContasReceber('true')).toEqual({
      a_prazo_sem_contas_receber: 'true',
    });
    expect(paramsFiltroAPrazoSemContasReceber('')).toEqual({});
    expect(paramsFiltroAPrazoSemContasReceber(null)).toEqual({});
    expect(paramsFiltroAPrazoSemContasReceber(undefined)).toEqual({});
  });
});
