import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  ChevronDown,
  DollarSign,
  FileText,
  Gauge,
  Info,
  Layers,
  Link2,
  Lock,
  Package,
  Ruler,
  ShieldCheck,
  SlidersHorizontal,
  Wrench,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { DecimalPtBrInput } from '@/components/produtos/DecimalPtBrInput';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import { ConversaoMedidasBlock } from '@/components/produtos/ConversaoMedidasBlock';
import { ProdutoComposicaoPanel } from '@/components/produtos/ProdutoComposicaoPanel';
import { ncmApiService, roscasConexaoService, schedulesEspessuraService } from '@/services/api/produtos';
import type {
  FamiliaProduto,
  Produto,
  RequisitosProdutoDimensionais,
  RoscaConexao,
  ScheduleEspessura,
  TipoControleUnidade,
  TipoFisicoProduto,
} from '@/types';
import type { Material, MaterialCategoria } from '@/types/material';
import type { ModoCodigoProduto, ProdutoFormState } from '../types';
import {
  estaHerdadoDaFamilia,
  valorFamiliaParaCampo,
  valoresConversaoHerdados,
  valoresConversaoProduto,
  type CampoHerancaVisivel,
} from '../lib/herancaFamilia';
import {
  getAtributosTecnicosFamilia,
  getFamReq,
  getLabelCampoEspessuraOuMenor,
  getLabelCampoOdPrincipal,
  getTdAtual,
  getUsaDimensoesMateriais,
} from '../lib/familiaDerivations';
import { campoId, classeErroCampo, type CampoFormProdutoInvalido } from '../lib/erroCampo';
import { resolverTipoMedida } from '../lib/tipoMedidaPolegada';
import {
  labelPolegadaPrincipal,
  labelPolegadaSecundaria,
  tipoMedidaPrincipalPorDimensional,
  tipoMedidaSecundariaPorDimensional,
} from '@/lib/familiaRegra';
import { etiquetaRosca } from '@/lib/roscaLabel';

/* -------------------------------------------------------------------------- */
/* Rótulos e helpers de apresentação                                          */
/* -------------------------------------------------------------------------- */

/** Asterisco de campo obrigatório (design system C: span text-destructive). */
function Obrigatorio() {
  return (
    <span className="text-destructive" aria-hidden>
      {' '}
      *
    </span>
  );
}

/** Rótulo de campo padronizado (text-sm font-medium mb-1.5). */
function CampoLabel({ children }: { children: ReactNode }) {
  return <Label className="text-sm font-medium mb-1.5 block">{children}</Label>;
}

/** Rótulos do bloco 'Tipo de cadastro' — valem para o RadioGroup e para a ficha read-only. */
const ROTULO_TIPO_CADASTRO: Record<ModoCodigoProduto, string> = {
  INTERNO: 'Código interno por regra (família / figura)',
  MANUAL: 'Código manual / fabricante',
  LEGADO: 'Legado (campos texto livres)',
};

/** Campo somente leitura do tipo texto: mesma célula de grid do controle que ele imita. */
function CampoLeitura({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <CampoLabel>{label}</CampoLabel>
      <Input className="h-10 bg-muted/40" value={value} disabled readOnly />
    </div>
  );
}

