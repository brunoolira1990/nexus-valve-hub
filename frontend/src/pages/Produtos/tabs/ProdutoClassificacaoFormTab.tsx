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
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Info, Wrench, Link2, Ruler, Boxes, Scale, Layers } from 'lucide-react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import type { ProdutoFormState } from '../types';
import type { FamiliaProduto, RequisitosProdutoDimensionais, Produto, RoscaConexao, ScheduleEspessura } from '@/types';
import type { Material, MaterialCategoria } from '@/types/material';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import { ConversaoMedidasBlock } from '@/components/produtos/ConversaoMedidasBlock';
import { ProdutoComposicaoPanel } from '@/components/produtos/ProdutoComposicaoPanel';
import { roscasConexaoService, schedulesEspessuraService } from '@/services/api/produtos';
import {
  getTdAtual,
  getUsaDimensoesMateriais,
  getLabelCampoOdPrincipal,
  getLabelCampoEspessuraOuMenor,
  getAtributosTecnicosFamilia,
} from '../lib/familiaDerivations';

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

interface ProdutoClassificacaoFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview?: { codigo?: string; descricao?: string; ncm?: string; mensagem?: string };
  familiaSelecionada?: FamiliaProduto | null;
  famReq?: RequisitosProdutoDimensionais | null;
  /** Produto em edição — habilita o painel de Composição. */
  editing?: Produto | null;
  /** Lista de produtos para o seletor de componentes da composição. */
  produtosOpcoes?: Array<{ id: number; codigo_completo: string; descricao: string }>;
  /** Catálogo de materiais (ativos) carregado pelo container — alimenta o dropdown. */
  materiais?: Material[];
  /** Indica que o catálogo de materiais ainda está carregando. */
  carregandoMateriais?: boolean;
}

