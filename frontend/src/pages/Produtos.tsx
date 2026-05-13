import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import {
  familiasProdutoService,
  ncmApiService,
  produtosService,
  roscasConexaoService,
  schedulesEspessuraService,
} from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import type {
  FamiliaProduto,
  ModoCodigoProduto,
  Produto,
  RequisitosProdutoDimensionais,
  RoscaConexao,
  ScheduleEspessura,
  TipoDimensional,
  TipoRegraCodigo,
} from '@/types';
import { MATERIAIS } from '@/types';
import {
  expandirSiglasValvulaDescricaoBase,
  flagsPorTipoRegra,
  hintTipoDimensional,
  labelPolegadaPrincipal,
  labelPolegadaSecundaria,
  labelsCamposObrigatorios,
  labelsCamposObrigatoriosProduto,
  normalizarTipoRegra,
  requisitosMedidasPermitidasModal,
  sugerirConfiguracaoFamilia,
  sugerirTipoRegraPorDimensional,
} from '@/lib/familiaRegra';
import { normalizarDescricaoProduto } from '@/lib/descricaoProduto';
import { ConversaoMedidasBlock, type CampoHeranca } from '@/components/produtos/ConversaoMedidasBlock';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import type { TipoControleUnidade, TipoFisicoProduto } from '@/types';
import type { AxiosError } from 'axios';

type FormState = Omit<Produto, 'id'> & { id?: number };