/** Preço em pt-BR com duas casas; quantidade em até 3 casas sem zeros forçados. */
function formatMoeda(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatQuantidade(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

/** Rótulos no plural para agrupar o dropdown de Material por categoria. */
const MATERIAL_GRUPO_LABELS: Record<MaterialCategoria, string> = {
  ACO_CARBONO: 'Aços Carbono',
  ACO_INOX: 'Aços Inox',
  FERRO_FUNDIDO: 'Ferros Fundidos',
  ACO_LIGA: 'Aços Liga',
  NAO_FERROSO: 'Não-ferrosos',
  POLIMERO: 'Polímeros',
  OUTRO: 'Outro',
};

const MATERIAL_GRUPO_ORDEM: MaterialCategoria[] = [
  'ACO_CARBONO',
  'ACO_INOX',
  'FERRO_FUNDIDO',
  'ACO_LIGA',
  'NAO_FERROSO',
  'POLIMERO',
  'OUTRO',
];

/**
 * Sentinela de "sem rosca" (Radix não aceita SelectItem com value=""). O rótulo antigo
 * prometia que a família resolvia o campo, mas `montar_codigo_interno` só lê
 * `produto.rosca_conexao` — sem rosca escolhida o segmento simplesmente não entra no código.
 */
const SEM_ROSCA = '__none__';
const SEM_ROSCA_LABEL = 'Sem rosca / conexão';

/** Campos da Família varridos na busca client-side do autocomplete de família. */
const CAMPOS_BUSCA_FAMILIA: readonly (keyof FamiliaProduto)[] = [
  'codigo_figura',
  'descricao_base',
  'material_base',
  'norma_base',
  'pressao_base',
];

function normalizarParaBusca(valor: string): string {
  return valor
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

/** Rótulo humano de cada campo que a herança da família preencheu. */
const ROTULO_HERANCA: Record<CampoHerancaVisivel, string> = {
  material_ref: 'Material',
  tipo_peca: 'Tipo de peça',
  norma: 'Norma técnica',
  pressao_nominal: 'Pressão nominal',
  conexao: 'Conexão',
};

/* -------------------------------------------------------------------------- */
/* Props                                                                       */
/* -------------------------------------------------------------------------- */

interface ProdutoFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview?: { codigo?: string; descricao?: string; ncm?: string; mensagem?: string };
  familiaSelecionada?: FamiliaProduto | null;
  famReq?: RequisitosProdutoDimensionais | null;
  /** Catálogo de famílias do container: a busca do autocomplete é client-side. */
  familias?: FamiliaProduto[];
  /** Produto do payload — dá os rótulos resolvidos da leitura, os preços praticados e o painel de Composição. */
  produto?: Produto | null;
  /** Lista de produtos para o seletor de componentes da composição. */
  produtosOpcoes?: Array<{ id: number; codigo_completo: string; descricao: string }>;
  /** Catálogo de materiais (ativos) carregado pelo container — alimenta o dropdown. */
  materiais?: Material[];
  /** Indica que o catálogo de materiais ainda está carregando. */
  carregandoMateriais?: boolean;
  duplicateCodigo?: string | null;
  /** Só a Edição usa: em leitura o RadioGroup não é montado. */
  setModoCodigo?: (modo: ModoCodigoProduto) => void;
  /** Abre o fluxo de criação rápida de família (orquestrado na página container). */
  onNovaFamilia?: () => void;
  /** Código efetivo do produto em edição — fallback read-only quando o preview está vazio. */
  editingCodigo?: string | null;
  /** Campo apontado pela validação do salvar(): recebe o anel e a âncora de rolagem. */
  campoErro?: CampoFormProdutoInvalido | null;
  /** Campos técnicos preenchidos pela última herança aplicada da família. */
  herdouFamilia?: CampoHerancaVisivel[];
  /** 'Tipo de cadastro' do Painel Avançado é restrito a admin (decisão Sprint 3.7). */
  ehAdmin?: boolean;
  /** Ficha de Visualização: mesma tela, tudo desabilitado, sem ações e sem catálogo. */
  somenteLeitura?: boolean;
}

/* -------------------------------------------------------------------------- */
/* Componente                                                                  */
/* -------------------------------------------------------------------------- */

export function ProdutoFormTab({
  form,
  setForm,
  preview = {},
  familiaSelecionada = null,
  famReq = null,
  familias = [],
  produto = null,
  produtosOpcoes = [],
  materiais = [],
  carregandoMateriais = false,
  duplicateCodigo = null,
  setModoCodigo,
  onNovaFamilia,
  editingCodigo = null,
  campoErro = null,
  herdouFamilia = [],
  ehAdmin = false,
  somenteLeitura = false,
}: ProdutoFormTabProps) {
  const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;

  const [avancadoAberto, setAvancadoAberto] = useState(false);

  // Uma âncora de erro dentro do painel exige o painel aberto: colapsado, o conteúdo
  // nem está montado e o scrollIntoView da página não encontraria o campo.
  useEffect(() => {
    if (campoErro === 'diametro_mostrador_mm') setAvancadoAberto(true);
  }, [campoErro]);

  const handleInputChange = <K extends keyof ProdutoFormState>(
    key: K,
    value: ProdutoFormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  /* --- Família: busca client-side sobre o catálogo já carregado ------------ */
  // O backend só filtra por codigo_figura/descricao_base; "buscar por material, norma
  // ou pressão" precisa varrer os campos técnicos da família, então o filtro é local.
  const buscaFamilias = useCallback(
    async (term: string, limit?: number) => {
      const q = normalizarParaBusca(term);
      if (!q) return [];
      const hits = familias.filter((f) =>
        CAMPOS_BUSCA_FAMILIA.some((campo) => normalizarParaBusca(String(f[campo] ?? '')).includes(q)),
      );
      return typeof limit === 'number' ? hits.slice(0, limit) : hits;
    },
    [familias],
  );

  /* --- Derivações da família ------------------------------------------------ */
  const req = famReq ?? getFamReq(familiaSelecionada);
  const tdAtual = getTdAtual(familiaSelecionada);
  const usaDimensoesMateriais = getUsaDimensoesMateriais(familiaSelecionada);
  const labelOd = getLabelCampoOdPrincipal(familiaSelecionada);
  const labelEsp = getLabelCampoEspessuraOuMenor(familiaSelecionada);
  const atributosTecnicos = getAtributosTecnicosFamilia(familiaSelecionada);
  const familiaEhMaterialDimensional =
    familiaSelecionada?.categoria_produto === 'MATERIAL_DIMENSIONAL';

  const usaPolegadaPrincipal = !!req?.usa_polegada_principal;
  const usaPolegadaSecundaria = !!req?.usa_polegada_secundaria;
  // O filtro NPS/OD da busca vem da regra da família (espelho do backend), nunca de um
  // valor fixo na tela: forçar OD fazia um NPS salvo sumir e virar outra polegada no código.
  const tipoMedidaPrincipal = resolverTipoMedida(
    produto?.polegada_principal_ref_detalhes?.tipo_medida,
    tipoMedidaPrincipalPorDimensional(tdAtual),
  );
  const tipoMedidaSecundaria = resolverTipoMedida(
    produto?.polegada_secundaria_ref_detalhes?.tipo_medida,
    tipoMedidaSecundariaPorDimensional(tdAtual),
  );
  // OD/espessura/comprimento em mm são do produto técnico; em material dimensional a
  // medida da peça é o conjunto dim_*. O bloco de Medidas nunca mostra os dois.
  const mmDoProdutoVisiveis = !familiaEhMaterialDimensional && !usaDimensoesMateriais;

  const exigeRosca = !familiaEhMaterialDimensional && !!req?.usa_rosca_conexao;
  const exigeSchedule = !familiaEhMaterialDimensional && !!req?.usa_schedule;
  const exigeMedidasMm =
    mmDoProdutoVisiveis &&
    (!!req?.exige_diametro_interno_mm ||
      !!req?.exige_od_mm ||
      !!req?.exige_espessura_mm ||
      !!req?.exige_comprimento_mm);
  // Bloco 2 só aparece quando a família pede alguma medida — sem família (manual/legado)
  // o produto não tem molde e o bloco fica de fora.
  const mostrarBlocoMedidas =
    !!familiaSelecionada &&
    !!req &&
    (exigeRosca ||
      exigeSchedule ||
      usaPolegadaPrincipal ||
      usaPolegadaSecundaria ||
      exigeMedidasMm ||
      usaDimensoesMateriais ||
      atributosTecnicos.length > 0);

  /* --- Medidas travadas em produto do banco --------------------------------- */
  /**
   * Rosca, polegadas e mm entram no `codigo_completo` (o backend remonta o código a
   * cada save). Num SKU já criado, mexer neles é criar outro produto — a mudança
   * estrutural é rejeitada pelo model no caso Manômetro e silenciosa nos demais.
   * Admin pode liberar na ficha para corrigir um erro de cadastro.
   */
  const produtoSalvo = !!produto?.id;
  const [medidasLiberadas, setMedidasLiberadas] = useState(false);
  const medidasBloqueadas = !somenteLeitura && produtoSalvo && !medidasLiberadas;
  /** Como o Bloco 2 é desenhado: ficha em leitura, ou produto salvo com as medidas travadas. */
  const leituraMedidas = somenteLeitura || medidasBloqueadas;

  const liberarMedidas = () => {
    const ok = window.confirm(
      'Liberar a edição das medidas deste produto salvo?\n\n' +
        'Estes campos participam do código do produto: alterá-los passa a apontar para outro ' +
        'código e pode duplicar um SKU já vendido. Use apenas para corrigir erro de cadastro.',
    );
    if (ok) setMedidasLiberadas(true);
  };

  /* --- Identidade técnica (molde da família) -------------------------------- */
  const materialLeitura = produto?.material_nome ?? form.material ?? '';
  /**
   * Regra da rodada: a família é o molde. Com `material_base_ref` e o produto
   * repetindo esse padrão, o Material é leitura — editar daqui é editar a
   * família. Sem molde (família sem padrão, ou produto com material próprio),
   * o campo continua editável: trancar um override já salvo esconderia a
   * exceção em vez de mostrá-la.
   */
  const materialPadraoFamilia = familiaSelecionada?.material_base_ref ?? null;
  const materialHerdaMolde = estaHerdadoDaFamilia(
    familiaSelecionada,
    'material_ref',
    form.material_ref,
  );
  const materialBloqueadoPelaFamilia = !somenteLeitura && materialPadraoFamilia !== null && materialHerdaMolde;
  const materialInputBloqueado = somenteLeitura || materialBloqueadoPelaFamilia;
  const materialEdicao =
    form.material?.trim() || produto?.material_nome?.trim() || String(familiaSelecionada?.material_base ?? '').trim();
  const linhasIdentidade = (
    [
      { campo: 'norma' as const, label: 'Norma técnica' },
      { campo: 'pressao_nominal' as const, label: 'Pressão nominal' },
      { campo: 'tipo_peca' as const, label: 'Tipo de peça' },
    ]
  )
    .map(({ campo, label }) => ({ campo, label, valor: valorFamiliaParaCampo(familiaSelecionada, campo) }))
    .filter((linha) => linha.valor.length > 0);
  const materialVedacao = String(familiaSelecionada?.material_vedacao ?? '').trim();
  const mostrarIdentidadeTecnica =
    !somenteLeitura || materialLeitura.trim().length > 0 || linhasIdentidade.length > 0;

  /* --- Preços e estoque ----------------------------------------------------- */
  // Última compra/venda e estoque atual só existem no payload da ficha.
  const mostrarPraticados = !!produto;

  /* --- Fiscal --------------------------------------------------------------- */
  const ncmInfoPayload = produto?.ncm_efetivo ?? null;
  const ncmCodigo =
    ncmInfoPayload?.codigo || form.ncm || familiaSelecionada?.ncm_padrao_info?.codigo || '';
  const ncmDescricao = ncmInfoPayload?.descricao || familiaSelecionada?.ncm_padrao_info?.descricao || '';
  const ncmOrigem = form.ncm
    ? 'override no produto'
    : familiaSelecionada?.ncm_padrao_id
    ? 'família / figura'
    : 'não definido';

  const [ncmProdutoOption, setNcmProdutoOption] = useState<NcmOption | null>(null);
  // Inicializa o autocomplete com o NCM salvo no produto; em leitura nada é editável.
  useEffect(() => {
    if (!form.ncm || somenteLeitura) {
      setNcmProdutoOption(null);
      return;
    }
    if (ncmProdutoOption?.codigo === form.ncm) return;
    ncmApiService
      .search(form.ncm, 1)
      .then((results) => {
        const match = results.find((o) => o.codigo === form.ncm);
        setNcmProdutoOption(match ?? null);
      })
      .catch(() => setNcmProdutoOption(null));
    // ncmProdutoOption intencionalmente omitido: só re-executa quando o código muda,
    // não quando a opção interna é atualizada por este mesmo efeito.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.ncm, somenteLeitura]);

  const ncmHerdadoDaFamilia = !!familiaSelecionada?.ncm_padrao_info?.codigo
    && familiaSelecionada.ncm_padrao_info.codigo === form.ncm;
  const mostrarOverrideNcm = !somenteLeitura || !!form.ncm;

  /* --- Catálogos usados só pela Edição -------------------------------------- */
  const materiaisAgrupados = MATERIAL_GRUPO_ORDEM.map((categoria) => ({
    categoria,
    label: MATERIAL_GRUPO_LABELS[categoria],
    itens: materiais.filter((m) => m.categoria === categoria),
  })).filter((grupo) => grupo.itens.length > 0);

  // Schedule: option controlada (não fixa em null) — resolve o id salvo para exibir rótulo.
  const [scheduleOption, setScheduleOption] = useState<ScheduleEspessura | null>(null);
  useEffect(() => {
    let ativo = true;
    const id = form.schedule_ref_id;
    if (!id || somenteLeitura) {
      setScheduleOption(null);
      return;
    }
    if (scheduleOption?.id === id) return;
    void schedulesEspessuraService
      .getAll()
      .then((list) => {
        if (!ativo) return;
        setScheduleOption(list.find((s) => s.id === id) ?? null);
      })
      .catch(() => {
        if (ativo) setScheduleOption(null);
      });
    return () => {
      ativo = false;
    };
  }, [form.schedule_ref_id, scheduleOption?.id, somenteLeitura]);

  // Rosca/conexão: lista pequena e estática — carregada uma vez por montagem.
  const [roscas, setRoscas] = useState<RoscaConexao[]>([]);
  useEffect(() => {
    if (leituraMedidas || !exigeRosca) {
      setRoscas([]);
      return;
    }
    let ativo = true;
    void roscasConexaoService
      .getAll()
      .then((list) => {
        if (ativo) setRoscas(list);
      })
      .catch(() => {
        if (ativo) setRoscas([]);
      });
    return () => {
      ativo = false;
    };
  }, [leituraMedidas, exigeRosca]);

  // Rótulos que só o payload da ficha traz: em leitura não se abre catálogo.
  const roscaTexto = (() => {
    const rotulo = etiquetaRosca(produto?.rosca_conexao_detalhes);
    return rotulo || SEM_ROSCA_LABEL;
  })();
  const scheduleTexto = (() => {
    const s = produto?.schedule_ref_detalhes;
    if (!s) return '—';
    return `${s.codigo || s.codigo_schedule} — ${s.descricao || s.codigo_schedule}`;
  })();
  /** Formato amigável: `1/2"` em vez do `nome` técnico 'NPS 1/2 — 1/2"'. */
  const textoPolegada = (p?: Produto['polegada_principal_ref_detalhes']) => {
    if (!p) return '—';
    const oficial = p.codigo_oficial || p.codigo;
    return oficial ? `${oficial}"` : p.descricao;
  };

  const getAtributoTecnico = (key: string): string => {
    const value = form.dimensoes_json?.[key];
    return value == null ? '' : String(value);
  };
  const setAtributoTecnico = (key: string, value: string) => {
    setForm((prev) => ({
      ...prev,
      dimensoes_json: { ...(prev.dimensoes_json || {}), [key]: value },
    }));
  };

  /* --- Gates dos cards do Painel Avançado ---------------------------------- */
  const conversao = familiaSelecionada
    ? valoresConversaoHerdados(form, familiaSelecionada)
    : valoresConversaoProduto(form);
  // Com família só aparece quando o molde usa conversão/composição; sem família o
  // produto é dono das próprias unidades e o card continua acessível.
  const mostrarConversao =
    !familiaSelecionada ||
    conversao.usaConversao ||
    conversao.controlaComposicaoFisica ||
    conversao.observacoes.trim().length > 0;

  const exigeCertificadoEfetivo =
    !!form.exige_certificado_qualidade || !!familiaSelecionada?.exige_certificado_qualidade;
  const mostrarQualidade = !familiaSelecionada || exigeCertificadoEfetivo;
  const mostrarManometro = tdAtual === 'MANOMETRO';
  const mostrarLegado = modo === 'LEGADO';
  const mostrarComposicao = !!produto?.id;

  // 'Tipo de peça' e 'Conexão' são texto livre: só têm valor aqui quando a família não
  // traz o padrão (hoje 0/117 famílias) ou quando o produto já carrega um valor salvo.
  const padraoFamiliaTipoPeca = valorFamiliaParaCampo(familiaSelecionada, 'tipo_peca');
  const padraoFamiliaConexao = valorFamiliaParaCampo(familiaSelecionada, 'conexao');
  const valorSalvoTipoPeca = (form.tipo_peca || '').trim();
  const valorSalvoConexao = (form.conexao || '').trim();
  const mostrarCamposTecnicosLivres =
    valorSalvoTipoPeca.length > 0 ||
    valorSalvoConexao.length > 0 ||
    (!somenteLeitura && (!padraoFamiliaTipoPeca || !padraoFamiliaConexao));

  const rotulosHerdados = useMemo(
    () => herdouFamilia.map((c) => ROTULO_HERANCA[c]).join(', '),
    [herdouFamilia],
  );

  return (
    <div className="space-y-6">
      {/* ============================= BLOCO 1 — Identificação ============================ */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Identificação</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Família/Figura, código e descrição do produto
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Família — o molde do produto; a busca varre código, descrição e campos técnicos. */}
          {modo === 'INTERNO' && (
            <div id={campoId('familia_id')} className={classeErroCampo(campoErro, 'familia_id')}>
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <Label className="text-sm font-medium">
                  Família / figura
                  <Obrigatorio />
                </Label>
                {!somenteLeitura && onNovaFamilia && (
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm"
                    onClick={onNovaFamilia}
                  >
                    + Nova família
                  </button>
                )}
              </div>
              <AsyncAutocomplete<FamiliaProduto>
                value={form.familia_id ?? null}
                selectedOption={familiaSelecionada}
                placeholder="Digite código, descrição, material, norma ou pressão..."
                disabled={somenteLeitura}
                search={buscaFamilias}
                getOptionValue={(opt) => opt.id}
                getOptionLabel={(opt) => `${opt.codigo_figura} — ${opt.descricao_base}`}
                onChange={(val) => {
                  const id = typeof val === 'number' ? val : null;
                  handleInputChange('familia_id', id);
                }}
              />
            </div>
          )}

          {/* Código — varia conforme o modo de cadastro (restrito ao Painel Avançado) */}
          {modo === 'MANUAL' && (
            <div>
              <CampoLabel>Código manual / fabricante</CampoLabel>
              <Input
                className="font-mono h-10"
                value={form.codigo_completo}
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('codigo_completo', e.target.value)}
                placeholder="Ex.: AV4000-F04-4DZ"
              />
              {duplicateCodigo && (
                <p className="text-xs text-destructive mt-1">
                  Já existe um produto cadastrado com o código "{duplicateCodigo}".
                </p>
              )}
            </div>
          )}

          {(modo === 'INTERNO' || modo === 'LEGADO') && (
            <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
              <Label className="text-sm font-medium">
                {modo === 'LEGADO' ? 'Código (prévia legado)' : 'Código'}
              </Label>
              <p className="font-mono font-semibold text-lg">
                {preview.codigo || editingCodigo || '—'}
              </p>
              {preview.mensagem && (
                <p className="text-xs text-amber-700 dark:text-amber-300">{preview.mensagem}</p>
              )}
              {duplicateCodigo && (
                <p className="text-xs text-destructive">Já existe produto com este código.</p>
              )}
            </div>
          )}

          {/* Descrição */}
          <div id={campoId('descricao')} className={classeErroCampo(campoErro, 'descricao')}>
            <CampoLabel>
              Descrição
              <Obrigatorio />
            </CampoLabel>
            <Input
              className="h-10"
              value={form.descricao}
              disabled={somenteLeitura}
              onChange={(e) => handleInputChange('descricao', e.target.value)}
              placeholder="Descrição do produto"
            />
            {!somenteLeitura && preview.descricao && preview.descricao !== form.descricao && (
              <button
                type="button"
                className="text-sm text-primary hover:underline mt-1 inline-block"
                onClick={() => handleInputChange('descricao', preview.descricao!)}
              >
                Usar descrição sugerida: {preview.descricao}
              </button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* --------- Identidade técnica: o que a família define, o produto apenas repete --------- */}
      {mostrarIdentidadeTecnica && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Identidade técnica</CardTitle>
              {familiaSelecionada && (
                <Badge variant="secondary">definido pela família</Badge>
              )}
            </div>
            <CardDescription className="text-xs">
              Material e padrões técnicos da Família/Figura {familiaSelecionada?.codigo_figura ?? ''}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {!somenteLeitura && herdouFamilia.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Herdados da família ao selecioná-la: {rotulosHerdados}
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div id={campoId('material_ref')} className={classeErroCampo(campoErro, 'material_ref')}>
                <CampoLabel>
                  Material
                  {!materialInputBloqueado && modo === 'INTERNO' && <Obrigatorio />}
                </CampoLabel>
                {materialInputBloqueado ? (
                  // material_nome já vem resolvido no payload: a ficha não carrega o catálogo.
                  <Input
                    className="h-10 bg-muted/40"
                    value={somenteLeitura ? materialLeitura : materialEdicao}
                    disabled
                    readOnly
                  />
                ) : (
                  <Select
                    value={form.material_ref?.toString() ?? ''}
                    onValueChange={(v) => {
                      const id = Number(v) || null;
                      const mat = id ? materiais.find((m) => m.id === id) : null;
                      setForm((prev) => ({
                        ...prev,
                        material_ref: id,
                        material: mat?.nome ?? prev.material,
                      }));
                    }}
                    disabled={carregandoMateriais}
                  >
                    <SelectTrigger className="w-full h-10">
                      <SelectValue
                        placeholder={carregandoMateriais ? 'Carregando materiais…' : 'Selecione...'}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {carregandoMateriais ? (
                        <div className="px-2 py-4 text-center text-xs text-muted-foreground">
                          Carregando catálogo de materiais…
                        </div>
                      ) : materiais.length === 0 ? (
                        <div className="px-2 py-4 text-center text-xs text-muted-foreground">
                          Nenhum material cadastrado.
                        </div>
                      ) : (
                        materiaisAgrupados.map((grupo) => (
                          <SelectGroup key={grupo.categoria}>
                            <SelectLabel>{grupo.label}</SelectLabel>
                            {grupo.itens.map((m) => (
                              <SelectItem key={m.id} value={m.id.toString()}>
                                {m.nome}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                )}
                {materialBloqueadoPelaFamilia && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Herdado da família {familiaSelecionada?.codigo_figura}. Para alterar, edite a família.
                  </p>
                )}
                {!materialInputBloqueado && materialPadraoFamilia !== null && (
                  <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                    Este produto usa material diferente do padrão da família.
                  </p>
                )}
              </div>
              {linhasIdentidade.map((linha) => (
                <CampoLeitura key={linha.campo} label={linha.label} value={linha.valor} />
              ))}
              {materialVedacao.length > 0 && (
                <CampoLeitura label="Material de vedação" value={materialVedacao} />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ============================= BLOCO 2 — Medidas ============================ */}
      {mostrarBlocoMedidas && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Ruler className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Medidas</CardTitle>
              <Badge variant="secondary">exigidas pela família</Badge>
            </div>
            <CardDescription className="text-xs">
              Dimensões e conexões que a Família/Figura {familiaSelecionada?.codigo_figura} pede
              para este produto
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {medidasBloqueadas && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-3 py-2">
                <p className="text-xs text-muted-foreground">
                  As medidas definem o código deste produto. Para um tamanho diferente, crie um novo produto.
                </p>
                {ehAdmin && (
                  <button type="button" className="erp-btn-outline erp-btn-sm" onClick={liberarMedidas}>
                    Liberar edição de medidas
                  </button>
                )}
              </div>
            )}
            {medidasLiberadas && !somenteLeitura && produtoSalvo && (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                Edição de medidas liberada: mudar estes campos faz o produto salvar com código
                diferente de {editingCodigo || 'atual'}.
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {exigeRosca && (
                <div>
                  <CampoLabel>
                    Rosca / conexão
                    {!leituraMedidas && !!req?.usa_rosca_conexao && <Obrigatorio />}
                  </CampoLabel>
                  {leituraMedidas ? (
                    <Input className="h-10 bg-muted/40" value={roscaTexto} disabled readOnly />
                  ) : (
                    <Select
                      value={form.rosca_conexao_id?.toString() ?? SEM_ROSCA}
                      onValueChange={(v) =>
                        handleInputChange('rosca_conexao_id', v === SEM_ROSCA ? null : Number(v))
                      }
                    >
                      <SelectTrigger className="w-full h-10">
                        <SelectValue placeholder="Selecione a rosca / conexão" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={SEM_ROSCA}>— {SEM_ROSCA_LABEL} —</SelectItem>
                        {roscas.map((r) => (
                          <SelectItem key={r.id} value={r.id.toString()}>
                            {etiquetaRosca(r)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
              )}

              {usaPolegadaPrincipal && (
                <div>
                  <CampoLabel>
                    {labelPolegadaPrincipal(tdAtual)}
                    {!leituraMedidas && <Obrigatorio />}
                  </CampoLabel>
                  {leituraMedidas ? (
                    <Input
                      className="h-10 bg-muted/40"
                      value={textoPolegada(produto?.polegada_principal_ref_detalhes)}
                      disabled
                      readOnly
                    />
                  ) : (
                    <PolegadaAutocomplete
                      value={form.polegada_principal_ref_id ?? null}
                      onChange={(id) => handleInputChange('polegada_principal_ref_id', id)}
                      tipoMedida={tipoMedidaPrincipal}
                      allowCreate
                      placeholder="Busque por código, polegada, decimal ou mm"
                    />
                  )}
                </div>
              )}

              {usaPolegadaSecundaria && (
                <div>
                  <CampoLabel>
                    {labelPolegadaSecundaria(tdAtual)}
                    {!leituraMedidas && <Obrigatorio />}
                  </CampoLabel>
                  {leituraMedidas ? (
                    <Input
                      className="h-10 bg-muted/40"
                      value={textoPolegada(produto?.polegada_secundaria_ref_detalhes)}
                      disabled
                      readOnly
                    />
                  ) : (
                    <PolegadaAutocomplete
                      value={form.polegada_secundaria_ref_id ?? null}
                      onChange={(id) => handleInputChange('polegada_secundaria_ref_id', id)}
                      tipoMedida={tipoMedidaSecundaria}
                      allowCreate
                      placeholder="Busque por código, polegada, decimal ou mm"
                    />
                  )}
                </div>
              )}

              {exigeSchedule && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Label className="text-sm font-medium">
                      Espessura da parede (schedule)
                      {!leituraMedidas && <Obrigatorio />}
                    </Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3.5 w-3.5 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent>
                          Busque por código, descrição ou aplicação (ex.: 10S, SCH 20, INOX).
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  {leituraMedidas ? (
                    <Input className="h-10 bg-muted/40" value={scheduleTexto} disabled readOnly />
                  ) : (
                    <AsyncAutocomplete<ScheduleEspessura>
                      value={form.schedule_ref_id ?? null}
                      selectedOption={scheduleOption}
                      placeholder="Digite código, descrição ou aplicação (ex.: 10S, SCH 20, INOX)"
                      search={async (term, limit) =>
                        schedulesEspessuraService.search(term, limit ?? 20)}
                      getOptionValue={(opt) => opt.id}
                      getOptionLabel={(opt) =>
                        `${opt.codigo || opt.codigo_schedule} — ${opt.descricao || opt.codigo_schedule}`}
                      onChange={(val, opt) => {
                        const id = typeof val === 'number' ? val : null;
                        handleInputChange('schedule_ref_id', id);
                        setScheduleOption(opt ?? null);
                      }}
                    />
                  )}
                </div>
              )}

              {mmDoProdutoVisiveis && !!req?.exige_diametro_interno_mm && (
                <div
                  id={campoId('diametro_interno_mm')}
                  className={classeErroCampo(campoErro, 'diametro_interno_mm')}
                >
                  <CampoLabel>
                    Diâmetro interno (mm)
                    {!leituraMedidas && <Obrigatorio />}
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 15 | 15,0"
                    value={form.diametro_interno_mm}
                    disabled={leituraMedidas}
                    onChange={(v) => handleInputChange('diametro_interno_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && !!req?.exige_od_mm && (
                <div id={campoId('od_mm')} className={classeErroCampo(campoErro, 'od_mm')}>
                  <CampoLabel>
                    {labelOd}
                    {!leituraMedidas && <Obrigatorio />}
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 10 | 10,0 | 1,5"
                    value={form.od_mm}
                    disabled={leituraMedidas}
                    onChange={(v) => handleInputChange('od_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && !!req?.exige_espessura_mm && (
                <div
                  id={campoId('espessura_mm')}
                  className={classeErroCampo(campoErro, 'espessura_mm')}
                >
                  <CampoLabel>
                    {labelEsp}
                    {!leituraMedidas && <Obrigatorio />}
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 2 | 2,0 | 1,5"
                    value={form.espessura_mm}
                    disabled={leituraMedidas}
                    onChange={(v) => handleInputChange('espessura_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && !!req?.exige_comprimento_mm && (
                <div
                  id={campoId('comprimento_mm')}
                  className={classeErroCampo(campoErro, 'comprimento_mm')}
                >
                  <CampoLabel>Comprimento (mm)</CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 6000"
                    value={form.comprimento_mm}
                    disabled={leituraMedidas}
                    onChange={(v) => handleInputChange('comprimento_mm', v)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Se vazio, pode usar o comprimento padrão da barra cadastrado na família.
                  </p>
                </div>
              )}
            </div>

            {/* Material dimensional: as medidas do material vivem no dimensoes_json e
                entram aqui — único lugar da tela onde Espessura/Comprimento aparecem. */}
            {usaDimensoesMateriais && (
              <div className="space-y-3 pt-3 border-t border-dashed border-border">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-foreground">
                    Dimensões do material (mm)
                  </p>
                  {tdAtual ? <Badge variant="secondary">tipo: {tdAtual}</Badge> : null}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                  <div>
                    <CampoLabel>Espessura (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 3,2"
                      value={form.dim_espessura_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_espessura_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Largura (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 1000"
                      value={form.dim_largura_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_largura_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Comprimento (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 2000"
                      value={form.dim_comprimento_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_comprimento_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Altura (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 50"
                      value={form.dim_altura_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_altura_mm', v)}
                    />
                  </div>
                  {/* Furo e Aba eram visíveis só na Visualização: sem eles aqui, a ficha
                      espelhada esconderia a medida do produto CHAPA_FURO_MM. */}
                  <div>
                    <CampoLabel>Furo (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 13,0"
                      value={form.dim_furo_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_furo_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Aba (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 40"
                      value={form.dim_aba_mm}
                      disabled={leituraMedidas}
                      onChange={(v) => handleInputChange('dim_aba_mm', v)}
                    />
                  </div>
                </div>
              </div>
            )}

            {atributosTecnicos.length > 0 && (
              <div className="space-y-3 pt-2">
                <p className="text-sm font-medium text-foreground">Atributos técnicos da Figura</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {atributosTecnicos.map(({ token, key, label, hint }) => (
                    <div key={token}>
                      <CampoLabel>
                        {label}
                        <code className="font-mono text-xs"> {token}</code>
                      </CampoLabel>
                      <Input
                        className="erp-input h-10"
                        value={getAtributoTecnico(key)}
                        disabled={leituraMedidas}
                        placeholder={hint}
                        onChange={(e) => setAtributoTecnico(key, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ========================== BLOCO 3 — Preços e Estoque ========================== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Preços e Estoque</CardTitle>
          </div>
          <CardDescription className="text-xs">
            O que a operação praticou (NF-e) é somente leitura; da tela do produto só se
            ajustam o estoque mínimo e a unidade comercial.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {mostrarPraticados && (
              <CampoLeitura
                label="Última Compra"
                value={formatMoeda(produto?.ultimo_preco_compra)}
              />
            )}
            {mostrarPraticados && (
              <CampoLeitura
                label="Última Venda"
                value={formatMoeda(produto?.ultimo_preco_venda)}
              />
            )}
            <CampoLeitura label="Preço Custo" value={formatMoeda(form.preco_custo)} />
            <CampoLeitura label="Preço Venda" value={formatMoeda(form.preco_venda)} />
            {mostrarPraticados && (
              <CampoLeitura label="Estoque Atual" value={formatQuantidade(produto?.estoque_atual)} />
            )}
            <div>
              <CampoLabel>Estoque Mínimo</CampoLabel>
              <DecimalPtBrInput
                className="h-10"
                value={form.estoque_minimo}
                disabled={somenteLeitura}
                onChange={(v) => handleInputChange('estoque_minimo', v ?? 0)}
                placeholder="0"
              />
            </div>
            <div>
              <CampoLabel>Unidade Comercial</CampoLabel>
              <Input
                className="h-10"
                value={form.unidade || ''}
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('unidade', e.target.value)}
                placeholder="Ex.: PC, KG, M"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ============================== BLOCO 4 — Fiscal ============================== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Fiscal</CardTitle>
            <Badge variant="secondary">somente leitura</Badge>
          </div>
          <CardDescription className="text-xs">
            NCM efetivo para NF-e — origem: {ncmOrigem}. CST/CSOSN e alíquotas são
            configurados no módulo fiscal, não no produto.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div>
              <CampoLabel>NCM efetivo</CampoLabel>
              <Input
                className="font-mono h-10 bg-muted/40"
                value={ncmCodigo || 'NÃO DEFINIDO'}
                disabled
                readOnly
              />
            </div>
            <div className="lg:col-span-2">
              <CampoLabel>Descrição do NCM</CampoLabel>
              <Input className="h-10 bg-muted/40" value={ncmDescricao} disabled readOnly />
            </div>
          </div>
          {familiaSelecionada?.ncm_padrao_info?.codigo && (
            <p className="text-xs text-muted-foreground">
              NCM padrão da família {familiaSelecionada.codigo_figura}:{' '}
              {familiaSelecionada.ncm_padrao_info.codigo}. Para usar outro, informe o override
              de NCM no Painel Avançado.
            </p>
          )}
        </CardContent>
      </Card>

      {/* ============================ PAINEL AVANÇADO ============================ */}
      <Card>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left"
          aria-expanded={avancadoAberto}
          onClick={() => setAvancadoAberto((aberto) => !aberto)}
        >
          <span className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
            <span className="text-base font-medium">Painel Avançado</span>
          </span>
          <span className="flex items-center gap-2">
            {!avancadoAberto && (
              <span className="text-xs text-muted-foreground">
                tipo de cadastro, legado, override fiscal, conversão, qualidade
              </span>
            )}
            <ChevronDown
              className={cn(
                'h-4 w-4 shrink-0 text-muted-foreground transition-transform',
                avancadoAberto && 'rotate-180',
              )}
            />
          </span>
        </button>

        {avancadoAberto && (
          <div className="space-y-6 border-t border-border p-6 pt-5">
            {/* --- Modo de cadastro + segmentos do código legado --- */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-base">Cadastro e código</CardTitle>
                </div>
                <CardDescription className="text-xs">
                  Tipo de cadastro e os segmentos texto do código legado. Mudar o tipo é
                  restrito ao administrador.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <CampoLabel>Tipo de cadastro</CampoLabel>
                  {!somenteLeitura && ehAdmin && setModoCodigo ? (
                    <RadioGroup
                      value={modo}
                      onValueChange={(v) => setModoCodigo(v as ModoCodigoProduto)}
                      className="flex flex-wrap gap-4 mt-1"
                    >
                      {(['INTERNO', 'MANUAL', 'LEGADO'] as ModoCodigoProduto[]).map((opcao) => (
                        <div key={opcao} className="flex items-center gap-2">
                          <RadioGroupItem value={opcao} id={`modo-${opcao.toLowerCase()}`} />
                          <Label
                            htmlFor={`modo-${opcao.toLowerCase()}`}
                            className="cursor-pointer font-normal"
                          >
                            {ROTULO_TIPO_CADASTRO[opcao]}
                          </Label>
                        </div>
                      ))}
                    </RadioGroup>
                  ) : (
                    <p className="text-sm font-medium mt-1">{ROTULO_TIPO_CADASTRO[modo]}</p>
                  )}
                </div>

                {mostrarLegado && (
                  <div className="space-y-3 pt-3 border-t border-dashed border-border">
                    {!somenteLeitura && (
                      <p className="text-xs text-muted-foreground">
                        Cadastro legado: apenas segmentos preenchidos entram no código (sem
                        reticências).
                      </p>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                      <div>
                        <CampoLabel>Figura</CampoLabel>
                        <Input
                          className="h-10"
                          value={form.figura || ''}
                          disabled={somenteLeitura}
                          onChange={(e) => handleInputChange('figura', e.target.value)}
                          placeholder="Ex.: 6119"
                        />
                      </div>
                      <div>
                        <CampoLabel>Sufixo (texto livre)</CampoLabel>
                        <Input
                          className="h-10"
                          value={form.sufixo || ''}
                          disabled={somenteLeitura}
                          onChange={(e) => handleInputChange('sufixo', e.target.value)}
                          placeholder="Ex.: F04"
                        />
                      </div>
                      <div>
                        <CampoLabel>Schedule (texto livre)</CampoLabel>
                        <Input
                          className="h-10"
                          value={form.schedule || ''}
                          disabled={somenteLeitura}
                          onChange={(e) => handleInputChange('schedule', e.target.value)}
                          placeholder="Ex.: 40"
                        />
                      </div>
                      <div>
                        <CampoLabel>Polegada principal (texto)</CampoLabel>
                        <Input
                          className="h-10"
                          value={form.polegada_principal || ''}
                          disabled={somenteLeitura}
                          onChange={(e) => handleInputChange('polegada_principal', e.target.value)}
                          placeholder='Ex.: 1 1/2"'
                        />
                      </div>
                      <div>
                        <CampoLabel>Polegada secundária (texto)</CampoLabel>
                        <Input
                          className="h-10"
                          value={form.polegada_secundaria || ''}
                          disabled={somenteLeitura}
                          onChange={(e) => handleInputChange('polegada_secundaria', e.target.value)}
                          placeholder='Ex.: 3/4"'
                        />
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* --- Fiscal: override e campos legados --- */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-base">Fiscal (avançado)</CardTitle>
                </div>
                <CardDescription className="text-xs">
                  Override de NCM e unidades de controle — use só quando este produto for
                  diferente da família.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {mostrarOverrideNcm && (
                  <div>
                    <CampoLabel>Override de NCM</CampoLabel>
                    {somenteLeitura ? (
                      <Input
                        className="font-mono h-10 bg-muted/40"
                        value={form.ncm || ''}
                        disabled
                        readOnly
                      />
                    ) : (
                      <>
                        <NcmAutocomplete
                          value={ncmProdutoOption}
                          onChange={(opt) => {
                            setNcmProdutoOption(opt);
                            handleInputChange('ncm', opt?.codigo || '');
                          }}
                          searchNcm={(term, limit) => ncmApiService.search(term, limit)}
                          placeholder="Digite código ou descrição do NCM..."
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Preencha para sobrescrever o NCM da família. Vazio = herda da
                          família/figura.
                        </p>
                        {form.ncm && !ncmHerdadoDaFamilia && (
                          <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                            Este produto usa NCM diferente do padrão da família.
                          </p>
                        )}
                        {form.ncm && (
                          <button
                            type="button"
                            className="erp-btn-outline erp-btn-sm mt-2 w-full sm:w-auto"
                            onClick={() => {
                              handleInputChange('ncm', '');
                              setNcmProdutoOption(null);
                            }}
                          >
                            Remover override e usar NCM da família
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  <div>
                    <CampoLabel>Unidade fiscal</CampoLabel>
                    <Input
                      className="h-10"
                      value={form.unidade_fiscal || ''}
                      disabled={somenteLeitura}
                      onChange={(e) => handleInputChange('unidade_fiscal', e.target.value)}
                      placeholder="Unidade para fins fiscais (NF-e)"
                    />
                  </div>
                  <div>
                    <CampoLabel>NCM específico (legado)</CampoLabel>
                    <Input
                      className="h-10"
                      value={form.ncm_especifico || ''}
                      disabled={somenteLeitura}
                      onChange={(e) => handleInputChange('ncm_especifico', e.target.value)}
                      placeholder="NCM específico legado"
                    />
                  </div>
                  <div>
                    <CampoLabel>Unidade específica (override)</CampoLabel>
                    <Input
                      className="h-10"
                      value={form.unidade_especifica || ''}
                      disabled={somenteLeitura}
                      onChange={(e) => handleInputChange('unidade_especifica', e.target.value)}
                      placeholder="Override de unidade para este produto"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* --- Manômetro: colunas próprias do SKU --- */}
            {mostrarManometro && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <Gauge className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-base">Manômetro</CardTitle>
                    <Badge variant="secondary">variação por SKU</Badge>
                  </div>
                  <CardDescription className="text-xs">
                    Medidas e faixa próprias deste Produto; alimentam a descrição técnica
                    sugerida
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div
                      id={campoId('diametro_mostrador_mm')}
                      className={classeErroCampo(campoErro, 'diametro_mostrador_mm')}
                    >
                      <CampoLabel>
                        Diâmetro do mostrador (mm)
                        {req?.exige_diametro_mostrador_mm && <Obrigatorio />}
                      </CampoLabel>
                      <DecimalPtBrInput
                        className="erp-input h-10"
                        placeholder="Ex.: 100"
                        value={form.diametro_mostrador_mm}
                        disabled={somenteLeitura}
                        onChange={(v) => handleInputChange('diametro_mostrador_mm', v)}
                      />
                    </div>
                    <div>
                      <CampoLabel>Escala</CampoLabel>
                      <Input
                        className="erp-input h-10"
                        placeholder="Ex.: 0 A 16"
                        value={form.escala || ''}
                        disabled={somenteLeitura}
                        onChange={(e) => handleInputChange('escala', e.target.value)}
                      />
                    </div>
                    <div>
                      <CampoLabel>Unidade da escala</CampoLabel>
                      <Input
                        className="erp-input h-10"
                        placeholder="Ex.: BAR"
                        value={form.unidade_escala || ''}
                        disabled={somenteLeitura}
                        onChange={(e) => handleInputChange('unidade_escala', e.target.value)}
                      />
                    </div>
                    <div>
                      <CampoLabel>Fluido / preenchimento</CampoLabel>
                      <Input
                        className="erp-input h-10"
                        placeholder="Ex.: GLICERINA"
                        value={form.fluido || ''}
                        disabled={somenteLeitura}
                        onChange={(e) => handleInputChange('fluido', e.target.value)}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* --- Conversão de Medidas (molde da Família/Figura) --- */}
            {mostrarConversao && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <Ruler className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-base">Conversão de Medidas</CardTitle>
                    {familiaSelecionada ? (
                      <Badge variant="secondary">somente leitura</Badge>
                    ) : null}
                  </div>
                  <CardDescription className="text-xs">
                    {familiaSelecionada
                      ? `Estas configurações são herdadas da Família/Figura. Para alterar, edite a família ${familiaSelecionada.codigo_figura}.`
                      : 'Unidades, pesos e conversão dimensional do produto'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ConversaoMedidasBlock
                    somenteLeitura={!!familiaSelecionada || somenteLeitura}
                    usaConversao={conversao.usaConversao}
                    onUsaConversaoChange={(v) => handleInputChange('usa_conversao_dimensional', v)}
                    controlaComposicaoFisica={conversao.controlaComposicaoFisica}
                    onControlaComposicaoFisicaChange={(v) =>
                      handleInputChange('controla_composicao_fisica', v)
                    }
                    tipoComposicaoFisica={conversao.tipoComposicaoFisica}
                    onTipoComposicaoFisicaChange={(v) =>
                      handleInputChange('tipo_composicao_fisica', v)
                    }
                    tipoFisicoEfetivo={conversao.tipoFisicoEfetivo}
                    tipoFisicoProduto={conversao.tipoFisico}
                    onTipoFisicoProdutoChange={(v) =>
                      handleInputChange('tipo_fisico', v as TipoFisicoProduto)
                    }
                    tipoControleProduto={conversao.tipoControleUnidade}
                    onTipoControleProdutoChange={(v) =>
                      handleInputChange('tipo_controle_unidade', v as TipoControleUnidade)
                    }
                    unidadeEstoque={conversao.unidadeEstoque}
                    onUnidadeEstoqueChange={(v) => handleInputChange('unidade_estoque', v)}
                    unidadeVenda={conversao.unidadeVenda}
                    onUnidadeVendaChange={(v) => handleInputChange('unidade_venda_padrao', v)}
                    unidadeCompra={conversao.unidadeCompra}
                    onUnidadeCompraChange={(v) => handleInputChange('unidade_compra_padrao', v)}
                    unidadeFiscal={conversao.unidadeFiscal}
                    onUnidadeFiscalChange={(v) => handleInputChange('unidade_fiscal', v)}
                    unidadesVenda={conversao.unidadesVenda}
                    onUnidadesVendaChange={(list) =>
                      handleInputChange('unidades_venda_permitidas', list)
                    }
                    unidadesCompra={conversao.unidadesCompra}
                    onUnidadesCompraChange={(list) =>
                      handleInputChange('unidades_compra_permitidas', list)
                    }
                    familiaUnidadesVenda={familiaSelecionada?.unidades_venda_permitidas}
                    familiaUnidadesCompra={familiaSelecionada?.unidades_compra_permitidas}
                    comprimentoBarra={conversao.comprimentoBarra}
                    onComprimentoBarraChange={(v) =>
                      handleInputChange('comprimento_padrao_barra_m', v)
                    }
                    pesoMetro={conversao.pesoMetro}
                    onPesoMetroChange={(v) => handleInputChange('peso_por_metro_kg', v)}
                    pesoPeca={conversao.pesoPeca}
                    onPesoPecaChange={(v) => handleInputChange('peso_por_peca_kg', v)}
                    pesoChapa={conversao.pesoChapa}
                    onPesoChapaChange={(v) => handleInputChange('peso_por_chapa_kg', v)}
                    densidade={conversao.densidade}
                    onDensidadeChange={(v) => handleInputChange('densidade', v)}
                    observacoes={conversao.observacoes}
                    onObservacoesChange={(v) => handleInputChange('observacoes_conversao', v)}
                    ocultarUnidadeFiscal
                  />
                </CardContent>
              </Card>
            )}

            {/* --- Qualidade (molde vem da Família/Figura) --- */}
            {mostrarQualidade && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-base">Qualidade</CardTitle>
                    {familiaSelecionada ? (
                      <Badge variant="secondary">somente leitura</Badge>
                    ) : null}
                  </div>
                  <CardDescription className="text-xs">
                    {familiaSelecionada
                      ? `Requisito herdado da Família/Figura ${familiaSelecionada.codigo_figura}. Para alterar, edite a família.`
                      : 'Sem família selecionada, o produto define o próprio requisito.'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-3">
                    <Switch
                      id="prod-exige-certificado"
                      disabled={!!familiaSelecionada || somenteLeitura}
                      checked={exigeCertificadoEfetivo}
                      onCheckedChange={(v) =>
                        setForm((prev) => ({ ...prev, exige_certificado_qualidade: v }))
                      }
                    />
                    <Label htmlFor="prod-exige-certificado" className="cursor-pointer text-sm font-medium">
                      Exige Certificado de Qualidade
                    </Label>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* --- Composição do produto (exige produto salvo) --- */}
            {mostrarComposicao && produto && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-base">Composição do produto</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Componentes que formam este produto
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ProdutoComposicaoPanel
                    produtoId={produto.id}
                    produtosOpcoes={produtosOpcoes}
                    somenteLeitura={somenteLeitura}
                  />
                </CardContent>
              </Card>
            )}

            {/* --- Tipo de peça e conexão: texto livre sem uso na base atual --- */}
            {mostrarCamposTecnicosLivres && (
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <Link2 className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-base">Tipo de peça e conexão</CardTitle>
                  </div>
                  <CardDescription className="text-xs">
                    Descrição livre do produto — a família não traz esses padrões
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                      <CampoLabel>Tipo de peça</CampoLabel>
                      <Input
                        className="erp-input h-10"
                        value={form.tipo_peca}
                        disabled={somenteLeitura}
                        onChange={(e) => handleInputChange('tipo_peca', e.target.value)}
                        placeholder="Ex.: Válvula, Conexão, Flange"
                      />
                    </div>
                    <div>
                      <CampoLabel>Conexão (texto livre)</CampoLabel>
                      <Input
                        className="erp-input h-10"
                        value={form.conexao}
                        disabled={somenteLeitura}
                        onChange={(e) => handleInputChange('conexao', e.target.value)}
                        placeholder="Descrição livre da conexão"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
