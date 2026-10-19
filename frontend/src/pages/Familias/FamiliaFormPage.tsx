import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Layers, Loader2, Receipt, Save, Wrench, X } from 'lucide-react';
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
import { familiasProdutoService } from '@/services/api/produtos';
import { materiaisService } from '@/services/api/materiais';
import { apiErrorMessage } from '@/services/api/config';
import type { FamiliaProduto } from '@/types';
import type { Material } from '@/types/material';
import { MENSAGEM_CODIGO_FIGURA_AUTO, validarDescricaoBaseLocal } from '@/lib/familiaCodigo';

/** Sentinela do Select — o Radix não aceita value="". */
const SEM_MATERIAL = '__none__';

type FamiliaFormState = {
  codigo_figura: string;
  descricao_base: string;
  ativo: boolean;
  material_base: string;
  material_base_ref: number | null;
  tipo_peca: string;
  subtipo_peca: string;
  norma_tecnica: string;
  pressao_nominal: string;
  tipo_conexao: string;
  material_vedacao: string;
  tipo_acionamento: string;
  cfop_padrao: string;
};

const emptyForm = (): FamiliaFormState => ({
  codigo_figura: '',
  descricao_base: '',
  ativo: true,
  material_base: '',
  material_base_ref: null,
  tipo_peca: '',
  subtipo_peca: '',
  norma_tecnica: '',
  pressao_nominal: '',
  tipo_conexao: '',
  material_vedacao: '',
  tipo_acionamento: '',
  cfop_padrao: '',
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
          material_base: fam.material_base ?? '',
          material_base_ref: fam.material_base_ref ?? null,
          tipo_peca: fam.tipo_peca ?? '',
          subtipo_peca: fam.subtipo_peca ?? '',
          norma_tecnica: fam.norma_tecnica ?? '',
          pressao_nominal: fam.pressao_nominal ?? '',
          tipo_conexao: fam.tipo_conexao ?? '',
          material_vedacao: fam.material_vedacao ?? '',
          tipo_acionamento: fam.tipo_acionamento ?? '',
          cfop_padrao: fam.cfop_padrao ?? '',
        });
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

    // Payload parcial: esta tela é dona apenas destes campos.
    // Os demais (regra de código, unidades, dims) continuam no modal legado de produtos.
    const payload: Partial<FamiliaProduto> = {
      descricao_base: form.descricao_base.trim(),
      ativo: form.ativo,
      material_base: form.material_base,
      material_base_ref: form.material_base_ref,
      tipo_peca: form.tipo_peca,
      subtipo_peca: form.subtipo_peca,
      norma_tecnica: form.norma_tecnica,
      pressao_nominal: form.pressao_nominal,
      tipo_conexao: form.tipo_conexao,
      material_vedacao: form.material_vedacao,
      tipo_acionamento: form.tipo_acionamento,
      cfop_padrao: form.cfop_padrao,
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
                <CampoLabel>Subtipo</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.subtipo_peca}
                  onChange={(e) => handleField('subtipo_peca', e.target.value)}
                  placeholder="Ex.: 3 peças, passagem reduzida"
                />
              </div>
              <div>
                <CampoLabel>Norma técnica</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={100}
                  value={form.norma_tecnica}
                  onChange={(e) => handleField('norma_tecnica', e.target.value)}
                  placeholder="Ex.: ASME B16.34"
                />
              </div>
              <div>
                <CampoLabel>Pressão nominal</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.pressao_nominal}
                  onChange={(e) => handleField('pressao_nominal', e.target.value)}
                  placeholder="Ex.: 150 lb"
                />
              </div>
              <div>
                <CampoLabel>Tipo de conexão</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.tipo_conexao}
                  onChange={(e) => handleField('tipo_conexao', e.target.value)}
                  placeholder="Ex.: Solda socket"
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
              <div>
                <CampoLabel>Tipo de acionamento</CampoLabel>
                <Input
                  className="h-10"
                  maxLength={50}
                  value={form.tipo_acionamento}
                  onChange={(e) => handleField('tipo_acionamento', e.target.value)}
                  placeholder="Ex.: Manual (volante)"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Fiscal ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Fiscal</CardTitle>
            </div>
            <CardDescription className="text-xs">CFOP sugerido para os produtos desta família</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <div>
                <CampoLabel>CFOP padrão</CampoLabel>
                <Input
                  className="h-10 font-mono"
                  maxLength={10}
                  value={form.cfop_padrao}
                  onChange={(e) => handleField('cfop_padrao', e.target.value)}
                  placeholder="Ex.: 5.101"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default FamiliaFormPage;
