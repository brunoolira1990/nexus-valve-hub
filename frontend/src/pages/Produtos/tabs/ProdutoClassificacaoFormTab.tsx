import { useEffect, useState, type ReactNode } from 'react';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Info, Wrench, Link2, Ruler, Lock, Scale, Layers, ShieldCheck, Gauge } from 'lucide-react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import type { ProdutoFormState } from '../types';
import type {
  FamiliaProduto,
  RequisitosProdutoDimensionais,
  Produto,
  RoscaConexao,
  ScheduleEspessura,
  TipoControleUnidade,
  TipoFisicoProduto,
} from '@/types';
import type { Material, MaterialCategoria } from '@/types/material';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import { DecimalPtBrInput } from '@/components/produtos/DecimalPtBrInput';
import { ConversaoMedidasBlock } from '@/components/produtos/ConversaoMedidasBlock';
import { InheritedBadge } from '@/components/produtos/InheritedBadge';
import { ProdutoComposicaoPanel } from '@/components/produtos/ProdutoComposicaoPanel';
import { roscasConexaoService, schedulesEspessuraService } from '@/services/api/produtos';
import {
  estaHerdadoDaFamilia,
  valorFamiliaParaCampo,
  valoresConversaoHerdados,
  valoresConversaoProduto,
  type CampoHerancaVisivel,
} from '../lib/herancaFamilia';
import {
  getTdAtual,
  getUsaDimensoesMateriais,
  getLabelCampoOdPrincipal,
  getLabelCampoEspessuraOuMenor,
  getAtributosTecnicosFamilia,
} from '../lib/familiaDerivations';
import {
  labelPolegadaPrincipal,
  labelPolegadaSecundaria,
  tipoMedidaPrincipalPorDimensional,
  tipoMedidaSecundariaPorDimensional,
} from '@/lib/familiaRegra';
import { campoId, classeErroCampo, type CampoFormProdutoInvalido } from '../lib/erroCampo';
import { resolverTipoMedida } from '../lib/tipoMedidaPolegada';

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

/** Sentinela de "sem rosca específica" (Radix não aceita SelectItem com value=""). */
const SEM_ROSCA = '__none__';

/**
 * Rosca há quem só tenha descrição (o catálogo permite `codigo` vazio). Concatenar com
 * '—' mostrava «— —» na tela, então o separador só aparece quando os dois lados existem.
 */
function rotuloRosca(codigo?: string | null, descricao?: string | null): string {
  const c = (codigo || '').trim();
  const d = (descricao || '').trim();
  if (c && d) return `${c} — ${d}`;
  return c || d || '—';
}

/**
 * Padrões técnicos que vivem apenas na Família/Figura (decisão Sprint 3.6: o Produto
 * não tem esses campos). São exibidos como leitura aqui para deixar claro que não se
 * digita nada no produto.
 */
const PADROES_FAMILIA: readonly { key: keyof FamiliaProduto; label: string }[] = [
  { key: 'material_vedacao', label: 'Material de vedação' },
];

interface ProdutoClassificacaoFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview?: { codigo?: string; descricao?: string; ncm?: string; mensagem?: string };
  familiaSelecionada?: FamiliaProduto | null;
  famReq?: RequisitosProdutoDimensionais | null;
  /** Produto do payload — habilita o painel de Composição e dá os rótulos resolvidos da leitura. */
  produto?: Produto | null;
  /** Lista de produtos para o seletor de componentes da composição. */
  produtosOpcoes?: Array<{ id: number; codigo_completo: string; descricao: string }>;
  /** Catálogo de materiais (ativos) carregado pelo container — alimenta o dropdown. */
  materiais?: Material[];
  /** Indica que o catálogo de materiais ainda está carregando. */
  carregandoMateriais?: boolean;
  /** Campos técnicos preenchidos pela última herança aplicada da família. */
  herdouFamilia?: CampoHerancaVisivel[];
  /** Botão "Limpar" da badge: solta o campo da família para virar override. */
  onLimparHerdado?: (campo: CampoHerancaVisivel) => void;
  /** Campo apontado pela validação do salvar(): recebe o anel e a âncora de rolagem. */
  campoErro?: CampoFormProdutoInvalido | null;
  /** Ficha de Visualização: cards e grid idênticos aos da Edição, tudo desabilitado e sem catálogo. */
  somenteLeitura?: boolean;
}

