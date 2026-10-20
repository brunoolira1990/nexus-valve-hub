import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2, Save, X } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { useProdutoForm } from './hooks/useProdutoForm';
import { ProdutoGeralFormTab } from './tabs/ProdutoGeralFormTab';
import { ProdutoClassificacaoFormTab } from './tabs/ProdutoClassificacaoFormTab';
import { ProdutoFiscalFormTab } from './tabs/ProdutoFiscalFormTab';
import { ProdutoPainelOperacionalTab } from '@/components/produtos/ProdutoPainelOperacionalTab';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import { familiasProdutoService, produtosService } from '@/services/api/produtos';
import { materiaisService } from '@/services/api/materiais';
import type { FamiliaProduto, Produto } from '@/types';
import type { Material } from '@/types/material';
import { campoId, type CampoFormProdutoInvalido } from './lib/erroCampo';

/** Seções do painel único. O `id` é a âncora usada pelo menu lateral. */
const SECOES: ReadonlyArray<{ id: string; rotulo: string; edicao?: boolean }> = [
  { id: 'secao-geral', rotulo: 'Identificação' },
  { id: 'secao-classificacao', rotulo: 'Classificação industrial' },
  { id: 'secao-fiscal', rotulo: 'Fiscal' },
  { id: 'secao-painel', rotulo: 'Painel operacional', edicao: true },
  { id: 'secao-rastreabilidade', rotulo: 'Rastreabilidade', edicao: true },
  { id: 'secao-historico', rotulo: 'Histórico', edicao: true },
];

const ProdutoFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isEdit = Boolean(id);
  const produtoId = id ? Number(id) : undefined;

  // Famílias carregadas no container e passadas ao hook (necessário para
  // familiaSelecionada / famReq funcionarem — antes vinha [] e ficava sempre null).
  const [familias, setFamilias] = useState<FamiliaProduto[]>([]);
  const [materiais, setMateriais] = useState<Material[]>([]);
  const [carregandoMateriais, setCarregandoMateriais] = useState(true);
  const [produtosOpcoes, setProdutosOpcoes] = useState<
    Array<{ id: number; codigo_completo: string; descricao: string }>
  >([]);

  useEffect(() => {
    let ativo = true;
    void materiaisService
      .getAll({ ativo: 'true' })
      .then((list) => {
        if (ativo) setMateriais(list);
      })
      .catch(() => {
        if (ativo) setMateriais([]);
      })
      .finally(() => {
        if (ativo) setCarregandoMateriais(false);
      });
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    let ativo = true;
    void familiasProdutoService
      .getAll({ apenas_ativas: '1' })
      .then((list) => {
        if (ativo) setFamilias(list);
      })
      .catch(() => {
        if (ativo) setFamilias([]);
      });
    return () => {
      ativo = false;
    };
  }, []);

  // Lista de produtos para o seletor de componentes da Composição (apenas em edição).
  useEffect(() => {
    if (!isEdit) return;
    let ativo = true;
    void produtosService
      .search('', 200)
      .then((hits: Produto[]) => {
        if (!ativo) return;
        setProdutosOpcoes(
          hits.map((p) => ({
            id: p.id,
            codigo_completo: p.codigo_completo,
            descricao: p.descricao,
          }))
        );
      })
      .catch(() => {
        if (ativo) setProdutosOpcoes([]);
      });
    return () => {
      ativo = false;
    };
  }, [isEdit]);

  const {
    form,
    setForm,
    salvando,
    erro,
    preview,
    carregando,
    salvar,
    familiaSelecionada,
    famReq,
    editing,
    duplicateCodigo,
    setModoCodigo,
    herdouFamilia,
    limparHerdadoCampo,
  } = useProdutoForm(produtoId, familias, async () => {
    // onSaveSuccess — navegação é tratada em handleSubmit (precisa do id retornado).
  }, materiais);

  const [saveError, setSaveError] = useState<string | null>(null);
  // Campo apontado pela validação do salvar(): a página rola até ele e o destaca.
  const [campoErro, setCampoErro] = useState<CampoFormProdutoInvalido | null>(null);

  // Pré-preenchimento vindo de outra tela (ex.: proposta → "Cadastrar novo produto").
  const descricaoUrl = searchParams.get('descricao') || '';
  useEffect(() => {
    if (isEdit || !descricaoUrl) return;
    setForm((prev) => (prev.descricao ? prev : { ...prev, descricao: descricaoUrl }));
  }, [isEdit, descricaoUrl, setForm]);

  const handleSubmit = async () => {
    setSaveError(null);
    const result = await salvar();
    setCampoErro(result.campo ?? null);
    if (result.campo) {
      document
        .getElementById(campoId(result.campo))
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    if (result.sucesso && result.id) {
      toast.success(isEdit ? 'Produto atualizado com sucesso.' : 'Produto criado com sucesso.');
      navigate(`/produtos/${result.id}`);
    } else if (!result.sucesso && erro) {
      setSaveError(erro);
      toast.error(erro);
    }
  };

  const handleCancel = () => {
    navigate('/produtos');
  };

  // A família tem módulo dedicado desde a Sprint 3.6: o botão navega para lá.
  const handleNovaFamilia = useMemo(() => () => navigate('/familias/nova'), [navigate]);

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

  if (erro && isEdit && !editing) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive text-center"
          role="alert"
        >
          {erro}
        </div>
        <NexusButton variant="outline" onClick={handleCancel}>
          <X className="h-4 w-4 mr-2" />
          Voltar à listagem
        </NexusButton>
      </div>
    );
  }

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

      {showSaveError && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          <p>{saveError || erro}</p>
        </div>
      )}

      {/* Painel único: as três seções antes separadas em abas vivem agora na mesma
          rolagem, porque a Família dita os campos técnicos e o operador precisa ver a
          herança junto de onde ela é selecionada. */}
      <div className="flex items-start gap-6">
        <nav
          aria-label="Seções do cadastro"
          className="sticky top-4 hidden w-52 shrink-0 flex-col gap-1 lg:flex"
        >
          {SECOES.filter((s) => !s.edicao || isEdit).map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={(e) => {
                e.preventDefault();
                document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
              className="rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {s.rotulo}
            </a>
          ))}
        </nav>

        <div className="min-w-0 flex-1 space-y-6">
          <section id="secao-geral" className="space-y-6 scroll-mt-20">
            <ProdutoGeralFormTab
              form={form}
              setForm={setForm}
              preview={preview}
              familiaSelecionada={familiaSelecionada}
              duplicateCodigo={duplicateCodigo}
              setModoCodigo={setModoCodigo}
              onNovaFamilia={handleNovaFamilia}
              editingCodigo={editing?.codigo_completo ?? null}
              campoErro={campoErro}
            />
          </section>

          <section id="secao-classificacao" className="space-y-6 scroll-mt-20">
            <ProdutoClassificacaoFormTab
              form={form}
              setForm={setForm}
              preview={preview}
              familiaSelecionada={familiaSelecionada}
              famReq={famReq}
              editing={editing}
              produtosOpcoes={produtosOpcoes}
              materiais={materiais}
              carregandoMateriais={carregandoMateriais}
              herdouFamilia={herdouFamilia}
              onLimparHerdado={limparHerdadoCampo}
              campoErro={campoErro}
            />
          </section>

          <section id="secao-fiscal" className="space-y-6 scroll-mt-20">
            <ProdutoFiscalFormTab
              form={form}
              setForm={setForm}
              preview={preview}
              familiaSelecionada={familiaSelecionada}
            />
          </section>

          {isEdit && (
            <>
              <section id="secao-painel" className="scroll-mt-20">
                <ProdutoPainelOperacionalTab produtoId={produtoId} active={true} />
              </section>

              <section id="secao-rastreabilidade" className="scroll-mt-20">
                <ProdutoRastreabilidadeTab produtoId={produtoId} active={true} />
              </section>

              <section id="secao-historico" className="scroll-mt-20">
                <HistoricoAlteracoesPanel
                  appLabel="cadastros"
                  modelName="produto"
                  objectId={produtoId}
                  active={true}
                  enabled={true}
                />
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProdutoFormPage;
