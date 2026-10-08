import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, Copy, CopyPlus, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { CatalogCodigoFiscalSelect } from '@/components/fiscal/CatalogCodigoFiscalSelect';
import { CatalogCfopSearchSelect } from '@/components/fiscal/CatalogCfopSearchSelect';
import {
  ALIQUOTA_CBS_2026_OPCOES,
  ALIQUOTA_COFINS_OPCOES,
  ALIQUOTA_IBS_UF_2026_OPCOES,
  ALIQUOTA_ICMS_OPCOES,
  ALIQUOTA_PIS_OPCOES,
  BOOL_TRI_OPCOES,
  CFOP_ENTRADA_OPCOES,
  CLASSIFICACAO_TRIBUTARIA_OPCOES,
  CSOSN_OPCOES,
  CST_IBS_CBS_OPCOES,
  CST_ICMS_OPCOES,
  CST_IPI_OPCOES,
  CST_PIS_COFINS_OPCOES,
  EMPTY_LABEL_NAO_VALIDAR,
  FONTE_REGRA_BASE_IBS_CBS_OPCOES,
  HINT_CFOP_ENTRADA,
  HINT_CFOP_SAIDA,
  MODALIDADE_BC_ICMS_OPCOES,
  MODO_BASE_IBS_CBS_OPCOES,
  MOTIVO_DESONERACAO_ICMS_OPCOES,
  TIPO_CALCULO_TRIBUTO_OPCOES,
} from '@/lib/catalogosFiscais';
import {
  cfopOrigemRegraEntrada,
  decFieldToForm,
  emptyReformaTributaria,
  HINT_CAMPOS_NAO_VALIDADOS,
  REFORMA_TRIBUTARIA_KEYS,
  badgeClassStatusConfiguracao,
  reformaFromApi,
  reformaToApi,
  labelSeveridadeRegraEntrada,
  labelStatusConfiguracao,
  resumoEfeitosMatriz,
  toApiDecimal,
  textoOpcionalParaApi,
  abaRegraEntradaParaErro,
  type RegrasFiscaisEntradaPrefill,
  type ReformaTributariaForm,
} from '@/lib/regrasFiscaisEntradaHelpers';
import { cenariosFiscaisEntradaService } from '@/services/api/cenarios-fiscais-entrada';
import { apiErrorMessage } from '@/services/api/config';
import { regrasFiscaisEntradaService } from '@/services/api/regras-fiscais-entrada';
import type {
  CenarioFiscalEntrada,
  CenarioFiscalEntradaEscopo,
  ConfiguracaoMatrizFiscalEntrada,
  DestinoCopiaConfiguracaoFiscal,
  MatrizEscopoFiscalEntrada,
  RegraFiscalEntrada,
  ResultadoCopiaConfiguracaoFiscal,
  SeveridadeRegraFiscalEntrada,
  TipoEscopoFiscalEntrada,
  TipoOperacaoFiscalEntrada,
} from '@/types';
import { UFS } from '@/types';

type View = 'cenarios' | 'escopos' | 'configuracoes';

type FormRegraEntrada = Omit<RegraFiscalEntrada, 'id' | 'criado_em' | 'atualizado_em' | 'fcp_aplicavel' | 'reforma_tributaria'> & {
  icms_st_aplicavel: '' | 'sim' | 'nao';
  fcp_aplicavel: '' | 'sim' | 'nao';
  reforma_tributaria: ReformaTributariaForm;
};

const empty: FormRegraEntrada = {
  nome: '',
  codigo: '',
  ativo: true,
  prioridade: 10,
  cfop: '',
  cfop_origem: '',
  cfop_entrada: '',
  descricao_cenario: '',
  ncm: '',
  ncm_prefixo: false,
  uf_origem: '',
  uf_destino: '',
  tipo_operacao_fiscal: '',
  produto_id: null,
  fornecedor_id: null,
  cst_icms_esperado: '',
  csosn_esperado: '',
  cst_pis_esperado: '',
  cst_cofins_esperado: '',
  cst_ipi_esperado: '',
  modalidade_bc_icms: '',
  aliquota_icms: '',
  reducao_bc_icms: '',
  motivo_desoneracao_icms: '',
  codigo_beneficio_icms: '',
  icms_st_aplicavel: '' as '' | 'sim' | 'nao',
  cst_icms_st_esperado: '',
  aliquota_icms_st: '',
  mva_st: '',
  reducao_bc_st: '',
  fcp_aplicavel: '',
  aliquota_fcp: '',
  aliquota_fcp_st: '',
  reducao_bc_fcp: '',
  valor_fcp_unidade: '',
  reforma_tributaria: emptyReformaTributaria(),
  tipo_calculo_ipi: '',
  aliquota_ipi: '',
  valor_ipi_unidade: '',
  enquadramento_ipi: '',
  tipo_calculo_pis: '',
  aliquota_pis: '',
  reducao_base_pis: '',
  valor_minimo_pis_unidade: '',
  aliquota_pis_st: '',
  tipo_calculo_cofins: '',
  aliquota_cofins: '',
  reducao_base_cofins: '',
  valor_minimo_cofins_unidade: '',
  aliquota_cofins_st: '',
  movimenta_estoque: true,
  exige_certificado_fornecedor: false,
  permite_credito_fiscal: true,
  severidade: 'INFORMATIVO',
  mensagem_padrao: '',
  observacoes: '',
};

const TIPOS_OP: { value: TipoOperacaoFiscalEntrada; label: string }[] = [
  { value: '', label: '— Qualquer —' },
  { value: 'COMPRA', label: 'Compra' },
  { value: 'DEVOLUCAO_VENDA', label: 'Devolução de venda' },
  { value: 'DEVOLUCAO_COMPRA', label: 'Devolução de compra' },
  { value: 'REMESSA', label: 'Remessa' },
  { value: 'BONIFICACAO', label: 'Bonificação' },
  { value: 'USO_CONSUMO', label: 'Uso e consumo' },
  { value: 'INDUSTRIALIZACAO', label: 'Industrialização' },
  { value: 'FRETE_TRANSPORTE', label: 'Frete / transporte (CT-e)' },
  { value: 'OUTROS', label: 'Outros' },
];

type AbaFormRegra = 'cfop' | 'icms' | 'ipi' | 'pis' | 'cofins' | 'reforma' | 'efeitos';

const ABAS_FORM: { id: AbaFormRegra; label: string }[] = [
  { id: 'cfop', label: 'Classificação' },
  { id: 'efeitos', label: 'Efeitos e severidade' },
  { id: 'icms', label: 'ICMS (validação XML)' },
  { id: 'ipi', label: 'IPI (validação XML)' },
  { id: 'pis', label: 'PIS (validação XML)' },
  { id: 'cofins', label: 'COFINS (validação XML)' },
  { id: 'reforma', label: 'Reforma (validação XML)' },
];

