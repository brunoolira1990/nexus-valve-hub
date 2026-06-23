import { useCallback, useEffect, useState } from 'react';
import type { AxiosError } from 'axios';
import { ArrowLeft, Pencil, Trash2 } from 'lucide-react';
import { ChecklistAtivacaoCenarioSaidaPanel } from '@/components/ChecklistAtivacaoCenarioSaidaPanel';
import { EditorRegraFiscalSaidaForm } from '@/components/fiscal/EditorRegraFiscalSaidaForm';
import { HomologacaoCenarioSaidaPanel } from '@/components/HomologacaoCenarioSaidaPanel';
import { Modal } from '@/components/Modal';
import {
  AVISO_CENARIO_SAIDA_CADASTRAL,
  badgeClassStatusConfiguracaoSaida,
  boolTriFromApi,
  boolTriToApi,
  consumidorFinalFromApi,
  consumidorFinalToApi,
  decFieldToForm,
  emptyReformaTributaria,
  labelDestinatario,
  labelStatusConfiguracaoSaida,
  reformaFromApi,
  reformaToApi,
  resumoEfeitosMatrizSaida,
  tituloCfopSaida,
  toApiDecimal,
} from '@/lib/regrasFiscaisSaidaHelpers';
import { recomendacoesFromApi, recomendacoesToApi } from '@/lib/recomendacoesNfeSaida';
import {
  ABAS_FORM_REGRA_FISCAL_SAIDA,
  emptyFormRegraFiscalSaida,
  type AbaFormRegraFiscalSaida,
  type FormRegraFiscalSaida,
} from '@/lib/regraFiscalSaidaForm';
import { cenariosFiscaisSaidaService } from '@/services/api/cenarios-fiscais-saida';
import { apiErrorMessage } from '@/services/api/config';
import { regrasFiscaisSaidaService } from '@/services/api/regras-fiscais-saida';
import type {
  CenarioFiscalSaida,
  CenarioFiscalSaidaEscopo,
  ConfiguracaoMatrizFiscalSaida,
  MatrizEscopoFiscalSaida,
  RegraFiscalSaida,
  LacunaCoberturaProposta,
  TipoEscopoFiscalSaida,
} from '@/types';

type View = 'cenarios' | 'escopos' | 'configuracoes';

function labelEscopoUi(e: CenarioFiscalSaidaEscopo): string {
  if (e.label) return e.label;
  if (e.tipo_escopo === 'GERAL') return 'Regra geral';
  if (e.tipo_escopo === 'PRODUTO') return `Produto ${e.produto_id ?? '—'}`;
  if (e.tipo_escopo === 'NCM_PREFIXO') return `NCM ${e.ncm} (prefixo)`;
  return `NCM ${e.ncm || '—'}`;
}

function formFromEscopo(escopo: CenarioFiscalSaidaEscopo, cenarioId: number): FormRegraFiscalSaida {
  return {
    ...emptyFormRegraFiscalSaida,
    escopo_id: escopo.id,
    cenario_id: cenarioId,
    descricao_cenario: '',
  };
}

