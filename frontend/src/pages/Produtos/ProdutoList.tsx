import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { familiasProdutoService, ncmApiService, produtosService } from '@/services/api/produtos';
import { apiErrorMessage } from '@/services/api/config';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState, LoadingState } from '@/components/list/ListStates';
import type { FamiliaProduto, Produto, TipoDimensional, TipoRegraCodigo } from '@/types';
import { PRODUTO_UI_LABELS } from '@/lib/operationalUi';
import { formatProdutoMaterial } from '@/lib/produtoMaterial';
import {
  expandirSiglasValvulaDescricaoBase,
  exemploCodigoDimensionalFamilia,
  exemploDescricaoDimensionalFamilia,
  hintTipoDimensional,
  labelsCamposObrigatorios,
  normalizarTipoRegra,
  orientacaoDescricaoBaseFamilia,
  OPCOES_CATEGORIA_FAMILIA,
  OPCOES_TIPO_REGRA,
  requisitosMedidasPermitidasModal,
  sugerirConfiguracaoFamilia,
  sugerirTipoRegraPorDimensional,
  tiposDimensionaisPorCategoria,
} from '@/lib/familiaRegra';
import {
  MENSAGEM_CODIGO_FIGURA_AUTO,
  MENSAGEM_CODIGO_FIGURA_MANUAL,
  alertaCodigoManualRepeteComplementoTemplate,
  classificarDuplicidadeDescricaoFamilia,
  campoCodigoFiguraVisivelNaCriacao,
  deveRecarregarFamiliasAposErroCodigoApi,
  extrairDuplicidadeDescricaoModeloApi,
  montarPayloadFamiliaSalvar,
  podeIniciarSalvarFamilia,
  validarCodigoFiguraManualLocal,
  validarDescricaoBaseLocal,
  type FamiliaDuplicidadeResumo,
} from '@/lib/familiaCodigo';
import { ConversaoMedidasBlock } from '@/components/produtos/ConversaoMedidasBlock';
import { NcmAutocomplete, type NcmOption } from '@/components/produtos/NcmAutocomplete';
import type { TipoControleUnidade, TipoFisicoProduto } from '@/types';
import {formatMoneyBRL} from '@/lib/numberFields';

