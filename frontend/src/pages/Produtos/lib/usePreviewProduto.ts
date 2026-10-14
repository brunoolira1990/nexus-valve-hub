/**
 * Orquestração do preview de produto (API + debounce 300ms + guarda de sequência
 * + checagem de duplicidade), extraída de ProdutoList.tsx (linhas 657–795).
 *
 * Arquitetura C1: este hook vive na PÁGINA CONTAINER (ProdutoFormPage), que repassa
 * os valores já computados às abas presentacionais (Geral/Classificação/Fiscal).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ProdutoFormState } from '../types';
import type { Produto } from '@/types';
import { produtosService } from '@/services/api/produtos';
import { codigoProdutoIgual } from './codigoPreview';

export interface PreviewProduto {
  codigo: string;
  codigoBase: string;
  sequenciaTecnica: boolean;
  descricao: string;
  mensagem: string;
  ncm: string;
  unidade: string;
  duplicado: string | null;
}

const EMPTY: PreviewProduto = {
  codigo: '',
  codigoBase: '',
  sequenciaTecnica: false,
  descricao: '',
  mensagem: '',
  ncm: '',
  unidade: '',
  duplicado: null,
};

export function usePreviewProduto(opts: {
  open: boolean;
  form: ProdutoFormState;
  editing: Produto | null;
}): PreviewProduto {
  const { open, form, editing } = opts;
  const seqRef = useRef(0);
  const [state, setState] = useState<PreviewProduto>(EMPTY);

  const refresh = useCallback(async () => {
    if (form.modo_codigo !== 'INTERNO' || !form.familia_id) {
      seqRef.current += 1;
      setState((s) => ({
        ...s,
        codigo: '',
        codigoBase: '',
        sequenciaTecnica: false,
        descricao: '',
        mensagem: '',
        ncm: '',
        unidade: '',
      }));
      return;
    }
    const seq = ++seqRef.current;
    try {
      const res = await produtosService.previewCodigo({
        familia_id: form.familia_id,
        rosca_conexao_id: form.rosca_conexao_id,
        schedule_ref_id: form.schedule_ref_id,
        polegada_principal_ref_id: form.polegada_principal_ref_id,
        polegada_secundaria_ref_id: form.polegada_secundaria_ref_id,
        od_mm: form.od_mm ?? null,
        espessura_mm: form.espessura_mm ?? null,
        comprimento_mm: form.comprimento_mm ?? null,
        dim_espessura_mm: form.dim_espessura_mm ?? null,
        dim_largura_mm: form.dim_largura_mm ?? null,
        dim_comprimento_mm: form.dim_comprimento_mm ?? null,
        dim_altura_mm: form.dim_altura_mm ?? null,
        dim_furo_mm: form.dim_furo_mm ?? null,
        dim_aba_mm: form.dim_aba_mm ?? null,
        dim_aba_polegada_ref_id: form.dim_aba_polegada_ref ?? null,
        dim_espessura_polegada_ref_id: form.dim_espessura_polegada_ref ?? null,
        dimensao_codigo: form.dimensao_codigo || '',
        dimensao_descricao: form.dimensao_descricao || '',
        dimensoes_json: form.dimensoes_json ?? {},
      });
      if (seq !== seqRef.current) return;
      setState((s) => ({
        ...s,
        codigo: res.codigo,
        codigoBase: res.codigo_base || res.codigo,
        sequenciaTecnica: Boolean(res.sequencia_tecnica),
        descricao: res.descricao_sugerida,
        mensagem: res.mensagem,
        ncm: res.ncm_efetivo || '',
        unidade: res.unidade_efetiva || '',
      }));
    } catch {
      if (seq !== seqRef.current) return;
      setState((s) => ({
        ...s,
        codigo: '',
        codigoBase: '',
        sequenciaTecnica: false,
        descricao: '',
        ncm: '',
        unidade: '',
        mensagem: 'Não foi possível calcular a prévia.',
      }));
    }
  }, [
    form.familia_id,
    form.modo_codigo,
    form.rosca_conexao_id,
    form.schedule_ref_id,
    form.polegada_principal_ref_id,
    form.polegada_secundaria_ref_id,
    form.od_mm,
    form.espessura_mm,
    form.comprimento_mm,
    form.dim_espessura_mm,
    form.dim_largura_mm,
    form.dim_comprimento_mm,
    form.dim_altura_mm,
    form.dim_furo_mm,
    form.dim_aba_mm,
    form.dim_aba_polegada_ref,
    form.dim_espessura_polegada_ref,
    form.dimensao_codigo,
    form.dimensao_descricao,
    form.dimensoes_json,
  ]);

  // Debounce 300ms (ProdutoList linhas 735–760)
  useEffect(() => {
    if (!open || form.modo_codigo !== 'INTERNO') return;
    const t = setTimeout(() => void refresh(), 300);
    return () => clearTimeout(t);
  }, [open, refresh, form.modo_codigo]);

  // Duplicidade (ProdutoList linhas 777–795)
  useEffect(() => {
    if (!open || form.modo_codigo !== 'INTERNO' || !state.codigo) {
      setState((s) => (s.duplicado === null ? s : { ...s, duplicado: null }));
      return;
    }
    const t = setTimeout(() => {
      void produtosService
        .search(state.codigo, 50)
        .then((hits) => {
          const hit = hits.find(
            (p) =>
              codigoProdutoIgual(p.codigo_completo, state.codigo) &&
              (!editing || p.id !== editing.id),
          );
          setState((s) => ({ ...s, duplicado: hit ? state.codigo : null }));
        })
        .catch(() => setState((s) => ({ ...s, duplicado: null })));
    }, 250);
    return () => clearTimeout(t);
  }, [open, form.modo_codigo, state.codigo, editing]);

  return state;
}