const emptyForm = (): FormState => ({
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

function formatDecimalField(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '';
  const txt = String(v);
  return txt.includes('.') ? txt.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1') : txt;
}

function parseDecimalFlexible(raw: string): number | null {
  const s = (raw || '').trim();
  if (!s) return null;
  const normalized = s.replace(',', '.');
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

function getDimInputValue(form: FormState, key: string): string {
  const explicit = (form as unknown as Record<string, number | string | null | undefined>)[`dim_${key}`];
  const v = explicit ?? form.dimensoes_json?.[key];
  if (v == null || v === '') return '';
  const n = typeof v === 'number' ? v : Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? formatDecimalField(n) : '';
}

function genCodigoLegadoPreview(f: FormState): string {
  const parts = [f.figura, f.sufixo, f.schedule].map((s) => (s || '').trim()).filter(Boolean);
  const p1 = (f.polegada_principal || '').replace(/"/g, '').trim();
  const p2 = (f.polegada_secundaria || '').replace(/"/g, '').trim();
  let inch = '';
  if (p1 && p2) inch = `${p1}x${p2}`;
  else if (p1) inch = p1;
  else if (p2) inch = p2;
  if (inch) parts.push(inch);
  return parts.join('.');
}

const REGRAS: { value: TipoRegraCodigo; label: string }[] = [
  { value: 'BASE_POLEGADA', label: '1) Base + polegada — {figura}.{id principal}' },
  { value: 'BASE_ROSCA_POLEGADA', label: '2) Base + rosca + polegada — {figura}{rosca}.{id principal}' },
  { value: 'BASE_DUAS_POLEGADAS', label: '3) Base + duas polegadas — {figura}.{id1}{id2}' },
  { value: 'BASE_ROSCA_DUAS_POLEGADAS', label: '4) Base + rosca + duas polegadas' },
  { value: 'BASE_SCHEDULE_POLEGADA', label: '5) Base + schedule + polegada — {figura}{schedule}.{id principal}' },
  { value: 'BASE_SCHEDULE_DUAS_POLEGADAS', label: '6) Base + schedule + duas polegadas' },
  { value: 'BASE_ROSCA_SCHEDULE_POLEGADA', label: '7) Base + rosca + schedule + polegada' },
  { value: 'BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS', label: '8) Base + rosca + schedule + duas polegadas' },
  { value: 'UNDERSCORE_POLEGADA', label: '9) Underscore + ID 3 dígitos — {figura}_{id}' },
  { value: 'MANUAL_FABRICANTE', label: '10) Manual/fabricante (sem código por família)' },
  { value: 'BASE_OD_MM_ESPESSURA', label: '11) Base + OD mm + espessura mm — {figura}.{od}{esp} (ex.: 6119OD.1002)' },
  { value: 'BASE_ESPIGAO_FLANGE_NPS', label: '12) Base + espigão NPS + flange NPS ({figura}.E{id}F{id})' },
];

const CATEGORIAS_FAMILIA = [
  { value: 'PRODUTO_TECNICO', label: 'Produto técnico' },
  { value: 'MATERIAL_DIMENSIONAL', label: 'Material dimensional' },
  { value: 'MANUAL_FABRICANTE', label: 'Produto manual/fabricante' },
] as const;

const TIPOS_DIMENSIONAIS: { value: TipoDimensional; label: string }[] = [
  { value: 'SIMPLES', label: 'Simples — só a regra de código define campos' },
  { value: 'NPS', label: 'NPS — polegada nominal' },
  { value: 'NPS_SCHEDULE', label: 'NPS + Schedule (SCH)' },
  { value: 'REDUCAO_NPS', label: 'Redução NPS + Schedule' },
  { value: 'NPS_X_ROSCA', label: 'NPS x Rosca' },
  { value: 'OD_POLEGADA', label: 'OD em polegada (não é NPS/SCH)' },
  { value: 'OD_POLEGADA_X_ROSCA', label: 'OD em polegada x Rosca' },
  { value: 'OD_MM', label: 'OD em mm' },
  { value: 'OD_MM_X_ESPESSURA', label: 'OD mm + espessura mm' },
  { value: 'OD_MM_X_ESPESSURA_X_COMPRIMENTO', label: 'OD mm + espessura + comprimento' },
  { value: 'CHAPA_MM', label: 'Chapa mm (espessura x largura x comprimento)' },
  { value: 'CHAPA_FURO_MM', label: 'Chapa furo mm (furo x espessura x largura x comprimento)' },
  { value: 'BARRA_CHATA_MM', label: 'Barra chata mm (largura x espessura [x comprimento])' },
  { value: 'METALON_MM', label: 'Metalon mm (altura x largura x espessura)' },
  { value: 'CANTONEIRA_MM', label: 'Cantoneira mm (aba x espessura [x comprimento])' },
  { value: 'CANTONEIRA_POLEGADA', label: 'Cantoneira polegada (aba x espessura)' },
  { value: 'DIMENSIONAL_LIVRE_CONTROLADO', label: 'Dimensional livre controlado' },
  { value: 'ROSCA', label: 'Rosca (orientação)' },
  { value: 'ROSCA_X_ROSCA', label: 'Rosca x Rosca (orientação)' },
  { value: 'FLANGE', label: 'Flange (orientação)' },
  { value: 'ESPIGAO_X_FLANGE', label: 'Espigão x Flange (duas NPS, texto flange na descrição base)' },
  { value: 'VALVULA', label: 'Válvula (orientação)' },
  { value: 'MANUAL', label: 'Dimensional manual' },
  { value: 'LEGADO', label: 'Legado / misto' },
];

const emptyFamiliaQuick = () => ({
  codigo_figura: '',
  descricao_base: '',
  categoria_produto: 'PRODUTO_TECNICO' as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE',
  tipo_regra_codigo: 'BASE_POLEGADA' as TipoRegraCodigo,
  tipo_dimensional: 'SIMPLES' as TipoDimensional,
  separador_base_medidas: '.',
  ativo: true,
  usa_conversao_dimensional: false,
  tipo_fisico: '' as TipoFisicoProduto | '',
  tipo_controle_unidade: '' as TipoControleUnidade | '',
  unidade_estoque_padrao: '',
  unidade_venda_padrao: '',
  unidade_compra_padrao: '',
  unidade_fiscal_padrao: '',
  unidades_venda_permitidas: [] as string[],
  unidades_compra_permitidas: [] as string[],
  comprimento_padrao_barra_m: null as number | null,
  peso_por_metro_kg: null as number | null,
  peso_por_peca_kg: null as number | null,
  peso_por_chapa_kg: null as number | null,
  densidade: null as number | null,
  observacoes_conversao: '',
  ncm_padrao: null as number | null,
});

function extractCodigoDuplicado(err: unknown): string | null {
  const ax = err as AxiosError<{
    non_field_errors?: unknown;
    codigo_completo?: unknown;
    detail?: unknown;
  }>;
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

const Produtos = () => {
  const [activeTab, setActiveTab] = useState<'produtos' | 'familias'>('produtos');
  const [items, setItems] = useState<Produto[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [famModalOpen, setFamModalOpen] = useState(false);
  const [editing, setEditing] = useState<Produto | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [familias, setFamilias] = useState<FamiliaProduto[]>([]);
  const [roscas, setRoscas] = useState<RoscaConexao[]>([]);
  const [schedules, setSchedules] = useState<ScheduleEspessura[]>([]);
  const [ncmFamiliaOption, setNcmFamiliaOption] = useState<NcmOption | null>(null);
  const [ncmProdutoOption, setNcmProdutoOption] = useState<NcmOption | null>(null);
  const [familiaOption, setFamiliaOption] = useState<FamiliaProduto | null>(null);
  const [scheduleOption, setScheduleOption] = useState<ScheduleEspessura | null>(null);
  const [famSearch, setFamSearch] = useState('');
  const [previewCodigo, setPreviewCodigo] = useState('');
  const [previewDesc, setPreviewDesc] = useState('');
  const [previewMsg, setPreviewMsg] = useState('');
  const [previewNcm, setPreviewNcm] = useState('');
  const [previewUnidade, setPreviewUnidade] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [duplicateCodigo, setDuplicateCodigo] = useState<string | null>(null);
  const [duplicateProdutoId, setDuplicateProdutoId] = useState<number | null>(null);
  const [previewCodigoDuplicado, setPreviewCodigoDuplicado] = useState<string | null>(null);
  const [famQuick, setFamQuick] = useState(emptyFamiliaQuick());
  const [odMmInput, setOdMmInput] = useState('');
  const [espessuraMmInput, setEspessuraMmInput] = useState('');
  const [comprimentoMmInput, setComprimentoMmInput] = useState('');
  const [famSaveErr, setFamSaveErr] = useState<string | null>(null);
  const [editingFamilia, setEditingFamilia] = useState<FamiliaProduto | null>(null);
  const [listNotice, setListNotice] = useState<string | null>(null);

  const codigoFiguraNorm = (famQuick.codigo_figura || '').trim().toLowerCase();
  const familiaDuplicada = useMemo(
    () =>
      familias.find(
        (x) =>
          x.codigo_figura.trim().toLowerCase() === codigoFiguraNorm &&
          (!editingFamilia || x.id !== editingFamilia.id),
      ) ?? null,
    [familias, codigoFiguraNorm, editingFamilia],
  );

  const fetchProdutos = useCallback(async (searchOverride?: string) => {
    const q = (searchOverride !== undefined ? searchOverride : search).trim();
    try {
      const data = await produtosService.getAll(q ? { search: q } : undefined);
      setItems(data);
    } catch (err) {
      console.error('Falha ao carregar produtos', err);
      setItems([]);
    }
  }, [search]);

  const loadBases = useCallback(async () => {
    const [f, r, s] = await Promise.all([
      familiasProdutoService.getAll({ apenas_ativas: '1' }),
      roscasConexaoService.getAll(),
      schedulesEspessuraService.getAll(),
    ]);
    setFamilias(f);
    setRoscas(r);
    setSchedules(s);
  }, []);

  useEffect(() => {
    if (activeTab !== 'produtos') return;
    const q = search.trim();
    const t = window.setTimeout(() => {
      void fetchProdutos();
    }, q ? 320 : 0);
    return () => window.clearTimeout(t);
  }, [search, activeTab, fetchProdutos]);

  useEffect(() => {
    if (!listNotice) return;
    const t = window.setTimeout(() => setListNotice(null), 6000);
    return () => window.clearTimeout(t);
  }, [listNotice]);

  useEffect(() => {
    if (modalOpen || famModalOpen || activeTab === 'familias') void loadBases();
  }, [modalOpen, famModalOpen, activeTab, loadBases]);

  const familiaSel = useMemo(
    () => familias.find((x) => x.id === form.familia_id) ?? null,
    [familias, form.familia_id],
  );

  const familiasFiltradas = useMemo(() => {
    const q = famSearch.trim().toLowerCase();
    if (!q) return familias;
    return familias.filter(
      (x) => x.codigo_figura.toLowerCase().includes(q) || x.descricao_base.toLowerCase().includes(q),
    );
  }, [familias, famSearch]);

  const regraLabelMap = useMemo(
    () => REGRAS.reduce<Record<string, string>>((acc, r) => ({ ...acc, [r.value]: r.label }), {}),
    [],
  );

  /** Famílias no select: em modo interno oculta MANUAL_FABRICANTE, mas mantém a selecionada para edição. */
  const familiasSelectInterno = useMemo(() => {
    const base = familiasFiltradas.filter((x) => normalizarTipoRegra(x.tipo_regra_codigo) !== 'MANUAL_FABRICANTE');
    const sel = form.familia_id ? familias.find((x) => x.id === form.familia_id) : null;
    if (sel && !base.some((x) => x.id === sel.id)) return [sel, ...base];
    return base;
  }, [familiasFiltradas, familias, form.familia_id]);

  const famReq = useMemo((): RequisitosProdutoDimensionais | null => {
    if (!familiaSel) return null;
    if (familiaSel.requisitos_produto) return familiaSel.requisitos_produto;
    const fl = flagsPorTipoRegra(normalizarTipoRegra(familiaSel.tipo_regra_codigo) || familiaSel.tipo_regra_codigo);
    return {
      usa_rosca_conexao: fl.usa_rosca_conexao,
      usa_schedule: fl.usa_schedule,
      usa_polegada_principal: fl.usa_polegada_principal,
      usa_polegada_secundaria: fl.usa_polegada_secundaria,
      exige_od_mm: false,
      exige_espessura_mm: false,
      exige_comprimento_mm: false,
      incluir_schedule_na_descricao: fl.usa_schedule,
    };
  }, [familiaSel]);
  const roscasPermitidas = roscas;
  const tipoMedidaPrincipal = useMemo<'NPS' | 'OD' | undefined>(() => {
    const td = familiaSel?.tipo_dimensional;
    if (!td) return undefined;
    if (td === 'OD_POLEGADA' || td === 'OD_POLEGADA_X_ROSCA') return 'OD';
    if (
      td === 'NPS' ||
      td === 'NPS_SCHEDULE' ||
      td === 'REDUCAO_NPS' ||
      td === 'NPS_X_ROSCA' ||
      td === 'FLANGE' ||
      td === 'ESPIGAO_X_FLANGE' ||
      td === 'VALVULA' ||
      td === 'ROSCA' ||
      td === 'ROSCA_X_ROSCA'
    )
      return 'NPS';
    return undefined;
  }, [familiaSel?.tipo_dimensional]);
  const tipoMedidaSecundaria = useMemo<'NPS' | 'OD' | undefined>(() => {
    const td = familiaSel?.tipo_dimensional;
    if (!td) return undefined;
    if (
      td === 'OD_POLEGADA_X_ROSCA' ||
      td === 'REDUCAO_NPS' ||
      td === 'NPS' ||
      td === 'NPS_SCHEDULE' ||
      td === 'NPS_X_ROSCA' ||
      td === 'ROSCA_X_ROSCA' ||
      td === 'ESPIGAO_X_FLANGE'
    )
      return 'NPS';
    return undefined;
  }, [familiaSel?.tipo_dimensional]);

  const famQuickFlags = useMemo(
    () => requisitosMedidasPermitidasModal(famQuick.tipo_dimensional, famQuick.tipo_regra_codigo),
    [famQuick.tipo_dimensional, famQuick.tipo_regra_codigo],
  );
  const sugestaoFamiliaAuto = useMemo(() => sugerirConfiguracaoFamilia(famQuick.descricao_base), [famQuick.descricao_base]);
  const tdAtual = familiaSel?.tipo_dimensional;
  const usaDimensoesMateriais = useMemo(
    () =>
      !!tdAtual &&
      ['CHAPA_MM', 'CHAPA_FURO_MM', 'BARRA_CHATA_MM', 'METALON_MM', 'PERFIL_RETANGULAR_MM', 'CANTONEIRA_MM', 'CANTONEIRA_POLEGADA', 'DIMENSIONAL_LIVRE_CONTROLADO'].includes(tdAtual),
    [tdAtual],
  );
  const refreshPreview = useCallback(async () => {
    if (form.modo_codigo !== 'INTERNO' || !form.familia_id) {
      setPreviewCodigo('');
      setPreviewDesc('');
      setPreviewMsg('');
      return;
    }
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
      setPreviewCodigo(res.codigo);
      setPreviewDesc(res.descricao_sugerida);
      setPreviewMsg(res.mensagem);
      setPreviewNcm(res.ncm_efetivo || '');
      setPreviewUnidade(res.unidade_efetiva || '');
    } catch {
      setPreviewCodigo('');
      setPreviewDesc('');
      setPreviewMsg('Não foi possível calcular a prévia.');
      setPreviewNcm('');
      setPreviewUnidade('');
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

  useEffect(() => {
    if (!modalOpen || form.modo_codigo !== 'INTERNO') return;
    const t = setTimeout(() => void refreshPreview(), 300);
    return () => clearTimeout(t);
  }, [
    modalOpen,
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

  useEffect(() => {
    if (!modalOpen || form.modo_codigo !== 'INTERNO' || !familiaSel) return;
    setForm((prev) => {
      const next = { ...prev };
      if (familiaSel.rosca_padrao_id && !next.rosca_conexao_id) next.rosca_conexao_id = familiaSel.rosca_padrao_id;
      if (familiaSel.schedule_padrao_id && !next.schedule_ref_id) next.schedule_ref_id = familiaSel.schedule_padrao_id;
      if (!next.unidade && familiaSel.unidade_padrao) next.unidade = familiaSel.unidade_padrao;
      if (!next.material && familiaSel.material_base) next.material = familiaSel.material_base;
      if (!next.pressao_nominal && familiaSel.pressao_base) next.pressao_nominal = familiaSel.pressao_base;
      if (!next.norma && familiaSel.norma_base) next.norma = familiaSel.norma_base;
      if (!next.conexao && familiaSel.conexao_base) next.conexao = familiaSel.conexao_base;
      return next;
    });
  }, [modalOpen, form.modo_codigo, familiaSel]);

  useEffect(() => {
    if (!modalOpen) return;
    setOdMmInput(formatDecimalField(form.od_mm));
    setEspessuraMmInput(formatDecimalField(form.espessura_mm));
    setComprimentoMmInput(formatDecimalField(form.comprimento_mm));
  }, [modalOpen, form.od_mm, form.espessura_mm, form.comprimento_mm]);

  useEffect(() => {
    setPreviewCodigoDuplicado(null);
    if (!modalOpen || form.modo_codigo !== 'INTERNO' || !previewCodigo) return;
    const t = setTimeout(() => {
      void produtosService
        .search(previewCodigo, 50)
        .then((hits) => {
          const hit = hits.find(
            (p) => codigoProdutoIgual(p.codigo_completo, previewCodigo) && (!editing || p.id !== editing.id),
          );
          setPreviewCodigoDuplicado(hit ? previewCodigo : null);
        })
        .catch(() => setPreviewCodigoDuplicado(null));
    }, 250);
    return () => clearTimeout(t);
  }, [modalOpen, form.modo_codigo, previewCodigo, editing]);

  const f = (k: keyof FormState, v: string | number | null) =>
    setForm((p) => ({ ...p, [k]: v } as FormState));
  const setDimensao = (key: string, raw: string) => {
    const fieldMap: Record<string, keyof FormState> = {
      espessura_mm: 'dim_espessura_mm',
      largura_mm: 'dim_largura_mm',
      comprimento_mm: 'dim_comprimento_mm',
      altura_mm: 'dim_altura_mm',
      furo_mm: 'dim_furo_mm',
      aba_mm: 'dim_aba_mm',
    };
    setForm((prev) => {
      const nextDims = { ...(prev.dimensoes_json || {}) } as Record<string, number | string | null>;
      const parsed = parseDecimalFlexible(raw);
      nextDims[key] = parsed;
      const fld = fieldMap[key];
      return { ...prev, dimensoes_json: nextDims, ...(fld ? { [fld]: parsed } : {}) };
    });
  };

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm());
    setFamSearch('');
    setSaveError(null);
    setDuplicateCodigo(null);
    setDuplicateProdutoId(null);
    setNcmProdutoOption(null);
    setFamiliaOption(null);
    setScheduleOption(null);
    setModalOpen(true);
  };

  const openNewFamilia = () => {
    setEditingFamilia(null);
    setFamQuick(emptyFamiliaQuick());
    setFamSaveErr(null);
    setNcmFamiliaOption(null);
    setFamModalOpen(true);
  };

  const usarFamiliaExistente = (familia: FamiliaProduto) => {
    setFamModalOpen(false);
    setFamSaveErr(null);
    setEditing(null);
    setForm({
      ...emptyForm(),
      modo_codigo: 'INTERNO',
      familia_id: familia.id,
    });
    setFamSearch(familia.codigo_figura);
    setModalOpen(true);
  };

  const openEditFamilia = (familia: FamiliaProduto) => {
    setEditingFamilia(familia);
    setFamQuick({
      codigo_figura: familia.codigo_figura,
      descricao_base: familia.descricao_base,
      tipo_regra_codigo: (normalizarTipoRegra(familia.tipo_regra_codigo) ?? 'BASE_POLEGADA') as TipoRegraCodigo,
      categoria_produto: (familia.categoria_produto || 'PRODUTO_TECNICO') as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE',
      tipo_dimensional: (familia.tipo_dimensional || 'SIMPLES') as TipoDimensional,
      separador_base_medidas: familia.separador_base_medidas || '.',
      ativo: familia.ativo,
      usa_conversao_dimensional: !!familia.usa_conversao_dimensional,
      tipo_fisico: (familia.tipo_fisico || '') as TipoFisicoProduto | '',
      tipo_controle_unidade: (familia.tipo_controle_unidade || '') as TipoControleUnidade | '',
      unidade_estoque_padrao: familia.unidade_estoque_padrao ?? '',
      unidade_venda_padrao: familia.unidade_venda_padrao ?? '',
      unidade_compra_padrao: familia.unidade_compra_padrao ?? '',
      unidade_fiscal_padrao: familia.unidade_fiscal_padrao ?? '',
      unidades_venda_permitidas: [...(familia.unidades_venda_permitidas || [])],
      unidades_compra_permitidas: [...(familia.unidades_compra_permitidas || [])],
      comprimento_padrao_barra_m: familia.comprimento_padrao_barra_m ?? null,
      peso_por_metro_kg: familia.peso_por_metro_kg ?? null,
      peso_por_peca_kg: familia.peso_por_peca_kg ?? null,
      peso_por_chapa_kg: familia.peso_por_chapa_kg ?? null,
      densidade: familia.densidade ?? null,
      observacoes_conversao: familia.observacoes_conversao ?? '',
      ncm_padrao: familia.ncm_padrao_id ?? familia.ncm_padrao ?? null,
    });
    setFamSaveErr(null);
    setNcmFamiliaOption(
      familia.ncm_padrao_info
        ? {
            id: familia.ncm_padrao_info.id,
            codigo: familia.ncm_padrao_info.codigo,
            descricao: familia.ncm_padrao_info.descricao,
          }
        : null,
    );
    setFamModalOpen(true);
  };

  const openEdit = (e: Produto) => {
    setEditing(e);
    setForm({
      modo_codigo: (e.modo_codigo as ModoCodigoProduto) || 'LEGADO',
      familia_id: e.familia_id ?? null,
      rosca_conexao_id: e.rosca_conexao_id ?? null,
      schedule_ref_id: e.schedule_ref_id ?? null,
      polegada_principal_ref_id: e.polegada_principal_ref_id ?? null,
      polegada_secundaria_ref_id: e.polegada_secundaria_ref_id ?? null,
      figura: e.figura ?? '',
      sufixo: e.sufixo ?? '',
      schedule: e.schedule ?? '',
      polegada_principal: e.polegada_principal ?? '',
      polegada_secundaria: e.polegada_secundaria ?? '',
      descricao: e.descricao,
      material: e.material,
      tipo_peca: e.tipo_peca,
      pressao_nominal: e.pressao_nominal,
      norma: e.norma,
      conexao: e.conexao,
      ncm: e.ncm,
      unidade: e.unidade ?? '',
      ncm_especifico: e.ncm_especifico ?? '',
      unidade_especifica: e.unidade_especifica ?? '',
      tipo_controle_unidade: e.tipo_controle_unidade ?? '',
      tipo_fisico: e.tipo_fisico ?? '',
      unidade_estoque: e.unidade_estoque ?? '',
      unidade_venda_padrao: e.unidade_venda_padrao ?? '',
      unidade_compra_padrao: e.unidade_compra_padrao ?? '',
      unidade_fiscal: e.unidade_fiscal ?? '',
      unidades_venda_permitidas: e.unidades_venda_permitidas ?? [],
      unidades_compra_permitidas: e.unidades_compra_permitidas ?? [],
      observacoes_conversao: e.observacoes_conversao ?? '',
      comprimento_padrao_barra_m: e.comprimento_padrao_barra_m ?? null,
      peso_por_metro_kg: e.peso_por_metro_kg ?? null,
      peso_por_peca_kg: e.peso_por_peca_kg ?? null,
      peso_por_chapa_kg: e.peso_por_chapa_kg ?? null,
      densidade: e.densidade ?? null,
      usa_conversao_dimensional: !!e.usa_conversao_dimensional,
      preco_custo: e.preco_custo,
      preco_venda: e.preco_venda,
      estoque_minimo: e.estoque_minimo,
      codigo_completo: e.codigo_completo,
      od_mm: e.od_mm ?? null,
      espessura_mm: e.espessura_mm ?? null,
      comprimento_mm: e.comprimento_mm ?? null,
      dim_espessura_mm: e.dim_espessura_mm ?? null,
      dim_largura_mm: e.dim_largura_mm ?? null,
      dim_comprimento_mm: e.dim_comprimento_mm ?? null,
      dim_altura_mm: e.dim_altura_mm ?? null,
      dim_furo_mm: e.dim_furo_mm ?? null,
      dim_aba_mm: e.dim_aba_mm ?? null,
      dim_aba_polegada_ref: e.dim_aba_polegada_ref ?? null,
      dim_espessura_polegada_ref: e.dim_espessura_polegada_ref ?? null,
      dimensao_codigo: e.dimensao_codigo ?? '',
      dimensao_descricao: e.dimensao_descricao ?? '',
      dimensoes_json: e.dimensoes_json ?? {},
    });
    setFamSearch('');
    setSaveError(null);
    setDuplicateCodigo(null);
    setDuplicateProdutoId(null);
    setFamiliaOption(familias.find((x) => x.id === (e.familia_id ?? 0)) ?? null);
    setScheduleOption(schedules.find((x) => x.id === (e.schedule_ref_id ?? 0)) ?? null);
    setNcmProdutoOption(
      e.ncm && e.ncm_efetivo
        ? {
            id: e.ncm_efetivo.id || 0,
            codigo: e.ncm_efetivo.codigo,
            descricao: e.ncm_efetivo.descricao,
          }
        : null,
    );
    setModalOpen(true);
  };

  useEffect(() => {
    if (!modalOpen || !form.ncm) return;
    if (ncmProdutoOption?.codigo === form.ncm) return;
    void ncmApiService
      .search(form.ncm, 1)
      .then((list) => {
        const match = list.find((x) => x.codigo === form.ncm);
        if (match) setNcmProdutoOption(match);
      })
      .catch(() => {});
  }, [modalOpen, form.ncm, ncmProdutoOption?.codigo]);

  useEffect(() => {
    if (!modalOpen || !form.familia_id || familiaOption?.id === form.familia_id) return;
    void familiasProdutoService
      .search(String(form.familia_id), 5)
      .then((items) => {
        const match = items.find((x) => x.id === form.familia_id);
        if (match) setFamiliaOption(match);
      })
      .catch(() => {});
  }, [modalOpen, form.familia_id, familiaOption?.id]);

  useEffect(() => {
    if (!modalOpen || !form.schedule_ref_id || scheduleOption?.id === form.schedule_ref_id) return;
    void schedulesEspessuraService
      .search(String(form.schedule_ref_id), 5)
      .then((items) => {
        const match = items.find((x) => x.id === form.schedule_ref_id);
        if (match) setScheduleOption(match);
      })
      .catch(() => {});
  }, [modalOpen, form.schedule_ref_id, scheduleOption?.id]);

  useEffect(() => {
    if (!famModalOpen || !famQuick.ncm_padrao || ncmFamiliaOption?.id === famQuick.ncm_padrao) return;
    void ncmApiService
      .getById(famQuick.ncm_padrao)
      .then((item) => setNcmFamiliaOption(item))
      .catch(() => {});
  }, [famModalOpen, famQuick.ncm_padrao, ncmFamiliaOption?.id]);

  const handleSave = async () => {
    setSaveError(null);
    setDuplicateCodigo(null);
    setDuplicateProdutoId(null);
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
      body.dimensao_descricao = normalizarDescricaoProduto(form.dimensao_descricao || '');
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
      if (editing) {
        const upd = await produtosService.update(editing.id, body);
        const code = (upd.codigo_completo || '').trim();
        setModalOpen(false);
        setSaveError(null);
        setDuplicateCodigo(null);
        setDuplicateProdutoId(null);
        await fetchProdutos();
        setListNotice(
          code ? `Produto ${code} atualizado. Lista atualizada.` : 'Produto atualizado. Lista atualizada.',
        );
      } else {
        const created = await produtosService.create(body as Omit<Produto, 'id'>);
        const codigoSalvo = (created.codigo_completo || '').trim();
        setModalOpen(false);
        setSaveError(null);
        setDuplicateCodigo(null);
        setDuplicateProdutoId(null);
        if (codigoSalvo) {
          setSearch(codigoSalvo);
          await fetchProdutos(codigoSalvo);
          setListNotice(`Produto ${codigoSalvo} salvo com sucesso. Lista atualizada.`);
        } else {
          await fetchProdutos();
          setListNotice('Produto salvo com sucesso. Lista atualizada.');
        }
      }
    } catch (e) {
      let codigo = extractCodigoDuplicado(e);
      if (!codigo && form.modo_codigo === 'MANUAL') {
        codigo = form.codigo_completo.trim() || null;
      }
      if (codigo) {
        setDuplicateCodigo(codigo);
        setSaveError(
          `Já existe um produto cadastrado com o código "${codigo}". Verifique o produto existente ou altere os parâmetros do código.`,
        );
        void produtosService
          .search(codigo, 50)
          .then((hits) => {
            const match = hits.find((p) => codigoProdutoIgual(p.codigo_completo, codigo)) ?? null;
            setDuplicateProdutoId(match?.id ?? null);
          })
          .catch(() => setDuplicateProdutoId(null));
        return;
      }
      setSaveError(apiErrorMessage(e, { fallback: 'Não foi possível salvar o produto.' }));
    }
  };

  const filtrarCodigoDuplicado = () => {
    if (!duplicateCodigo) return;
    setModalOpen(false);
    setActiveTab('produtos');
    setSearch(duplicateCodigo);
    void fetchProdutos(duplicateCodigo);
  };

  const abrirProdutoDuplicado = async () => {
    if (duplicateProdutoId != null) {
      const existente = items.find((it) => it.id === duplicateProdutoId);
      if (existente) {
        setModalOpen(false);
        openEdit(existente);
        return;
      }
      try {
        const p = await produtosService.getById(duplicateProdutoId);
        setModalOpen(false);
        setActiveTab('produtos');
        const code = (duplicateCodigo || p.codigo_completo || '').trim();
        if (code) {
          setSearch(code);
          await fetchProdutos(code);
        } else {
          await fetchProdutos();
        }
        openEdit(p);
        return;
      } catch {
        filtrarCodigoDuplicado();
        return;
      }
    }
    filtrarCodigoDuplicado();
  };

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await produtosService.delete(id);
      await fetchProdutos();
    }
  };

  const aplicarDescricaoPreview = () => {
    if (previewDesc) f('descricao', previewDesc);
  };

  const salvarFamiliaRapida = async () => {
    setFamSaveErr(null);
    if (familiaDuplicada) {
      setFamSaveErr(
        `A família/figura ${familiaDuplicada.codigo_figura} já existe. Use "Novo Produto" para cadastrar uma variação dessa família, ou edite a família existente.`,
      );
      return;
    }
    const effSave = requisitosMedidasPermitidasModal(famQuick.tipo_dimensional, famQuick.tipo_regra_codigo);
    try {
      const payload = {
        codigo_figura: famQuick.codigo_figura.trim(),
        descricao_base: famQuick.descricao_base.trim(),
        categoria_produto: famQuick.categoria_produto,
        tipo_regra_codigo: famQuick.tipo_regra_codigo,
        tipo_dimensional: famQuick.tipo_dimensional || 'SIMPLES',
        separador_base_medidas: famQuick.separador_base_medidas,
        ativo: famQuick.ativo,
        usa_rosca_conexao: effSave.usa_rosca_conexao,
        usa_schedule: effSave.usa_schedule,
        usa_polegada_principal: effSave.usa_polegada_principal,
        usa_polegada_secundaria: effSave.usa_polegada_secundaria,
        ncm_padrao: famQuick.ncm_padrao,
        unidade_padrao: '',
        material_base: '',
        pressao_base: '',
        norma_base: '',
        usa_conversao_dimensional: famQuick.usa_conversao_dimensional,
        tipo_fisico: (famQuick.tipo_fisico || 'PECA') as TipoFisicoProduto,
        tipo_controle_unidade: (famQuick.tipo_controle_unidade || 'PECA') as TipoControleUnidade,
        unidade_estoque_padrao: famQuick.unidade_estoque_padrao || '',
        unidade_venda_padrao: famQuick.unidade_venda_padrao || '',
        unidade_compra_padrao: famQuick.unidade_compra_padrao || '',
        unidade_fiscal_padrao: famQuick.unidade_fiscal_padrao || '',
        unidades_venda_permitidas: famQuick.unidades_venda_permitidas || [],
        unidades_compra_permitidas: famQuick.unidades_compra_permitidas || [],
        comprimento_padrao_barra_m: famQuick.comprimento_padrao_barra_m,
        peso_por_metro_kg: famQuick.peso_por_metro_kg,
        peso_por_peca_kg: famQuick.peso_por_peca_kg,
        peso_por_chapa_kg: famQuick.peso_por_chapa_kg,
        densidade: famQuick.densidade,
        observacoes_conversao: famQuick.observacoes_conversao || '',
      } as Omit<FamiliaProduto, 'id'>;
      if (editingFamilia) await familiasProdutoService.update(editingFamilia.id, payload);
      else await familiasProdutoService.create(payload);
      setFamModalOpen(false);
      setFamQuick(emptyFamiliaQuick());
      setEditingFamilia(null);
      await loadBases();
    } catch (e) {
      const err = e as { response?: { status?: number; data?: Record<string, unknown> } };
      const status = err.response?.status;
      const data = err.response?.data;
      const hasCodigoFiguraError =
        status === 400 &&
        !!data &&
        typeof data === 'object' &&
        Object.prototype.hasOwnProperty.call(data, 'codigo_figura');
      if (hasCodigoFiguraError) {
        const codigo = (famQuick.codigo_figura || '').trim();
        const jaExistente =
          familias.find((x) => x.codigo_figura.trim().toLowerCase() === codigo.toLowerCase()) ?? null;
        setFamSaveErr(
          `A família/figura ${codigo || 'informada'} já existe. Use "Novo Produto" para cadastrar uma variação dessa família, ou edite a família existente.`,
        );
        if (jaExistente) {
          // Mantém os dados digitados e só orienta; ação rápida fica disponível no modal.
          void loadBases();
        }
        return;
      }
      setFamSaveErr(apiErrorMessage(e, { fallback: 'Não foi possível salvar a família.' }));
    }
  };

  const tipoFisicoEfetivo = useMemo(() => {
    const t = (form.tipo_fisico || '').trim();
    if (t) return t;
    const ft = (familiaSel?.tipo_fisico || '').trim();
    return ft || 'PECA';
  }, [form.tipo_fisico, familiaSel?.tipo_fisico]);
  const familiaCategoria = (familiaSel?.categoria_produto || 'PRODUTO_TECNICO') as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';
  const familiaEhMaterialDimensional = familiaCategoria === 'MATERIAL_DIMENSIONAL';
  const tiposDimensionaisPorCategoria = useMemo(() => {
    if (famQuick.categoria_produto === 'MANUAL_FABRICANTE') return [{ value: 'MANUAL' as TipoDimensional, label: 'Manual/fabricante' }];
    if (famQuick.categoria_produto === 'MATERIAL_DIMENSIONAL') {
      return TIPOS_DIMENSIONAIS.filter((x) =>
        ['CHAPA_MM', 'CHAPA_FURO_MM', 'BARRA_CHATA_MM', 'METALON_MM', 'CANTONEIRA_MM', 'CANTONEIRA_POLEGADA', 'PERFIL_RETANGULAR_MM', 'DIMENSIONAL_LIVRE_CONTROLADO'].includes(x.value),
      );
    }
    return TIPOS_DIMENSIONAIS.filter((x) =>
      [
        'SIMPLES',
        'NPS',
        'NPS_SCHEDULE',
        'REDUCAO_NPS',
        'ROSCA',
        'ROSCA_X_ROSCA',
        'NPS_X_ROSCA',
        'OD_POLEGADA',
        'OD_POLEGADA_X_ROSCA',
        'OD_MM',
        'OD_MM_X_ESPESSURA',
        'OD_MM_X_ESPESSURA_X_COMPRIMENTO',
        'FLANGE',
        'ESPIGAO_X_FLANGE',
        'VALVULA',
      ].includes(x.value),
    );
  }, [famQuick.categoria_produto]);

  const herancaConv = useMemo(() => {
    if (!familiaSel) return undefined;
    const fam = familiaSel;
    const lista = (a?: string[]) => (a && a.length ? a.join(', ') : null);
    const numTxt = (n?: number | null) => (n != null ? `${n}` : null);
    return {
      isOverride: (campo: CampoHeranca): boolean => {
        switch (campo) {
          case 'tipo_fisico':
            return !!(form.tipo_fisico || '').trim();
          case 'tipo_controle_unidade':
            return !!(form.tipo_controle_unidade || '').trim();
          case 'unidade_estoque':
            return !!(form.unidade_estoque || '').trim();
          case 'unidade_venda':
            return !!(form.unidade_venda_padrao || '').trim();
          case 'unidade_compra':
            return !!(form.unidade_compra_padrao || '').trim();
          case 'unidade_fiscal':
            return !!(form.unidade_fiscal || '').trim();
          case 'unidades_venda':
            return (form.unidades_venda_permitidas?.length ?? 0) > 0;
          case 'unidades_compra':
            return (form.unidades_compra_permitidas?.length ?? 0) > 0;
          case 'comprimento':
            return form.comprimento_padrao_barra_m != null;
          case 'peso_metro':
            return form.peso_por_metro_kg != null;
          case 'peso_peca':
            return form.peso_por_peca_kg != null;
          case 'peso_chapa':
            return form.peso_por_chapa_kg != null;
          case 'densidade':
            return form.densidade != null;
          case 'observacoes':
            return !!(form.observacoes_conversao || '').trim();
          default:
            return false;
        }
      },
      valorFamiliaTexto: (campo: CampoHeranca): string | null => {
        switch (campo) {
          case 'tipo_fisico':
            return fam.tipo_fisico || null;
          case 'tipo_controle_unidade':
            return fam.tipo_controle_unidade || null;
          case 'unidade_estoque':
            return (fam.unidade_estoque_padrao || '').trim() || null;
          case 'unidade_venda':
            return (fam.unidade_venda_padrao || '').trim() || null;
          case 'unidade_compra':
            return (fam.unidade_compra_padrao || '').trim() || null;
          case 'unidade_fiscal':
            return (fam.unidade_fiscal_padrao || '').trim() || null;
          case 'unidades_venda':
            return lista(fam.unidades_venda_permitidas);
          case 'unidades_compra':
            return lista(fam.unidades_compra_permitidas);
          case 'comprimento':
            return numTxt(fam.comprimento_padrao_barra_m ?? null);
          case 'peso_metro':
            return numTxt(fam.peso_por_metro_kg ?? null);
          case 'peso_peca':
            return numTxt(fam.peso_por_peca_kg ?? null);
          case 'peso_chapa':
            return numTxt(fam.peso_por_chapa_kg ?? null);
          case 'densidade':
            return numTxt(fam.densidade ?? null);
          case 'observacoes':
            return (fam.observacoes_conversao || '').trim() || null;
          default:
            return null;
        }
      },
      onUsarFamilia: (campo: CampoHeranca) => {
        setForm((prev) => {
          const n = { ...prev } as FormState;
          switch (campo) {
            case 'tipo_fisico':
              n.tipo_fisico = '';
              break;
            case 'tipo_controle_unidade':
              n.tipo_controle_unidade = '';
              break;
            case 'unidade_estoque':
              n.unidade_estoque = '';
              break;
            case 'unidade_venda':
              n.unidade_venda_padrao = '';
              break;
            case 'unidade_compra':
              n.unidade_compra_padrao = '';
              break;
            case 'unidade_fiscal':
              n.unidade_fiscal = '';
              break;
            case 'unidades_venda':
              n.unidades_venda_permitidas = [];
              break;
            case 'unidades_compra':
              n.unidades_compra_permitidas = [];
              break;
            case 'comprimento':
              n.comprimento_padrao_barra_m = null;
              break;
            case 'peso_metro':
              n.peso_por_metro_kg = null;
              break;
            case 'peso_peca':
              n.peso_por_peca_kg = null;
              break;
            case 'peso_chapa':
              n.peso_por_chapa_kg = null;
              break;
            case 'densidade':
              n.densidade = null;
              break;
            case 'observacoes':
              n.observacoes_conversao = '';
              break;
            default:
              break;
          }
          return n;
        });
      },
    };
  }, [
    familiaSel,
    form.tipo_fisico,
    form.tipo_controle_unidade,
    form.unidade_estoque,
    form.unidade_venda_padrao,
    form.unidade_compra_padrao,
    form.unidade_fiscal,
    form.unidades_venda_permitidas,
    form.unidades_compra_permitidas,
    form.comprimento_padrao_barra_m,
    form.peso_por_metro_kg,
    form.peso_por_peca_kg,
    form.peso_por_chapa_kg,
    form.densidade,
    form.observacoes_conversao,
  ]);

  const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;
  const familiasTabela = familias.filter(
    (f) =>
      f.codigo_figura.toLowerCase().includes(search.toLowerCase()) ||
      f.descricao_base.toLowerCase().includes(search.toLowerCase()),
  );

  const filtrosProdutosAtivos = activeTab === 'produtos' && !!search.trim();
  const limparFiltrosProdutos = () => {
    setSearch('');
    void fetchProdutos('');
  };

  return (
    <div>
      <PageHeader title="Produtos" onAdd={openNew} addLabel="Novo Produto" searchValue={search} onSearch={setSearch} />
      {listNotice ? <p className="text-sm text-emerald-800 dark:text-emerald-200 mb-3">{listNotice}</p> : null}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={openNewFamilia} className="erp-btn-outline text-sm">
          <Plus className="h-4 w-4 inline mr-1" />
          Nova família / figura (nova base técnica)
        </button>
        <p className="text-xs text-muted-foreground">
          Família/Figura define a base técnica do produto. Para cadastrar medida, rosca ou variação, use
          {' '}
          <span className="font-medium">Novo Produto</span>.
        </p>
      </div>
      <div className="mb-3 flex gap-2">
        <button
          type="button"
          className={activeTab === 'produtos' ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
          onClick={() => setActiveTab('produtos')}
        >
          Produtos
        </button>
        <button
          type="button"
          className={activeTab === 'familias' ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
          onClick={() => setActiveTab('familias')}
        >
          Famílias / Figuras
        </button>
      </div>
      {activeTab === 'produtos' && filtrosProdutosAtivos ? (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Há filtros ativos na lista de produtos. Limpe os filtros para ver todos os produtos.</span>
          <button type="button" className="erp-btn-outline erp-btn-sm shrink-0" onClick={limparFiltrosProdutos}>
            Limpar filtros
          </button>
        </div>
      ) : null}
      <div className="erp-card overflow-x-auto">
        {activeTab === 'produtos' ? (
          <table className="erp-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Descrição</th>
                <th>Modo</th>
                <th>Material</th>
                <th>NCM</th>
                <th>Preço Venda</th>
                <th className="w-24">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-sm text-muted-foreground py-6 px-3">
                    {filtrosProdutosAtivos ? (
                      <div className="space-y-2">
                        <p>Nenhum produto encontrado com o filtro atual.</p>
                        <p>Há filtros ativos. Limpe os filtros para ver todos os produtos.</p>
                        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={limparFiltrosProdutos}>
                          Limpar filtros
                        </button>
                      </div>
                    ) : (
                      'Nenhum produto cadastrado.'
                    )}
                  </td>
                </tr>
              ) : (
                items.map((e) => (
                  <tr key={e.id}>
                    <td className="font-mono text-xs">{e.codigo_completo}</td>
                    <td className="font-medium">{e.descricao}</td>
                    <td className="text-xs text-muted-foreground">{e.modo_codigo || 'LEGADO'}</td>
                    <td>{e.material}</td>
                    <td>{e.ncm_efetivo?.codigo || e.ncm || '—'}</td>
                    <td>R$ {e.preco_venda.toFixed(2)}</td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" onClick={() => openEdit(e)} className="erp-btn-ghost erp-btn-sm">
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => handleDelete(e.id)} className="erp-btn-ghost erp-btn-sm text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        ) : (
          <table className="erp-table">
            <thead>
              <tr>
                <th>Código figura/base</th>
                <th>Descrição base</th>
                <th>Regra de código</th>
                <th>Rosca</th>
                <th>Schedule</th>
                <th>Polegada 1</th>
                <th>Polegada 2</th>
                <th className="w-36">Ações</th>
              </tr>
            </thead>
            <tbody>
              {familiasTabela.map((fml) => (
                <tr key={fml.id}>
                  <td className="font-mono text-xs">{fml.codigo_figura}</td>
                  <td className="font-medium">{fml.descricao_base}</td>
                  <td className="text-xs text-muted-foreground">{regraLabelMap[normalizarTipoRegra(fml.tipo_regra_codigo) || fml.tipo_regra_codigo] || fml.tipo_regra_codigo}</td>
                  <td>{fml.usa_rosca_conexao ? 'Sim' : 'Não'}</td>
                  <td>{fml.usa_schedule ? 'Sim' : 'Não'}</td>
                  <td>{fml.usa_polegada_principal ? 'Sim' : 'Não'}</td>
                  <td>{fml.usa_polegada_secundaria ? 'Sim' : 'Não'}</td>
                  <td>
                    <div className="flex gap-1">
                      <button type="button" onClick={() => openEditFamilia(fml)} className="erp-btn-ghost erp-btn-sm">
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button type="button" onClick={() => usarFamiliaExistente(fml)} className="erp-btn-outline erp-btn-sm">
                        Usar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Editar Produto' : 'Novo Produto'} size="lg">
        {saveError && <p className="text-sm text-destructive mb-3">{saveError}</p>}
        {duplicateCodigo ? (
          <div className="mb-3 flex flex-wrap gap-2">
            <button type="button" className="erp-btn-outline erp-btn-sm" onClick={filtrarCodigoDuplicado}>
              Filtrar lista por este código
            </button>
            <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => void abrirProdutoDuplicado()}>
              Abrir produto existente
            </button>
          </div>
        ) : null}

        <div className="mb-4 space-y-2">
          <p className="text-sm font-medium">Tipo de cadastro</p>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="modo"
                checked={modo === 'INTERNO'}
                onChange={() => f('modo_codigo', 'INTERNO')}
              />
              Código interno por regra (família / figura)
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="modo"
                checked={modo === 'MANUAL'}
                onChange={() => f('modo_codigo', 'MANUAL')}
              />
              Código manual / fabricante
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="modo"
                checked={modo === 'LEGADO'}
                onChange={() => f('modo_codigo', 'LEGADO')}
              />
              Legado (campos texto livres — mantém produtos antigos)
            </label>
          </div>
        </div>

        {modo === 'INTERNO' && familias.length === 0 && (
          <p className="text-sm text-amber-800 dark:text-amber-200 mb-3">
            Nenhuma família cadastrada. Use &quot;Nova família / figura&quot; ou rode no backend:{' '}
            <code className="text-xs bg-muted px-1 rounded">python manage.py seed_bases_produto</code>.
          </p>
        )}

        {modo === 'INTERNO' && (
          <div className="mb-4 p-3 rounded-md border border-border bg-muted/30 space-y-3">
            {familiaSel ? (
              <div className="rounded-md border border-dashed border-border bg-background p-3 text-xs">
                <p className="font-semibold text-foreground">Produto guiado pela Família/Figura</p>
                <p>Categoria: {familiaCategoria === 'MATERIAL_DIMENSIONAL' ? 'Material dimensional' : familiaCategoria === 'MANUAL_FABRICANTE' ? 'Produto manual/fabricante' : 'Produto técnico'}</p>
                <p>Tipo dimensional: {familiaSel.tipo_dimensional || 'SIMPLES'}</p>
                <p>Regra de código: {regraLabelMap[normalizarTipoRegra(familiaSel.tipo_regra_codigo) || familiaSel.tipo_regra_codigo] || familiaSel.tipo_regra_codigo}</p>
                <p>Obrigatórios: {labelsCamposObrigatoriosProduto(familiaSel).join(' · ')}</p>
              </div>
            ) : null}
            <div>
              <label className="erp-label">Família / figura</label>
              <AsyncAutocomplete<FamiliaProduto>
                value={form.familia_id ?? null}
                selectedOption={familiaOption}
                placeholder="Digite código ou descrição da família..."
                search={(term, limit) => familiasProdutoService.search(term, limit ?? 20)}
                getOptionValue={(opt) => opt.id}
                getOptionLabel={(opt) => `${opt.codigo_figura} — ${opt.descricao_base}`}
                onChange={(val, opt) => {
                  const id = typeof val === 'number' ? val : null;
                  f('familia_id', id);
                  setFamiliaOption(opt ?? null);
                }}
              />
            </div>
            {familiaSel && famReq && (
              <>
                <p className="text-xs text-muted-foreground rounded-md bg-muted/50 px-2 py-1.5">
                  <span className="font-medium text-foreground">Obrigatórios no produto (regra + tipo dimensional):</span>{' '}
                  {labelsCamposObrigatoriosProduto(familiaSel).join(' · ')}
                </p>
                {familiaSel.tipo_dimensional && familiaSel.tipo_dimensional !== 'SIMPLES' ? (
                  <p className="text-xs text-muted-foreground">{hintTipoDimensional(familiaSel.tipo_dimensional)}</p>
                ) : null}
                {!familiaEhMaterialDimensional && famReq.usa_rosca_conexao && (
                  <div>
                    <label className="erp-label">Rosca / conexão</label>
                    <select
                      className="erp-select mt-1 w-full"
                      value={form.rosca_conexao_id ?? ''}
                      onChange={(e) => f('rosca_conexao_id', e.target.value ? +e.target.value : null)}
                    >
                      <option value="">Selecione…</option>
                      {roscasPermitidas.map((r) => (
                        <option key={r.id} value={r.id}>
                          {(r.codigo || '∅') + ' — ' + r.descricao}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.usa_schedule && (
                  <div>
                    <label className="erp-label">Schedule / espessura</label>
                    <AsyncAutocomplete<ScheduleEspessura>
                      value={form.schedule_ref_id ?? null}
                      selectedOption={scheduleOption}
                      placeholder="Digite código, descrição ou aplicação (ex.: 10S, SCH 20, INOX)"
                      search={async (term, limit) => schedulesEspessuraService.search(term, limit ?? 20)}
                      getOptionValue={(opt) => opt.id}
                      getOptionLabel={(opt) =>
                        `${opt.codigo || opt.codigo_schedule} — ${opt.descricao || opt.codigo_schedule}`
                      }
                      onChange={(val, opt) => {
                        const id = typeof val === 'number' ? val : null;
                        f('schedule_ref_id', id);
                        setScheduleOption(opt ?? null);
                      }}
                    />
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.exige_od_mm && (
                  <div>
                    <label className="erp-label">OD externo (mm)</label>
                    <input
                      type="text"
                      inputMode="decimal"
                      className="erp-input mt-1"
                      placeholder='Ex.: 10 | 10,0 | 1,5'
                      value={odMmInput}
                      onChange={(e) => {
                        const v = e.target.value;
                        setOdMmInput(v);
                        f('od_mm', parseDecimalFlexible(v));
                      }}
                    />
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.exige_espessura_mm && (
                  <div>
                    <label className="erp-label">Espessura (mm)</label>
                    <input
                      type="text"
                      inputMode="decimal"
                      className="erp-input mt-1"
                      placeholder='Ex.: 2 | 2,0 | 1,5'
                      value={espessuraMmInput}
                      onChange={(e) => {
                        const v = e.target.value;
                        setEspessuraMmInput(v);
                        f('espessura_mm', parseDecimalFlexible(v));
                      }}
                    />
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.exige_comprimento_mm && (
                  <div>
                    <label className="erp-label">Comprimento (mm)</label>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Se vazio, pode usar o comprimento padrão da barra cadastrado na família (metros → mm no servidor).
                    </p>
                    <input
                      type="text"
                      inputMode="decimal"
                      className="erp-input mt-1"
                      placeholder='Ex.: 6000'
                      value={comprimentoMmInput}
                      onChange={(e) => {
                        const v = e.target.value;
                        setComprimentoMmInput(v);
                        f('comprimento_mm', parseDecimalFlexible(v));
                      }}
                    />
                  </div>
                )}
                {familiaEhMaterialDimensional && usaDimensoesMateriais && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {(tdAtual === 'CHAPA_MM' || tdAtual === 'CHAPA_FURO_MM') ? (
                      <>
                        {tdAtual === 'CHAPA_FURO_MM' ? (
                          <div>
                            <label className="erp-label">Furo (mm)</label>
                            <input
                              type="text"
                              inputMode="decimal"
                              className="erp-input mt-1"
                              value={getDimInputValue(form, 'furo_mm')}
                              onChange={(e) => setDimensao('furo_mm', e.target.value)}
                            />
                          </div>
                        ) : null}
                        <div>
                          <label className="erp-label">Espessura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'espessura_mm')} onChange={(e) => setDimensao('espessura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Largura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'largura_mm')} onChange={(e) => setDimensao('largura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Comprimento (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'comprimento_mm')} onChange={(e) => setDimensao('comprimento_mm', e.target.value)} />
                        </div>
                      </>
                    ) : null}
                    {(tdAtual === 'METALON_MM' || tdAtual === 'PERFIL_RETANGULAR_MM') ? (
                      <>
                        <div>
                          <label className="erp-label">Altura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'altura_mm')} onChange={(e) => setDimensao('altura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Largura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'largura_mm')} onChange={(e) => setDimensao('largura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Espessura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'espessura_mm')} onChange={(e) => setDimensao('espessura_mm', e.target.value)} />
                        </div>
                      </>
                    ) : null}
                    {(tdAtual === 'BARRA_CHATA_MM' || tdAtual === 'CANTONEIRA_MM') ? (
                      <>
                        <div>
                          <label className="erp-label">{tdAtual === 'CANTONEIRA_MM' ? 'Aba (mm)' : 'Largura (mm)'}</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, tdAtual === 'CANTONEIRA_MM' ? 'aba_mm' : 'largura_mm')} onChange={(e) => setDimensao(tdAtual === 'CANTONEIRA_MM' ? 'aba_mm' : 'largura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Espessura (mm)</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'espessura_mm')} onChange={(e) => setDimensao('espessura_mm', e.target.value)} />
                        </div>
                        <div>
                          <label className="erp-label">Comprimento (mm) opcional</label>
                          <input type="text" inputMode="decimal" className="erp-input mt-1" value={getDimInputValue(form, 'comprimento_mm')} onChange={(e) => setDimensao('comprimento_mm', e.target.value)} />
                        </div>
                      </>
                    ) : null}
                    {tdAtual === 'CANTONEIRA_POLEGADA' ? (
                      <>
                        <div>
                          <label className="erp-label">Aba (polegada OD)</label>
                          <PolegadaAutocomplete value={form.dim_aba_polegada_ref ?? null} onChange={(id) => f('dim_aba_polegada_ref', id)} tipoMedida="OD" allowCreate />
                        </div>
                        <div>
                          <label className="erp-label">Espessura (polegada OD)</label>
                          <PolegadaAutocomplete value={form.dim_espessura_polegada_ref ?? null} onChange={(id) => f('dim_espessura_polegada_ref', id)} tipoMedida="OD" allowCreate />
                        </div>
                      </>
                    ) : null}
                    {tdAtual === 'DIMENSIONAL_LIVRE_CONTROLADO' ? (
                      <>
                        <div>
                          <label className="erp-label">Dimensão código</label>
                          <input className="erp-input mt-1 font-mono" value={form.dimensao_codigo || ''} onChange={(e) => f('dimensao_codigo', e.target.value.toUpperCase())} />
                        </div>
                        <div className="md:col-span-2">
                          <label className="erp-label">Dimensão descrição</label>
                          <input
                            className="erp-input mt-1"
                            value={form.dimensao_descricao || ''}
                            onChange={(e) => f('dimensao_descricao', normalizarDescricaoProduto(e.target.value))}
                          />
                        </div>
                      </>
                    ) : null}
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.usa_polegada_principal && (
                  <div>
                    <label className="erp-label">{labelPolegadaPrincipal(familiaSel.tipo_dimensional)}</label>
                    <PolegadaAutocomplete
                      value={form.polegada_principal_ref_id ?? null}
                      onChange={(id) => f('polegada_principal_ref_id', id)}
                      tipoMedida={tipoMedidaPrincipal}
                      allowCreate
                    />
                  </div>
                )}
                {!familiaEhMaterialDimensional && famReq.usa_polegada_secundaria && (
                  <div>
                    <label className="erp-label">{labelPolegadaSecundaria(familiaSel.tipo_dimensional)}</label>
                    <PolegadaAutocomplete
                      value={form.polegada_secundaria_ref_id ?? null}
                      onChange={(id) => f('polegada_secundaria_ref_id', id)}
                      tipoMedida={tipoMedidaSecundaria}
                      allowCreate
                    />
                  </div>
                )}
              </>
            )}
            <div className="rounded-md border border-dashed border-border p-3 bg-background">
              <p className="text-xs font-semibold text-foreground">Prévia do produto</p>
              <p className="text-xs text-muted-foreground mt-1">Código sugerido</p>
              <p className="font-mono font-semibold text-lg mt-1">{previewCodigo || '—'}</p>
              {previewCodigoDuplicado ? (
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                  Status: já existe produto com este código.
                </p>
              ) : null}
              {(previewNcm || previewUnidade) && (
                <p className="text-xs text-muted-foreground mt-1">
                  NCM efetivo: {previewNcm || '—'} | Unidade efetiva: {previewUnidade || '—'}
                </p>
              )}
              <p className="text-xs text-muted-foreground mt-2">Descrição sugerida</p>
              {previewMsg ? <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">{previewMsg}</p> : null}
              {previewDesc ? (
                <div className="mt-2">
                  <p className="text-sm">{previewDesc}</p>
                  <button type="button" className="erp-btn-outline erp-btn-sm mt-2" onClick={aplicarDescricaoPreview}>
                    Usar descrição sugerida
                  </button>
                </div>
              ) : !previewMsg ? (
                <p className="text-xs text-muted-foreground mt-1">Preencha os campos obrigatórios da família para ver código e descrição.</p>
              ) : null}
            </div>
          </div>
        )}

        {modo === 'MANUAL' && (
          <div className="mb-4">
            <label className="erp-label">Código manual / fabricante</label>
            <input
              className="erp-input mt-1 font-mono"
              value={form.codigo_completo}
              onChange={(e) => f('codigo_completo', e.target.value)}
              placeholder="Ex.: AV4000-F04-4DZ"
            />
            <p className="text-xs text-muted-foreground mt-1">Não será gerado código automaticamente. Preencha a descrição manualmente.</p>
          </div>
        )}

        {modo === 'LEGADO' && (
          <div className="mb-4 p-3 rounded-md border border-border bg-muted/20">
            <p className="text-xs text-muted-foreground mb-2">
              Cadastro legado: apenas segmentos preenchidos entram no código (sem reticências).
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="erp-label">Figura</label>
                <input className="erp-input mt-1" value={form.figura} onChange={(e) => f('figura', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Sufixo (texto livre)</label>
                <input className="erp-input mt-1" value={form.sufixo} onChange={(e) => f('sufixo', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Schedule (texto livre)</label>
                <input className="erp-input mt-1" value={form.schedule} onChange={(e) => f('schedule', e.target.value)} />
              </div>
              <div className="md:col-span-3">
                <label className="erp-label">Polegada principal (texto)</label>
                <input className="erp-input mt-1" value={form.polegada_principal} onChange={(e) => f('polegada_principal', e.target.value)} />
              </div>
              <div className="md:col-span-3">
                <label className="erp-label">Polegada secundária (texto)</label>
                <input className="erp-input mt-1" value={form.polegada_secundaria} onChange={(e) => f('polegada_secundaria', e.target.value)} />
              </div>
            </div>
            <p className="text-xs mt-2 font-mono">
              Prévia: <span className="font-bold">{genCodigoLegadoPreview(form) || '—'}</span>
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-3">
            <label className="erp-label">Descrição</label>
            <input className="erp-input mt-1" value={form.descricao} onChange={(e) => f('descricao', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Material</label>
            <select className="erp-select mt-1 w-full" value={form.material} onChange={(e) => f('material', e.target.value)}>
              {MATERIAIS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Tipo de Peça</label>
            <input className="erp-input mt-1" value={form.tipo_peca} onChange={(e) => f('tipo_peca', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Pressão Nominal</label>
            <input className="erp-input mt-1" value={form.pressao_nominal} onChange={(e) => f('pressao_nominal', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Norma</label>
            <input className="erp-input mt-1" value={form.norma} onChange={(e) => f('norma', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Conexão (texto livre)</label>
            <input className="erp-input mt-1" value={form.conexao} onChange={(e) => f('conexao', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">NCM (override opcional)</label>
            <NcmAutocomplete
              value={ncmProdutoOption}
              onChange={(opt) => {
                setNcmProdutoOption(opt);
                f('ncm', opt?.codigo || '');
              }}
              searchNcm={(term, limit) => ncmApiService.search(term, limit)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              NCM efetivo: {form.ncm || familiaSel?.ncm_padrao_info?.codigo || 'NÃO DEFINIDO'} | Origem: {form.ncm ? 'produto' : (familiaSel?.ncm_padrao_id ? 'familia' : 'nao_definido')}
            </p>
            {form.ncm ? (
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm mt-2"
                onClick={() => {
                  f('ncm', '');
                  setNcmProdutoOption(null);
                }}
              >
                Usar padrão da família
              </button>
            ) : (
              <p className="text-xs text-muted-foreground mt-2">
                Usando valor da família. Preencha o campo para sobrescrever neste produto.
              </p>
            )}
          </div>
          <div>
            <label className="erp-label">Unidade</label>
            <input className="erp-input mt-1" value={form.unidade || ''} onChange={(e) => f('unidade', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">NCM específico (legado)</label>
            <input className="erp-input mt-1" value={form.ncm_especifico || ''} onChange={(e) => f('ncm_especifico', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Unidade específica (override)</label>
            <input className="erp-input mt-1" value={form.unidade_especifica || ''} onChange={(e) => f('unidade_especifica', e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Preço Custo</label>
            <input type="number" step="0.01" className="erp-input mt-1" value={form.preco_custo} onChange={(e) => f('preco_custo', +e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Preço Venda</label>
            <input type="number" step="0.01" className="erp-input mt-1" value={form.preco_venda} onChange={(e) => f('preco_venda', +e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Estoque Mínimo</label>
            <input type="number" className="erp-input mt-1" value={form.estoque_minimo} onChange={(e) => f('estoque_minimo', +e.target.value)} />
          </div>
        </div>
        <ConversaoMedidasBlock
          usaConversao={!!form.usa_conversao_dimensional}
          onUsaConversaoChange={(v) => f('usa_conversao_dimensional', v)}
          tipoFisicoEfetivo={tipoFisicoEfetivo}
          tipoFisicoProduto={form.tipo_fisico || ''}
          onTipoFisicoProdutoChange={(v) => f('tipo_fisico', v)}
          tipoControleProduto={form.tipo_controle_unidade || ''}
          onTipoControleProdutoChange={(v) => f('tipo_controle_unidade', v)}
          unidadeEstoque={form.unidade_estoque || ''}
          onUnidadeEstoqueChange={(v) => f('unidade_estoque', v)}
          unidadeVenda={form.unidade_venda_padrao || ''}
          onUnidadeVendaChange={(v) => f('unidade_venda_padrao', v)}
          unidadeCompra={form.unidade_compra_padrao || ''}
          onUnidadeCompraChange={(v) => f('unidade_compra_padrao', v)}
          unidadeFiscal={form.unidade_fiscal || ''}
          onUnidadeFiscalChange={(v) => f('unidade_fiscal', v)}
          unidadesVenda={form.unidades_venda_permitidas || []}
          onUnidadesVendaChange={(list) => f('unidades_venda_permitidas', list)}
          unidadesCompra={form.unidades_compra_permitidas || []}
          onUnidadesCompraChange={(list) => f('unidades_compra_permitidas', list)}
          familiaUnidadesVenda={familiaSel?.unidades_venda_permitidas}
          familiaUnidadesCompra={familiaSel?.unidades_compra_permitidas}
          comprimentoBarra={form.comprimento_padrao_barra_m ?? null}
          onComprimentoBarraChange={(v) => f('comprimento_padrao_barra_m', v)}
          pesoMetro={form.peso_por_metro_kg ?? null}
          onPesoMetroChange={(v) => f('peso_por_metro_kg', v)}
          pesoPeca={form.peso_por_peca_kg ?? null}
          onPesoPecaChange={(v) => f('peso_por_peca_kg', v)}
          pesoChapa={form.peso_por_chapa_kg ?? null}
          onPesoChapaChange={(v) => f('peso_por_chapa_kg', v)}
          densidade={form.densidade ?? null}
          onDensidadeChange={(v) => f('densidade', v)}
          observacoes={form.observacoes_conversao || ''}
          onObservacoesChange={(v) => f('observacoes_conversao', v)}
          heranca={familiaSel ? herancaConv : undefined}
        />
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
            Cancelar
          </button>
          <button type="button" onClick={handleSave} className="erp-btn-primary">
            Salvar
          </button>
        </div>
      </Modal>

      <Modal isOpen={famModalOpen} onClose={() => setFamModalOpen(false)} title={editingFamilia ? 'Editar família / figura' : 'Nova família / figura'} size="lg">
        {famSaveErr && <p className="text-sm text-destructive mb-2">{famSaveErr}</p>}
        {familiaDuplicada && (
          <div className="mb-3 rounded-md border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 p-3">
            <p className="text-xs text-amber-900 dark:text-amber-100">
              Família já cadastrada:
              {' '}
              <span className="font-mono font-semibold">{familiaDuplicada.codigo_figura}</span>
              {' — '}
              {familiaDuplicada.descricao_base}
            </p>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm mt-2"
              onClick={() => usarFamiliaExistente(familiaDuplicada)}
            >
              Usar família existente em Novo Produto
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm mt-2 ml-2"
              onClick={() => {
                setActiveTab('familias');
                setSearch(familiaDuplicada.codigo_figura);
                setFamModalOpen(false);
              }}
            >
              Ver família existente
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm mt-2 ml-2"
              onClick={() => openEditFamilia(familiaDuplicada)}
            >
              Editar família existente
            </button>
          </div>
        )}
        <div className="space-y-4">
          <div className="rounded-md border border-border p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Identificação</p>
            <div>
            <label className="erp-label">Código figura / base</label>
            <input className="erp-input mt-1 font-mono" value={famQuick.codigo_figura} onChange={(e) => setFamQuick((q) => ({ ...q, codigo_figura: e.target.value }))} />
            </div>
            <div className="mt-3">
            <label className="erp-label">Descrição base</label>
            <input className="erp-input mt-1" value={famQuick.descricao_base} onChange={(e) => setFamQuick((q) => ({ ...q, descricao_base: e.target.value }))} />
            </div>
            {famQuick.descricao_base.trim().length >= 2 ? (
              <div className="mt-3 rounded-md border border-dashed border-border bg-muted/20 p-3 text-xs space-y-2">
                <p className="font-semibold text-foreground">Sugestão automática</p>
                <p>
                  Categoria:{' '}
                  {sugestaoFamiliaAuto.categoria_produto === 'MATERIAL_DIMENSIONAL'
                    ? 'Material dimensional'
                    : sugestaoFamiliaAuto.categoria_produto === 'MANUAL_FABRICANTE'
                      ? 'Produto manual/fabricante'
                      : 'Produto técnico'}
                </p>
                <p>Tipo dimensional: {sugestaoFamiliaAuto.tipo_dimensional}</p>
                <p>Regra de código: {sugestaoFamiliaAuto.tipo_regra_codigo}</p>
                <p>Campos que o produto vai pedir: {sugestaoFamiliaAuto.campos_obrigatorios_labels.join(' · ')}</p>
                {sugestaoFamiliaAuto.observacao ? <p className="text-muted-foreground">{sugestaoFamiliaAuto.observacao}</p> : null}
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  onClick={() => {
                    setFamQuick((q) => ({
                      ...q,
                      categoria_produto: sugestaoFamiliaAuto.categoria_produto,
                      tipo_dimensional: sugestaoFamiliaAuto.tipo_dimensional,
                      tipo_regra_codigo: sugestaoFamiliaAuto.tipo_regra_codigo,
                    }));
                  }}
                >
                  Aplicar sugestão
                </button>
              </div>
            ) : null}
            <div className="mt-3">
            <label className="erp-label">NCM padrão</label>
            <NcmAutocomplete
              value={ncmFamiliaOption}
              onChange={(opt) => {
                setNcmFamiliaOption(opt);
                setFamQuick((q) => ({ ...q, ncm_padrao: opt?.id ?? null }));
              }}
              searchNcm={(term, limit) => ncmApiService.search(term, limit)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Se não encontrar resultados, verifique se a lista TIPI/NCM foi importada.
            </p>
            </div>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Classificação</p>
            <div>
              <label className="erp-label">Categoria do produto</label>
              <select
                className="erp-select mt-1 w-full"
                value={famQuick.categoria_produto}
                onChange={(e) => {
                  const categoria = e.target.value as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';
                  setFamQuick((q) => {
                    const nextTipo = categoria === 'MANUAL_FABRICANTE' ? 'MANUAL' : q.tipo_dimensional;
                    const nextRegra = categoria === 'MANUAL_FABRICANTE' ? 'MANUAL_FABRICANTE' : sugerirTipoRegraPorDimensional(nextTipo);
                    return { ...q, categoria_produto: categoria, tipo_dimensional: nextTipo, tipo_regra_codigo: nextRegra };
                  });
                }}
              >
                {CATEGORIAS_FAMILIA.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="mt-3">
              <label className="erp-label">Tipo dimensional</label>
              <select
                className="erp-select mt-1 w-full"
                value={famQuick.tipo_dimensional}
                onChange={(e) => {
                  const td = e.target.value as TipoDimensional;
                  setFamQuick((q) => ({ ...q, tipo_dimensional: td, tipo_regra_codigo: sugerirTipoRegraPorDimensional(td) }));
                }}
              >
                {tiposDimensionaisPorCategoria.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground mt-1">{hintTipoDimensional(famQuick.tipo_dimensional)}</p>
            </div>
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Regra e campos do produto</p>
            <div>
            <label className="erp-label">Regra de código</label>
            <select
              className="erp-select mt-1 w-full"
              value={famQuick.tipo_regra_codigo}
              onChange={(e) => setFamQuick((q) => ({ ...q, tipo_regra_codigo: e.target.value as TipoRegraCodigo }))}
            >
              {REGRAS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-3">
            <label className="erp-label">Separador base → medidas</label>
            <input
              className="erp-input mt-1 w-16 font-mono"
              maxLength={1}
              value={famQuick.separador_base_medidas}
              onChange={(e) => setFamQuick((q) => ({ ...q, separador_base_medidas: e.target.value.slice(-1) || '.' }))}
            />
            <p className="text-xs text-muted-foreground mt-1">Em UNDERSCORE_POLEGADA o código usa &quot;_&quot; fixo; o separador acima afeta demais regras com ponto.</p>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-3 text-sm space-y-1 mt-3">
            <p className="font-medium text-foreground">Campos exigidos no produto (regra de código)</p>
            <p className="text-muted-foreground">{labelsCamposObrigatorios(famQuickFlags, famQuick.tipo_dimensional).join(' · ')}</p>
            <p className="text-xs text-muted-foreground mt-1">
              O tipo dimensional combina com a regra no cadastro de produto (validação no servidor). {hintTipoDimensional(famQuick.tipo_dimensional)}
            </p>
            <ul className="text-xs text-muted-foreground grid grid-cols-2 gap-x-3 gap-y-0.5 mt-2 font-mono">
              <li>Rosca: {famQuickFlags.usa_rosca_conexao ? 'sim' : 'não'}</li>
              <li>Schedule: {famQuickFlags.usa_schedule ? 'sim' : 'não'}</li>
              <li>Polegada 1: {famQuickFlags.usa_polegada_principal ? 'sim' : 'não'}</li>
              <li>Polegada 2: {famQuickFlags.usa_polegada_secundaria ? 'sim' : 'não'}</li>
            </ul>
          </div>
          <div className="rounded-md border border-dashed border-border bg-background p-3 text-xs text-muted-foreground mt-3">
            <p className="font-semibold text-foreground mb-1">Prévia de cadastro da família</p>
            <p>Categoria: {CATEGORIAS_FAMILIA.find((c) => c.value === famQuick.categoria_produto)?.label}</p>
            <p>Tipo: {famQuick.tipo_dimensional}</p>
            <p>Produto vai pedir: {labelsCamposObrigatorios(famQuickFlags, famQuick.tipo_dimensional).join(' · ')}</p>
            <p className="mt-1">Exemplo de código: {famQuick.codigo_figura || 'FIG'}.{famQuick.tipo_dimensional === 'NPS_SCHEDULE' ? '20.XX' : '...'}</p>
            <p>Exemplo de descrição: {expandirSiglasValvulaDescricaoBase(famQuick.descricao_base || 'DESCRIÇÃO BASE')} …</p>
          </div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-4">
          <span className="font-medium text-foreground">Conversão de medidas</span> — unidades comerciais (PC, KG, TON…). Não
          substituem bitolas NPS/OD nem schedule escolhidos no cadastro do produto.
        </p>
        <ConversaoMedidasBlock
          usaConversao={!!famQuick.usa_conversao_dimensional}
          onUsaConversaoChange={(v) => setFamQuick((q) => ({ ...q, usa_conversao_dimensional: v }))}
          tipoFisicoEfetivo={(famQuick.tipo_fisico || 'PECA') as string}
          tipoFisicoProduto={famQuick.tipo_fisico || ''}
          onTipoFisicoProdutoChange={(v) => setFamQuick((q) => ({ ...q, tipo_fisico: v as TipoFisicoProduto | '' }))}
          tipoControleProduto={famQuick.tipo_controle_unidade || ''}
          onTipoControleProdutoChange={(v) => setFamQuick((q) => ({ ...q, tipo_controle_unidade: v as TipoControleUnidade | '' }))}
          unidadeEstoque={famQuick.unidade_estoque_padrao || ''}
          onUnidadeEstoqueChange={(v) => setFamQuick((q) => ({ ...q, unidade_estoque_padrao: v }))}
          unidadeVenda={famQuick.unidade_venda_padrao || ''}
          onUnidadeVendaChange={(v) => setFamQuick((q) => ({ ...q, unidade_venda_padrao: v }))}
          unidadeCompra={famQuick.unidade_compra_padrao || ''}
          onUnidadeCompraChange={(v) => setFamQuick((q) => ({ ...q, unidade_compra_padrao: v }))}
          unidadeFiscal={famQuick.unidade_fiscal_padrao || ''}
          onUnidadeFiscalChange={(v) => setFamQuick((q) => ({ ...q, unidade_fiscal_padrao: v }))}
          unidadesVenda={famQuick.unidades_venda_permitidas || []}
          onUnidadesVendaChange={(list) => setFamQuick((q) => ({ ...q, unidades_venda_permitidas: list }))}
          unidadesCompra={famQuick.unidades_compra_permitidas || []}
          onUnidadesCompraChange={(list) => setFamQuick((q) => ({ ...q, unidades_compra_permitidas: list }))}
          comprimentoBarra={famQuick.comprimento_padrao_barra_m ?? null}
          onComprimentoBarraChange={(v) => setFamQuick((q) => ({ ...q, comprimento_padrao_barra_m: v }))}
          pesoMetro={famQuick.peso_por_metro_kg ?? null}
          onPesoMetroChange={(v) => setFamQuick((q) => ({ ...q, peso_por_metro_kg: v }))}
          pesoPeca={famQuick.peso_por_peca_kg ?? null}
          onPesoPecaChange={(v) => setFamQuick((q) => ({ ...q, peso_por_peca_kg: v }))}
          pesoChapa={famQuick.peso_por_chapa_kg ?? null}
          onPesoChapaChange={(v) => setFamQuick((q) => ({ ...q, peso_por_chapa_kg: v }))}
          densidade={famQuick.densidade ?? null}
          onDensidadeChange={(v) => setFamQuick((q) => ({ ...q, densidade: v }))}
          observacoes={famQuick.observacoes_conversao || ''}
          onObservacoesChange={(v) => setFamQuick((q) => ({ ...q, observacoes_conversao: v }))}
          rotulos={{ limparUnidades: 'Limpar seleção' }}
        />
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" className="erp-btn-outline" onClick={() => setFamModalOpen(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void salvarFamiliaRapida()}>
            {editingFamilia ? 'Salvar alterações' : 'Salvar família'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default Produtos;