const emptyFamiliaQuick = () => ({
  codigo_figura: '',
  modo_codigo_figura: 'AUTOMATICO' as 'AUTOMATICO' | 'MANUAL',
  descricao_base: '',
  categoria_produto: 'PRODUTO_TECNICO' as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE',
  tipo_regra_codigo: 'BASE_POLEGADA' as TipoRegraCodigo,
  tipo_dimensional: 'SIMPLES' as TipoDimensional,
  separador_base_medidas: '.',
  ativo: true,
  usa_conversao_dimensional: false,
  controla_composicao_fisica: false,
  tipo_composicao_fisica: 'BARRA_M' as 'BARRA_M' | 'PECA_KG',
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

const Produtos = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const semNcmUrl = searchParams.get('sem_ncm') || '';
  const [activeTab, setActiveTab] = useState<'produtos' | 'familias'>('produtos');
  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    setFilter,
    loading: listLoading,
    error: listError,
    reload: reloadProdutos,
  } = usePaginatedList<Produto>({
    fetchPage: produtosService.listPaginated,
    enabled: activeTab === 'produtos',
    initialFilters: semNcmUrl ? { sem_ncm: semNcmUrl } : {},
  });

  useEffect(() => {
    if (semNcmUrl) setFilter('sem_ncm', semNcmUrl);
  }, [semNcmUrl, setFilter]);

  const [famModalOpen, setFamModalOpen] = useState(false);
  const [familias, setFamilias] = useState<FamiliaProduto[]>([]);
  const [ncmFamiliaOption, setNcmFamiliaOption] = useState<NcmOption | null>(null);
  const [famQuick, setFamQuick] = useState(emptyFamiliaQuick());
  const [famSaveErr, setFamSaveErr] = useState<string | null>(null);
  const [famCodigoFiguraErr, setFamCodigoFiguraErr] = useState<string | null>(null);
  const [famDuplicidadeExistente, setFamDuplicidadeExistente] = useState<FamiliaDuplicidadeResumo | null>(
    null,
  );
  /** true após o usuário aplicar sugestão ou alterar modelo/dimensional/categoria. */
  const [famModeloConfirmado, setFamModeloConfirmado] = useState(false);
  const [famSaving, setFamSaving] = useState(false);
  const [famDeleteErr, setFamDeleteErr] = useState<string | null>(null);
  const [editingFamilia, setEditingFamilia] = useState<FamiliaProduto | null>(null);
  const [listNotice, setListNotice] = useState<string | null>(null);
  const famSavingRef = useRef(false);
  const famDescricaoRef = useRef<HTMLInputElement>(null);

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
  const alertaOdManualCriacao = useMemo(() => {
    if (editingFamilia) return null;
    return alertaCodigoManualRepeteComplementoTemplate(
      famQuick.modo_codigo_figura || 'AUTOMATICO',
      famQuick.codigo_figura,
      famQuick.tipo_regra_codigo,
    );
  }, [
    editingFamilia,
    famQuick.modo_codigo_figura,
    famQuick.codigo_figura,
    famQuick.tipo_regra_codigo,
  ]);

  const limparErroDuplicidadeDescricao = () => {
    setFamDuplicidadeExistente(null);
    setFamSaveErr((prev) => (prev && /mesmo modelo de formação|duplicidade|com esta descrição/i.test(prev) ? null : prev));
  };

  const fetchProdutos = useCallback(async (searchOverride?: string) => {
    if (searchOverride !== undefined) setSearch(searchOverride);
    await reloadProdutos();
  }, [reloadProdutos, setSearch]);

  const loadBases = useCallback(async () => {
    const items = await familiasProdutoService.getAll({ apenas_ativas: '1' });
    setFamilias(items);
  }, []);

  useEffect(() => {
    if (!listNotice) return;
    const t = window.setTimeout(() => setListNotice(null), 6000);
    return () => window.clearTimeout(t);
  }, [listNotice]);

  useEffect(() => {
    if (famModalOpen || activeTab === 'familias') void loadBases();
  }, [famModalOpen, activeTab, loadBases]);

  const regraLabelMap = useMemo(
    () => OPCOES_TIPO_REGRA.reduce<Record<string, string>>((acc, r) => ({ ...acc, [r.value]: r.label }), {}),
    [],
  );

  const famQuickFlags = useMemo(
    () => requisitosMedidasPermitidasModal(famQuick.tipo_dimensional, famQuick.tipo_regra_codigo),
    [famQuick.tipo_dimensional, famQuick.tipo_regra_codigo],
  );
  const manometroEstruturalNaFamilia = famQuick.tipo_dimensional === 'MANOMETRO';
  const sugestaoFamiliaAuto = useMemo(() => sugerirConfiguracaoFamilia(famQuick.descricao_base), [famQuick.descricao_base]);
  const classificacaoDupFamilia = useMemo(
    () =>
      classificarDuplicidadeDescricaoFamilia({
        descricaoBase: famQuick.descricao_base,
        tipoRegraFormulario: famQuick.tipo_regra_codigo,
        tipoRegraSugerido: sugestaoFamiliaAuto.tipo_regra_codigo,
        modeloConfirmado: famModeloConfirmado || !!editingFamilia,
        familias,
        editingId: editingFamilia?.id ?? null,
      }),
    [
      famQuick.descricao_base,
      famQuick.tipo_regra_codigo,
      sugestaoFamiliaAuto.tipo_regra_codigo,
      famModeloConfirmado,
      familias,
      editingFamilia,
    ],
  );

  const openNewFamilia = () => {
    setEditingFamilia(null);
    setFamQuick(emptyFamiliaQuick());
    setFamSaveErr(null);
    setFamCodigoFiguraErr(null);
    setFamDuplicidadeExistente(null);
    setFamModeloConfirmado(false);
    famSavingRef.current = false;
    setFamSaving(false);
    setNcmFamiliaOption(null);
    setFamModalOpen(true);
  };

  const openEditFamilia = (familia: FamiliaProduto) => {
    setEditingFamilia(familia);
    setFamCodigoFiguraErr(null);
    setFamSaveErr(null);
    setFamDuplicidadeExistente(null);
    setFamModeloConfirmado(true);
    famSavingRef.current = false;
    setFamSaving(false);
    setFamQuick({
      codigo_figura: familia.codigo_figura,
      modo_codigo_figura: 'AUTOMATICO',
      descricao_base: familia.descricao_base,
      tipo_regra_codigo: (normalizarTipoRegra(familia.tipo_regra_codigo) ?? 'BASE_POLEGADA') as TipoRegraCodigo,
      categoria_produto: (familia.categoria_produto || 'PRODUTO_TECNICO') as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE',
      tipo_dimensional: (familia.tipo_dimensional || 'SIMPLES') as TipoDimensional,
      separador_base_medidas: familia.separador_base_medidas || '.',
      ativo: familia.ativo,
      usa_conversao_dimensional: !!familia.usa_conversao_dimensional,
      controla_composicao_fisica: !!familia.controla_composicao_fisica,
      tipo_composicao_fisica: (familia.tipo_composicao_fisica || 'BARRA_M') as 'BARRA_M' | 'PECA_KG',
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

  useEffect(() => {
    if (!famModalOpen || !famQuick.ncm_padrao || ncmFamiliaOption?.id === famQuick.ncm_padrao) return;
    void ncmApiService
      .getById(famQuick.ncm_padrao)
      .then((item) => setNcmFamiliaOption(item))
      .catch(() => {});
  }, [famModalOpen, famQuick.ncm_padrao, ncmFamiliaOption?.id]);

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir este produto?')) return;
    try {
      await produtosService.delete(id);
      await fetchProdutos();
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível excluir o produto.' }));
    }
  };

  const handleDeleteFamilia = async (familia: FamiliaProduto) => {
    const ok = confirm(
      `Excluir permanentemente a família/figura ${familia.codigo_figura} — ${familia.descricao_base}?\n\n` +
        'Esta ação não pode ser desfeita. Só é permitida se não houver nenhum produto cadastrado nesta família.',
    );
    if (!ok) return;
    setFamDeleteErr(null);
    try {
      await familiasProdutoService.delete(familia.id);
      await loadBases();
      setListNotice(`Família ${familia.codigo_figura} excluída com sucesso.`);
    } catch (e) {
      setFamDeleteErr(apiErrorMessage(e, { fallback: 'Não foi possível excluir a família.' }));
    }
  };

  const salvarFamiliaRapida = async () => {
    if (!podeIniciarSalvarFamilia(famSavingRef.current)) return;
    setFamSaveErr(null);
    setFamCodigoFiguraErr(null);
    setFamDuplicidadeExistente(null);
    const errDesc = validarDescricaoBaseLocal(famQuick.descricao_base);
    if (errDesc) {
      setFamSaveErr(errDesc);
      return;
    }
    if (!editingFamilia && classificacaoDupFamilia.tipo === 'exata') {
      setFamSaveErr(classificacaoDupFamilia.mensagem);
      setFamDuplicidadeExistente(classificacaoDupFamilia.existente);
      return;
    }
    if (!editingFamilia) {
      const errLocal = validarCodigoFiguraManualLocal(
        famQuick.modo_codigo_figura || 'AUTOMATICO',
        famQuick.codigo_figura,
      );
      if (errLocal) {
        setFamCodigoFiguraErr(errLocal);
        return;
      }
    }
    if (
      !editingFamilia &&
      famQuick.modo_codigo_figura === 'MANUAL' &&
      familiaDuplicada
    ) {
      setFamCodigoFiguraErr(
        `Já existe uma Família/Figura com este código (${familiaDuplicada.codigo_figura}).`,
      );
      return;
    }
    const effSave = requisitosMedidasPermitidasModal(famQuick.tipo_dimensional, famQuick.tipo_regra_codigo);
    famSavingRef.current = true;
    setFamSaving(true);
    try {
      const payload = montarPayloadFamiliaSalvar(famQuick, editingFamilia, effSave) as Omit<
        FamiliaProduto,
        'id'
      >;
      const saved = editingFamilia
        ? await familiasProdutoService.update(editingFamilia.id, payload)
        : await familiasProdutoService.create(payload);
      setFamModalOpen(false);
      setFamQuick(emptyFamiliaQuick());
      setEditingFamilia(null);
      setFamCodigoFiguraErr(null);
      setFamDuplicidadeExistente(null);
      if (!editingFamilia && saved?.codigo_figura) {
        setListNotice(`Família ${saved.codigo_figura} cadastrada com sucesso.`);
      }
      await loadBases();
    } catch (e) {
      const err = e as { response?: { status?: number; data?: Record<string, unknown> } };
      const status = err.response?.status;
      const data = err.response?.data;
      if (status === 400 && data && typeof data === 'object') {
        const dup = extrairDuplicidadeDescricaoModeloApi(data);
        if (dup) {
          setFamSaveErr(dup.mensagem);
          setFamDuplicidadeExistente(dup.existente);
          return;
        }
      }
      const codigoErro =
        status === 400 && data && typeof data === 'object'
          ? (data as Record<string, unknown>).codigo_figura
          : undefined;
      if (codigoErro != null) {
        const msg = Array.isArray(codigoErro) ? String(codigoErro[0]) : String(codigoErro);
        setFamCodigoFiguraErr(msg);
        if (deveRecarregarFamiliasAposErroCodigoApi(msg)) {
          void loadBases();
        }
        return;
      }
      const modoErro =
        status === 400 && data && typeof data === 'object'
          ? (data as Record<string, unknown>).modo_codigo
          : undefined;
      if (modoErro != null) {
        setFamSaveErr(Array.isArray(modoErro) ? String(modoErro[0]) : String(modoErro));
        return;
      }
      setFamSaveErr(apiErrorMessage(e, { fallback: 'Não foi possível salvar a família.' }));
    } finally {
      famSavingRef.current = false;
      setFamSaving(false);
    }
  };

  const opcoesTipoDimensionalFamQuick = useMemo(
    () => tiposDimensionaisPorCategoria(famQuick.categoria_produto),
    [famQuick.categoria_produto],
  );

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
      <PageHeader
        title="Produtos"
        description="Cadastro de produtos e informações fiscais."
        onAdd={() => navigate('/produtos/novo')}
        addLabel="Novo Produto"
        searchValue={search}
        onSearch={setSearch}
      />
      {listNotice ? <p className="text-sm text-emerald-800 dark:text-emerald-200 mb-3">{listNotice}</p> : null}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={openNewFamilia} className="erp-btn-outline text-sm w-full sm:w-auto">
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
          <>
            {listError ? <ErrorState onRetry={() => void reloadProdutos()} /> : null}
            {listLoading ? <LoadingState /> : null}
            {!listLoading && !listError ? (
          <table className="erp-table" data-mobile-table-mode="cards">
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
                    <td>{formatProdutoMaterial(e)}</td>
                    <td>{e.ncm_efetivo?.codigo || e.ncm || '—'}</td>
                    <td>{formatMoneyBRL(e.preco_venda)}</td>
                    <td>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/produtos/${e.id}/editar`)}
                          className="erp-btn-ghost erp-btn-sm"
                        >
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
            ) : null}
            {!listLoading && !listError && count > 0 ? (
              <PaginationControls
                page={page}
                pageSize={pageSize}
                count={count}
                totalPages={totalPages}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            ) : null}
          </>
        ) : (
          <>
            {famDeleteErr ? <p className="text-sm text-destructive p-3">{famDeleteErr}</p> : null}
            <table className="erp-table" data-mobile-table-mode="cards">
            <thead>
              <tr>
                <th>Código figura/base</th>
                <th>Descrição base</th>
                <th>{PRODUTO_UI_LABELS.regraCodigo}</th>
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
                      <button
                        type="button"
                        onClick={() => void handleDeleteFamilia(fml)}
                        className="erp-btn-ghost erp-btn-sm text-destructive"
                        title="Excluir família (permanente; só sem produtos vinculados)"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </>
        )}
      </div>

      <Modal
        isOpen={famModalOpen}
        onClose={() => {
          if (famSavingRef.current) return;
          setFamModalOpen(false);
          setFamSaveErr(null);
          setFamCodigoFiguraErr(null);
          setFamDuplicidadeExistente(null);
          setFamModeloConfirmado(false);
        }}
        title={editingFamilia ? 'Editar família / figura' : 'Nova família / figura'}
        size="lg"
      >
        {famSaveErr && !famDuplicidadeExistente && classificacaoDupFamilia.tipo !== 'exata' ? (
          <p className="text-sm text-destructive mb-2">{famSaveErr}</p>
        ) : null}
        {familiaDuplicada && famQuick.modo_codigo_figura === 'MANUAL' && !editingFamilia && (
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
              className="erp-btn-outline erp-btn-sm mt-2 w-full sm:w-auto sm:ml-2"
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
              className="erp-btn-outline erp-btn-sm mt-2 w-full sm:w-auto sm:ml-2"
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
            {editingFamilia ? (
              <input
                className="erp-input mt-1 font-mono bg-muted/40"
                value={famQuick.codigo_figura}
                readOnly
                aria-readonly="true"
              />
            ) : (
              <div className="mt-1 space-y-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:gap-4">
                  <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="modo_codigo_figura"
                      checked={famQuick.modo_codigo_figura === 'AUTOMATICO'}
                      onChange={() => {
                        setFamCodigoFiguraErr(null);
                        setFamSaveErr(null);
                        setFamQuick((q) => ({
                          ...q,
                          modo_codigo_figura: 'AUTOMATICO',
                          codigo_figura: '',
                        }));
                      }}
                    />
                    Gerar automaticamente
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="modo_codigo_figura"
                      checked={famQuick.modo_codigo_figura === 'MANUAL'}
                      onChange={() => {
                        setFamCodigoFiguraErr(null);
                        setFamQuick((q) => ({ ...q, modo_codigo_figura: 'MANUAL' }));
                      }}
                    />
                    Informar manualmente
                  </label>
                </div>
                {campoCodigoFiguraVisivelNaCriacao(famQuick.modo_codigo_figura) ? (
                  <>
                    <input
                      className={`erp-input font-mono${famCodigoFiguraErr ? ' border-destructive' : ''}`}
                      value={famQuick.codigo_figura}
                      onChange={(e) => {
                        setFamCodigoFiguraErr(null);
                        setFamQuick((q) => ({ ...q, codigo_figura: e.target.value }));
                      }}
                      placeholder="Ex.: 0023OD ou FLEG01"
                      maxLength={32}
                      aria-invalid={famCodigoFiguraErr ? true : undefined}
                      aria-describedby={famCodigoFiguraErr ? 'fam-codigo-figura-err' : undefined}
                    />
                    {famCodigoFiguraErr ? (
                      <p id="fam-codigo-figura-err" className="text-xs text-destructive" role="alert">
                        {famCodigoFiguraErr}
                      </p>
                    ) : null}
                    <p className="text-xs text-muted-foreground">{MENSAGEM_CODIGO_FIGURA_MANUAL}</p>
                    {alertaOdManualCriacao ? (
                      <p className="text-xs text-amber-800 dark:text-amber-200 mt-1" role="status">
                        {alertaOdManualCriacao}
                      </p>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground italic">{MENSAGEM_CODIGO_FIGURA_AUTO}</p>
                )}
              </div>
            )}
            </div>
            <div className="mt-3">
            <label className="erp-label">Descrição base</label>
            <input
              className={`erp-input mt-1${
                classificacaoDupFamilia.tipo === 'exata' || famDuplicidadeExistente
                  ? ' border-destructive'
                  : ''
              }`}
              ref={famDescricaoRef}
              value={famQuick.descricao_base}
              placeholder={manometroEstruturalNaFamilia ? 'Ex.: MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA' : undefined}
              onChange={(e) => {
                limparErroDuplicidadeDescricao();
                setFamQuick((q) => ({ ...q, descricao_base: e.target.value }));
              }}
            />
            {orientacaoDescricaoBaseFamilia(famQuick.tipo_dimensional) ? (
              <div className="mt-2 rounded-md border border-dashed border-border bg-muted/20 p-3">
                <p className="text-xs text-muted-foreground">
                  {orientacaoDescricaoBaseFamilia(famQuick.tipo_dimensional)}
                </p>
              </div>
            ) : null}
            {(() => {
              const cls =
                famDuplicidadeExistente && classificacaoDupFamilia.tipo !== 'exata'
                  ? {
                      tipo: 'exata' as const,
                      mensagem:
                        famSaveErr ||
                        `Já existe a Família/Figura ${famDuplicidadeExistente.codigo_figura} com o mesmo modelo de formação.`,
                      existente: famDuplicidadeExistente,
                    }
                  : classificacaoDupFamilia;
              if (cls.tipo === 'nenhuma') return null;
              if (cls.tipo === 'exata') {
                return (
                  <div className="mt-2 rounded-md border border-destructive/40 bg-destructive/5 p-3">
                    <p className="text-xs text-destructive" role="alert">
                      {cls.mensagem}
                    </p>
                  </div>
                );
              }
              if (cls.tipo === 'provavel_exata' || cls.tipo === 'descricao_sem_modelo') {
                return (
                  <p className="text-xs text-amber-800 dark:text-amber-200 mt-1" role="status">
                    {cls.mensagem}
                  </p>
                );
              }
              if (cls.tipo === 'modelo_diferente') {
                return (
                  <p className="text-xs text-amber-800 dark:text-amber-200 mt-1" role="status">
                    {cls.mensagem}
                  </p>
                );
              }
              return null;
            })()}
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
                <p>{PRODUTO_UI_LABELS.tipoDimensional}: {sugestaoFamiliaAuto.tipo_dimensional}</p>
                <p>{PRODUTO_UI_LABELS.regraCodigo}: {sugestaoFamiliaAuto.tipo_regra_codigo}</p>
                <p className="text-xs text-muted-foreground mt-1">{PRODUTO_UI_LABELS.sugestaoModelo}</p>
                <p>Campos que o produto vai pedir: {sugestaoFamiliaAuto.campos_obrigatorios_labels.join(' · ')}</p>
                {sugestaoFamiliaAuto.observacao ? <p className="text-muted-foreground">{sugestaoFamiliaAuto.observacao}</p> : null}
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  onClick={() => {
                    limparErroDuplicidadeDescricao();
                    setFamModeloConfirmado(true);
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
                  limparErroDuplicidadeDescricao();
                  setFamModeloConfirmado(true);
                  const categoria = e.target.value as 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';
                  setFamQuick((q) => {
                    const nextTipo = categoria === 'MANUAL_FABRICANTE' ? 'MANUAL' : q.tipo_dimensional;
                    const nextRegra = categoria === 'MANUAL_FABRICANTE' ? 'MANUAL_FABRICANTE' : sugerirTipoRegraPorDimensional(nextTipo);
                    return { ...q, categoria_produto: categoria, tipo_dimensional: nextTipo, tipo_regra_codigo: nextRegra };
                  });
                }}
              >
                {OPCOES_CATEGORIA_FAMILIA.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="mt-3">
              <label className="erp-label">{PRODUTO_UI_LABELS.tipoDimensional}</label>
              <select
                className="erp-select mt-1 w-full"
                value={famQuick.tipo_dimensional}
                onChange={(e) => {
                  limparErroDuplicidadeDescricao();
                  setFamModeloConfirmado(true);
                  const td = e.target.value as TipoDimensional;
                  setFamQuick((q) => ({ ...q, tipo_dimensional: td, tipo_regra_codigo: sugerirTipoRegraPorDimensional(td) }));
                }}
              >
                {opcoesTipoDimensionalFamQuick.map((r) => (
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
            <label className="erp-label">{PRODUTO_UI_LABELS.regraCodigo}</label>
            <select
              className="erp-select mt-1 w-full"
              value={famQuick.tipo_regra_codigo}
              onChange={(e) => {
                limparErroDuplicidadeDescricao();
                setFamModeloConfirmado(true);
                setFamQuick((q) => ({ ...q, tipo_regra_codigo: e.target.value as TipoRegraCodigo }));
              }}
            >
              {OPCOES_TIPO_REGRA.map((r) => (
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
            <p className="font-medium text-foreground">{PRODUTO_UI_LABELS.camposExigidos}</p>
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
            <p>Categoria: {OPCOES_CATEGORIA_FAMILIA.find((c) => c.value === famQuick.categoria_produto)?.label}</p>
            <p>Tipo: {famQuick.tipo_dimensional}</p>
            <p>Produto vai pedir: {labelsCamposObrigatorios(famQuickFlags, famQuick.tipo_dimensional).join(' · ')}</p>
            <p className="mt-1">
              Exemplo de código:{' '}
              {exemploCodigoDimensionalFamilia(famQuick.tipo_dimensional, famQuick.codigo_figura) ||
                `${famQuick.codigo_figura || 'FIG'}.${famQuick.tipo_dimensional === 'NPS_SCHEDULE' ? '20.XX' : '...'}`}
            </p>
            <p>
              Exemplo de descrição dimensional:{' '}
              {exemploDescricaoDimensionalFamilia(famQuick.tipo_dimensional) ||
                `${expandirSiglasValvulaDescricaoBase(famQuick.descricao_base || 'DESCRIÇÃO BASE')} …`}
            </p>
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
          controlaComposicaoFisica={!!famQuick.controla_composicao_fisica}
          onControlaComposicaoFisicaChange={(v) =>
            setFamQuick((q) => ({
              ...q,
              controla_composicao_fisica: v,
              usa_conversao_dimensional: v && (q.tipo_composicao_fisica || 'BARRA_M') === 'BARRA_M' ? true : q.usa_conversao_dimensional,
              unidade_estoque_padrao: v
                ? (q.tipo_composicao_fisica || 'BARRA_M') === 'PECA_KG'
                  ? 'KG'
                  : 'M'
                : q.unidade_estoque_padrao,
            }))
          }
          tipoComposicaoFisica={famQuick.tipo_composicao_fisica || 'BARRA_M'}
          onTipoComposicaoFisicaChange={(v) =>
            setFamQuick((q) => ({
              ...q,
              tipo_composicao_fisica: v as 'BARRA_M' | 'PECA_KG',
              unidade_estoque_padrao: q.controla_composicao_fisica ? (v === 'PECA_KG' ? 'KG' : 'M') : q.unidade_estoque_padrao,
              usa_conversao_dimensional:
                q.controla_composicao_fisica && v === 'BARRA_M' ? true : q.usa_conversao_dimensional,
            }))
          }
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
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
          <button
            type="button"
            className="erp-btn-outline w-full sm:w-auto"
            disabled={famSaving}
            onClick={() => setFamModalOpen(false)}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary w-full sm:w-auto"
            disabled={famSaving}
            aria-busy={famSaving || undefined}
            onClick={() => void salvarFamiliaRapida()}
          >
            {famSaving ? 'Salvando…' : editingFamilia ? 'Salvar alterações' : 'Salvar família'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default Produtos;