function icmsStFromApi(v: boolean | null | undefined): '' | 'sim' | 'nao' {
  if (v === true) return 'sim';
  if (v === false) return 'nao';
  return '';
}

function icmsStToApi(v: '' | 'sim' | 'nao'): boolean | null {
  if (v === 'sim') return true;
  if (v === 'nao') return false;
  return null;
}

function labelEscopoUi(e: CenarioFiscalEntradaEscopo): string {
  if (e.label) return e.label;
  if (e.tipo_escopo === 'GERAL') return 'Regra geral';
  if (e.tipo_escopo === 'PRODUTO') return `Produto ${e.produto_id ?? '—'}`;
  if (e.tipo_escopo === 'NCM_PREFIXO') return `NCM ${e.ncm} (prefixo)`;
  return `NCM ${e.ncm || '—'}`;
}

function formFromEscopo(
  escopo: CenarioFiscalEntradaEscopo,
  cenarioId: number,
  prefill?: RegrasFiscaisEntradaPrefill,
): typeof empty {
  const base: typeof empty = {
    ...empty,
    escopo_id: escopo.id,
    cenario_id: cenarioId,
    descricao_cenario: '',
    nome: '',
  };
  if (escopo.tipo_escopo === 'NCM') {
    base.ncm = escopo.ncm;
    base.ncm_prefixo = false;
    base.produto_id = null;
  } else if (escopo.tipo_escopo === 'NCM_PREFIXO') {
    base.ncm = escopo.ncm;
    base.ncm_prefixo = true;
    base.produto_id = null;
  } else if (escopo.tipo_escopo === 'PRODUTO') {
    base.produto_id = escopo.produto_id ?? null;
    base.ncm = '';
    base.ncm_prefixo = false;
  } else {
    base.ncm = '';
    base.ncm_prefixo = false;
    base.produto_id = null;
  }
  if (prefill) {
    const cfopOrigem = prefill.cfop_origem || prefill.cfop || '';
    base.cfop_origem = cfopOrigem;
    base.cfop = cfopOrigem;
    base.uf_origem = prefill.uf_origem || '';
    base.uf_destino = prefill.uf_destino || '';
    if (prefill.tipo_operacao_fiscal) {
      base.tipo_operacao_fiscal = prefill.tipo_operacao_fiscal;
    }
    if (typeof prefill.movimenta_estoque === 'boolean') {
      base.movimenta_estoque = prefill.movimenta_estoque;
    }
  }
  return base;
}

function normalizarFormParaApi(
  form: typeof empty,
  ctx: { escopoId: number; cenarioId: number },
): Omit<RegraFiscalEntrada, 'id' | 'criado_em' | 'atualizado_em'> {
  const cfopOrigem = (form.cfop_origem || form.cfop || '').trim();
  const cfopEntrada = (form.cfop_entrada || '').trim();
  return {
    ...form,
    escopo_id: ctx.escopoId,
    cenario_id: ctx.cenarioId,
    nome: (form.nome || '').trim() || 'Configuração',
    codigo: (form.codigo || '').trim(),
    descricao_cenario: (form.descricao_cenario || '').trim(),
    cfop_origem: cfopOrigem,
    cfop: cfopOrigem,
    cfop_entrada: cfopEntrada,
    uf_origem: (form.uf_origem || '').trim(),
    uf_destino: (form.uf_destino || '').trim(),
    tipo_operacao_fiscal: (form.tipo_operacao_fiscal || '') as TipoOperacaoFiscalEntrada,
    fornecedor_id: form.fornecedor_id ?? null,
    produto_id: form.produto_id ?? null,
    ncm: (form.ncm || '').trim(),
    cst_icms_esperado: (form.cst_icms_esperado || '').trim(),
    csosn_esperado: (form.csosn_esperado || '').trim(),
    cst_pis_esperado: (form.cst_pis_esperado || '').trim(),
    cst_cofins_esperado: (form.cst_cofins_esperado || '').trim(),
    cst_ipi_esperado: (form.cst_ipi_esperado || '').trim(),
    modalidade_bc_icms: textoOpcionalParaApi(form.modalidade_bc_icms) ?? '',
    motivo_desoneracao_icms: textoOpcionalParaApi(form.motivo_desoneracao_icms) ?? '',
    codigo_beneficio_icms: textoOpcionalParaApi(form.codigo_beneficio_icms) ?? '',
    cst_icms_st_esperado: (form.cst_icms_st_esperado || '').trim(),
    tipo_calculo_ipi: textoOpcionalParaApi(form.tipo_calculo_ipi) ?? '',
    enquadramento_ipi: textoOpcionalParaApi(form.enquadramento_ipi) ?? '',
    tipo_calculo_pis: textoOpcionalParaApi(form.tipo_calculo_pis) ?? '',
    tipo_calculo_cofins: textoOpcionalParaApi(form.tipo_calculo_cofins) ?? '',
    mensagem_padrao: textoOpcionalParaApi(form.mensagem_padrao) ?? '',
    observacoes: textoOpcionalParaApi(form.observacoes) ?? '',
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
    icms_st_aplicavel: icmsStToApi(form.icms_st_aplicavel),
    fcp_aplicavel: icmsStToApi(form.fcp_aplicavel),
    aliquota_fcp: toApiDecimal(form.aliquota_fcp),
    aliquota_fcp_st: toApiDecimal(form.aliquota_fcp_st),
    reducao_bc_fcp: toApiDecimal(form.reducao_bc_fcp),
    valor_fcp_unidade: toApiDecimal(form.valor_fcp_unidade),
    reforma_tributaria: reformaToApi(form.reforma_tributaria),
  };
}

function temCriterioClassificacaoEntrada(form: FormRegraEntrada): boolean {
  return Boolean(
    (form.cfop_origem || form.cfop || '').trim()
      || (form.cfop_entrada || '').trim()
      || (form.uf_origem || '').trim()
      || (form.uf_destino || '').trim()
      || (form.tipo_operacao_fiscal || '').trim()
      || form.fornecedor_id
      || (form.ncm || '').trim(),
  );
}

