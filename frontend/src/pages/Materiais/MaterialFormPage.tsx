import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, Save, X } from 'lucide-react';
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
import { AliasesInput } from '@/components/materiais/AliasesInput';
import { materiaisService } from '@/services/api/materiais';
import { apiErrorMessage } from '@/services/api/config';
import {
  materialFormDefault,
  MATERIAL_CATEGORIA_OPTIONS,
  type MaterialFormState,
} from '@/types/material';
import { FlaskConical, FileText, Percent } from 'lucide-react';

/** Rótulo de campo padronizado. */
function CampoLabel({ children }: { children: React.ReactNode }) {
  return <Label className="text-sm font-medium mb-1.5 block">{children}</Label>;
}

function Obrigatorio() {
  return <span className="text-destructive" aria-hidden> *</span>;
}

const MaterialFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const materialId = id ? Number(id) : undefined;

  const [form, setForm] = useState<MaterialFormState>(materialFormDefault());
  const [carregando, setCarregando] = useState(isEdit);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Carrega dados em modo edição
  useEffect(() => {
    if (!materialId) return;
    let ativo = true;
    setCarregando(true);
    materiaisService
      .getById(materialId)
      .then((mat) => {
        if (!ativo) return;
        // Preenche apenas campos editáveis (exclui read-only)
        setForm({
          nome: mat.nome,
          nome_curto: mat.nome_curto,
          categoria: mat.categoria,
          norma_astm: mat.norma_astm,
          ncm_sugerido: mat.ncm_sugerido,
          densidade_kg_m3: mat.densidade_kg_m3,
          aliases: mat.aliases ?? [],
          ativo: mat.ativo,
          ordem: mat.ordem,
        });
      })
      .catch((e) => {
        if (ativo) setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar o material.' }));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [materialId]);

  const handleField = <K extends keyof MaterialFormState>(key: K, value: MaterialFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    setErro(null);
    if (!form.nome.trim()) {
      setErro('O campo "Nome completo" é obrigatório.');
      return;
    }
    if (!form.nome_curto.trim()) {
      setErro('O campo "Nome curto" é obrigatório.');
      return;
    }
    setSalvando(true);
    try {
      if (isEdit && materialId) {
        await materiaisService.update(materialId, form);
        toast.success('Material atualizado com sucesso.');
      } else {
        const created = await materiaisService.create(form);
        toast.success('Material criado com sucesso.');
        navigate(`/materiais/${created.id}/editar`, { replace: true });
        return;
      }
      navigate('/materiais');
    } catch (e) {
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível salvar o material.' });
      setErro(msg);
      toast.error(msg);
    } finally {
      setSalvando(false);
    }
  };

  const handleCancel = () => navigate('/materiais');

  if (carregando) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span>Carregando material…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={isEdit ? `Editar material #${id}` : 'Novo material'}
        breadcrumbs={[
          { label: 'Catálogo', path: '/produtos' },
          { label: 'Materiais', path: '/materiais' },
          { label: isEdit ? `Editar #${id}` : 'Novo' },
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
        {/* ===== Identificação ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Identificação</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Nome, nome curto, categoria e status do material
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {/* Nome completo */}
              <div className="lg:col-span-2">
                <CampoLabel>
                  Nome completo
                  <Obrigatorio />
                </CampoLabel>
                <Input
                  className="h-10"
                  value={form.nome}
                  onChange={(e) => handleField('nome', e.target.value)}
                  placeholder="Ex.: Aço Inox 316L"
                />
              </div>

              {/* Nome curto */}
              <div>
                <CampoLabel>
                  Nome curto (UI compacta)
                  <Obrigatorio />
                </CampoLabel>
                <Input
                  className="h-10"
                  value={form.nome_curto}
                  onChange={(e) => handleField('nome_curto', e.target.value)}
                  placeholder="Ex.: 316L"
                />
              </div>

              {/* Categoria */}
              <div>
                <CampoLabel>
                  Categoria
                  <Obrigatorio />
                </CampoLabel>
                <Select
                  value={form.categoria}
                  onValueChange={(v) => handleField('categoria', v as MaterialFormState['categoria'])}
                >
                  <SelectTrigger className="h-10 w-full">
                    <SelectValue placeholder="Selecione…" />
                  </SelectTrigger>
                  <SelectContent>
                    {MATERIAL_CATEGORIA_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Ordem */}
              <div>
                <CampoLabel>Ordem de exibição</CampoLabel>
                <Input
                  type="number"
                  className="h-10"
                  value={form.ordem}
                  min={1}
                  onChange={(e) => handleField('ordem', Number(e.target.value) || 100)}
                  placeholder="100"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Menor número aparece primeiro nas listas.
                </p>
              </div>

              {/* Ativo */}
              <div className="flex items-center gap-3 pt-6">
                <Switch
                  id="material-ativo"
                  checked={form.ativo}
                  onCheckedChange={(v) => handleField('ativo', v)}
                />
                <Label htmlFor="material-ativo" className="cursor-pointer text-sm font-medium">
                  {form.ativo ? 'Ativo' : 'Inativo'}
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Especificação técnica ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Especificação técnica</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Norma, NCM orientativo e densidade
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {/* Norma ASTM */}
              <div className="lg:col-span-2">
                <CampoLabel>Norma / especificação</CampoLabel>
                <Input
                  className="h-10"
                  value={form.norma_astm}
                  onChange={(e) => handleField('norma_astm', e.target.value)}
                  placeholder="Ex.: ASTM A182 F316L/CF3M"
                />
              </div>

              {/* NCM sugerido */}
              <div>
                <CampoLabel>NCM sugerido</CampoLabel>
                <Input
                  className="h-10 font-mono"
                  value={form.ncm_sugerido}
                  onChange={(e) => handleField('ncm_sugerido', e.target.value)}
                  placeholder="7307.23.00"
                  maxLength={10}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Apenas orientativo — o NCM real é definido no produto/família.
                </p>
              </div>

              {/* Densidade */}
              <div>
                <CampoLabel>Densidade (kg/m³)</CampoLabel>
                <Input
                  type="number"
                  step="0.01"
                  className="h-10"
                  value={form.densidade_kg_m3 ?? ''}
                  onChange={(e) =>
                    handleField('densidade_kg_m3', e.target.value === '' ? null : e.target.value)
                  }
                  placeholder="Ex.: 7900.00"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Aliases / sinônimos ===== */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Percent className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Aliases / sinônimos</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Termos alternativos usados na busca e na inferência automática de material.
              Ex.: {"316L, CF3M, AISI 316L"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AliasesInput
              value={form.aliases}
              onChange={(list) => handleField('aliases', list)}
              label=""
              placeholder="Digite um sinônimo e pressione Enter"
              hint="Pressione Enter ou clique em Adicionar. Backspace com campo vazio remove o último item."
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MaterialFormPage;