function formFromRegra(regra: RegraFiscalSaida): FormRegraFiscalSaida {
  return {
    ...regra,
    descricao_cenario: '',
    aliquota_icms: decFieldToForm(regra.aliquota_icms),
    reducao_bc_icms: decFieldToForm(regra.reducao_bc_icms),
    aliquota_icms_st: decFieldToForm(regra.aliquota_icms_st),
    mva_st: decFieldToForm(regra.mva_st),
    reducao_bc_st: decFieldToForm(regra.reducao_bc_st),
    aliquota_icms_interestadual: decFieldToForm(regra.aliquota_icms_interestadual),
    aliquota_icms_interna_destino: decFieldToForm(regra.aliquota_icms_interna_destino),
    aliquota_ipi: decFieldToForm(regra.aliquota_ipi),
    valor_ipi_unidade: decFieldToForm(regra.valor_ipi_unidade),
    aliquota_pis: decFieldToForm(regra.aliquota_pis),
    reducao_base_pis: decFieldToForm(regra.reducao_base_pis),
    valor_minimo_pis_unidade: decFieldToForm(regra.valor_minimo_pis_unidade),
    aliquota_pis_st: decFieldToForm(regra.aliquota_pis_st),
    aliquota_cofins: decFieldToForm(regra.aliquota_cofins),
    reducao_base_cofins: decFieldToForm(regra.reducao_base_cofins),
    valor_minimo_cofins_unidade: decFieldToForm(regra.valor_minimo_cofins_unidade),
    aliquota_cofins_st: decFieldToForm(regra.aliquota_cofins_st),
    aliquota_fcp: decFieldToForm(regra.aliquota_fcp),
    aliquota_fcp_st: decFieldToForm(regra.aliquota_fcp_st),
    reducao_bc_fcp: decFieldToForm(regra.reducao_bc_fcp),
    valor_fcp_unidade: decFieldToForm(regra.valor_fcp_unidade),
    icms_st_aplicavel: boolTriFromApi(regra.icms_st_aplicavel),
    difal_aplicavel: boolTriFromApi(regra.difal_aplicavel),
    fcp_aplicavel: boolTriFromApi(regra.fcp_aplicavel),
    consumidor_final_tri: consumidorFinalFromApi(regra.consumidor_final),
    reforma_tributaria: reformaFromApi(regra.reforma_tributaria),
    recomendacoes_nfe: recomendacoesFromApi(regra.recomendacoes_nfe as Record<string, unknown> | null),
  };
}

function normalizarFormParaApi(
  form: FormRegraFiscalSaida,
  ctx: { escopoId: number; cenarioId: number },
): Partial<RegraFiscalSaida> {
  return {
    ...form,
    escopo_id: ctx.escopoId,
    cenario_id: ctx.cenarioId,
    nome: (form.nome || '').trim() || 'Configuração',
    descricao_cenario: '',
    consumidor_final: consumidorFinalToApi(form.consumidor_final_tri),
    aliquota_icms: toApiDecimal(form.aliquota_icms),
    reducao_bc_icms: toApiDecimal(form.reducao_bc_icms),
    aliquota_icms_st: toApiDecimal(form.aliquota_icms_st),
    mva_st: toApiDecimal(form.mva_st),
    reducao_bc_st: toApiDecimal(form.reducao_bc_st),
    aliquota_ipi: toApiDecimal(form.aliquota_ipi),
    valor_ipi_unidade: toApiDecimal(form.valor_ipi_unidade),
    aliquota_pis: toApiDecimal(form.aliquota_pis),
    reducao_base_pis: toApiDecimal(form.reducao_base_pis),
    valor_minimo_pis_unidade: toApiDecimal(form.valor_minimo_pis_unidade),
    aliquota_pis_st: toApiDecimal(form.aliquota_pis_st),
    aliquota_cofins: toApiDecimal(form.aliquota_cofins),
    reducao_base_cofins: toApiDecimal(form.reducao_base_cofins),
    valor_minimo_cofins_unidade: toApiDecimal(form.valor_minimo_cofins_unidade),
    aliquota_cofins_st: toApiDecimal(form.aliquota_cofins_st),
    icms_st_aplicavel: boolTriToApi(form.icms_st_aplicavel),
    difal_aplicavel: boolTriToApi(form.difal_aplicavel),
    aliquota_icms_interestadual: toApiDecimal(form.aliquota_icms_interestadual),
    aliquota_icms_interna_destino: toApiDecimal(form.aliquota_icms_interna_destino),
    fcp_aplicavel: boolTriToApi(form.fcp_aplicavel),
    aliquota_fcp: toApiDecimal(form.aliquota_fcp),
    aliquota_fcp_st: toApiDecimal(form.aliquota_fcp_st),
    reducao_bc_fcp: toApiDecimal(form.reducao_bc_fcp),
    valor_fcp_unidade: toApiDecimal(form.valor_fcp_unidade),
    reforma_tributaria: reformaToApi(form.reforma_tributaria),
    recomendacoes_nfe: recomendacoesToApi(form.recomendacoes_nfe),
  };
}