function formFromRegra(regra: RegraFiscalEntrada): typeof empty {
  const cfopOrigem = cfopOrigemRegraEntrada(regra);
  return {
    ...regra,
    cfop_origem: cfopOrigem,
    cfop: cfopOrigem,
    descricao_cenario: '',
    aliquota_icms: decFieldToForm(regra.aliquota_icms),
    reducao_bc_icms: decFieldToForm(regra.reducao_bc_icms),
    aliquota_icms_st: decFieldToForm(regra.aliquota_icms_st),
    mva_st: decFieldToForm(regra.mva_st),
    reducao_bc_st: decFieldToForm(regra.reducao_bc_st),
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
    icms_st_aplicavel: icmsStFromApi(regra.icms_st_aplicavel),
    fcp_aplicavel: icmsStFromApi(regra.fcp_aplicavel),
    aliquota_fcp: decFieldToForm(regra.aliquota_fcp),
    aliquota_fcp_st: decFieldToForm(regra.aliquota_fcp_st),
    reducao_bc_fcp: decFieldToForm(regra.reducao_bc_fcp),
    valor_fcp_unidade: decFieldToForm(regra.valor_fcp_unidade),
    reforma_tributaria: reformaFromApi(regra.reforma_tributaria),
  };
}

type Props = {
  autoOpenNew?: boolean;
  prefill?: RegrasFiscaisEntradaPrefill;
};