export function ProdutoClassificacaoFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada = null,
  famReq = null,
  editing = null,
  produtosOpcoes = [],
  materiais = [],
  carregandoMateriais = false,
}: ProdutoClassificacaoFormTabProps) {
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
    if (!id) {
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
  }, [form.schedule_ref_id, scheduleOption?.id]);

  // Rosca/conexão: lista pequena e estática — carregada uma vez por montagem.
  const [roscas, setRoscas] = useState<RoscaConexao[]>([]);
  useEffect(() => {
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
  }, []);

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
  const familiaEhMaterialDimensional =
    familiaSelecionada?.categoria_produto === 'MATERIAL_DIMENSIONAL';

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

  const parseDec = (raw: string): number | null => {
    const v = raw.replace(',', '.');
    if (v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const decToText = (n: number | null | undefined) =>
    n?.toString().replace('.', ',') || '';

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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div>
              <CampoLabel>Material</CampoLabel>
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
            </div>
            <div>
              <CampoLabel>Norma técnica</CampoLabel>
              <Input
                className="erp-input h-10"
                value={form.norma}
                onChange={(e) => handleInputChange('norma', e.target.value)}
                placeholder="Ex.: ASME B16.34, DIN 3352"
              />
            </div>
            <div>
              <CampoLabel>Pressão nominal</CampoLabel>
              <Input
                className="erp-input h-10"
                value={form.pressao_nominal}
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
              <CampoLabel>Tipo de peça</CampoLabel>
              <Input
                className="erp-input h-10"
                value={form.tipo_peca}
                onChange={(e) => handleInputChange('tipo_peca', e.target.value)}
                placeholder="Ex.: Válvula, Conexão, Flange"
              />
            </div>
            <div className="lg:col-span-2">
              <CampoLabel>Conexão (texto livre)</CampoLabel>
              <Input
                className="erp-input h-10"
                value={form.conexao}
                onChange={(e) => handleInputChange('conexao', e.target.value)}
                placeholder="Descrição livre da conexão"
              />
            </div>
          </div>
        </CardContent>
      </Card>

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
                  <CampoLabel>Rosca / conexão</CampoLabel>
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
                          {(r.codigo || '—') + ' — ' + r.descricao}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {!familiaEhMaterialDimensional && famReq.usa_schedule && (
                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Label className="text-sm font-medium">Schedule / espessura</Label>
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
                </div>
              )}

              {!familiaEhMaterialDimensional && famReq.exige_od_mm && (
                <div>
                  <CampoLabel>
                    {labelOd}
                    <Obrigatorio />
                  </CampoLabel>
                  <Input
                    type="text"
                    inputMode="decimal"
                    className="erp-input h-10"
                    placeholder="Ex.: 10 | 10,0 | 1,5"
                    value={decToText(form.od_mm)}
                    onChange={(e) => handleInputChange('od_mm', parseDec(e.target.value))}
                  />
                </div>
              )}

              {!familiaEhMaterialDimensional && famReq.exige_espessura_mm && (
                <div>
                  <CampoLabel>
                    {labelEsp}
                    <Obrigatorio />
                  </CampoLabel>
                  <Input
                    type="text"
                    inputMode="decimal"
                    className="erp-input h-10"
                    placeholder="Ex.: 2 | 2,0 | 1,5"
                    value={decToText(form.espessura_mm)}
                    onChange={(e) => handleInputChange('espessura_mm', parseDec(e.target.value))}
                  />
                </div>
              )}

              {!familiaEhMaterialDimensional && famReq.exige_comprimento_mm && (
                <div>
                  <CampoLabel>Comprimento (mm)</CampoLabel>
                  <Input
                    type="text"
                    inputMode="decimal"
                    className="erp-input h-10"
                    placeholder="Ex.: 6000"
                    value={decToText(form.comprimento_mm)}
                    onChange={(e) => handleInputChange('comprimento_mm', parseDec(e.target.value))}
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

      {/* ===== Dimensões e referências ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Ruler className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Dimensões e referências</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Polegadas de referência deste produto. Medidas em milímetros (OD, espessura,
            comprimento) ficam no card Requisitos da Família/Figura.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div>
              <CampoLabel>Polegada principal (autocomplete)</CampoLabel>
              <PolegadaAutocomplete
                value={form.polegada_principal_ref_id ?? null}
                onChange={(id) => handleInputChange('polegada_principal_ref_id', id)}
                tipoMedida="OD"
                allowCreate
                placeholder="Busque por código, polegada, decimal ou mm"
              />
            </div>
            <div>
              <CampoLabel>Polegada secundária (autocomplete)</CampoLabel>
              <PolegadaAutocomplete
                value={form.polegada_secundaria_ref_id ?? null}
                onChange={(id) => handleInputChange('polegada_secundaria_ref_id', id)}
                tipoMedida="OD"
                allowCreate
                placeholder="Busque por código, polegada, decimal ou mm"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ===== Dimensões especiais (JSON) ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Boxes className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Dimensões especiais</CardTitle>
            {usaDimensoesMateriais && tdAtual ? (
              <Badge variant="secondary">tipo: {tdAtual}</Badge>
            ) : null}
          </div>
          <CardDescription className="text-xs">
            Dimensões de material dimensional (armazenadas em{' '}
            <code className="font-mono">dimensoes_json</code>)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {usaDimensoesMateriais ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div>
                <CampoLabel>Espessura (mm)</CampoLabel>
                <Input
                  type="text"
                  inputMode="decimal"
                  className="erp-input h-10"
                  placeholder="Ex.: 3,2"
                  value={decToText(form.dim_espessura_mm)}
                  onChange={(e) => handleInputChange('dim_espessura_mm', parseDec(e.target.value))}
                />
              </div>
              <div>
                <CampoLabel>Largura (mm)</CampoLabel>
                <Input
                  type="text"
                  inputMode="decimal"
                  className="erp-input h-10"
                  placeholder="Ex.: 1000"
                  value={decToText(form.dim_largura_mm)}
                  onChange={(e) => handleInputChange('dim_largura_mm', parseDec(e.target.value))}
                />
              </div>
              <div>
                <CampoLabel>Comprimento (mm)</CampoLabel>
                <Input
                  type="text"
                  inputMode="decimal"
                  className="erp-input h-10"
                  placeholder="Ex.: 2000"
                  value={decToText(form.dim_comprimento_mm)}
                  onChange={(e) => handleInputChange('dim_comprimento_mm', parseDec(e.target.value))}
                />
              </div>
              <div>
                <CampoLabel>Altura (mm)</CampoLabel>
                <Input
                  type="text"
                  inputMode="decimal"
                  className="erp-input h-10"
                  placeholder="Ex.: 50"
                  value={decToText(form.dim_altura_mm)}
                  onChange={(e) => handleInputChange('dim_altura_mm', parseDec(e.target.value))}
                />
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground text-center py-8 border border-dashed rounded-md bg-muted/30">
              Dimensões especiais aparecem quando a família/figura é do tipo MATERIAL_DIMENSIONAL.
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== Conversão de Medidas ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Conversão de Medidas</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Unidades, pesos e conversão dimensional do produto
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ConversaoMedidasBlock
            usaConversao={!!form.usa_conversao_dimensional}
            onUsaConversaoChange={(v) => handleInputChange('usa_conversao_dimensional', v)}
            controlaComposicaoFisica={!!form.controla_composicao_fisica}
            onControlaComposicaoFisicaChange={(v) => handleInputChange('controla_composicao_fisica', v)}
            tipoComposicaoFisica={form.tipo_composicao_fisica || 'BARRA_M'}
            onTipoComposicaoFisicaChange={(v) => handleInputChange('tipo_composicao_fisica', v)}
            tipoFisicoEfetivo={form.tipo_fisico_efetivo || form.tipo_fisico || ''}
            tipoFisicoProduto={form.tipo_fisico || ''}
            onTipoFisicoProdutoChange={(v) => handleInputChange('tipo_fisico', v)}
            tipoControleProduto={form.tipo_controle_unidade || ''}
            onTipoControleProdutoChange={(v) => handleInputChange('tipo_controle_unidade', v)}
            unidadeEstoque={form.unidade_estoque || ''}
            onUnidadeEstoqueChange={(v) => handleInputChange('unidade_estoque', v)}
            unidadeVenda={form.unidade_venda_padrao || ''}
            onUnidadeVendaChange={(v) => handleInputChange('unidade_venda_padrao', v)}
            unidadeCompra={form.unidade_compra_padrao || ''}
            onUnidadeCompraChange={(v) => handleInputChange('unidade_compra_padrao', v)}
            unidadeFiscal={form.unidade_fiscal || ''}
            onUnidadeFiscalChange={(v) => handleInputChange('unidade_fiscal', v)}
            unidadesVenda={form.unidades_venda_permitidas || []}
            onUnidadesVendaChange={(list) => handleInputChange('unidades_venda_permitidas', list)}
            unidadesCompra={form.unidades_compra_permitidas || []}
            onUnidadesCompraChange={(list) => handleInputChange('unidades_compra_permitidas', list)}
            familiaUnidadesVenda={familiaSelecionada?.unidades_venda_permitidas}
            familiaUnidadesCompra={familiaSelecionada?.unidades_compra_permitidas}
            comprimentoBarra={form.comprimento_padrao_barra_m ?? null}
            onComprimentoBarraChange={(v) => handleInputChange('comprimento_padrao_barra_m', v)}
            pesoMetro={form.peso_por_metro_kg ?? null}
            onPesoMetroChange={(v) => handleInputChange('peso_por_metro_kg', v)}
            pesoPeca={form.peso_por_peca_kg ?? null}
            onPesoPecaChange={(v) => handleInputChange('peso_por_peca_kg', v)}
            pesoChapa={form.peso_por_chapa_kg ?? null}
            onPesoChapaChange={(v) => handleInputChange('peso_por_chapa_kg', v)}
            densidade={form.densidade ?? null}
            onDensidadeChange={(v) => handleInputChange('densidade', v)}
            observacoes={form.observacoes_conversao || ''}
            onObservacoesChange={(v) => handleInputChange('observacoes_conversao', v)}
            ocultarUnidadeFiscal
          />
        </CardContent>
      </Card>

      {/* ===== Composição do produto (apenas em edição) ===== */}
      {editing?.id ? (
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
            <ProdutoComposicaoPanel produtoId={editing.id} produtosOpcoes={produtosOpcoes} />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
