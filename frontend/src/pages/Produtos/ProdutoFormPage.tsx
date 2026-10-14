import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, Save, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useProdutoForm } from './hooks/useProdutoForm';
import { ProdutoGeralFormTab } from './tabs/ProdutoGeralFormTab';
import { ProdutoClassificacaoFormTab } from './tabs/ProdutoClassificacaoFormTab';
import { ProdutoFiscalFormTab } from './tabs/ProdutoFiscalFormTab';
import { ProdutoPainelOperacionalTab } from '@/components/produtos/ProdutoPainelOperacionalTab';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';

const ProdutoFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const produtoId = id ? Number(id) : undefined;

  const {
    form,
    setForm,
    salvando,
    erro,
    preview,
    carregando,
    salvar,
    familiaSelecionada,
    duplicateCodigo,
    setModoCodigo,
  } = useProdutoForm(produtoId, [], async () => {
    // onSaveSuccess callback
    if (!isEdit) {
      // For create, we need to wait for the ID to be returned
      // The hook returns the new ID, so we handle navigation in the handleSubmit
    }
  });

  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedId, setLastSavedId] = useState<number | null>(null);

  const handleSubmit = async () => {
    setSaveError(null);
    const result = await salvar();
    if (result.sucesso && result.id) {
      setLastSavedId(result.id);
      const targetId = result.id;
      toast.success(isEdit ? 'Produto atualizado com sucesso.' : 'Produto criado com sucesso.');
      navigate(`/produtos/${targetId}`);
    } else if (!result.sucesso) {
      // Error is already set in the hook via `erro` state
      if (erro) {
        setSaveError(erro);
        toast.error(erro);
      }
    }
  };

  const handleCancel = () => {
    navigate('/produtos');
  };

  // Loading state for initial fetch (edit mode)
  if (carregando) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span>Carregando produto…</span>
        </div>
      </div>
    );
  }

  // Error state for initial fetch
  if (erro && isEdit) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive text-center" role="alert">
          {erro}
        </div>
        <NexusButton variant="outline" onClick={handleCancel}>
          <X className="h-4 w-4 mr-2" />
          Voltar à listagem
        </NexusButton>
      </div>
    );
  }

  // Save error banner (shown above tabs)
  const showSaveError = saveError || (erro && !carregando);

  return (
    <div className="space-y-6">
      <PageHeader
        title={isEdit ? `Editar produto #${id}` : 'Novo produto'}
        breadcrumbs={[
          { label: 'Cadastros', path: '/produtos' },
          { label: 'Produtos', path: '/produtos' },
          { label: isEdit ? `Editar #${id}` : 'Novo' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <NexusButton
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={salvando}
            >
              <X className="h-4 w-4 mr-2" />
              Cancelar
            </NexusButton>
            <NexusButton
              type="button"
              onClick={handleSubmit}
              disabled={salvando}
              loading={salvando}
            >
              <Save className="h-4 w-4 mr-2" />
              Salvar
            </NexusButton>
          </div>
        }
      />

      {showSaveError && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {(saveError || erro) && <p>{saveError || erro}</p>}
        </div>
      )}

      <Tabs defaultValue="geral" className="w-full">
        <TabsList className="flex flex-wrap gap-1 w-full justify-start">
          <TabsTrigger value="geral">Dados gerais</TabsTrigger>
          <TabsTrigger value="classificacao">Classificação industrial</TabsTrigger>
          <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
          {isEdit && (
            <>
              <TabsTrigger value="painel">Painel operacional</TabsTrigger>
              <TabsTrigger value="rastreabilidade">Rastreabilidade</TabsTrigger>
              <TabsTrigger value="historico">Histórico</TabsTrigger>
            </>
          )}
        </TabsList>

        <TabsContent value="geral" className="mt-4">
          <ProdutoGeralFormTab
            form={form}
            setForm={setForm}
            preview={preview}
            familiaSelecionada={familiaSelecionada}
            erro={showSaveError ? (saveError || erro) : undefined}
            duplicateCodigo={duplicateCodigo}
            setModoCodigo={setModoCodigo}
          />
        </TabsContent>

        <TabsContent value="classificacao" className="mt-4">
          <ProdutoClassificacaoFormTab
            form={form}
            setForm={setForm}
            preview={preview}
          />
        </TabsContent>

        <TabsContent value="fiscal" className="mt-4">
          <ProdutoFiscalFormTab
            form={form}
            setForm={setForm}
            preview={preview}
            familiaSelecionada={familiaSelecionada}
          />
        </TabsContent>

        {isEdit && (
          <>
            <TabsContent value="painel" className="mt-4">
              <ProdutoPainelOperacionalTab produtoId={produtoId} active={true} />
            </TabsContent>

            <TabsContent value="rastreabilidade" className="mt-4">
              <ProdutoRastreabilidadeTab produtoId={produtoId} active={true} />
            </TabsContent>

            <TabsContent value="historico" className="mt-4">
              <HistoricoAlteracoesPanel
                appLabel="cadastros"
                modelName="produto"
                objectId={produtoId}
                active={true}
                enabled={true}
              />
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
};

export default ProdutoFormPage;