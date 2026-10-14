import { useCallback, useEffect, useRef, useState } from 'react';
import { produtosService } from '@/services/api/produtos';
import { familiasProdutoService } from '@/services/api/produtos';
import type { Produto, FamiliaProduto, ModoCodigoProduto, TipoRegraCodigo, TipoDimensional, TipoFisicoProduto, TipoControleUnidade } from '@/types';
import type { ProdutoFormState } from '../types';
import { apiErrorMessage } from '@/services/api/config';
import { normalizarTipoRegra } from '@/lib/familiaRegra';

// --- Utilitários copiados de ProdutoList.tsx (não exportados) ---

const emptyForm = (): ProdutoFormState => ({
  modo_codigo: 'INTERNO',
  familia_id: null,
  rosca_conexao_id: null,
  schedule_ref_id: null,
  polegada_principal_ref_id: null,
  polegada_secundaria_ref_id: null,
  figura: '',
  sufixo: '',
  schedule: '',
  polegada_principal: '',
  polegada_secundaria: '',
  descricao: '',
  material: 'Aço Carbono',
  tipo_peca: '',
  pressao_nominal: '',
  norma: '',
  conexao: '',
  ncm: '',
  unidade: '',
  ncm_especifico: '',
  unidade_especifica: '',
  tipo_controle_unidade: '',
  tipo_fisico: '',
  unidade_estoque: '',
  unidade_venda_padrao: '',
  unidade_compra_padrao: '',
  unidade_fiscal: '',
  unidades_venda_permitidas: [],
  unidades_compra_permitidas: [],
  observacoes_conversao: '',
  comprimento_padrao_barra_m: null,
  peso_por_metro_kg: null,
  peso_por_peca_kg: null,
  peso_por_chapa_kg: null,
  densidade: null,
  usa_conversao_dimensional: false,
  controla_composicao_fisica: false,
  tipo_composicao_fisica: 'BARRA_M' as 'BARRA_M' | 'PECA_KG',
  preco_custo: 0,
  preco_venda: 0,
  estoque_minimo: 0,
  codigo_completo: '',
  od_mm: null,
  espessura_mm: null,
  comprimento_mm: null,
  dim_espessura_mm: null,
  dim_largura_mm: null,
  dim_comprimento_mm: null,
  dim_altura_mm: null,
  dim_furo_mm: null,
  dim_aba_mm: null,
  dim_aba_polegada_ref: null,
  dim_espessura_polegada_ref: null,
  dimensao_codigo: '',
  dimensao_descricao: '',
  dimensoes_json: {},
});

function familiaEhManualFabricante(familia: FamiliaProduto): boolean {
  return (
    normalizarTipoRegra(familia.tipo_regra_codigo) === 'MANUAL_FABRICANTE' ||
    familia.categoria_produto === 'MANUAL_FABRICANTE'
  );
}

function aplicarHerancaFamiliaProduto(
  prev: ProdutoFormState,
  familia: FamiliaProduto,
  modo: ModoCodigoProduto,
  opts?: { forcarCamposIniciais?: boolean },
): ProdutoFormState {
  const forcar = opts?.forcarCamposIniciais ?? false;
  const next = { ...prev };

  const setStrSeVazio = (key: keyof ProdutoFormState, value: string | undefined | null) => {
    const v = (value || '').trim();
    if (!v) return;
    const atual = String(next[key] ?? '').trim();
    if (forcar || !atual) next[key] = v as ProdutoFormState[typeof key];
  };

  if (modo === 'INTERNO') {
    if ((forcar || !next.rosca_conexao_id) && familia.rosca_padrao_id) {
      next.rosca_conexao_id = familia.rosca_padrao_id;
    }
    if ((forcar || !next.schedule_ref_id) && familia.schedule_padrao_id) {
      next.schedule_ref_id = familia.schedule_padrao_id;
    }
  }

  if (modo === 'MANUAL') {
    setStrSeVazio('descricao', familia.descricao_base);
    setStrSeVazio('ncm', familia.ncm_padrao_info?.codigo);
  }

  setStrSeVazio('unidade', familia.unidade_padrao || familia.unidade_estoque_padrao);
  setStrSeVazio('unidade_estoque', familia.unidade_estoque_padrao);
  setStrSeVazio('unidade_venda_padrao', familia.unidade_venda_padrao);
  setStrSeVazio('unidade_compra_padrao', familia.unidade_compra_padrao);
  setStrSeVazio('unidade_fiscal', familia.unidade_fiscal_padrao);
  setStrSeVazio('material', familia.material_base);
  setStrSeVazio('pressao_nominal', familia.pressao_base);
  setStrSeVazio('norma', familia.norma_base);
  setStrSeVazio('conexao', familia.conexao_base);

  if (forcar || !(next.unidades_venda_permitidas || []).length) {
    if (familia.unidades_venda_permitidas?.length) {
      next.unidades_venda_permitidas = [...familia.unidades_venda_permitidas];
    }
  }
  if (forcar || !(next.unidades_compra_permitidas || []).length) {
    if (familia.unidades_compra_permitidas?.length) {
      next.unidades_compra_permitidas = [...familia.unidades_compra_permitidas];
    }
  }
  if ((forcar || !next.tipo_fisico) && familia.tipo_fisico) next.tipo_fisico = familia.tipo_fisico;
  if ((forcar || !next.tipo_controle_unidade) && familia.tipo_controle_unidade) {
    next.tipo_controle_unidade = familia.tipo_controle_unidade;
  }

  return next;
}