export const RegrasFiscaisSaidaTab = () => {
  const [view, setView] = useState<View>('cenarios');
  const [cenarios, setCenarios] = useState<CenarioFiscalSaida[]>([]);
  const [cenariosLoading, setCenariosLoading] = useState(true);
  const [cenariosErro, setCenariosErro] = useState('');
  const [cenarioAtual, setCenarioAtual] = useState<CenarioFiscalSaida | null>(null);
  const [escopos, setEscopos] = useState<CenarioFiscalSaidaEscopo[]>([]);
  const [escopoAtual, setEscopoAtual] = useState<CenarioFiscalSaidaEscopo | null>(null);
  const [matriz, setMatriz] = useState<MatrizEscopoFiscalSaida | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalEscopoOpen, setModalEscopoOpen] = useState(false);
  const [editing, setEditing] = useState<RegraFiscalSaida | null>(null);
  const [form, setForm] = useState(emptyFormRegraFiscalSaida);
  const [showAvancado, setShowAvancado] = useState(false);
  const [abaForm, setAbaForm] = useState<AbaFormRegraFiscalSaida>('cfop');
  const [erro, setErro] = useState('');
  const [novoEscopoTipo, setNovoEscopoTipo] = useState<TipoEscopoFiscalSaida>('NCM');
  const [novoEscopoNcm, setNovoEscopoNcm] = useState('');
  const [novoEscopoProdutoId, setNovoEscopoProdutoId] = useState('');

  const loadCenarios = useCallback(async () => {
    setCenariosLoading(true);
    setCenariosErro('');
    try {
      setCenarios(await cenariosFiscaisSaidaService.getAll());
    } catch (e) {
      setCenarios([]);
      const status = (e as AxiosError)?.response?.status;
      if (status === 404) {
        setCenariosErro(
          'A API de cenários fiscais de saída não foi encontrada (404). Reinicie o backend para carregar as rotas: docker compose restart backend',
        );
      } else {
        setCenariosErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar os cenários fiscais de saída.' }));
      }
    } finally {
      setCenariosLoading(false);
    }
  }, []);

  const loadEscopos = useCallback(async (cenarioId: number) => {
    setEscopos(await cenariosFiscaisSaidaService.getEscopos(cenarioId));
  }, []);

  const loadMatriz = useCallback(async (cenarioId: number, escopoId: number) => {
    setMatriz(await cenariosFiscaisSaidaService.getMatrizEscopo(cenarioId, escopoId));
  }, []);

  useEffect(() => {
    void loadCenarios();
  }, [loadCenarios]);

  const abrirCenario = async (c: CenarioFiscalSaida) => {
    setCenarioAtual(c);
    await loadEscopos(c.id);
    setView('escopos');
  };

  const abrirEscopo = async (e: CenarioFiscalSaidaEscopo) => {
    if (!cenarioAtual) return;
    setEscopoAtual(e);
    await loadMatriz(cenarioAtual.id, e.id);
    setView('configuracoes');
  };

  const voltar = () => {
    if (view === 'configuracoes') {
      setView('escopos');
      setEscopoAtual(null);
      if (cenarioAtual) void loadEscopos(cenarioAtual.id);
    } else if (view === 'escopos') {
      setView('cenarios');
      setCenarioAtual(null);
      setEscopos([]);
    }
  };

  const openNewConfig = () => {
    if (!escopoAtual || !cenarioAtual) return;
    setEditing(null);
    setForm(formFromEscopo(escopoAtual, cenarioAtual.id));
    setShowAvancado(false);
    setAbaForm('cfop');
    setErro('');
    setModalOpen(true);
  };

  const openEdit = async (cfg: ConfiguracaoMatrizFiscalSaida) => {
    const regra = await regrasFiscaisSaidaService.getById(cfg.id);
    setEditing(regra);
    setForm(formFromRegra(regra));
    setShowAvancado(Boolean(regra.codigo?.trim() || (regra.nome || '').trim()));
    setAbaForm('cfop');
    setErro('');
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir configuração fiscal de saída?')) return;
    await regrasFiscaisSaidaService.delete(id);
    if (cenarioAtual && escopoAtual) void loadMatriz(cenarioAtual.id, escopoAtual.id);
  };

  const handleSave = async () => {
    if (!escopoAtual || !cenarioAtual) return;
    setErro('');
    const cfop = (form.cfop_venda || '').trim();
    if (!cfop && !form.uf_origem && !form.uf_destino) {
      setErro('Informe ao menos CFOP de venda ou UF origem/destino.');
      return;
    }
    try {
      const payload = normalizarFormParaApi(form, {
        escopoId: escopoAtual.id,
        cenarioId: cenarioAtual.id,
      });
      if (editing) await regrasFiscaisSaidaService.update(editing.id, payload);
      else await regrasFiscaisSaidaService.create(payload);
      setModalOpen(false);
      void loadMatriz(cenarioAtual.id, escopoAtual.id);
      void loadEscopos(cenarioAtual.id);
    } catch {
      setErro('Não foi possível salvar. Verifique os campos obrigatórios.');
    }
  };

  const aplicarLacunaHomologacao = useCallback(
    async (lacuna: LacunaCoberturaProposta) => {
      const cenario = cenarios.find((c) => c.padrao) ?? cenarios[0];
      if (!cenario) return;
      setCenarioAtual(cenario);
      await loadEscopos(cenario.id);
      setView('escopos');
      setNovoEscopoTipo('NCM');
      setNovoEscopoNcm(lacuna.ncm);
      setNovoEscopoProdutoId('');
      setModalEscopoOpen(true);
    },
    [cenarios, loadEscopos],
  );

  const cenarioPadraoId = cenarios.find((c) => c.padrao)?.id ?? cenarios[0]?.id;

  const handleCriarEscopo = async () => {
    if (!cenarioAtual) return;
    setErro('');
    try {
      await cenariosFiscaisSaidaService.createEscopo(cenarioAtual.id, {
        tipo_escopo: novoEscopoTipo,
        ncm: novoEscopoTipo === 'NCM' || novoEscopoTipo === 'NCM_PREFIXO' ? novoEscopoNcm.trim() : '',
        produto_id:
          novoEscopoTipo === 'PRODUTO' && novoEscopoProdutoId ? Number(novoEscopoProdutoId) : null,
        ativo: true,
        prioridade_escopo: 10,
      });
      setModalEscopoOpen(false);
      setNovoEscopoNcm('');
      setNovoEscopoProdutoId('');
      void loadEscopos(cenarioAtual.id);
    } catch {
      setErro('Não foi possível criar o escopo. Verifique NCM ou produto.');
    }
  };

  const f = <K extends keyof FormRegraFiscalSaida>(k: K, v: FormRegraFiscalSaida[K]) =>
    setForm((p) => ({ ...p, [k]: v }));

  const escoposOrdenados = [...escopos].sort((a, b) => {
    const ord: Record<TipoEscopoFiscalSaida, number> = { GERAL: 0, NCM: 1, NCM_PREFIXO: 2, PRODUTO: 3 };
    return (ord[a.tipo_escopo] ?? 9) - (ord[b.tipo_escopo] ?? 9);
  });

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Cenário Fiscal de Saída</h2>
        <p className="text-xs text-muted-foreground mt-1 max-w-3xl">
          Configura impostos e efeitos para <strong>emissão de NF-e saída</strong> e, no futuro, propostas. Diferente da
          aba de entrada, que apenas <strong>classifica o XML recebido</strong> do fornecedor.
        </p>
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-2 max-w-3xl border border-amber-500/30 bg-amber-500/10 rounded px-3 py-2">
          {AVISO_CENARIO_SAIDA_CADASTRAL}
        </p>
        {view === 'cenarios' ? (
          <>
            <HomologacaoCenarioSaidaPanel
              cenarioId={cenarioPadraoId}
              onCriarRegraLacuna={(lac) => void aplicarLacunaHomologacao(lac)}
            />
            <ChecklistAtivacaoCenarioSaidaPanel cenarioId={cenarioPadraoId} />
          </>
        ) : null}
      </div>

      {view !== 'cenarios' ? (
        <button type="button" className="erp-btn-outline erp-btn-sm mb-3 flex items-center gap-1" onClick={voltar}>
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </button>
      ) : null}

      {view === 'cenarios' ? (
        <div>
          {cenariosLoading ? (
            <p className="text-sm text-muted-foreground py-6">Carregando cenários fiscais de saída…</p>
          ) : null}
          {!cenariosLoading && cenariosErro ? (
            <div className="erp-card p-4 border-destructive/30 bg-destructive/5 mb-3">
              <p className="text-sm text-destructive">{cenariosErro}</p>
              <button type="button" className="erp-btn-outline erp-btn-sm mt-2" onClick={() => void loadCenarios()}>
                Tentar novamente
              </button>
            </div>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {cenarios.map((c) => (
              <div key={c.id} className="erp-card p-4 flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{c.nome}</span>
                  {c.padrao ? <span className="erp-badge-info text-[10px]">Padrão</span> : null}
                  {c.ativo ? (
                    <span className="erp-badge-success text-[10px]">Ativo</span>
                  ) : (
                    <span className="erp-badge-secondary text-[10px]">Inativo</span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {c.total_escopos ?? 0} escopo{(c.total_escopos ?? 0) === 1 ? '' : 's'}
                  {' · '}
                  {c.total_configuracoes ?? 0} configuração
                  {(c.total_configuracoes ?? 0) === 1 ? '' : 'ões'}
                </p>
                <button type="button" className="erp-btn-primary erp-btn-sm w-fit mt-1" onClick={() => void abrirCenario(c)}>
                  Abrir cenário
                </button>
              </div>
            ))}
            {!cenariosLoading && cenarios.length === 0 && !cenariosErro ? (
              <div className="erp-card p-4 border-dashed opacity-60 flex items-center justify-center min-h-[100px]">
                <span className="text-sm text-muted-foreground">Novo cenário (em breve)</span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {view === 'escopos' && cenarioAtual ? (
        <div>
          <h2 className="text-lg font-semibold mb-1">{cenarioAtual.nome}</h2>
          <p className="text-xs text-muted-foreground mb-3">Escopos: regra geral, NCM, prefixo ou produto</p>
          <div className="flex flex-wrap gap-2 mb-3">
            <button type="button" className="erp-btn-primary erp-btn-sm" onClick={() => setModalEscopoOpen(true)}>
              Novo escopo NCM
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => {
                setNovoEscopoTipo('PRODUTO');
                setModalEscopoOpen(true);
              }}
            >
              Nova exceção por produto
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={async () => {
                const existente = escopos.find((e) => e.tipo_escopo === 'GERAL');
                if (existente) void abrirEscopo(existente);
                else if (cenarioAtual) {
                  const escopo = await cenariosFiscaisSaidaService.createEscopo(cenarioAtual.id, {
                    tipo_escopo: 'GERAL',
                    ncm: '',
                    ativo: true,
                    prioridade_escopo: 10,
                  });
                  void abrirEscopo(escopo);
                }
              }}
            >
              Regra geral
            </button>
          </div>
          <div className="erp-card overflow-x-auto">
            <table className="erp-table text-sm">
              <thead>
                <tr>
                  <th>Escopo</th>
                  <th>Tipo</th>
                  <th>Configurações</th>
                  <th>Ativo</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {escoposOrdenados.map((e) => (
                  <tr key={e.id}>
                    <td className="font-medium">
                      {labelEscopoUi(e)}
                      {e.tem_reforma ? (
                        <span className="erp-badge-secondary text-[9px] ml-1">Reforma</span>
                      ) : null}
                      {e.tem_recomendacoes_nfe ? (
                        <span className="erp-badge-secondary text-[9px] ml-1">Recomendações NF-e</span>
                      ) : null}
                    </td>
                    <td className="text-xs">{e.tipo_escopo}</td>
                    <td className="font-mono">{e.configuracoes_count ?? 0}</td>
                    <td>{e.ativo ? 'Sim' : 'Não'}</td>
                    <td>
                      <button type="button" className="erp-btn-primary erp-btn-sm" onClick={() => void abrirEscopo(e)}>
                        Abrir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {view === 'configuracoes' && cenarioAtual && escopoAtual ? (
        <div>
          <h2 className="text-lg font-semibold">{labelEscopoUi(escopoAtual)}</h2>
          <p className="text-xs text-muted-foreground mb-1">{cenarioAtual.nome}</p>
          <p className="text-xs text-muted-foreground mb-3">
            Configurações por UF, destinatário e CFOP de venda. Impostos para emissão própria (não validação de XML).
          </p>
          <button type="button" className="erp-btn-primary erp-btn-sm mb-3" onClick={openNewConfig}>
            Nova configuração
          </button>
          {matriz?.ufs_sem_configuracao?.length ? (
            <p className="text-xs text-muted-foreground mb-2">
              UFs ainda sem configuração neste escopo:{' '}
              <span className="font-mono">{matriz.ufs_sem_configuracao.join(', ')}</span>
            </p>
          ) : null}
          <div className="erp-card overflow-x-auto">
            <table className="erp-table text-sm">
              <thead>
                <tr>
                  <th>UF orig.</th>
                  <th>UF dest.</th>
                  <th>Destinatário</th>
                  <th>CFOP venda</th>
                  <th>CFOP ST</th>
                  <th>ICMS</th>
                  <th>IPI</th>
                  <th>PIS</th>
                  <th>COFINS</th>
                  <th>Efeitos</th>
                  <th>Status</th>
                  <th className="min-w-[80px]">Ações</th>
                </tr>
              </thead>
              <tbody>
                {(matriz?.configuracoes ?? []).map((cfg) => (
                  <tr key={cfg.id}>
                    <td>{cfg.uf_origem || '*'}</td>
                    <td>{cfg.uf_destino || '*'}</td>
                    <td className="text-xs">{labelDestinatario(cfg.destinatario_contribuinte)}</td>
                    <td className="font-mono text-xs" title={tituloCfopSaida(cfg.cfop_venda)}>
                      {cfg.cfop_venda || '—'}
                    </td>
                    <td className="font-mono text-xs" title={tituloCfopSaida(cfg.cfop_venda_st)}>
                      {cfg.cfop_venda_st || '—'}
                    </td>
                    <td className="text-xs text-muted-foreground max-w-[90px] truncate" title={cfg.resumo_impostos.icms}>
                      {cfg.resumo_impostos.icms || '—'}
                    </td>
                    <td className="text-xs text-muted-foreground">{cfg.resumo_impostos.ipi || '—'}</td>
                    <td className="text-xs text-muted-foreground">{cfg.resumo_impostos.pis || '—'}</td>
                    <td className="text-xs text-muted-foreground">{cfg.resumo_impostos.cofins || '—'}</td>
                    <td className="text-xs max-w-[120px] truncate" title={resumoEfeitosMatrizSaida(cfg)}>
                      {resumoEfeitosMatrizSaida(cfg)}
                    </td>
                    <td>
                      <span className={badgeClassStatusConfiguracaoSaida(cfg.status_configuracao)}>
                        {labelStatusConfiguracaoSaida(cfg.status_configuracao)}
                      </span>
                      {cfg.tem_reforma ? (
                        <span
                          className="erp-badge-secondary text-[9px] ml-1"
                          title={cfg.resumo_reforma || 'Reforma Tributária configurada'}
                        >
                          Reforma
                        </span>
                      ) : null}
                      {cfg.tem_recomendacoes_nfe ? (
                        <span
                          className="erp-badge-secondary text-[9px] ml-1"
                          title={`${cfg.qtd_recomendacoes_nfe ?? 0} recomendação(ões) NF-e/DANFE`}
                        >
                          Recomendações NF-e
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Editar" onClick={() => void openEdit(cfg)}>
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-destructive"
                          title="Excluir"
                          onClick={() => void handleDelete(cfg.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <Modal isOpen={modalEscopoOpen} onClose={() => setModalEscopoOpen(false)} title="Novo escopo" size="md">
        {erro ? <p className="text-destructive text-sm mb-2">{erro}</p> : null}
        <div className="space-y-3 text-sm">
          <div>
            <label className="erp-label">Tipo</label>
            <select
              className="erp-select mt-1 w-full"
              value={novoEscopoTipo}
              onChange={(e) => setNovoEscopoTipo(e.target.value as TipoEscopoFiscalSaida)}
            >
              <option value="NCM">NCM</option>
              <option value="NCM_PREFIXO">NCM por prefixo</option>
              <option value="PRODUTO">Produto</option>
            </select>
          </div>
          {novoEscopoTipo === 'NCM' || novoEscopoTipo === 'NCM_PREFIXO' ? (
            <div>
              <label className="erp-label">NCM</label>
              <input className="erp-input mt-1 w-full" value={novoEscopoNcm} onChange={(e) => setNovoEscopoNcm(e.target.value)} />
            </div>
          ) : null}
          {novoEscopoTipo === 'PRODUTO' ? (
            <div>
              <label className="erp-label">ID produto</label>
              <input
                type="number"
                className="erp-input mt-1 w-full"
                value={novoEscopoProdutoId}
                onChange={(e) => setNovoEscopoProdutoId(e.target.value)}
              />
            </div>
          ) : null}
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button type="button" className="erp-btn-outline" onClick={() => setModalEscopoOpen(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void handleCriarEscopo()}>
            Criar
          </button>
        </div>
      </Modal>

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar configuração de saída' : 'Nova configuração de saída'}
        size="lg"
      >
        {escopoAtual ? (
          <p className="text-xs text-muted-foreground mb-2">
            Escopo: <strong>{labelEscopoUi(escopoAtual)}</strong>
          </p>
        ) : null}
        {erro ? <p className="text-destructive text-sm mb-3">{erro}</p> : null}
        <div className="flex flex-wrap gap-1 mb-3">
          {ABAS_FORM_REGRA_FISCAL_SAIDA.map((aba) => (
            <button
              key={aba.id}
              type="button"
              className={abaForm === aba.id ? 'erp-btn-primary erp-btn-sm' : 'erp-btn-outline erp-btn-sm'}
              onClick={() => setAbaForm(aba.id)}
            >
              {aba.label}
            </button>
          ))}
        </div>
        <EditorRegraFiscalSaidaForm abaForm={abaForm} form={form} setForm={setForm} />

        <section className="mt-4">
          <button type="button" className="text-xs text-primary underline" onClick={() => setShowAvancado((v) => !v)}>
            {showAvancado ? 'Ocultar' : 'Mostrar'} nome interno e código
          </button>
          {showAvancado ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
              <div>
                <label className="erp-label">Nome interno</label>
                <input className="erp-input mt-1" value={form.nome} onChange={(e) => f('nome', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Código</label>
                <input className="erp-input mt-1" value={form.codigo} onChange={(e) => f('codigo', e.target.value)} />
              </div>
            </div>
          ) : null}
        </section>

        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" className="erp-btn-outline" onClick={() => setModalOpen(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void handleSave()}>
            Salvar
          </button>
        </div>
      </Modal>
    </div>
  );
};
