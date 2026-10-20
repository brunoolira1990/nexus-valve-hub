import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Boxes, Layers, Loader2, Receipt, Ruler, Save, ShieldCheck, Wrench, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { familiasProdutoService, ncmApiService } from '@/services/api/produtos';
import { materiaisService } from '@/services/api/materiais';
import { apiErrorMessage } from '@/services/api/config';
import { Textarea } from '@/components/ui/textarea';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import { FamiliaDominioCard } from '@/components/familias/FamiliaDominioCard';
import {
  TIPO_CONTROLE_OPTIONS,
  TIPO_FISICO_OPTIONS,
  UNIDADES_CATALOGO,
  toggleUnidadeLista,
} from '@/lib/conversaoMedidasUx';
import type {
  FamiliaProduto,
  TipoControleUnidade,
  TipoDimensional,
  TipoFisicoProduto,
  TipoRegraCodigo,
} from '@/types';
import type { Material } from '@/types/material';
import { MENSAGEM_CODIGO_FIGURA_AUTO, validarDescricaoBaseLocal } from '@/lib/familiaCodigo';
import {
  OPCOES_CATEGORIA_FAMILIA,
  OPCOES_TIPO_DIMENSIONAL,
  OPCOES_TIPO_REGRA,
  hintTipoDimensional,
  sugerirTipoRegraPorDimensional,
  tiposDimensionaisPorCategoria,
  type CategoriaProdutoSugestao,
} from '@/lib/familiaRegra';

/** Sentinela do Select — o Radix não aceita value="". */
const SEM_MATERIAL = '__none__';

type FamiliaFormState = {
  codigo_figura: string;
  descricao_base: string;
  ativo: boolean;
  tipo_regra_codigo: TipoRegraCodigo;
  tipo_dimensional: TipoDimensional;
  categoria_produto: CategoriaProdutoSugestao;
  separador_base_medidas: string;
  ncm_padrao: number | null;
  unidade_padrao: string;
  unidade_estoque_padrao: string;
  unidade_venda_padrao: string;
  unidade_compra_padrao: string;
  unidade_fiscal_padrao: string;
  tipo_fisico: TipoFisicoProduto;
  tipo_controle_unidade: TipoControleUnidade;
  unidades_venda_permitidas: string[];
  unidades_compra_permitidas: string[];
  comprimento_padrao_barra_m: number | null;
  peso_por_metro_kg: number | null;
  peso_por_peca_kg: number | null;
  peso_por_chapa_kg: number | null;
  densidade: number | null;
  usa_conversao_dimensional: boolean;
  controla_composicao_fisica: boolean;
  exige_certificado_qualidade: boolean;
  tipo_composicao_fisica: string;
  observacoes_conversao: string;
  material_base: string;
  material_base_ref: number | null;
  tipo_peca: string;
  material_vedacao: string;
};

const emptyForm = (): FamiliaFormState => ({
  codigo_figura: '',
  descricao_base: '',
  ativo: true,
  tipo_regra_codigo: 'BASE_POLEGADA',
  tipo_dimensional: 'SIMPLES',
  categoria_produto: 'PRODUTO_TECNICO',
  separador_base_medidas: '.',
  ncm_padrao: null,
  unidade_padrao: '',
  unidade_estoque_padrao: '',
  unidade_venda_padrao: '',
  unidade_compra_padrao: '',
  unidade_fiscal_padrao: '',
  tipo_fisico: 'PECA',
  tipo_controle_unidade: 'PECA',
  unidades_venda_permitidas: [],
  unidades_compra_permitidas: [],
  comprimento_padrao_barra_m: null,
  peso_por_metro_kg: null,
  peso_por_peca_kg: null,
  peso_por_chapa_kg: null,
  densidade: null,
  usa_conversao_dimensional: false,
  controla_composicao_fisica: false,
  exige_certificado_qualidade: false,
  tipo_composicao_fisica: 'BARRA_M',
  observacoes_conversao: '',
  material_base: '',
  material_base_ref: null,
  tipo_peca: '',
  material_vedacao: '',
});

function CampoLabel({ children }: { children: React.ReactNode }) {
  return <Label className="text-sm font-medium mb-1.5 block">{children}</Label>;
}

function Obrigatorio() {
  return <span className="text-destructive" aria-hidden> *</span>;
}

const FamiliaFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const familiaId = id ? Number(id) : undefined;

  const [form, setForm] = useState<FamiliaFormState>(emptyForm);
  const [carregando, setCarregando] = useState(isEdit);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [materiais, setMateriais] = useState<Material[]>([]);
  const [ncmOption, setNcmOption] = useState<NcmOption | null>(null);

  useEffect(() => {
    let ativo = true;
    materiaisService
      .getAll({ ativo: 'true' })
      .then((rows) => {
        if (ativo) setMateriais(rows);
      })
      .catch(() => {
        if (ativo) setMateriais([]);
      });
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    if (!familiaId) return;
    let ativo = true;
    setCarregando(true);
    familiasProdutoService
      .getById(familiaId)
      .then((fam) => {
        if (!ativo) return;
        setForm({
          codigo_figura: fam.codigo_figura ?? '',
          descricao_base: fam.descricao_base ?? '',
          ativo: fam.ativo,
          tipo_regra_codigo: fam.tipo_regra_codigo ?? 'BASE_POLEGADA',
          tipo_dimensional: fam.tipo_dimensional ?? 'SIMPLES',
          categoria_produto: fam.categoria_produto ?? 'PRODUTO_TECNICO',
          separador_base_medidas: fam.separador_base_medidas || '.',
          ncm_padrao: fam.ncm_padrao ?? fam.ncm_padrao_id ?? null,
          unidade_padrao: fam.unidade_padrao ?? '',
          unidade_estoque_padrao: fam.unidade_estoque_padrao ?? '',
          unidade_venda_padrao: fam.unidade_venda_padrao ?? '',
          unidade_compra_padrao: fam.unidade_compra_padrao ?? '',
          unidade_fiscal_padrao: fam.unidade_fiscal_padrao ?? '',
          tipo_fisico: fam.tipo_fisico ?? 'PECA',
          tipo_controle_unidade: fam.tipo_controle_unidade ?? 'PECA',
          unidades_venda_permitidas: fam.unidades_venda_permitidas ?? [],
          unidades_compra_permitidas: fam.unidades_compra_permitidas ?? [],
          comprimento_padrao_barra_m: fam.comprimento_padrao_barra_m ?? null,
          peso_por_metro_kg: fam.peso_por_metro_kg ?? null,
          peso_por_peca_kg: fam.peso_por_peca_kg ?? null,
          peso_por_chapa_kg: fam.peso_por_chapa_kg ?? null,
          densidade: fam.densidade ?? null,
          usa_conversao_dimensional: !!fam.usa_conversao_dimensional,
          controla_composicao_fisica: !!fam.controla_composicao_fisica,
          exige_certificado_qualidade: !!fam.exige_certificado_qualidade,
          tipo_composicao_fisica: fam.tipo_composicao_fisica || 'BARRA_M',
          observacoes_conversao: fam.observacoes_conversao ?? '',
          material_base: fam.material_base ?? '',
          material_base_ref: fam.material_base_ref ?? null,
          tipo_peca: fam.tipo_peca ?? '',
          material_vedacao: fam.material_vedacao ?? '',
        });
        setNcmOption(
          fam.ncm_padrao_info
            ? {
                id: fam.ncm_padrao_info.id,
                codigo: fam.ncm_padrao_info.codigo,
                descricao: fam.ncm_padrao_info.descricao,
              }
            : null,
        );
      })
      .catch((e) => {
        if (ativo) setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar a família.' }));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [familiaId]);

  const handleField = <K extends keyof FamiliaFormState>(key: K, value: FamiliaFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  // Mesma cadeia do modal legado: categoria restringe os tipos dimensionais e o tipo sugere a regra.
  const handleCategoriaChange = (categoria: CategoriaProdutoSugestao) => {
    setForm((prev) => {
      if (categoria === 'MANUAL_FABRICANTE') {
        return {
          ...prev,
          categoria_produto: categoria,
          tipo_dimensional: 'MANUAL',
          tipo_regra_codigo: 'MANUAL_FABRICANTE',
        };
      }
      const tiposPermitidos = tiposDimensionaisPorCategoria(categoria).map((t) => t.value);
      const tipo = tiposPermitidos.includes(prev.tipo_dimensional)
        ? prev.tipo_dimensional
        : tiposPermitidos[0] ?? 'SIMPLES';
      return {
        ...prev,
        categoria_produto: categoria,
        tipo_dimensional: tipo,
        tipo_regra_codigo: prev.categoria_produto === 'MANUAL_FABRICANTE' ? 'BASE_POLEGADA' : prev.tipo_regra_codigo,
      };
    });
  };

  const handleTipoDimensionalChange = (tipo: TipoDimensional) => {
    setForm((prev) => ({ ...prev, tipo_dimensional: tipo, tipo_regra_codigo: sugerirTipoRegraPorDimensional(tipo) }));
  };

  const handleMaterialChange = (v: string) => {
    if (v === SEM_MATERIAL) {
      setForm((prev) => ({ ...prev, material_base_ref: null, material_base: '' }));
      return;
    }
    const materialId = Number(v);
    const mat = materiais.find((m) => m.id === materialId) ?? null;
    setForm((prev) => ({
      ...prev,
      material_base_ref: materialId,
      material_base: mat?.nome ?? prev.material_base,
    }));
  };

  const handleSubmit = async () => {
    setErro(null);
    const erroDescricao = validarDescricaoBaseLocal(form.descricao_base);
    if (erroDescricao) {
      setErro(erroDescricao);
      return;
    }

    // Payload parcial: esta tela é dona da estrutura do molde (regra, NCM), da
    // classificação técnica e do molde de medidas/unidades da Sprint 3.6 — o produto
    // apenas herda tudo isto ao ser cadastrado com a família.
    const payload: Partial<FamiliaProduto> = {
      descricao_base: form.descricao_base.trim(),
      ativo: form.ativo,
      tipo_regra_codigo: form.tipo_regra_codigo,
      tipo_dimensional: form.tipo_dimensional,
      categoria_produto: form.categoria_produto,
      separador_base_medidas: form.separador_base_medidas || '.',
      ncm_padrao: form.ncm_padrao,
      unidade_padrao: form.unidade_padrao,
      unidade_estoque_padrao: form.unidade_estoque_padrao,
      unidade_venda_padrao: form.unidade_venda_padrao,
      unidade_compra_padrao: form.unidade_compra_padrao,
      unidade_fiscal_padrao: form.unidade_fiscal_padrao,
      tipo_fisico: form.tipo_fisico,
      tipo_controle_unidade: form.tipo_controle_unidade,
      unidades_venda_permitidas: form.unidades_venda_permitidas,
      unidades_compra_permitidas: form.unidades_compra_permitidas,
      comprimento_padrao_barra_m: form.comprimento_padrao_barra_m,
      peso_por_metro_kg: form.peso_por_metro_kg,
      peso_por_peca_kg: form.peso_por_peca_kg,
      peso_por_chapa_kg: form.peso_por_chapa_kg,
      densidade: form.densidade,
      usa_conversao_dimensional: form.usa_conversao_dimensional,
      controla_composicao_fisica: form.controla_composicao_fisica,
      exige_certificado_qualidade: form.exige_certificado_qualidade,
      tipo_composicao_fisica: form.tipo_composicao_fisica,
      observacoes_conversao: form.observacoes_conversao,
      material_base: form.material_base,
      material_base_ref: form.material_base_ref,
      tipo_peca: form.tipo_peca,
      material_vedacao: form.material_vedacao,
    };

    setSalvando(true);
    try {
      if (isEdit && familiaId) {
        await familiasProdutoService.update(familiaId, payload);
        toast.success('Família atualizada com sucesso.');
        navigate('/familias');
      } else {
        const created = await familiasProdutoService.create({
          modo_codigo: 'AUTOMATICO',
          ...payload,
        });
        toast.success('Família criada com sucesso.');
        navigate(`/familias/${created.id}/editar`, { replace: true });
      }
    } catch (e) {
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível salvar a família.' });
      setErro(msg);
      toast.error(msg);
    } finally {
      setSalvando(false);
    }
  };

  const handleCancel = () => navigate('/familias');

  if (carregando) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span>Carregando família…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={isEdit ? `Editar família ${form.codigo_figura}` : 'Nova família'}
        breadcrumbs={[
          { label: 'Catálogo', path: '/produtos' },
          { label: 'Famílias', path: '/familias' },
          { label: isEdit ? `Editar ${form.codigo_figura}` : 'Nova' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <NexusButton type="button" variant="outline" onClick={handleCancel} disabled={salvando}>
              <X className="h-4 w-4 mr-2" />
              Cancelar
            </NexusButton>
            <NexusButton type="button" onClick={handleSubmit} disabled={salvando} loading={salvando}>
              <Save className="h-4 w-4 mr-2" />
              Salvar
            </NexusButton>
          </div>
        }
      />

      {erro && (
        <div
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {erro}
        </div>
      )}

      <div className="space-y-6">
        {/* ===== Dados gerais ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Dados gerais</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Identificação da família e material base herdado pelos produtos
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div className="lg:col-span-2">
                <CampoLabel>
                  Nome / descrição base
                  <Obrigatorio />
                </CampoLabel>
                <Input
                  className="h-10"
                  value={form.descricao_base}
                  onChange={(e) => handleField('descricao_base', e.target.value)}
                  placeholder={'Ex.: Válvula de esfera inox 316L 2"'}
                />
              </div>

              {isEdit ? (
                <div>
                  <CampoLabel>Código / figura</CampoLabel>
                  <Input className="h-10 font-mono" value={form.codigo_figura} readOnly disabled />
                  <p className="text-xs text-muted-foreground mt-1">
                    Gerado pela regra da família; não é editável aqui.
                  </p>
                </div>
              ) : (
                <div>
                  <CampoLabel>Código / figura</CampoLabel>
                  <div className="h-10 rounded-md border border-input bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                    {MENSAGEM_CODIGO_FIGURA_AUTO}
                  </div>
                </div>
              )}

              <div>
                <CampoLabel>Material base</CampoLabel>
                <Select value={form.material_base_ref?.toString() ?? SEM_MATERIAL} onValueChange={handleMaterialChange}>
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="Selecione…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={SEM_MATERIAL}>— Sem material —</SelectItem>
                    {materiais.map((m) => (
                      <SelectItem key={m.id} value={m.id.toString()}>
                        {m.nome}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-3 pt-6">
                <Switch
                  id="familia-ativa"
                  checked={form.ativo}
                  onCheckedChange={(v) => handleField('ativo', v)}
                />
                <Label htmlFor="familia-ativa" className="cursor-pointer text-sm font-medium">
                  {form.ativo ? 'Ativa' : 'Inativa'}
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Regras de geração de código e estrutura ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Boxes className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Regras de Geração de Código e Estrutura</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Modelo de formação do código e significado dimensional — são estes campos que definem
              o que o produto desta família precisa preencher
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div>
                <CampoLabel>
                  Categoria do produto
                  <Obrigatorio />
                </CampoLabel>
                <Select
                  value={form.categoria_produto}
                  onValueChange={(v) => handleCategoriaChange(v as CategoriaProdutoSugestao)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPCOES_CATEGORIA_FAMILIA.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <CampoLabel>
                  Modelo de medidas (tipo dimensional)
                  <Obrigatorio />
                </CampoLabel>
                <Select
                  value={form.tipo_dimensional}
                  onValueChange={(v) => handleTipoDimensionalChange(v as TipoDimensional)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {tiposDimensionaisPorCategoria(form.categoria_produto).map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">{hintTipoDimensional(form.tipo_dimensional)}</p>
              </div>

              <div>
                <CampoLabel>
                  Regra de código
                  <Obrigatorio />
                </CampoLabel>
                <Select
                  value={form.tipo_regra_codigo}
                  onValueChange={(v) => handleField('tipo_regra_codigo', v as TipoRegraCodigo)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPCOES_TIPO_REGRA.map((r) => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <CampoLabel>Separador base → medidas</CampoLabel>
                <Input
                  className="h-10 w-16 font-mono"
                  maxLength={1}
                  value={form.separador_base_medidas}
                  onChange={(e) => handleField('separador_base_medidas', e.target.value.slice(-1) || '.')}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Em UNDERSCORE_POLEGADA o código usa &quot;_&quot; fixo; o separador acima afeta as demais regras.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Conversão de Medidas e Unidades ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Ruler className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Conversão de Medidas e Unidades</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Molde de unidades, pesos e conversão dimensional que os produtos desta família herdam
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div>
                <CampoLabel>Tipo físico</CampoLabel>
                <Select
                  value={form.tipo_fisico}
                  onValueChange={(v) => handleField('tipo_fisico', v as TipoFisicoProduto)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="Selecione…" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIPO_FISICO_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <CampoLabel>Tipo de controle de unidade</CampoLabel>
                <Select
                  value={form.tipo_controle_unidade}
                  onValueChange={(v) => handleField('tipo_controle_unidade', v as TipoControleUnidade)}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="Selecione…" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIPO_CONTROLE_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <CampoLabel>Tipo de composição física</CampoLabel>
                <Select
                  value={form.tipo_composicao_fisica}
                  onValueChange={(v) => handleField('tipo_composicao_fisica', v)}
                  disabled={!form.controla_composicao_fisica}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="Selecione…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="BARRA_M">Barra — comprimento em metros (tubo)</SelectItem>
                    <SelectItem value="PECA_KG">Peça/chapa — peso real em kg</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
              <div>
                <CampoLabel>Unidade padrão</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={16}
                  value={form.unidade_padrao}
                  onChange={(e) => handleField('unidade_padrao', e.target.value)}
                  placeholder="Ex.: UN"
                />
              </div>
              <div>
                <CampoLabel>Unidade de estoque</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={16}
                  value={form.unidade_estoque_padrao}
                  onChange={(e) => handleField('unidade_estoque_padrao', e.target.value)}
                  placeholder="Ex.: M"
                />
              </div>
              <div>
                <CampoLabel>Unidade de venda</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={16}
                  value={form.unidade_venda_padrao}
                  onChange={(e) => handleField('unidade_venda_padrao', e.target.value)}
                  placeholder="Ex.: PC"
                />
              </div>
              <div>
                <CampoLabel>Unidade de compra</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={16}
                  value={form.unidade_compra_padrao}
                  onChange={(e) => handleField('unidade_compra_padrao', e.target.value)}
                  placeholder="Ex.: M"
                />
              </div>
              <div>
                <CampoLabel>Unidade fiscal</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={16}
                  value={form.unidade_fiscal_padrao}
                  onChange={(e) => handleField('unidade_fiscal_padrao', e.target.value)}
                  placeholder="Ex.: M"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
              <div className="flex items-center gap-3">
                <Switch
                  id="fam-usa-conversao"
                  checked={form.usa_conversao_dimensional}
                  onCheckedChange={(v) => handleField('usa_conversao_dimensional', v)}
                />
                <Label htmlFor="fam-usa-conversao" className="cursor-pointer text-sm font-medium">
                  Usa conversão dimensional
                </Label>
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  id="fam-controla-composicao"
                  checked={form.controla_composicao_fisica}
                  onCheckedChange={(v) => handleField('controla_composicao_fisica', v)}
                />
                <Label htmlFor="fam-controla-composicao" className="cursor-pointer text-sm font-medium">
                  Controla composição física na conferência NF-e
                </Label>
              </div>
            </div>
            {form.controla_composicao_fisica ? (
              <p className="text-xs text-muted-foreground">
                {form.tipo_composicao_fisica === 'PECA_KG'
                  ? 'Na conferência, informe o peso real de cada peça/chapa. O estoque base fica em KG.'
                  : 'Na conferência, informe quantidade de barras e comprimento unitário em metros. O estoque base fica em M.'}
              </p>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <CampoLabel>Unidades permitidas para venda</CampoLabel>
                <div className="flex flex-wrap gap-3">
                  {UNIDADES_CATALOGO.map((u) => (
                    <label key={u} className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.unidades_venda_permitidas.includes(u)}
                        onChange={() =>
                          handleField(
                            'unidades_venda_permitidas',
                            toggleUnidadeLista(form.unidades_venda_permitidas, u),
                          )
                        }
                      />
                      {u}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <CampoLabel>Unidades permitidas para compra</CampoLabel>
                <div className="flex flex-wrap gap-3">
                  {UNIDADES_CATALOGO.map((u) => (
                    <label key={u} className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.unidades_compra_permitidas.includes(u)}
                        onChange={() =>
                          handleField(
                            'unidades_compra_permitidas',
                            toggleUnidadeLista(form.unidades_compra_permitidas, u),
                          )
                        }
                      />
                      {u}
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
              <div>
                <CampoLabel>Comprimento padrão da barra (m)</CampoLabel>
                <Input
                  type="number"
                  step="0.001"
                  className="h-10"
                  value={form.comprimento_padrao_barra_m ?? ''}
                  onChange={(e) =>
                    handleField(
                      'comprimento_padrao_barra_m',
                      e.target.value === '' ? null : Number(e.target.value),
                    )
                  }
                />
              </div>
              <div>
                <CampoLabel>Peso por metro (kg/m)</CampoLabel>
                <Input
                  type="number"
                  step="0.0001"
                  className="h-10"
                  value={form.peso_por_metro_kg ?? ''}
                  onChange={(e) =>
                    handleField('peso_por_metro_kg', e.target.value === '' ? null : Number(e.target.value))
                  }
                />
              </div>
              <div>
                <CampoLabel>Peso por peça (kg)</CampoLabel>
                <Input
                  type="number"
                  step="0.0001"
                  className="h-10"
                  value={form.peso_por_peca_kg ?? ''}
                  onChange={(e) =>
                    handleField('peso_por_peca_kg', e.target.value === '' ? null : Number(e.target.value))
                  }
                />
              </div>
              <div>
                <CampoLabel>Peso por chapa (kg)</CampoLabel>
                <Input
                  type="number"
                  step="0.0001"
                  className="h-10"
                  value={form.peso_por_chapa_kg ?? ''}
                  onChange={(e) =>
                    handleField('peso_por_chapa_kg', e.target.value === '' ? null : Number(e.target.value))
                  }
                />
              </div>
              <div>
                <CampoLabel>Densidade (opcional)</CampoLabel>
                <Input
                  type="number"
                  step="0.0001"
                  className="h-10"
                  value={form.densidade ?? ''}
                  onChange={(e) =>
                    handleField('densidade', e.target.value === '' ? null : Number(e.target.value))
                  }
                />
              </div>
            </div>

            <div>
              <CampoLabel>Observações da conversão</CampoLabel>
              <Textarea
                className="min-h-[72px] text-sm"
                maxLength={512}
                value={form.observacoes_conversao}
                onChange={(e) => handleField('observacoes_conversao', e.target.value)}
                placeholder="Notas internas sobre conversão, tolerâncias, fornecedor, etc."
              />
            </div>
          </CardContent>
        </Card>

        {/* ===== Classificação técnica ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Classificação técnica</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Padrões técnicos herdados pelos produtos desta família
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div>
                <CampoLabel>Tipo de peça</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.tipo_peca}
                  onChange={(e) => handleField('tipo_peca', e.target.value)}
                  placeholder="Ex.: Válvula esfera"
                />
              </div>
              <div>
                <CampoLabel>Material de vedação</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.material_vedacao}
                  onChange={(e) => handleField('material_vedacao', e.target.value)}
                  placeholder="Ex.: PTFE"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Qualidade ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Qualidade</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Requisito herdado pelos produtos desta família
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Switch
                id="fam-exige-certificado"
                checked={form.exige_certificado_qualidade}
                onCheckedChange={(v) => handleField('exige_certificado_qualidade', v)}
              />
              <Label htmlFor="fam-exige-certificado" className="cursor-pointer text-sm font-medium">
                Exige Certificado de Qualidade
              </Label>
            </div>
            {form.exige_certificado_qualidade ? (
              <p className="text-xs text-muted-foreground mt-3">
                Os produtos desta família precisam de Certificado de Qualidade (CQ) com corrida/lote e dados
                técnicos. O módulo de Qualidade usa esse requisito para saber o que rastreabilizar.
              </p>
            ) : null}
          </CardContent>
        </Card>

        {/* ===== Fiscal ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Fiscal</CardTitle>
            </div>
            <CardDescription className="text-xs">
              NCM sugerido para os produtos desta família
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div className="lg:col-span-2">
                <CampoLabel>NCM padrão</CampoLabel>
                <NcmAutocomplete
                  value={ncmOption}
                  onChange={(opt) => {
                    setNcmOption(opt);
                    handleField('ncm_padrao', opt?.id ?? null);
                  }}
                  searchNcm={(term, limit) => ncmApiService.search(term, limit)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  O produto usa este NCM quando não informa um específico. Se não encontrar resultados,
                  verifique se a lista TIPI/NCM foi importada.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {isEdit && familiaId ? (
          <FamiliaDominioCard familiaId={familiaId} />
        ) : (
          <p className="text-xs text-muted-foreground">
            Após salvar esta família, o card “Variações Permitidas (Domínio)” libera a escolha de
            roscas, schedules e polegadas.
          </p>
        )}
      </div>
    </div>
  );
};

export default FamiliaFormPage;