function extractCodigoDuplicado(err: unknown): string | null {
  const ax = err as { response?: { data?: { non_field_errors?: unknown; codigo_completo?: unknown; detail?: unknown } } };
  const msgs: string[] = [];
  const nfe = ax.response?.data?.non_field_errors;
  if (Array.isArray(nfe)) msgs.push(...nfe.map(String));
  const cc = ax.response?.data?.codigo_completo;
  if (typeof cc === 'string') msgs.push(cc);
  if (Array.isArray(cc)) msgs.push(...cc.map(String));
  const msg = msgs.join(' ');
  const m =
    msg.match(/c[oó]digo\s+"([^"]+)"/i) ||
    msg.match(/c[oó]digo\s+([A-Z0-9._-]+)/i) ||
    msg.match(/["']([A-Z0-9._]+)["']/i);
  return m?.[1]?.trim() || null;
}

function codigoProdutoIgual(a: string | null | undefined, b: string | null | undefined): boolean {
  return (a || '').trim().toLowerCase() === (b || '').trim().toLowerCase();
}

interface UseProdutoFormReturn {
  form: ProdutoFormState;
  setForm: React.Dispatch<React.SetStateAction<ProdutoFormState>>;
  salvando: boolean;
  erro: string | null;
  preview: { codigo?: string; descricao?: string; ncm?: string };
  carregando: boolean;
  salvar: () => Promise<{ sucesso: boolean; id?: number }>;
  limpar: () => void;
  familiaSelecionada: FamiliaProduto | null;
  duplicateCodigo: string | null;
  duplicateProdutoId: number | null;
  setDuplicateCodigo: React.Dispatch<React.SetStateAction<string | null>>;
  setDuplicateProdutoId: React.Dispatch<React.SetStateAction<number | null>>;
  setModoCodigo: (modo: ModoCodigoProduto) => void;
}

export function useProdutoForm(
  id?: number,
  familias: FamiliaProduto[] = [],
  onSaveSuccess?: () => void
): UseProdutoFormReturn {
  const [form, setForm] = useState<ProdutoFormState>(emptyForm());
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [previewCodigo, setPreviewCodigo] = useState('');
  const [previewDesc, setPreviewDesc] = useState('');
  const [previewNcm, setPreviewNcm] = useState('');
  const [duplicateCodigo, setDuplicateCodigo] = useState<string | null>(null);
  const [duplicateProdutoId, setDuplicateProdutoId] = useState<number | null>(null);
  const previewRequestSeqRef = useRef(0);

  const familiaSelecionada = familias.find((f) => f.id === form.familia_id) ?? null;

  // Carregar produto se id fornecido
  useEffect(() => {
    if (!id) {
      setForm(emptyForm());
      setCarregando(false);
      return;
    }
    setCarregando(true);
    produtosService
      .getById(id)
      .then((produto) => {
        setForm({
          modo_codigo: (produto.modo_codigo as ModoCodigoProduto) || 'LEGADO',
          familia_id: produto.familia_id ?? null,
          rosca_conexao_id: produto.rosca_conexao_id ?? null,
          schedule_ref_id: produto.schedule_ref_id ?? null,
          polegada_principal_ref_id: produto.polegada_principal_ref_id ?? null,
          polegada_secundaria_ref_id: produto.polegada_secundaria_ref_id ?? null,
          figura: produto.figura ?? '',
          sufixo: produto.sufixo ?? '',
          schedule: produto.schedule ?? '',
          polegada_principal: produto.polegada_principal ?? '',
          polegada_secundaria: produto.polegada_secundaria ?? '',
          descricao: produto.descricao,
          material: produto.material ?? 'Aço Carbono',
          tipo_peca: produto.tipo_peca ?? '',
          pressao_nominal: produto.pressao_nominal ?? '',
          norma: produto.norma ?? '',
          conexao: produto.conexao ?? '',
          ncm: produto.ncm ?? '',
          unidade: produto.unidade ?? '',
          ncm_especifico: produto.ncm_especifico ?? '',
          unidade_especifica: produto.unidade_especifica ?? '',
          tipo_controle_unidade: produto.tipo_controle_unidade ?? '',
          tipo_fisico: produto.tipo_fisico ?? '',
          unidade_estoque: produto.unidade_estoque ?? '',
          unidade_venda_padrao: produto.unidade_venda_padrao ?? '',
          unidade_compra_padrao: produto.unidade_compra_padrao ?? '',
          unidade_fiscal: produto.unidade_fiscal ?? '',
          unidades_venda_permitidas: produto.unidades_venda_permitidas ?? [],
          unidades_compra_permitidas: produto.unidades_compra_permitidas ?? [],
          observacoes_conversao: produto.observacoes_conversao ?? '',
          comprimento_padrao_barra_m: produto.comprimento_padrao_barra_m ?? null,
          peso_por_metro_kg: produto.peso_por_metro_kg ?? null,
          peso_por_peca_kg: produto.peso_por_peca_kg ?? null,
          peso_por_chapa_kg: produto.peso_por_chapa_kg ?? null,
          densidade: produto.densidade ?? null,
          usa_conversao_dimensional: !!produto.usa_conversao_dimensional,
          controla_composicao_fisica: !!produto.controla_composicao_fisica,
          tipo_composicao_fisica: (produto.tipo_composicao_fisica || produto.tipo_composicao_fisica_efetivo || 'BARRA_M') as
            | 'BARRA_M'
            | 'PECA_KG',
          preco_custo: produto.preco_custo ?? 0,
          preco_venda: produto.preco_venda ?? 0,
          estoque_minimo: produto.estoque_minimo ?? 0,
          codigo_completo: produto.codigo_completo ?? '',
          od_mm: produto.od_mm ?? null,
          espessura_mm: produto.espessura_mm ?? null,
          comprimento_mm: produto.comprimento_mm ?? null,
          dim_espessura_mm: produto.dim_espessura_mm ?? null,
          dim_largura_mm: produto.dim_largura_mm ?? null,
          dim_comprimento_mm: produto.dim_comprimento_mm ?? null,
          dim_altura_mm: produto.dim_altura_mm ?? null,
          dim_furo_mm: produto.dim_furo_mm ?? null,
          dim_aba_mm: produto.dim_aba_mm ?? null,
          dim_aba_polegada_ref: produto.dim_aba_polegada_ref ?? null,
          dim_espessura_polegada_ref: produto.dim_espessura_polegada_ref ?? null,
          dimensao_codigo: produto.dimensao_codigo ?? '',
          dimensao_descricao: produto.dimensao_descricao ?? '',
          dimensoes_json: produto.dimensoes_json ?? {},
        });
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar o produto.' }));
      })
      .finally(() => setCarregando(false));
  }, [id]);

  // Aplicar herança da família quando muda modo_codigo ou familia_id
  useEffect(() => {
    if (!familiaSelecionada) return;
    const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;
    if (modo === 'INTERNO') {
      setForm((prev) => aplicarHerancaFamiliaProduto(prev, familiaSelecionada, 'INTERNO'));
    } else if (modo === 'MANUAL' && familiaEhManualFabricante(familiaSelecionada)) {
      setForm((prev) => aplicarHerancaFamiliaProduto(prev, familiaSelecionada, 'MANUAL'));
    }
  }, [form.modo_codigo, familiaSelecionada]);

  // Preview de código com debounce e race condition protection
  const refreshPreview = useCallback(async () => {
    if (form.modo_codigo !== 'INTERNO' || !form.familia_id) {
      previewRequestSeqRef.current += 1;
      setPreviewCodigo('');
      setPreviewDesc('');
      setPreviewNcm('');
      return;
    }
    const seq = ++previewRequestSeqRef.current;
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
      if (seq !== previewRequestSeqRef.current) return;
      setPreviewCodigo(res.codigo);
      setPreviewDesc(res.descricao_sugerida);
      setPreviewNcm(res.ncm_efetivo || '');
    } catch {
      if (seq !== previewRequestSeqRef.current) return;
      setPreviewCodigo('');
      setPreviewDesc('');
      setPreviewNcm('');
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

  // Debounce do preview
  useEffect(() => {
    if (form.modo_codigo !== 'INTERNO') return;
    const t = setTimeout(() => void refreshPreview(), 300);
    return () => clearTimeout(t);
  }, [
    form.modo_codigo,
    form.familia_id,
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
    refreshPreview,
  ]);

  // Detecção de código duplicado
  useEffect(() => {
    if (form.modo_codigo !== 'INTERNO' || !previewCodigo) {
      setDuplicateCodigo(null);
      setDuplicateProdutoId(null);
      return;
    }
    const t = setTimeout(() => {
      void produtosService
        .search(previewCodigo, 50)
        .then((hits) => {
          const hit = hits.find((p) => codigoProdutoIgual(p.codigo_completo, previewCodigo) && (!id || p.id !== id));
          setDuplicateCodigo(hit ? previewCodigo : null);
          setDuplicateProdutoId(hit?.id ?? null);
        })
        .catch(() => {
          setDuplicateCodigo(null);
          setDuplicateProdutoId(null);
        });
    }, 250);
    return () => clearTimeout(t);
  }, [form.modo_codigo, previewCodigo, id]);

  const setModoCodigo = useCallback((modo: ModoCodigoProduto) => {
    setForm((prev) => {
      const next = { ...prev, modo_codigo: modo };
      if (modo === 'INTERNO' && prev.familia_id) {
        const fam = familias.find((x) => x.id === prev.familia_id);
        if (fam && familiaEhManualFabricante(fam)) {
          next.familia_id = null;
        }
      }
      return next;
    });
  }, [familias]);

  const salvar = useCallback(async (): Promise<{ sucesso: boolean; id?: number }> => {
    setErro(null);
    setDuplicateCodigo(null);
    setDuplicateProdutoId(null);
    setSalvando(true);

    const body: Partial<Produto> = {
      modo_codigo: form.modo_codigo as ModoCodigoProduto,
      descricao: form.descricao,
      material: form.material,
      tipo_peca: form.tipo_peca,
      pressao_nominal: form.pressao_nominal,
      norma: form.norma,
      conexao: form.conexao,
      ncm: form.ncm,
      unidade: form.unidade,
      ncm_especifico: form.ncm_especifico,
      unidade_especifica: form.unidade_especifica,
      tipo_controle_unidade: form.tipo_controle_unidade || undefined,
      tipo_fisico: form.tipo_fisico || undefined,
      unidade_estoque: form.unidade_estoque || '',
      unidade_venda_padrao: form.unidade_venda_padrao || '',
      unidade_compra_padrao: form.unidade_compra_padrao || '',
      unidade_fiscal: form.unidade_fiscal || '',
      unidades_venda_permitidas: form.unidades_venda_permitidas || [],
      unidades_compra_permitidas: form.unidades_compra_permitidas || [],
      observacoes_conversao: form.observacoes_conversao || '',
      comprimento_padrao_barra_m: form.comprimento_padrao_barra_m,
      peso_por_metro_kg: form.peso_por_metro_kg,
      peso_por_peca_kg: form.peso_por_peca_kg,
      peso_por_chapa_kg: form.peso_por_chapa_kg,
      densidade: form.densidade,
      usa_conversao_dimensional: !!form.usa_conversao_dimensional,
      controla_composicao_fisica: !!form.controla_composicao_fisica,
      tipo_composicao_fisica: form.tipo_composicao_fisica || 'BARRA_M',
      preco_custo: form.preco_custo,
      preco_venda: form.preco_venda,
      estoque_minimo: form.estoque_minimo,
    };

    if (form.modo_codigo === 'MANUAL') {
      body.codigo_completo = form.codigo_completo.trim();
      body.familia_id = null;
      body.rosca_conexao_id = null;
      body.schedule_ref_id = null;
      body.polegada_principal_ref_id = null;
      body.polegada_secundaria_ref_id = null;
      body.od_mm = null;
      body.espessura_mm = null;
      body.comprimento_mm = null;
      body.dim_espessura_mm = null;
      body.dim_largura_mm = null;
      body.dim_comprimento_mm = null;
      body.dim_altura_mm = null;
      body.dim_furo_mm = null;
      body.dim_aba_mm = null;
      body.dim_aba_polegada_ref = null;
      body.dim_espessura_polegada_ref = null;
      body.dimensao_codigo = '';
      body.dimensao_descricao = '';
      body.dimensoes_json = {};
    } else if (form.modo_codigo === 'INTERNO') {
      body.familia_id = form.familia_id;
      body.rosca_conexao_id = form.rosca_conexao_id;
      body.schedule_ref_id = form.schedule_ref_id;
      body.polegada_principal_ref_id = form.polegada_principal_ref_id;
      body.polegada_secundaria_ref_id = form.polegada_secundaria_ref_id;
      body.od_mm = form.od_mm ?? null;
      body.espessura_mm = form.espessura_mm ?? null;
      body.comprimento_mm = form.comprimento_mm ?? null;
      body.dim_espessura_mm = form.dim_espessura_mm ?? null;
      body.dim_largura_mm = form.dim_largura_mm ?? null;
      body.dim_comprimento_mm = form.dim_comprimento_mm ?? null;
      body.dim_altura_mm = form.dim_altura_mm ?? null;
      body.dim_furo_mm = form.dim_furo_mm ?? null;
      body.dim_aba_mm = form.dim_aba_mm ?? null;
      body.dim_aba_polegada_ref = form.dim_aba_polegada_ref ?? null;
      body.dim_espessura_polegada_ref = form.dim_espessura_polegada_ref ?? null;
      body.dimensao_codigo = (form.dimensao_codigo || '').toUpperCase();
      body.dimensao_descricao = form.dimensao_descricao || '';
      body.dimensoes_json = form.dimensoes_json ?? {};
    } else {
      body.figura = form.figura;
      body.sufixo = form.sufixo;
      body.schedule = form.schedule;
      body.polegada_principal = form.polegada_principal;
      body.polegada_secundaria = form.polegada_secundaria;
      body.od_mm = null;
      body.espessura_mm = null;
      body.comprimento_mm = null;
      body.dim_espessura_mm = null;
      body.dim_largura_mm = null;
      body.dim_comprimento_mm = null;
      body.dim_altura_mm = null;
      body.dim_furo_mm = null;
      body.dim_aba_mm = null;
      body.dim_aba_polegada_ref = null;
      body.dim_espessura_polegada_ref = null;
      body.dimensao_codigo = '';
      body.dimensao_descricao = '';
      body.dimensoes_json = {};
    }

    try {
      let result: Produto;
      if (id) {
        result = await produtosService.update(id, body);
      } else {
        result = await produtosService.create(body as Omit<Produto, 'id'>);
      }
      setSalvando(false);
      onSaveSuccess?.();
      return { sucesso: true, id: result.id };
    } catch (e) {
      setSalvando(false);
      let codigo = extractCodigoDuplicado(e);
      if (!codigo && form.modo_codigo === 'MANUAL') {
        codigo = form.codigo_completo.trim() || null;
      }
      if (codigo) {
        setDuplicateCodigo(codigo);
        setErro(
          `Já existe um produto cadastrado com o código "${codigo}". Verifique o produto existente ou altere os parâmetros do código.`,
        );
        void produtosService
          .search(codigo, 50)
          .then((hits) => {
            const match = hits.find((p) => codigoProdutoIgual(p.codigo_completo, codigo)) ?? null;
            setDuplicateProdutoId(match?.id ?? null);
          })
          .catch(() => setDuplicateProdutoId(null));
        return { sucesso: false };
      }
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível salvar o produto.' });
      setErro(msg);
      return { sucesso: false };
    }
  }, [form, id, familias, onSaveSuccess]);

  const limpar = useCallback(() => {
    setForm(emptyForm());
    setErro(null);
    setDuplicateCodigo(null);
    setDuplicateProdutoId(null);
    setPreviewCodigo('');
    setPreviewDesc('');
    setPreviewNcm('');
  }, []);

  return {
    form,
    setForm,
    salvando,
    erro,
    preview: { codigo: previewCodigo, descricao: previewDesc, ncm: previewNcm },
    carregando,
    salvar,
    limpar,
    familiaSelecionada,
    duplicateCodigo,
    duplicateProdutoId,
    setDuplicateCodigo,
    setDuplicateProdutoId,
    setModoCodigo,
  };
}