export function ProdutoClassificacaoFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada = null,
  famReq = null,
  produto = null,
  produtosOpcoes = [],
  materiais = [],
  carregandoMateriais = false,
  herdouFamilia = [],
  onLimparHerdado,
  campoErro = null,
  somenteLeitura = false,
}: ProdutoClassificacaoFormTabProps) {
  // Rótulo humano de cada campo herdável (usado na badge e no resumo).
  const ROTULO_HERANCA: Record<CampoHerancaVisivel, string> = {
    material_ref: 'Material',
    tipo_peca: 'Tipo de peça',
    norma: 'Norma técnica',
    pressao_nominal: 'Pressão nominal',
    conexao: 'Conexão',
  };

  const badgeHeranca = (campo: CampoHerancaVisivel, valorProduto: unknown) => {
    // A badge tem botão "Limpar" (ação de escrita): na ficha ela não existe.
    if (somenteLeitura) return null;
    if (!familiaSelecionada || !estaHerdadoDaFamilia(familiaSelecionada, campo, valorProduto)) {
      return null;
    }
    const valorFamiliaExibido =
      campo === 'material_ref'
        ? familiaSelecionada.material_base || String(valorProduto ?? '')
        : valorFamiliaParaCampo(familiaSelecionada, campo);
    return (
      <InheritedBadge
        campo={ROTULO_HERANCA[campo]}
        valor={valorFamiliaExibido}
        onLimpar={() => onLimparHerdado?.(campo)}
      />
    );
  };

  const rotuloLinha = (label: string, campo: CampoHerancaVisivel, valorProduto: unknown) => (
    <div className="flex items-center justify-between gap-2">
      <CampoLabel>{label}</CampoLabel>
      {badgeHeranca(campo, valorProduto)}
    </div>
  );

  const handleInputChange = <K extends keyof ProdutoFormState>(
    key: K,
    value: ProdutoFormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

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
    if (somenteLeitura) {
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
  }, [somenteLeitura]);

  // Material: o catálogo (ativos) vem do container via prop `materiais`.
  // A resolução material→material_ref (herança da família / produto legado) vive
  // no useProdutoForm, que também recebe `materiais`. Aqui só agrupamos p/ render.
  const materiaisAgrupados = MATERIAL_GRUPO_ORDEM.map((categoria) => ({
    categoria,
    label: MATERIAL_GRUPO_LABELS[categoria],
    itens: materiais.filter((m) => m.categoria === categoria),
  })).filter((grupo) => grupo.itens.length > 0);

  // Derivações da família (puras — vindas de lib/familiaDerivations)
  const tdAtual = getTdAtual(familiaSelecionada);
  const usaDimensoesMateriais = getUsaDimensoesMateriais(familiaSelecionada);
  const labelOd = getLabelCampoOdPrincipal(familiaSelecionada);
  const labelEsp = getLabelCampoEspessuraOuMenor(familiaSelecionada);
  const atributosTecnicos = getAtributosTecnicosFamilia(familiaSelecionada);
  // Card de leitura: sem valor na família não há nada a mostrar, então o card não aparece.
  const padroesFamilia = PADROES_FAMILIA.filter(
    ({ key }) => String(familiaSelecionada?.[key] ?? '').trim().length > 0,
  );
  const familiaEhMaterialDimensional =
    familiaSelecionada?.categoria_produto === 'MATERIAL_DIMENSIONAL';

  // As polegadas de referência (FK) só existem quando a regra da família as usa;
  // no modo LEGADO os segmentos de texto do código ficam na aba Geral.
  const usaPolegadaPrincipal = !!famReq?.usa_polegada_principal;
  const usaPolegadaSecundaria = !!famReq?.usa_polegada_secundaria;
  const exigePolegadas = usaPolegadaPrincipal || usaPolegadaSecundaria;
  // O filtro NPS/OD da busca vem da regra da família (espelho do backend), nunca de um
  // valor fixo na tela: forçar OD fazia um NPS salvo sumir e virar outra polegada no código.
  const tipoMedidaEsperado = {
    polegada_principal_ref_id: tipoMedidaPrincipalPorDimensional(tdAtual),
    polegada_secundaria_ref_id: tipoMedidaSecundariaPorDimensional(tdAtual),
  };
  const tipoMedidaPrincipal = resolverTipoMedida(
    produto?.polegada_principal_ref_detalhes?.tipo_medida,
    tipoMedidaEsperado.polegada_principal_ref_id,
  );
  const tipoMedidaSecundaria = resolverTipoMedida(
    produto?.polegada_secundaria_ref_detalhes?.tipo_medida,
    tipoMedidaEsperado.polegada_secundaria_ref_id,
  );
  // OD/espessura/comprimento em mm são do produto técnico; em material dimensional a
  // medida da peça é o conjunto dim_*. O card Requisitos nunca mostra os dois.
  const mmDoProdutoVisiveis = !familiaEhMaterialDimensional && !usaDimensoesMateriais;

  // Conversão de Medidas: com família, o card mostra o molde herdado (Família/Figura)
  // e bloqueia a edição; sem família, o produto continua dono das próprias medidas.
  const conversao = familiaSelecionada
    ? valoresConversaoHerdados(form, familiaSelecionada)
    : valoresConversaoProduto(form);

  // Certificado de Qualidade: requisito do molde (Família/Figura). Sem família, o produto decide.
  const exigeCertificadoEfetivo =
    !!form.exige_certificado_qualidade || !!familiaSelecionada?.exige_certificado_qualidade;

  // Rótulos que só o payload da ficha traz: em leitura não se abre catálogo, então o
  // texto do select/autompletar vem direto dos *_detalhes já resolvidos pelo backend.
  const roscaTexto = (() => {
    const r = produto?.rosca_conexao_detalhes;
    if (!r) return 'Sem rosca específica (usa o padrão da família)';
    return rotuloRosca(r.codigo, r.descricao);
  })();
  const scheduleTexto = (() => {
    const s = produto?.schedule_ref_detalhes;
    if (!s) return '—';
    return `${s.codigo || s.codigo_schedule} — ${s.descricao || s.codigo_schedule}`;
  })();
  /** Formato amigável (decisão Sprint 3.6): `1/2"` em vez do `nome` técnico 'NPS 1/2 — 1/2"'. */
  const textoPolegada = (p?: Produto['polegada_principal_ref_detalhes']) => {
    if (!p) return '—';
    const oficial = p.codigo_oficial || p.codigo;
    return oficial ? `${oficial}"` : p.descricao;
  };
  const polegadaPrincipalTexto = textoPolegada(produto?.polegada_principal_ref_detalhes);
  const polegadaSecundariaTexto = textoPolegada(produto?.polegada_secundaria_ref_detalhes);

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

  return (
    <div className="space-y-6">
      {/* ===== Identidade técnica ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Wrench className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Identidade técnica</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Material, norma e pressão nominal do produto
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {!somenteLeitura && herdouFamilia.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Herdados da família ao selecioná-la: {herdouFamilia.map((c) => ROTULO_HERANCA[c]).join(', ')}
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div id={campoId('material_ref')} className={classeErroCampo(campoErro, 'material_ref')}>
              {rotuloLinha('Material', 'material_ref', form.material_ref)}
              {somenteLeitura ? (
                // material_nome já vem resolvido no payload: a ficha não carrega o catálogo de materiais.
                <Input
                  className="h-10 bg-muted/40"
                  value={produto?.material_nome ?? form.material ?? ''}
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
            </div>
            <div>
              {rotuloLinha('Norma técnica', 'norma', form.norma)}
              <Input
                className="erp-input h-10"
                value={form.norma}
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('norma', e.target.value)}
                placeholder="Ex.: ASME B16.34, DIN 3352"
              />
            </div>
            <div>
              {rotuloLinha('Pressão nominal', 'pressao_nominal', form.pressao_nominal)}
              <Input
                className="erp-input h-10"
                value={form.pressao_nominal}
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('pressao_nominal', e.target.value)}
                placeholder="Ex.: PN 16, Class 150"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ===== Tipo de peça / Conexão ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Tipo de peça e conexão</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Classificação da peça e descrição da conexão
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-1">
              {rotuloLinha('Tipo de peça', 'tipo_peca', form.tipo_peca)}
              <Input
                className="erp-input h-10"
                value={form.tipo_peca}
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('tipo_peca', e.target.value)}
                placeholder="Ex.: Válvula, Conexão, Flange"
              />
            </div>
            <div className="lg:col-span-2">
              {rotuloLinha('Conexão (texto livre)', 'conexao', form.conexao)}
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

      {/* ===== Padrões da Família (somente leitura — o produto herda, não digita) ===== */}
      {familiaSelecionada && padroesFamilia.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Padrões da Família/Figura</CardTitle>
              <Badge variant="secondary">somente leitura</Badge>
            </div>
            <CardDescription className="text-xs">
              Estes campos pertencem à Família/Figura — o produto apenas os herda. Para
              alterar, edite a família {familiaSelecionada.codigo_figura}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
              {padroesFamilia.map(({ key, label }) => {
                const valor = String(familiaSelecionada?.[key] ?? '').trim();
                return (
                  <div key={key}>
                    <CampoLabel>{label}</CampoLabel>
                    <Input
                      className="erp-input h-10 bg-muted/40"
                      value={valor}
                      disabled
                      readOnly
                      placeholder="Não definido na família"
                      title="Herda da Família/Figura — edite a família para alterar"
                    />
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== Requisitos da Família/Figura (condicional) ===== */}
      {familiaSelecionada && famReq && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Link2 className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Requisitos da Família/Figura</CardTitle>
              <Badge variant="secondary">guiado pela regra</Badge>
            </div>
            <CardDescription className="text-xs">
              Campos exigidos pela regra estrutural desta família
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {!familiaEhMaterialDimensional && famReq.usa_rosca_conexao && (
                <div>
                  <CampoLabel>
                    Rosca / conexão
                    <Obrigatorio />
                  </CampoLabel>
                  {somenteLeitura ? (
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
                        <SelectItem value={SEM_ROSCA}>
                          — Sem rosca específica (usa o padrão da família) —
                        </SelectItem>
                        {roscas.map((r) => (
                          <SelectItem key={r.id} value={r.id.toString()}>
                            {rotuloRosca(r.codigo, r.descricao)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
              )}

              {!familiaEhMaterialDimensional && famReq.usa_schedule && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Label className="text-sm font-medium">
                      Schedule / espessura
                      <Obrigatorio />
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
                  {somenteLeitura ? (
                    <Input className="h-10 bg-muted/40" value={scheduleTexto} disabled readOnly />
                  ) : (
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
                        handleInputChange('schedule_ref_id', id);
                        setScheduleOption(opt ?? null);
                      }}
                    />
                  )}
                </div>
              )}

              {mmDoProdutoVisiveis && famReq.exige_diametro_interno_mm && (
                <div
                  id={campoId('diametro_interno_mm')}
                  className={classeErroCampo(campoErro, 'diametro_interno_mm')}
                >
                  <CampoLabel>
                    Diâmetro interno ID (mm)
                    <Obrigatorio />
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 15 | 15,0"
                    value={form.diametro_interno_mm}
                    disabled={somenteLeitura}
                    onChange={(v) => handleInputChange('diametro_interno_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && famReq.exige_od_mm && (
                <div id={campoId('od_mm')} className={classeErroCampo(campoErro, 'od_mm')}>
                  <CampoLabel>
                    {labelOd}
                    <Obrigatorio />
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 10 | 10,0 | 1,5"
                    value={form.od_mm}
                    disabled={somenteLeitura}
                    onChange={(v) => handleInputChange('od_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && famReq.exige_espessura_mm && (
                <div id={campoId('espessura_mm')} className={classeErroCampo(campoErro, 'espessura_mm')}>
                  <CampoLabel>
                    {labelEsp}
                    <Obrigatorio />
                  </CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 2 | 2,0 | 1,5"
                    value={form.espessura_mm}
                    disabled={somenteLeitura}
                    onChange={(v) => handleInputChange('espessura_mm', v)}
                  />
                </div>
              )}

              {mmDoProdutoVisiveis && famReq.exige_comprimento_mm && (
                <div id={campoId('comprimento_mm')} className={classeErroCampo(campoErro, 'comprimento_mm')}>
                  <CampoLabel>Comprimento (mm)</CampoLabel>
                  <DecimalPtBrInput
                    className="erp-input h-10"
                    placeholder="Ex.: 6000"
                    value={form.comprimento_mm}
                    disabled={somenteLeitura}
                    onChange={(v) => handleInputChange('comprimento_mm', v)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Se vazio, pode usar o comprimento padrão da barra cadastrado na família.
                  </p>
                </div>
              )}
            </div>

            {!familiaEhMaterialDimensional && (famReq.usa_schedule || famReq.exige_espessura_mm) && (
              <p className="text-xs text-muted-foreground rounded-md bg-muted/50 px-2 py-1.5">
                Informe o schedule/espessura conforme a regra desta Família/Figura.
              </p>
            )}

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
                      disabled={somenteLeitura}
                      onChange={(v) => handleInputChange('dim_espessura_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Largura (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 1000"
                      value={form.dim_largura_mm}
                      disabled={somenteLeitura}
                      onChange={(v) => handleInputChange('dim_largura_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Comprimento (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 2000"
                      value={form.dim_comprimento_mm}
                      disabled={somenteLeitura}
                      onChange={(v) => handleInputChange('dim_comprimento_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Altura (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 50"
                      value={form.dim_altura_mm}
                      disabled={somenteLeitura}
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
                      disabled={somenteLeitura}
                      onChange={(v) => handleInputChange('dim_furo_mm', v)}
                    />
                  </div>
                  <div>
                    <CampoLabel>Aba (mm)</CampoLabel>
                    <DecimalPtBrInput
                      className="erp-input h-10"
                      placeholder="Ex.: 40"
                      value={form.dim_aba_mm}
                      disabled={somenteLeitura}
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
                        disabled={somenteLeitura}
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

      {/* ===== Manômetro (colunas próprias do SKU, não vêm da Família) ===== */}
      {tdAtual === 'MANOMETRO' && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Manômetro</CardTitle>
              <Badge variant="secondary">variação por SKU</Badge>
            </div>
            <CardDescription className="text-xs">
              Medidas e faixa próprias deste Produto; alimentam a descrição técnica sugerida
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div
                id={campoId('diametro_mostrador_mm')}
                className={classeErroCampo(campoErro, 'diametro_mostrador_mm')}
              >
                <CampoLabel>
                  Diâmetro do mostrador (mm)
                  {famReq?.exige_diametro_mostrador_mm && <Obrigatorio />}
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

      {/* ===== Polegadas de referência (só quando a regra da família as usa) ===== */}
      {exigePolegadas && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Ruler className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Polegadas de referência</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Medidas em milímetros (OD, espessura, comprimento) ficam apenas no card
              Requisitos da Família/Figura.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {usaPolegadaPrincipal && (
                <div>
                  <CampoLabel>
                    {labelPolegadaPrincipal(tdAtual)}
                    <Obrigatorio />
                  </CampoLabel>
                  {somenteLeitura ? (
                    <Input className="h-10 bg-muted/40" value={polegadaPrincipalTexto} disabled readOnly />
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
                    <Obrigatorio />
                  </CampoLabel>
                  {somenteLeitura ? (
                    <Input className="h-10 bg-muted/40" value={polegadaSecundariaTexto} disabled readOnly />
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
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== Conversão de Medidas (molde da Família/Figura) ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Conversão de Medidas</CardTitle>
            {familiaSelecionada ? <Badge variant="secondary">somente leitura</Badge> : null}
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
            onControlaComposicaoFisicaChange={(v) => handleInputChange('controla_composicao_fisica', v)}
            tipoComposicaoFisica={conversao.tipoComposicaoFisica}
            onTipoComposicaoFisicaChange={(v) => handleInputChange('tipo_composicao_fisica', v)}
            tipoFisicoEfetivo={conversao.tipoFisicoEfetivo}
            tipoFisicoProduto={conversao.tipoFisico}
            onTipoFisicoProdutoChange={(v) => handleInputChange('tipo_fisico', v as TipoFisicoProduto)}
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
            onUnidadesVendaChange={(list) => handleInputChange('unidades_venda_permitidas', list)}
            unidadesCompra={conversao.unidadesCompra}
            onUnidadesCompraChange={(list) => handleInputChange('unidades_compra_permitidas', list)}
            familiaUnidadesVenda={familiaSelecionada?.unidades_venda_permitidas}
            familiaUnidadesCompra={familiaSelecionada?.unidades_compra_permitidas}
            comprimentoBarra={conversao.comprimentoBarra}
            onComprimentoBarraChange={(v) => handleInputChange('comprimento_padrao_barra_m', v)}
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

      {/* ===== Qualidade (molde vem da Família/Figura) ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Qualidade</CardTitle>
            {familiaSelecionada ? <Badge variant="secondary">somente leitura</Badge> : null}
          </div>
          <CardDescription className="text-xs">
            {familiaSelecionada
              ? `Estas configurações são herdadas da Família/Figura ${familiaSelecionada.codigo_figura}. Para alterar, edite a família.`
              : 'Sem família selecionada, o produto define o próprio requisito.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Switch
              id="prod-exige-certificado"
              disabled={!!familiaSelecionada || somenteLeitura}
              checked={exigeCertificadoEfetivo}
              onCheckedChange={(v) => setForm((prev) => ({ ...prev, exige_certificado_qualidade: v }))}
            />
            <Label htmlFor="prod-exige-certificado" className="cursor-pointer text-sm font-medium">
              Exige Certificado de Qualidade
            </Label>
          </div>
        </CardContent>
      </Card>

      {/* ===== Composição do produto (exige produto salvo; na ficha só lista, sem ações) ===== */}
      {produto?.id ? (
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
      ) : null}
    </div>
  );
}