export const RegrasFiscaisEntradaTab = ({ autoOpenNew, prefill }: Props) => {
  const [view, setView] = useState<View>('cenarios');
  const [cenarios, setCenarios] = useState<CenarioFiscalEntrada[]>([]);
  const [cenariosLoading, setCenariosLoading] = useState(true);
  const [cenariosErro, setCenariosErro] = useState('');
  const [cenarioAtual, setCenarioAtual] = useState<CenarioFiscalEntrada | null>(null);
  const [escopos, setEscopos] = useState<CenarioFiscalEntradaEscopo[]>([]);
  const [escopoAtual, setEscopoAtual] = useState<CenarioFiscalEntradaEscopo | null>(null);
  const [matriz, setMatriz] = useState<MatrizEscopoFiscalEntrada | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalEscopoOpen, setModalEscopoOpen] = useState(false);
  const [modalDuplicarOpen, setModalDuplicarOpen] = useState(false);
  const [modalCopiarOpen, setModalCopiarOpen] = useState(false);
  const [cfgDuplicar, setCfgDuplicar] = useState<ConfiguracaoMatrizFiscalEntrada | null>(null);
  const [dupForm, setDupForm] = useState({ uf_origem: '', uf_destino: '', cfop_origem: '', cfop_entrada: '' });
  const [copiarOrigemId, setCopiarOrigemId] = useState<number | ''>('');
  const [copiarDestinos, setCopiarDestinos] = useState<DestinoCopiaConfiguracaoFiscal[]>([
    { uf_origem: '', uf_destino: '', cfop_origem: '', cfop_entrada: '' },
  ]);
  const [copiarSobrescrever, setCopiarSobrescrever] = useState(false);
  const [resultadoCopia, setResultadoCopia] = useState<ResultadoCopiaConfiguracaoFiscal | null>(null);
  const [editing, setEditing] = useState<RegraFiscalEntrada | null>(null);
  const [form, setForm] = useState(empty);
  const [showAvancado, setShowAvancado] = useState(false);
  const [abaForm, setAbaForm] = useState<AbaFormRegra>('cfop');
  const [erro, setErro] = useState('');
  const [novoEscopoTipo, setNovoEscopoTipo] = useState<TipoEscopoFiscalEntrada>('NCM');
  const [novoEscopoNcm, setNovoEscopoNcm] = useState('');
  const [novoEscopoProdutoId, setNovoEscopoProdutoId] = useState('');
  const prefillHandled = useRef(false);

  const loadCenarios = useCallback(async () => {
    setCenariosLoading(true);
    setCenariosErro('');
    try {
      const lista = await cenariosFiscaisEntradaService.getAll();
      setCenarios(lista);
    } catch (e) {
      setCenarios([]);
      setCenariosErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar as classificações fiscais de entrada.' }));
    } finally {
      setCenariosLoading(false);
    }
  }, []);

  const loadEscopos = useCallback(async (cenarioId: number) => {
    setEscopos(await cenariosFiscaisEntradaService.getEscopos(cenarioId));
  }, []);

  const loadMatriz = useCallback(async (cenarioId: number, escopoId: number) => {
    setMatriz(await cenariosFiscaisEntradaService.getMatrizEscopo(cenarioId, escopoId));
  }, []);

  useEffect(() => {
    void loadCenarios();
  }, [loadCenarios]);

  useEffect(() => {
    if (!autoOpenNew || prefillHandled.current || !cenarios.length) return;
    const padrao = cenarios.find((c) => c.padrao) ?? cenarios[0];
    if (!padrao) return;
    prefillHandled.current = true;
    void (async () => {
      setCenarioAtual(padrao);
      const lista = await cenariosFiscaisEntradaService.getEscopos(padrao.id);
      setEscopos(lista);
      let escopo =
        (prefill?.ncm
          ? lista.find((e) => e.tipo_escopo === 'NCM' && e.ncm === prefill.ncm)
          : null) ?? lista.find((e) => e.tipo_escopo === 'GERAL');
      if (!escopo && prefill?.ncm) {
        escopo = await cenariosFiscaisEntradaService.createEscopo(padrao.id, {
          tipo_escopo: 'NCM',
          ncm: prefill.ncm,
          ativo: true,
          prioridade_escopo: 10,
        });
        setEscopos((prev) => [...prev, escopo]);
      }
      if (escopo) {
        setEscopoAtual(escopo);
        setView('configuracoes');
        setEditing(null);
        setForm(formFromEscopo(escopo, padrao.id, prefill));
        setAbaForm('cfop');
        setModalOpen(true);
      }
    })();
  }, [autoOpenNew, prefill, cenarios]);

  const abrirCenario = async (c: CenarioFiscalEntrada) => {
    setCenarioAtual(c);
    await loadEscopos(c.id);
    setView('escopos');
  };

  const abrirEscopo = async (e: CenarioFiscalEntradaEscopo) => {
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

  const openEdit = async (cfg: ConfiguracaoMatrizFiscalEntrada) => {
    const regra = await regrasFiscaisEntradaService.getById(cfg.id);
    setEditing(regra);
    setForm(formFromRegra(regra));
    setShowAvancado(Boolean(regra.codigo?.trim() || (regra.nome || '').trim()));
    setAbaForm('cfop');
    setErro('');
    setModalOpen(true);
  };

  const openDuplicar = (cfg: ConfiguracaoMatrizFiscalEntrada) => {
    setCfgDuplicar(cfg);
    setDupForm({
      uf_origem: cfg.uf_origem,
      uf_destino: cfg.uf_destino,
      cfop_origem: cfg.cfop_origem,
      cfop_entrada: cfg.cfop_entrada,
    });
    setErro('');
    setModalDuplicarOpen(true);
  };

  const openCopiar = (cfg?: ConfiguracaoMatrizFiscalEntrada) => {
    setCopiarOrigemId(cfg?.id ?? '');
    setCopiarDestinos([{ uf_origem: '', uf_destino: '', cfop_origem: '', cfop_entrada: '' }]);
    setCopiarSobrescrever(false);
    setResultadoCopia(null);
    setErro('');
    setModalCopiarOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir configuração fiscal?')) return;
    await regrasFiscaisEntradaService.delete(id);
    if (cenarioAtual && escopoAtual) void loadMatriz(cenarioAtual.id, escopoAtual.id);
  };

  const handleDuplicar = async () => {
    if (!cfgDuplicar) return;
    setErro('');
    try {
      await regrasFiscaisEntradaService.duplicar(cfgDuplicar.id, dupForm);
      setModalDuplicarOpen(false);
      if (cenarioAtual && escopoAtual) void loadMatriz(cenarioAtual.id, escopoAtual.id);
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível duplicar. Verifique se já existe configuração para esta UF/CFOP.' }));
    }
  };

  const handleCopiar = async () => {
    if (!cenarioAtual || !escopoAtual || !copiarOrigemId) return;
    setErro('');
    try {
      const res = await cenariosFiscaisEntradaService.copiarConfiguracao(cenarioAtual.id, escopoAtual.id, {
        origem_regra_id: Number(copiarOrigemId),
        destinos: copiarDestinos,
        sobrescrever: copiarSobrescrever,
      });
      setResultadoCopia(res);
      void loadMatriz(cenarioAtual.id, escopoAtual.id);
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível copiar as configurações.' }));
    }
  };

  const handleSave = async () => {
    if (!escopoAtual || !cenarioAtual) return;
    setErro('');
    if (!temCriterioClassificacaoEntrada(form)) {
      setErro(
        'Informe ao menos um critério na aba Classificação (CFOP origem, CFOP entrada, UF, tipo de operação, fornecedor ou NCM).',
      );
      setAbaForm('cfop');
      return;
    }
    try {
      const payload = normalizarFormParaApi(form, {
        escopoId: escopoAtual.id,
        cenarioId: cenarioAtual.id,
      });
      if (editing) await regrasFiscaisEntradaService.update(editing.id, payload);
      else await regrasFiscaisEntradaService.create(payload);
      toast.success(editing ? 'Classificação de entrada atualizada.' : 'Classificação de entrada criada.');
      setModalOpen(false);
      void loadMatriz(cenarioAtual.id, escopoAtual.id);
      void loadEscopos(cenarioAtual.id);
    } catch (e) {
      const msg = apiErrorMessage(e, {
        fallback: 'Não foi possível salvar a regra fiscal de entrada. Verifique os campos informados.',
      });
      setErro(msg);
      const aba = abaRegraEntradaParaErro(msg);
      if (aba) setAbaForm(aba as AbaFormRegra);
    }
  };

  const handleCriarEscopo = async () => {
    if (!cenarioAtual) return;
    setErro('');
    try {
      const data: Parameters<typeof cenariosFiscaisEntradaService.createEscopo>[1] = {
        tipo_escopo: novoEscopoTipo,
        ncm: novoEscopoTipo === 'NCM' || novoEscopoTipo === 'NCM_PREFIXO' ? novoEscopoNcm.trim() : '',
        produto_id:
          novoEscopoTipo === 'PRODUTO' && novoEscopoProdutoId
            ? Number(novoEscopoProdutoId)
            : null,
        ativo: true,
        prioridade_escopo: 10,
      };
      await cenariosFiscaisEntradaService.createEscopo(cenarioAtual.id, data);
      setModalEscopoOpen(false);
      setNovoEscopoNcm('');
      setNovoEscopoProdutoId('');
      void loadEscopos(cenarioAtual.id);
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível criar o escopo. Verifique NCM ou produto.' }));
    }
  };

  const f = <K extends keyof FormRegraEntrada>(k: K, v: FormRegraEntrada[K]) =>
    setForm((p) => ({ ...p, [k]: v }));
  const fReforma = (k: keyof ReformaTributariaForm, v: string) =>
    setForm((p) => ({ ...p, reforma_tributaria: { ...p.reforma_tributaria, [k]: v } }));

  const escoposOrdenados = [...escopos].sort((a, b) => {
    const ord: Record<TipoEscopoFiscalEntrada, number> = { GERAL: 0, NCM: 1, NCM_PREFIXO: 2, PRODUTO: 3 };
    return (ord[a.tipo_escopo] ?? 9) - (ord[b.tipo_escopo] ?? 9);
  });

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Classificação Fiscal de Entrada</h2>
        <p className="text-xs text-muted-foreground mt-1 max-w-3xl">
          Valida o XML recebido do fornecedor: classifica <strong>CFOP origem → CFOP entrada</strong>, indica{' '}
          <strong>movimentação de estoque</strong>, <strong>crédito fiscal</strong> e <strong>certificado</strong>, e
          aponta <strong>divergências de impostos</strong> no XML. Bloqueia a conferência apenas com severidade{' '}
          <strong>BLOQUEIO</strong>. Não é cenário de emissão de impostos (isso fica em Saída / Propostas).
        </p>
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
            <p className="text-sm text-muted-foreground py-6">Carregando classificações fiscais…</p>
          ) : null}
          {!cenariosLoading && cenariosErro ? (
            <div className="erp-card p-4 border-destructive/30 bg-destructive/5 mb-3">
              <p className="text-sm text-destructive">{cenariosErro}</p>
              <button type="button" className="erp-btn-outline erp-btn-sm mt-2" onClick={() => void loadCenarios()}>
                Tentar novamente
              </button>
            </div>
          ) : null}
          {!cenariosLoading && !cenariosErro && cenarios.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 mb-3">
              Nenhuma classificação cadastrada. O servidor cria a classificação padrão automaticamente — tente recarregar.
            </p>
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
                  {c.regime_tributario ? ` · ${c.regime_tributario}` : ''}
                </p>
                <button type="button" className="erp-btn-primary erp-btn-sm w-fit mt-1" onClick={() => void abrirCenario(c)}>
                  Abrir classificação
                </button>
              </div>
            ))}
            {!cenariosLoading ? (
              <div className="erp-card p-4 border-dashed opacity-60 flex items-center justify-center min-h-[100px]">
                <span className="text-sm text-muted-foreground">Nova classificação (em breve)</span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {view === 'escopos' && cenarioAtual ? (
        <div>
          <h2 className="text-lg font-semibold mb-1">{cenarioAtual.nome}</h2>
          <p className="text-xs text-muted-foreground mb-3">Escopos: NCM, produto ou regra geral</p>
          <div className="flex flex-wrap gap-2 mb-3">
            <button type="button" className="erp-btn-primary erp-btn-sm" onClick={() => setModalEscopoOpen(true)}>
              Configurar outro NCM
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => {
                setNovoEscopoTipo('PRODUTO');
                setModalEscopoOpen(true);
              }}
            >
              Exceção por produto
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={async () => {
                const existente = escopos.find((e) => e.tipo_escopo === 'GERAL');
                if (existente) void abrirEscopo(existente);
                else if (cenarioAtual) {
                  const escopo = await cenariosFiscaisEntradaService.createEscopo(cenarioAtual.id, {
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
            <table className="erp-table text-sm" data-mobile-table-mode="cards">
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
                    <td className="font-medium">{labelEscopoUi(e)}</td>
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
            Defina classificação (CFOP origem/entrada, UF, efeitos) e valores esperados no XML para divergências de
            impostos. Use copiar para replicar entre UFs.
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            <button type="button" className="erp-btn-primary erp-btn-sm" onClick={openNewConfig}>
              Nova configuração
            </button>
            <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => openCopiar()}>
              <CopyPlus className="h-4 w-4 inline mr-1" />
              Copiar configuração
            </button>
          </div>
          {matriz?.ufs_sem_configuracao?.length ? (
            <p className="text-xs text-muted-foreground mb-2">
              UFs ainda sem nenhuma configuração neste escopo:{' '}
              <span className="font-mono">{matriz.ufs_sem_configuracao.join(', ')}</span>
            </p>
          ) : null}
          <div className="erp-card overflow-x-auto">
            <table className="erp-table text-sm" data-mobile-table-mode="cards">
              <thead>
                <tr>
                  <th>UF origem</th>
                  <th>UF destino</th>
                  <th>CFOP origem</th>
                  <th>CFOP entrada</th>
                  <th>Efeitos</th>
                  <th>Validação impostos (XML)</th>
                  <th>Status</th>
                  <th className="min-w-[120px]">Ações</th>
                </tr>
              </thead>
              <tbody>
                {(matriz?.configuracoes ?? []).map((cfg) => (
                  <tr key={cfg.id}>
                    <td>{cfg.uf_origem || '*'}</td>
                    <td>{cfg.uf_destino || '*'}</td>
                    <td className="font-mono text-xs">{cfg.cfop_origem || '—'}</td>
                    <td className="font-mono text-xs">{cfg.cfop_entrada || '—'}</td>
                    <td className="text-xs max-w-[180px] truncate" title={resumoEfeitosMatriz(cfg)}>
                      {resumoEfeitosMatriz(cfg)}
                      <span className="block text-muted-foreground">
                        {labelSeveridadeRegraEntrada(cfg.efeitos.severidade)}
                      </span>
                    </td>
                    <td
                      className="text-xs text-muted-foreground max-w-[200px] truncate"
                      title={`ICMS: ${cfg.resumo_impostos.icms || '—'} · IPI: ${cfg.resumo_impostos.ipi || '—'} · PIS: ${cfg.resumo_impostos.pis || '—'} · COFINS: ${cfg.resumo_impostos.cofins || '—'}`}
                    >
                      {[cfg.resumo_impostos.icms, cfg.resumo_impostos.ipi, cfg.resumo_impostos.pis, cfg.resumo_impostos.cofins]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </td>
                    <td>
                      <span className={badgeClassStatusConfiguracao(cfg.status_configuracao)}>
                        {labelStatusConfiguracao(cfg.status_configuracao)}
                      </span>
                      {cfg.incompleta && cfg.ativo !== false ? (
                        <span
                          className="erp-badge-warning text-[9px] ml-1"
                          title={(cfg.pendencias_fiscais ?? []).join(' ')}
                        >
                          Incompleta
                        </span>
                      ) : null}
                      {cfg.tem_reforma ? (
                        <span className="erp-badge-secondary text-[9px] ml-1" title="Reforma Tributária configurada">
                          Reforma
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Editar" onClick={() => void openEdit(cfg)}>
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Duplicar" onClick={() => openDuplicar(cfg)}>
                          <Copy className="h-4 w-4" />
                        </button>
                        <button type="button" className="erp-btn-ghost erp-btn-sm" title="Copiar para estados" onClick={() => openCopiar(cfg)}>
                          <CopyPlus className="h-4 w-4" />
                        </button>
                        <button type="button" className="erp-btn-ghost erp-btn-sm text-destructive" title="Excluir" onClick={() => void handleDelete(cfg.id)}>
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


      <Modal isOpen={modalDuplicarOpen} onClose={() => setModalDuplicarOpen(false)} title="Duplicar configuração" size="md">
        {erro ? <p className="text-destructive text-sm mb-2">{erro}</p> : null}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div>
            <label className="erp-label">UF origem</label>
            <select className="erp-select mt-1 w-full" value={dupForm.uf_origem} onChange={(e) => setDupForm((p) => ({ ...p, uf_origem: e.target.value }))}>
              <option value="">—</option>
              {UFS.map((u) => (<option key={u} value={u}>{u}</option>))}
            </select>
          </div>
          <div>
            <label className="erp-label">UF destino</label>
            <select className="erp-select mt-1 w-full" value={dupForm.uf_destino} onChange={(e) => setDupForm((p) => ({ ...p, uf_destino: e.target.value }))}>
              <option value="">—</option>
              {UFS.map((u) => (<option key={u} value={u}>{u}</option>))}
            </select>
          </div>
          <div>
            <label className="erp-label">CFOP origem</label>
            <input className="erp-input mt-1 w-full" value={dupForm.cfop_origem} onChange={(e) => setDupForm((p) => ({ ...p, cfop_origem: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">CFOP entrada</label>
            <input className="erp-input mt-1 w-full" value={dupForm.cfop_entrada} onChange={(e) => setDupForm((p) => ({ ...p, cfop_entrada: e.target.value }))} />
          </div>
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-4">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={() => setModalDuplicarOpen(false)}>Cancelar</button>
          <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleDuplicar()}>Duplicar</button>
        </div>
      </Modal>

      <Modal isOpen={modalCopiarOpen} onClose={() => setModalCopiarOpen(false)} title="Copiar para outros estados" size="lg">
        {erro ? <p className="text-destructive text-sm mb-2">{erro}</p> : null}
        <div className="space-y-3 text-sm max-h-[50vh] overflow-y-auto pr-1">
          <div>
            <label className="erp-label">Configuração de origem</label>
            <select className="erp-select mt-1 w-full" value={copiarOrigemId} onChange={(e) => setCopiarOrigemId(e.target.value === '' ? '' : Number(e.target.value))}>
              <option value="">Selecione...</option>
              {(matriz?.configuracoes ?? []).map((c) => (
                <option key={c.id} value={c.id}>{c.label_configuracao || `${c.uf_origem}→${c.uf_destino} ${c.cfop_origem}→${c.cfop_entrada}`}</option>
              ))}
            </select>
          </div>
          {copiarDestinos.map((dest, idx) => (
            <div key={idx} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 border border-border rounded p-2">
              <select className="erp-select" value={dest.uf_origem || ''} onChange={(e) => setCopiarDestinos((prev) => prev.map((d, i) => i === idx ? { ...d, uf_origem: e.target.value } : d))}>
                <option value="">UF orig.</option>
                {UFS.map((u) => (<option key={u} value={u}>{u}</option>))}
              </select>
              <select className="erp-select" value={dest.uf_destino || ''} onChange={(e) => setCopiarDestinos((prev) => prev.map((d, i) => i === idx ? { ...d, uf_destino: e.target.value } : d))}>
                <option value="">UF dest.</option>
                {UFS.map((u) => (<option key={u} value={u}>{u}</option>))}
              </select>
              <input className="erp-input" placeholder="CFOP orig." value={dest.cfop_origem || ''} onChange={(e) => setCopiarDestinos((prev) => prev.map((d, i) => i === idx ? { ...d, cfop_origem: e.target.value } : d))} />
              <input className="erp-input" placeholder="CFOP entr." value={dest.cfop_entrada || ''} onChange={(e) => setCopiarDestinos((prev) => prev.map((d, i) => i === idx ? { ...d, cfop_entrada: e.target.value } : d))} />
            </div>
          ))}
          <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setCopiarDestinos((p) => [...p, { uf_origem: '', uf_destino: '', cfop_origem: '', cfop_entrada: '' }])}>
            + Adicionar destino
          </button>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={copiarSobrescrever} onChange={(e) => setCopiarSobrescrever(e.target.checked)} />
            Sobrescrever configurações existentes
          </label>
          {resultadoCopia ? (
            <div className="text-xs bg-muted/40 rounded p-2 space-y-1">
              <p>Criados: {resultadoCopia.criados.length ? resultadoCopia.criados.join(', ') : '—'}</p>
              <p>Atualizados: {resultadoCopia.atualizados.length ? resultadoCopia.atualizados.join(', ') : '—'}</p>
              <p>Ignorados: {resultadoCopia.ignorados.length}</p>
              {resultadoCopia.ignorados.map((ig, i) => (
                <p key={i} className="text-muted-foreground">{ig.motivo}</p>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-4">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={() => setModalCopiarOpen(false)}>Fechar</button>
          <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleCopiar()}>Copiar</button>
        </div>
      </Modal>

      <Modal
        isOpen={modalEscopoOpen}
        onClose={() => setModalEscopoOpen(false)}
        title="Novo escopo"
        size="md"
      >
        {erro ? <p className="text-destructive text-sm mb-2">{erro}</p> : null}
        <div className="space-y-3 text-sm">
          <div>
            <label className="erp-label">Tipo</label>
            <select
              className="erp-select mt-1 w-full"
              value={novoEscopoTipo}
              onChange={(e) => setNovoEscopoTipo(e.target.value as TipoEscopoFiscalEntrada)}
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
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-4">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={() => setModalEscopoOpen(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleCriarEscopo()}>
            Criar
          </button>
        </div>
      </Modal>

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar classificação de entrada' : 'Nova classificação de entrada'}
        size="lg"
      >
        {escopoAtual ? (
          <p className="text-xs text-muted-foreground mb-2">
            Escopo: <strong>{labelEscopoUi(escopoAtual)}</strong> — o rótulo da configuração é gerado automaticamente.
          </p>
        ) : null}
        {erro ? <p className="text-destructive text-sm mb-3">{erro}</p> : null}
        <p className="text-xs text-muted-foreground mb-2">{HINT_CAMPOS_NAO_VALIDADOS}</p>
        <p className="text-[11px] text-muted-foreground mb-3">
          Prefira <strong className="text-foreground font-medium">selecionar</strong> nos catálogos.
          Campo vazio = não valida / espelha a NF-e de origem na devolução.
        </p>

        <div className="flex flex-wrap gap-1 mb-3">
          {ABAS_FORM.map((aba) => (
            <button
              key={aba.id}
              type="button"
              className={abaForm === aba.id ? 'erp-btn-primary erp-btn-sm w-full sm:w-auto' : 'erp-btn-outline erp-btn-sm w-full sm:w-auto'}
              onClick={() => setAbaForm(aba.id)}
            >
              {aba.label}
            </button>
          ))}
        </div>
        <div className="space-y-4 text-sm max-h-[60vh] overflow-y-auto pr-1">
          {abaForm === 'cfop' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">CFOP e UF</h3>
              {form.tipo_operacao_fiscal === 'DEVOLUCAO_VENDA' ? (
                <div className="mb-3">
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm text-[11px]"
                    onClick={() => {
                      setForm((p) => ({
                        ...p,
                        cst_pis_esperado: '98',
                        aliquota_pis: '0.65',
                        cst_cofins_esperado: '98',
                        aliquota_cofins: '3',
                        cst_ipi_esperado: p.cst_ipi_esperado || '49',
                      }));
                      toast.success('Preset Lucro Presumido aplicado (PIS/COFINS 98). Revise e salve.');
                      setAbaForm('pis');
                    }}
                  >
                    Preencher PIS/COFINS Lucro Presumido (98)
                  </button>
                </div>
              ) : null}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCfopSearchSelect
                  label="CFOP origem (NF de saída)"
                  value={form.cfop_origem}
                  onChange={(v) => setForm((p) => ({ ...p, cfop_origem: v, cfop: v }))}
                  ufOrigem={form.uf_origem}
                  ufDestino={form.uf_destino}
                  hint={HINT_CFOP_SAIDA}
                />
                <CatalogCfopSearchSelect
                  label="CFOP entrada esperado"
                  value={form.cfop_entrada}
                  onChange={(v) => f('cfop_entrada', v)}
                  opcoes={CFOP_ENTRADA_OPCOES}
                  agruparPorUf={false}
                  hint={HINT_CFOP_ENTRADA}
                  placeholder="Buscar CFOP de entrada..."
                />
                <div>
                  <label className="erp-label">UF origem</label>
                  <select className="erp-select mt-1" value={form.uf_origem} onChange={(e) => f('uf_origem', e.target.value)}>
                    <option value="">— Qualquer —</option>
                    {UFS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="erp-label">UF destino</label>
                  <select className="erp-select mt-1" value={form.uf_destino} onChange={(e) => f('uf_destino', e.target.value)}>
                    <option value="">— Qualquer —</option>
                    {UFS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="erp-label">Tipo operação</label>
                  <select
                    className="erp-select mt-1"
                    value={form.tipo_operacao_fiscal}
                    onChange={(e) => f('tipo_operacao_fiscal', e.target.value as TipoOperacaoFiscalEntrada)}
                  >
                    {TIPOS_OP.map((o) => (
                      <option key={o.value || 'any'} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="erp-label">Fornecedor (ID)</label>
                  <input
                    type="number"
                    className="erp-input mt-1"
                    placeholder="Opcional"
                    value={form.fornecedor_id ?? ''}
                    onChange={(e) => f('fornecedor_id', e.target.value ? Number(e.target.value) : null)}
                  />
                </div>
                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={form.ativo} onChange={(e) => f('ativo', e.target.checked)} />
                    Ativo
                  </label>
                </div>
                <div className="md:col-span-3">
                  <label className="erp-label">Mensagem padrão / informações complementares</label>
                  <input className="erp-input mt-1" value={form.mensagem_padrao} onChange={(e) => f('mensagem_padrao', e.target.value)} />
                </div>
              </div>
            </section>
          ) : null}

          {abaForm === 'icms' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">ICMS</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCodigoFiscalSelect
                  label="CST ICMS"
                  value={form.cst_icms_esperado}
                  onChange={(v) => f('cst_icms_esperado', v)}
                  opcoes={CST_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="CSOSN"
                  value={form.csosn_esperado}
                  onChange={(v) => f('csosn_esperado', v)}
                  opcoes={CSOSN_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Modalidade BC"
                  value={form.modalidade_bc_icms}
                  onChange={(v) => f('modalidade_bc_icms', v)}
                  opcoes={MODALIDADE_BC_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota ICMS (%)"
                  value={form.aliquota_icms}
                  onChange={(v) => f('aliquota_icms', v)}
                  opcoes={ALIQUOTA_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">Redução BC (%)</label>
                  <input className="erp-input mt-1" value={form.reducao_bc_icms} onChange={(e) => f('reducao_bc_icms', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Cód. benefício</label>
                  <input className="erp-input mt-1" value={form.codigo_beneficio_icms} onChange={(e) => f('codigo_beneficio_icms', e.target.value)} />
                </div>
                <CatalogCodigoFiscalSelect
                  label="Motivo desoneração"
                  value={form.motivo_desoneracao_icms}
                  onChange={(v) => f('motivo_desoneracao_icms', v)}
                  opcoes={MOTIVO_DESONERACAO_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">ST aplicável</label>
                  <select
                    className="erp-select mt-1"
                    value={form.icms_st_aplicavel}
                    onChange={(e) => f('icms_st_aplicavel', e.target.value as '' | 'sim' | 'nao')}
                  >
                    {BOOL_TRI_OPCOES.map((o) => (
                      <option key={o.value || 'nv'} value={o.value}>
                        {o.value === '' ? '— Não validar —' : o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <CatalogCodigoFiscalSelect
                  label="CST ICMS ST"
                  value={form.cst_icms_st_esperado}
                  onChange={(v) => f('cst_icms_st_esperado', v)}
                  opcoes={CST_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota ICMS ST (%)"
                  value={form.aliquota_icms_st}
                  onChange={(v) => f('aliquota_icms_st', v)}
                  opcoes={ALIQUOTA_ICMS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">MVA ST (%)</label>
                  <input className="erp-input mt-1" value={form.mva_st} onChange={(e) => f('mva_st', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Redução BC ST (%)</label>
                  <input className="erp-input mt-1" value={form.reducao_bc_st} onChange={(e) => f('reducao_bc_st', e.target.value)} />
                </div>
              </div>
              <h4 className="font-medium text-xs mt-4 mb-2 text-muted-foreground">FCP (opcional)</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="erp-label">FCP aplicável</label>
                  <select
                    className="erp-select mt-1"
                    value={form.fcp_aplicavel}
                    onChange={(e) => f('fcp_aplicavel', e.target.value as '' | 'sim' | 'nao')}
                  >
                    {BOOL_TRI_OPCOES.map((o) => (
                      <option key={`fcp-${o.value || 'nv'}`} value={o.value}>
                        {o.value === '' ? '— Não validar —' : o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="erp-label">Alíquota FCP (%)</label>
                  <input className="erp-input mt-1" value={form.aliquota_fcp} onChange={(e) => f('aliquota_fcp', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Alíquota FCP ST (%)</label>
                  <input className="erp-input mt-1" value={form.aliquota_fcp_st} onChange={(e) => f('aliquota_fcp_st', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Redução BC FCP (%)</label>
                  <input className="erp-input mt-1" value={form.reducao_bc_fcp} onChange={(e) => f('reducao_bc_fcp', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Valor FCP/unidade</label>
                  <input className="erp-input mt-1" value={form.valor_fcp_unidade} onChange={(e) => f('valor_fcp_unidade', e.target.value)} />
                </div>
              </div>
            </section>
          ) : null}

          {abaForm === 'ipi' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">IPI</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCodigoFiscalSelect
                  label="CST IPI"
                  value={form.cst_ipi_esperado}
                  onChange={(v) => f('cst_ipi_esperado', v)}
                  opcoes={CST_IPI_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Tipo cálculo"
                  value={form.tipo_calculo_ipi}
                  onChange={(v) => f('tipo_calculo_ipi', v)}
                  opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">Alíquota IPI (%)</label>
                  <input className="erp-input mt-1" value={form.aliquota_ipi} onChange={(e) => f('aliquota_ipi', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Valor/unidade</label>
                  <input className="erp-input mt-1" value={form.valor_ipi_unidade} onChange={(e) => f('valor_ipi_unidade', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Enquadramento</label>
                  <input className="erp-input mt-1" value={form.enquadramento_ipi} onChange={(e) => f('enquadramento_ipi', e.target.value)} />
                </div>
              </div>
            </section>
          ) : null}

          {abaForm === 'pis' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">PIS</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCodigoFiscalSelect
                  label="CST PIS"
                  value={form.cst_pis_esperado}
                  onChange={(v) => f('cst_pis_esperado', v)}
                  opcoes={CST_PIS_COFINS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Tipo cálculo"
                  value={form.tipo_calculo_pis}
                  onChange={(v) => f('tipo_calculo_pis', v)}
                  opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota PIS (%)"
                  value={form.aliquota_pis}
                  onChange={(v) => f('aliquota_pis', v)}
                  opcoes={ALIQUOTA_PIS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">Redução base (%)</label>
                  <input className="erp-input mt-1" value={form.reducao_base_pis} onChange={(e) => f('reducao_base_pis', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Valor mín./unidade</label>
                  <input className="erp-input mt-1" value={form.valor_minimo_pis_unidade} onChange={(e) => f('valor_minimo_pis_unidade', e.target.value)} />
                </div>
                <CatalogCodigoFiscalSelect
                  label="Alíquota PIS ST (%)"
                  value={form.aliquota_pis_st}
                  onChange={(v) => f('aliquota_pis_st', v)}
                  opcoes={ALIQUOTA_PIS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
              </div>
            </section>
          ) : null}

          {abaForm === 'cofins' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">COFINS</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCodigoFiscalSelect
                  label="CST COFINS"
                  value={form.cst_cofins_esperado}
                  onChange={(v) => f('cst_cofins_esperado', v)}
                  opcoes={CST_PIS_COFINS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Tipo cálculo"
                  value={form.tipo_calculo_cofins}
                  onChange={(v) => f('tipo_calculo_cofins', v)}
                  opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota COFINS (%)"
                  value={form.aliquota_cofins}
                  onChange={(v) => f('aliquota_cofins', v)}
                  opcoes={ALIQUOTA_COFINS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">Redução base (%)</label>
                  <input className="erp-input mt-1" value={form.reducao_base_cofins} onChange={(e) => f('reducao_base_cofins', e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Valor mín./unidade</label>
                  <input className="erp-input mt-1" value={form.valor_minimo_cofins_unidade} onChange={(e) => f('valor_minimo_cofins_unidade', e.target.value)} />
                </div>
                <CatalogCodigoFiscalSelect
                  label="Alíquota COFINS ST (%)"
                  value={form.aliquota_cofins_st}
                  onChange={(v) => f('aliquota_cofins_st', v)}
                  opcoes={ALIQUOTA_COFINS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
              </div>
            </section>
          ) : null}

          {abaForm === 'reforma' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">Reforma Tributária</h3>
              <p className="text-xs text-muted-foreground mb-3">
                Campos preparatórios (IBS/CBS). Em devolução, deixe vazio para espelhar a saída; ou selecione a
                alíquota-teste 2026.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <CatalogCodigoFiscalSelect
                  label="CST IBS/CBS"
                  value={form.reforma_tributaria.cst_ibs_cbs}
                  onChange={(v) => fReforma('cst_ibs_cbs', v)}
                  opcoes={CST_IBS_CBS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Classificação tributária"
                  value={form.reforma_tributaria.classificacao_tributaria}
                  onChange={(v) => fReforma('classificacao_tributaria', v)}
                  opcoes={CLASSIFICACAO_TRIBUTARIA_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota CBS (%)"
                  value={form.reforma_tributaria.aliquota_cbs}
                  onChange={(v) => fReforma('aliquota_cbs', v)}
                  opcoes={ALIQUOTA_CBS_2026_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Alíquota IBS estadual (%)"
                  value={form.reforma_tributaria.aliquota_ibs_estadual}
                  onChange={(v) => fReforma('aliquota_ibs_estadual', v)}
                  opcoes={ALIQUOTA_IBS_UF_2026_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <div>
                  <label className="erp-label">Alíquota IBS municipal (%)</label>
                  <input
                    className="erp-input mt-1"
                    value={form.reforma_tributaria.aliquota_ibs_municipal}
                    onChange={(e) => fReforma('aliquota_ibs_municipal', e.target.value)}
                  />
                </div>
                <CatalogCodigoFiscalSelect
                  label="Modo base IBS/CBS"
                  value={form.reforma_tributaria.modo_base_ibs_cbs}
                  onChange={(v) => fReforma('modo_base_ibs_cbs', v)}
                  opcoes={MODO_BASE_IBS_CBS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                <CatalogCodigoFiscalSelect
                  label="Fonte da regra de base"
                  value={form.reforma_tributaria.fonte_regra_base_ibs_cbs}
                  onChange={(v) => fReforma('fonte_regra_base_ibs_cbs', v)}
                  opcoes={FONTE_REGRA_BASE_IBS_CBS_OPCOES}
                  emptyLabel={EMPTY_LABEL_NAO_VALIDAR}
                />
                {REFORMA_TRIBUTARIA_KEYS.filter(
                  (key) =>
                    ![
                      'cst_ibs_cbs',
                      'classificacao_tributaria',
                      'aliquota_cbs',
                      'aliquota_ibs_estadual',
                      'aliquota_ibs_municipal',
                      'modo_base_ibs_cbs',
                      'fonte_regra_base_ibs_cbs',
                    ].includes(key),
                ).map((key) => (
                  <div key={key}>
                    <label className="erp-label">{key.replace(/_/g, ' ')}</label>
                    <input
                      className="erp-input mt-1"
                      value={form.reforma_tributaria[key]}
                      onChange={(e) => fReforma(key, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {abaForm === 'efeitos' ? (
            <section>
              <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">Efeitos</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="erp-label">Severidade</label>
                  <select
                    className="erp-select mt-1"
                    value={form.severidade}
                    onChange={(e) => f('severidade', e.target.value as SeveridadeRegraFiscalEntrada)}
                  >
                    <option value="INFORMATIVO">Informativo</option>
                    <option value="ALERTA">Alerta</option>
                    <option value="BLOQUEIO">Bloqueio</option>
                  </select>
                </div>
                <div className="md:col-span-3 flex flex-wrap gap-4">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={form.movimenta_estoque} onChange={(e) => f('movimenta_estoque', e.target.checked)} />
                    Movimenta estoque
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={form.exige_certificado_fornecedor}
                      onChange={(e) => f('exige_certificado_fornecedor', e.target.checked)}
                    />
                    Exige cert. fornecedor
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={form.permite_credito_fiscal}
                      onChange={(e) => f('permite_credito_fiscal', e.target.checked)}
                    />
                    Permite crédito fiscal
                  </label>
                </div>
                <div className="md:col-span-3">
                  <label className="erp-label">Observações</label>
                  <textarea className="erp-input mt-1 min-h-[72px]" value={form.observacoes} onChange={(e) => f('observacoes', e.target.value)} />
                </div>
              </div>
            </section>
          ) : null}
        </div>

        <section>
          <button type="button" className="text-xs text-primary underline" onClick={() => setShowAvancado((v) => !v)}>
            {showAvancado ? 'Ocultar' : 'Mostrar'} campos avançados (prioridade, nome, código)
          </button>
          {showAvancado ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2">
              <div>
                <label className="erp-label">Prioridade</label>
                <input
                  type="number"
                  className="erp-input mt-1"
                  value={form.prioridade}
                  onChange={(e) => f('prioridade', Number(e.target.value))}
                />
              </div>
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
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2 mt-6 pt-4 border-t border-border">
          <button type="button" className="erp-btn-outline w-full sm:w-auto" onClick={() => setModalOpen(false)}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary w-full sm:w-auto" onClick={() => void handleSave()}>
            Salvar
          </button>
        </div>
      </Modal>
    </div>
  );
};
