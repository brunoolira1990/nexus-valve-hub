import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ClipboardCheck, Loader2, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { BotaoAtualizarImpostosNFe } from '@/components/fiscal/NFeSaidaAtualizarImpostosModal';
import { NFeSaidaEmissaoProducaoPanel } from '@/components/fiscal/NFeSaidaEmissaoProducaoPanel';
import { NFeSaidaEfeitosPanel } from '@/components/fiscal/NFeSaidaEfeitosPanel';
import { TransportadoraNFeField } from '@/components/fiscal/TransportadoraNFeField';
import { AlocacaoAtendimentoGerenciarSection } from '@/components/comercial/AlocacaoAtendimentoGerenciarPanel';
import { AtendimentoOperacionalResumo } from '@/components/comercial/AtendimentoOperacionalResumo';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { Modal } from '@/components/Modal';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { extrairErrosXsd, formatNfeErrosLista } from '@/lib/nfeXsdErros';
import { apiErrorMessage } from '@/services/api/config';
import {
  nfeSaidasService,
  type NFeSaidaConferenciaPayload,
  type DanfePreviewMeta,
  type NFeSaidaPreviewXmlResponse,
  type ValidacaoNFeSaidaItem,
  type ValidacaoNFeSaidaResponse,
} from '@/services/api/fiscal';
import {
  badgeNfeSaidaStatus,
  badgeNfeSaidaEmissaoSefaz,
  deveExibirMensagemProntaEmissao,
  isAutorizadaHomologacao,
  mensagemCabecalhoNfeAutorizadaHomolog,
  mensagemProntaParaEmissao,
  nfeSalvarFormularioBloqueado,
  nfePodeDescartarRascunho,
} from '@/lib/nfeSaidaUi';
import {
  GRUPO_VALIDACAO_LABELS,
  badgeStatusConferencia,
  fmtMoeda,
  fmtNum,
  labelOrigemNfe,
} from '@/lib/nfeSaidaConferencia';
import { linhasReformaItemExibicao, badgeStatusBaseReforma, mensagemBaseReforma } from '@/lib/nfeSaidaReformaExibicao';
import {
  conferenciaTemAlteracoesNaoSalvas,
  montarPayloadSalvarConferencia,
  snapshotConferenciaDirty,
  transporteTemDadosPreenchidos,
  type ConferenciaDirtySnapshot,
} from '@/lib/nfeSaidaConferenciaDirty';
import {
  badgeStatusConferenciaNFe,
  mensagemOrientacaoProntidao,
  type NFeSaidaProntidaoPayload,
} from '@/lib/nfeSaidaProntidaoConferencia';
import {
  MODALIDADE_FRETE_OPCOES,
  agruparValidacaoPorGrupo,
  agruparValidacaoPorSeveridade,
  alertasTransporteLocal,
  diagnosticoReformaExibicao,
  labelModalidadeFrete,
  transportadoraStub,
} from '@/lib/nfeSaidaConferenciaUx';
import type { Transportadora } from '@/types';
import { AdvancedSupportSection } from '@/components/nexus/AdvancedSupportSection';
import { GerarContasReceberNfeModal } from '@/components/fiscal/GerarContasReceberNfeModal';
import { NFeConsultaSefazModal } from '@/components/fiscal/NFeConsultaSefazModal';
import { NFeCartaCorrecaoModal } from '@/components/fiscal/NFeCartaCorrecaoModal';
import { NFeCancelamentoModal } from '@/components/fiscal/NFeCancelamentoModal';
import { buildCartaCorrecaoContextoFromConferencia } from '@/lib/nfeCartaCorrecaoPreview';
import { NFeFinanceiroPanel } from '@/components/fiscal/NFeFinanceiroPanel';
import { NFeSaidaAcoesOperacionais } from '@/components/fiscal/NFeSaidaAcoesOperacionais';
import { NFeSaidaAcoesContextoBanner } from '@/components/fiscal/NFeSaidaAcoesGruposPanel';
import {
  GRUPO_ACAO_LABELS,
  obterMatrizAcoesNfeSaida,
  resolverContextoNfeSaida,
} from '@/lib/nfeSaidaAcoesMatriz';
import { podeExibirBotaoEmitirProducao } from '@/lib/nfeSaidaEmissaoProducao';
import { isNfeAmbienteProducao } from '@/lib/empresaNfeAmbiente';
import {
  ambienteEmissaoNfeDefinido,
  labelProximaNumeracaoCadastro,
  MSG_AMBIENTE_NAO_DEFINIDO,
  resolverAmbienteEmissaoNfeConferencia,
  resolverNumeracaoCadastroConferencia,
} from '@/lib/nfeSaidaAmbienteEmissao';
import { ACTION_LABELS } from '@/lib/operationalUi';

type ConferenciaItem = NFeSaidaConferenciaPayload['itens'][number] & {
  fiscal_alertas?: string[];
  reforma_diagnostico?: string;
};

type Props = {
  nfeId: number;
  onClose: () => void;
  onSaved: () => void;
};

function campoEditavel(editavel: boolean) {
  return editavel ? 'erp-input' : 'erp-input bg-muted/40 text-muted-foreground cursor-default';
}

function SeveridadeBloco({
  titulo,
  badgeClass,
  itens,
}: {
  titulo: string;
  badgeClass: string;
  itens: ValidacaoNFeSaidaItem[];
}) {
  if (!itens.length) return null;
  const porGrupo = agruparValidacaoPorGrupo(itens);
  return (
    <div className="rounded-md border border-border overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/30 border-b border-border">
        <span className={badgeClass}>{titulo}</span>
        <span className="text-xs text-muted-foreground">{itens.length}</span>
      </div>
      <div className="p-2 space-y-2 max-h-48 overflow-y-auto">
        {Object.entries(porGrupo).map(([grupo, lista]) => (
          <div key={grupo}>
            <p className="text-xs font-medium text-muted-foreground mb-0.5">
              {GRUPO_VALIDACAO_LABELS[grupo] ?? grupo}
            </p>
            <ul className="text-xs space-y-0.5 pl-3 list-disc">
              {lista.map((x, i) => (
                <li key={`${grupo}-${i}`}>{x.mensagem}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export function NFeSaidaConferenciaModal({ nfeId, onClose, onSaved }: Props) {
  const [conf, setConf] = useState<NFeSaidaConferenciaPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [validacao, setValidacao] = useState<ValidacaoNFeSaidaResponse | null>(null);
  const [validacaoLoading, setValidacaoLoading] = useState(false);
  const [marcarProntaLoading, setMarcarProntaLoading] = useState(false);
  const [selectedTransportadora, setSelectedTransportadora] = useState<Transportadora | null>(null);
  const [expandedItem, setExpandedItem] = useState<number | null>(null);
  const [xmlModalOpen, setXmlModalOpen] = useState(false);
  const [xmlPreview, setXmlPreview] = useState<NFeSaidaPreviewXmlResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [danfeMeta, setDanfeMeta] = useState<DanfePreviewMeta | null>(null);
  const [danfeLoading, setDanfeLoading] = useState(false);
  const [historicoRefreshKey, setHistoricoRefreshKey] = useState(0);
  const [emissaoLoading, setEmissaoLoading] = useState(false);
  const [emissaoMsg, setEmissaoMsg] = useState<string | null>(null);
  const [validarXmlLoading, setValidarXmlLoading] = useState(false);
  const [validacaoXsdErros, setValidacaoXsdErros] = useState<Array<Record<string, unknown>>>([]);
  const [emitirHomologConfirmOpen, setEmitirHomologConfirmOpen] = useState(false);
  const [corrigirSerieConfirmOpen, setCorrigirSerieConfirmOpen] = useState(false);
  const [mod9ConfirmOpen, setMod9ConfirmOpen] = useState(false);
  const [xmlTransmissaoLoading, setXmlTransmissaoLoading] = useState(false);
  const [corrigirSerieLoading, setCorrigirSerieLoading] = useState(false);
  const [descarteOpen, setDescarteOpen] = useState(false);
  const [descarteLoading, setDescarteLoading] = useState(false);
  const [gerarCrOpen, setGerarCrOpen] = useState(false);
  const [consultaSefazOpen, setConsultaSefazOpen] = useState(false);
  const [cartaCorrecaoOpen, setCartaCorrecaoOpen] = useState(false);
  const [cancelamentoOpen, setCancelamentoOpen] = useState(false);
  const [baselineSnapshot, setBaselineSnapshot] = useState<ConferenciaDirtySnapshot | null>(null);
  const [acaoLoadingMsg, setAcaoLoadingMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setAcaoLoadingMsg('Carregando conferência...');
    try {
      const data = await nfeSaidasService.conferencia(nfeId, { modo: 'abertura' });
      setConf(data);
      setBaselineSnapshot(snapshotConferenciaDirty(data));
      setValidacao((data.checklist as ValidacaoNFeSaidaResponse | null) ?? null);
      const emissaoSt = (data.emissao_sefaz as { status_emissao_sefaz?: string } | undefined)
        ?.status_emissao_sefaz;
      if (emissaoSt !== 'ERRO_TRANSMISSAO') {
        setValidacaoXsdErros([]);
      }
      const tr = data.transporte as {
        transportadora_id?: number | null;
        transportadora_nome?: string;
        transportadora_cnpj?: string;
      };
      if (tr.transportadora_id) {
        setSelectedTransportadora(
          transportadoraStub(tr.transportadora_id, tr.transportadora_nome || '', tr.transportadora_cnpj || ''),
        );
      } else {
        setSelectedTransportadora(null);
      }
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setLoading(false);
      setAcaoLoadingMsg(null);
    }
  }, [nfeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const validacaoAgrupada = useMemo(() => agruparValidacaoPorSeveridade(validacao), [validacao]);
  const alteracoesNaoSalvas = useMemo(
    () => (conf ? conferenciaTemAlteracoesNaoSalvas(conf, baselineSnapshot) : false),
    [conf, baselineSnapshot],
  );

  const contextoAcao = useMemo(
    () =>
      resolverContextoNfeSaida(
        {
          status: conf?.nfe?.status,
          status_emissao_sefaz: conf?.emissao_sefaz?.status_emissao_sefaz,
          ambiente_emissao: conf
            ? resolverAmbienteEmissaoNfeConferencia(conf)
            : undefined,
          chave_acesso: conf?.apresentacao?.chave_acesso || conf?.emissao_sefaz?.chave_acesso,
          tem_xml_autorizado: conf?.emissao_sefaz?.tem_xml_autorizado,
          autorizada_producao: conf?.emissao_producao?.autorizada_producao,
        },
        conf?.emissao_sefaz ?? undefined,
      ),
    [conf],
  );

  const { matrizAcoesConferencia, acoesFuturas, acoesFiscaisPosAutorizacao } = useMemo(() => {
    if (!conf) {
      return {
        matrizAcoesConferencia: [] as ReturnType<typeof obterMatrizAcoesNfeSaida>,
        acoesFuturas: [] as ReturnType<typeof obterMatrizAcoesNfeSaida>,
        acoesFiscaisPosAutorizacao: [] as ReturnType<typeof obterMatrizAcoesNfeSaida>,
      };
    }
    const autorizadaHomologCtx = isAutorizadaHomologacao(
      { status: String(conf.nfe.status) },
      conf.emissao_sefaz ?? null,
    );
    const prontidaoCtx = (conf.prontidao ?? {}) as NFeSaidaProntidaoPayload;
    const podeValidarCtx = Boolean(conf.permissoes.pode_validar_conferencia ?? prontidaoCtx.pode_validar);
    const podeTentarHomologCtx =
      Boolean(conf.permissoes.pode_tentar_emitir_homologacao) && !contextoAcao.isAmbienteProducao;
    const descarteCtx = nfePodeDescartarRascunho({
      status: String(conf.nfe.status),
      status_emissao_sefaz: conf.emissao_sefaz?.status_emissao_sefaz,
      protocolo_autorizacao:
        conf.emissao_sefaz?.protocolo_autorizacao || conf.apresentacao?.protocolo_autorizacao,
      cstat_autorizacao: conf.nfe.cstat_autorizacao as string | undefined,
    });
    const matriz = obterMatrizAcoesNfeSaida(contextoAcao, {
      podeDescartar: descarteCtx.pode,
      podeValidar: podeValidarCtx && !autorizadaHomologCtx,
      podeEmitirHomolog: podeTentarHomologCtx && !autorizadaHomologCtx,
      podeEmitirProducao:
        contextoAcao.exibirPainelEmissaoProducao &&
        podeExibirBotaoEmitirProducao(conf.emissao_producao, conf.permissoes),
    });
    return {
      matrizAcoesConferencia: matriz,
      acoesFuturas: matriz.filter((a) => a.grupo === 'futuras'),
      acoesFiscaisPosAutorizacao: matriz.filter((a) => a.grupo === 'fiscal'),
    };
  }, [conf, contextoAcao]);

  // Nenhum hook (useState/useEffect/useMemo/useCallback) abaixo desta linha.

  const serieHomologConfirm =
    conf?.emissao_sefaz?.serie_nfe ??
    conf?.emissao_sefaz?.numeracao_homologacao?.serie ??
    '0';
  const numeroHomologConfirm = conf?.emissao_sefaz?.numero_nfe ?? '';
  const emissaoErroTransmissao = conf?.emissao_sefaz?.status_emissao_sefaz === 'ERRO_TRANSMISSAO';
  const emissaoRejeitada = conf?.emissao_sefaz?.status_emissao_sefaz === 'REJEITADA_HOMOLOGACAO';
  const rejeicao225 = conf?.emissao_sefaz?.nfe?.cstat === '225';
  const rejeicao434 = conf?.emissao_sefaz?.nfe?.cstat === '434';
  const rejeicao588 = conf?.emissao_sefaz?.nfe?.cstat === '588';
  const rejeicao266 =
    conf?.emissao_sefaz?.nfe?.cstat === '266' || conf?.emissao_sefaz?.cstat_serie_invalida;
  const podeCorrigirSerie = Boolean(conf?.emissao_sefaz?.pode_corrigir_serie_homologacao);
  const serieConfigHomolog = conf?.emissao_sefaz?.numeracao_homologacao?.serie ?? '0';
  const emissaoOrfaPendente = Boolean(conf?.emissao_sefaz?.emissao_iniciada_pendente);
  const retryEmissaoHomolog = emissaoErroTransmissao || emissaoRejeitada || emissaoOrfaPendente;
  const labelEmitirHomolog = retryEmissaoHomolog ? ACTION_LABELS.reenviarNfe : ACTION_LABELS.emitirNfe;

  async function executarValidarXmlLocal() {
    setValidarXmlLoading(true);
    setValidacaoXsdErros([]);
    try {
      const res = (await nfeSaidasService.validarXmlSchema(nfeId)) as {
        ok?: boolean;
        erros?: Array<Record<string, unknown>>;
        compacto?: boolean;
        schema_ok?: boolean;
        tipo?: string;
      };
      if (res.ok) {
        const partes = [
          res.schema_ok !== false ? 'schema OK' : '',
          res.compacto !== false ? 'compacto para envio' : '',
        ].filter(Boolean);
        toast.success(`XML válido — ${partes.join(' · ') || 'pronto para transmitir'}.`);
      } else {
        const erros = (res.erros ?? []) as Array<Record<string, unknown>>;
        setValidacaoXsdErros(erros);
        if (res.tipo === 'CARACTERES_EDICAO') {
          toast.error(
            'Caracteres de edição no XML (cStat 588). Remova quebras/tabs/BOM entre tags antes de reenviar.',
          );
        } else {
          toast.error(`XML inválido — ${erros.length} erro(s).`);
        }
      }
      await load();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setValidarXmlLoading(false);
    }
  }

  async function executarCorrigirSerieHomologacao() {
    setCorrigirSerieConfirmOpen(false);
    setCorrigirSerieLoading(true);
    try {
      const res = await nfeSaidasService.corrigirSerieHomologacao(nfeId);
      if (!res.ok) {
        toast.error(res.mensagem || 'Não foi possível corrigir a série.');
        return;
      }
      toast.success(
        `Série ${res.serie_anterior || '—'} → ${res.serie_nova || serieConfigHomolog}. Chave recalculada.`,
      );
      setEmissaoMsg(
        `Série corrigida: ${res.serie_anterior} → ${res.serie_nova}. Nova chave: ${res.chave_nova || '—'}`,
      );
      await load();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setCorrigirSerieLoading(false);
    }
  }

  async function executarEmitirHomologacao() {
    setEmitirHomologConfirmOpen(false);
    setEmissaoLoading(true);
    setEmissaoMsg(null);
    try {
      const res = await nfeSaidasService.emitirHomologacao(nfeId);
      const cstatNfe = res.nfe?.cstat ?? res.cstat ?? res.cStat ?? '';
      const cstatLote = res.lote?.cstat ?? '';
      const xmotivoNfe = res.nfe?.xmotivo ?? res.xmotivo ?? res.xMotivo ?? '';
      const xsdExtraidos = extrairErrosXsd(res);
      const errosTxt = formatNfeErrosLista(xsdExtraidos.length ? xsdExtraidos : res.erros);
      const etapaTxt = res.etapa ? `Etapa: ${res.etapa}. ` : '';
      const xsdLista = xsdExtraidos as Array<Record<string, unknown>>;
      if (xsdLista.length) {
        setValidacaoXsdErros(xsdLista);
      } else {
        setValidacaoXsdErros([]);
      }
      const msgBase = res.mensagem || xmotivoNfe || errosTxt || 'Emissão não concluída.';
      if (res.ok || res.autorizado) {
        const linha = cstatNfe ? `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}` : msgBase;
        toast.success(`Autorizada em homologação — ${linha}`);
        setEmissaoMsg(`Autorizada homologação — ${linha}`);
      } else if (cstatNfe && cstatNfe !== 'ERRO' && cstatNfe !== cstatLote) {
        const linha = `cStat ${cstatNfe}: ${xmotivoNfe || msgBase}`.trim();
        toast.error(`SEFAZ — ${linha}`);
        setEmissaoMsg(`Rejeição SEFAZ — ${linha}`);
      } else if (cstatLote === '104' && !cstatNfe) {
        const linha = `Lote processado (cStat 104) — aguardando protocolo da NF-e. ${msgBase}`.trim();
        toast.warning(linha);
        setEmissaoMsg(linha);
      } else {
        const tecnico = `${etapaTxt}${msgBase}${errosTxt ? ` (${errosTxt})` : ''}`.trim();
        toast.error(tecnico);
        setEmissaoMsg(`Erro técnico — ${tecnico}`);
      }
      await load();
      setHistoricoRefreshKey((k) => k + 1);
    } catch (err) {
      const ax = err as { code?: string; message?: string };
      const msg =
        ax.code === 'ECONNABORTED'
          ? 'Tempo esgotado ao transmitir para a SEFAZ (homologação). Verifique certificado/rede e tente novamente.'
          : apiErrorMessage(err, {
              fallback:
                'Falha ao emitir em homologação. Verifique certificado A1, numeração e pendências na aba Validação.',
            });
      toast.error(msg);
      setEmissaoMsg(msg);
    } finally {
      setEmissaoLoading(false);
    }
  }

  if (loading) {
    return (
      <Modal isOpen onClose={onClose} title="Conferência NF-e Saída" size="2xl">
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{acaoLoadingMsg ?? 'Carregando conferência...'}</p>
        </div>
      </Modal>
    );
  }

  if (!conf) {
    return (
      <Modal isOpen onClose={onClose} title="Conferência NF-e Saída" size="2xl">
        <div className="flex flex-col items-center justify-center py-12 gap-4 px-4 text-center">
          <p className="text-sm text-destructive">
            {saveError || 'Não foi possível carregar a conferência desta NF-e.'}
          </p>
          <button type="button" className="erp-btn-outline" onClick={() => void load()}>
            Tentar novamente
          </button>
        </div>
      </Modal>
    );
  }

  const { nfe, permissoes, apresentacao } = conf;
  const resumoOperacional = nfe.resumo_atendimento_operacional as ResumoAtendimentoOperacional | undefined;
  const itens = conf.itens as ConferenciaItem[];
  const complementosEditaveis = permissoes.dados_complementares_editaveis;
  const podeAtualizarImpostos = permissoes.pode_atualizar_impostos;
  const itensTotal = itens.length;

  const handleImpostosAtualizados = async (novaConf: typeof conf) => {
    setConf(novaConf);
    setHistoricoRefreshKey((k) => k + 1);
    setValidacao(novaConf.checklist as ValidacaoNFeSaidaResponse);
    onSaved();
  };

  const aplicarRespostaProntidao = (res: {
    conferencia: typeof conf;
    validacao: ValidacaoNFeSaidaResponse;
  }) => {
    setConf(res.conferencia);
    setBaselineSnapshot(snapshotConferenciaDirty(res.conferencia));
    setValidacao(res.validacao);
    onSaved();
  };

  const persistConferencia = async (): Promise<boolean> => {
    if (!conf || !podeSalvar) return false;
    setSaveLoading(true);
    setSaveError(null);
    setAcaoLoadingMsg('Salvando alterações...');
    try {
      const payload = montarPayloadSalvarConferencia(
        conf,
        Boolean(permissoes.origem_comercial_travada),
      );
      const res = await nfeSaidasService.salvarConferencia(nfeId, payload);
      setConf(res.conferencia);
      setBaselineSnapshot(snapshotConferenciaDirty(res.conferencia));
      if (res.conferencia.checklist) {
        setValidacao(res.conferencia.checklist as ValidacaoNFeSaidaResponse);
      }
      return true;
    } catch (err) {
      setSaveError(apiErrorMessage(err));
      return false;
    } finally {
      setSaveLoading(false);
      setAcaoLoadingMsg(null);
    }
  };

  const handleValidarConferencia = async () => {
    if (alteracoesNaoSalvas) {
      toast.error('Salve as alterações antes de validar os dados persistidos.');
      return;
    }
    setValidacaoLoading(true);
    setSaveError(null);
    setAcaoLoadingMsg('Validando dados fiscais...');
    try {
      const res = await nfeSaidasService.validarConferencia(nfeId);
      aplicarRespostaProntidao(res);
      toast.success('Conferência validada com os dados salvos.');
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setValidacaoLoading(false);
      setAcaoLoadingMsg(null);
    }
  };

  const handleSaveAndValidate = async () => {
    if (!conf || !podeSalvar) return;
    setValidacaoLoading(true);
    setSaveError(null);
    setAcaoLoadingMsg('Salvando alterações...');
    try {
      const payload = montarPayloadSalvarConferencia(
        conf,
        Boolean(permissoes.origem_comercial_travada),
      );
      setAcaoLoadingMsg('Validando dados fiscais...');
      const res = await nfeSaidasService.salvarEValidarConferencia(nfeId, payload);
      aplicarRespostaProntidao(res);
      toast.success('Alterações salvas e conferência validada.');
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setValidacaoLoading(false);
      setAcaoLoadingMsg(null);
    }
  };

  const handleMarcarPronta = async () => {
    if (alteracoesNaoSalvas) {
      toast.error('Salve as alterações antes de marcar a NF-e como pronta.');
      return;
    }
    setMarcarProntaLoading(true);
    setSaveError(null);
    try {
      const res = await nfeSaidasService.marcarPronta(nfeId);
      aplicarRespostaProntidao(res);
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setMarcarProntaLoading(false);
    }
  };
  const podeSalvar = !nfeSalvarFormularioBloqueado(nfe.status) && complementosEditaveis;
  const prontidao = (conf.prontidao ?? {}) as NFeSaidaProntidaoPayload;
  const autorizadaHomolog = isAutorizadaHomologacao(
    { status: String(nfe.status) },
    conf.emissao_sefaz ?? null,
  );
  const ambienteEmissaoNfe = resolverAmbienteEmissaoNfeConferencia(conf);
  const ambienteEmissaoDefinido =
    Boolean(permissoes.ambiente_emissao_definido) || ambienteEmissaoNfeDefinido(ambienteEmissaoNfe);
  const isAmbienteProducaoNfe = isNfeAmbienteProducao(ambienteEmissaoNfe);
  const prontidaoBadge = badgeStatusConferenciaNFe(prontidao.status_conferencia);
  const orientacaoProntidao = mensagemOrientacaoProntidao(prontidao.status_conferencia, ambienteEmissaoNfe);
  const exibirMensagemPronta = deveExibirMensagemProntaEmissao(prontidao.status_conferencia, autorizadaHomolog);
  const podeValidarConferencia = Boolean(permissoes.pode_validar_conferencia ?? prontidao.pode_validar);
  const podeMarcarPronta = Boolean(permissoes.pode_marcar_pronta ?? prontidao.pode_marcar_pronta);
  const motivoMarcarProntaBloqueado = permissoes.motivo_marcar_pronta_bloqueado ?? '';
  const podeTentarEmitirHomolog =
    Boolean(permissoes.pode_tentar_emitir_homologacao) && !isAmbienteProducaoNfe;
  const podeEmitirHomolog = Boolean(permissoes.pode_emitir_homologacao);
  const motivoEmitirHomologBloqueado = permissoes.motivo_emitir_homologacao_bloqueado ?? '';
  const emissaoSefazBadge = badgeNfeSaidaEmissaoSefaz(conf.emissao_sefaz ?? null);
  const numeracaoCadastro = resolverNumeracaoCadastroConferencia(conf, ambienteEmissaoNfe);
  const transporte = conf.transporte as Record<string, unknown>;
  const modalidadeFrete = String(transporte.modalidade_frete ?? '9');
  const alertasTransp = alertasTransporteLocal({
    modalidade_frete: modalidadeFrete,
    transportadora_id: transporte.transportadora_id as number | null | undefined,
    quantidade_volumes: Number(transporte.quantidade_volumes) || 0,
    peso_bruto: Number(transporte.peso_bruto) || 0,
    peso_liquido: Number(transporte.peso_liquido) || 0,
    valor_frete: Number(transporte.valor_frete) || 0,
    placa_veiculo: String(transporte.placa_veiculo ?? ''),
    uf_veiculo: String(transporte.uf_veiculo ?? ''),
    especie_volumes: String(transporte.especie_volumes ?? ''),
    marca_volumes: String(transporte.marca_volumes ?? ''),
    numeracao_volumes: String(transporte.numeracao_volumes ?? ''),
  });

  const patchField = (section: 'observacoes' | 'transporte', key: string, value: unknown) => {
    setConf((p) => {
      if (!p) return p;
      if (section === 'observacoes') {
        return { ...p, observacoes: { ...p.observacoes, [key]: value } };
      }
      return { ...p, transporte: { ...p.transporte, [key]: value } };
    });
  };

  const limparDadosTransporte = () => {
    setSelectedTransportadora(null);
    setConf((p) => {
      if (!p) return p;
      return {
        ...p,
        transporte: {
          ...p.transporte,
          transportadora_id: null,
          valor_frete: 0,
          quantidade_volumes: 0,
          especie_volumes: '',
          marca_volumes: '',
          numeracao_volumes: '',
          peso_bruto: 0,
          peso_liquido: 0,
          placa_veiculo: '',
          uf_veiculo: '',
        },
      };
    });
  };

  const handleModalidadeFreteChange = (novoValor: string) => {
    if (novoValor === '9' && transporteTemDadosPreenchidos(transporte)) {
      setMod9ConfirmOpen(true);
      return;
    }
    patchField('transporte', 'modalidade_frete', novoValor);
  };

  const patchIndicadores = (key: 'ind_final' | 'ind_pres', value: string) => {
    setConf((p) =>
      p
        ? {
            ...p,
            indicadores_fiscais: {
              ...(p.indicadores_fiscais ?? {
                ind_final: '1',
                ind_pres: '1',
              }),
              [key]: value,
              indicadores_fiscais_confirmados: false,
            },
          }
        : p,
    );
  };

  const patchNfe = (key: string, value: unknown) => {
    setConf((p) => (p ? { ...p, nfe: { ...p.nfe, [key]: value } } : p));
  };

  const patchItemComplementar = (itemId: number, key: string, value: string) => {
    setConf((p) => {
      if (!p) return p;
      return {
        ...p,
        itens: p.itens.map((it) => (it.item_id === itemId ? { ...it, [key]: value } : it)),
      };
    });
  };

  const handleSave = async () => {
    const ok = await persistConferencia();
    if (ok) toast.success('Alterações da conferência salvas.');
  };

  const statusBadge = autorizadaHomolog
    ? { label: 'NF-e autorizada', className: 'erp-badge-success' }
    : badgeNfeSaidaStatus(nfe.status);
  const reformaBadge = badgeStatusConferencia(conf.reforma_tributaria.resumo.status);
  const resumoReforma = conf.reforma_tributaria.resumo as Record<string, number | string>;
  const fiscalAlertasGerais = (conf.fiscal_atual as { alertas_gerais?: string[] }).alertas_gerais || [];
  const descartePerm = nfePodeDescartarRascunho({
    status: String(nfe.status),
    status_emissao_sefaz: conf.emissao_sefaz?.status_emissao_sefaz,
    protocolo_autorizacao:
      conf.emissao_sefaz?.protocolo_autorizacao || apresentacao?.protocolo_autorizacao,
    cstat_autorizacao: nfe.cstat_autorizacao as string | undefined,
  });

  const descartarRascunho = async (motivo: string) => {
    setDescarteLoading(true);
    try {
      const r = await nfeSaidasService.descartarRascunho(nfeId, { motivo });
      toast.success(r.mensagem || 'NF-e rascunho descartada internamente.');
      onSaved();
      onClose();
    } catch (err) {
      toast.error(apiErrorMessage(err, { fallback: 'Não foi possível descartar o rascunho.' }));
      throw err;
    } finally {
      setDescarteLoading(false);
    }
  };

  const footer = (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-4">
      {saveError ? <p className="text-sm text-destructive sm:mr-auto">{saveError}</p> : <span className="flex-1" />}
      <div className="flex flex-wrap justify-end gap-2 shrink-0">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        {descartePerm.pode && !autorizadaHomolog ? (
          <button
            type="button"
            className="erp-btn-outline text-destructive border-destructive/40"
            disabled={descarteLoading || saveLoading}
            title="Descartar rascunho sem enviar evento à SEFAZ"
            onClick={() => setDescarteOpen(true)}
          >
            {descarteLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
            ) : (
              <Trash2 className="h-4 w-4 mr-1 inline" />
            )}
            Descartar rascunho
          </button>
        ) : null}
        {podeValidarConferencia && !autorizadaHomolog ? (
          alteracoesNaoSalvas ? (
            <button
              type="button"
              className="erp-btn-outline"
              disabled={validacaoLoading || saveLoading || !podeSalvar}
              onClick={() => void handleSaveAndValidate()}
            >
              {validacaoLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
              ) : (
                <ClipboardCheck className="h-4 w-4 mr-1 inline" />
              )}
              Salvar e validar
            </button>
          ) : (
            <button
              type="button"
              className="erp-btn-outline"
              disabled={validacaoLoading || saveLoading}
              title="Valida os dados já salvos no backend, sem gravar alterações locais."
              onClick={() => void handleValidarConferencia()}
            >
              {validacaoLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
              ) : (
                <ClipboardCheck className="h-4 w-4 mr-1 inline" />
              )}
              Validar dados
            </button>
          )
        ) : null}
        {podeValidarConferencia && !autorizadaHomolog ? (
          <button
            type="button"
            className="erp-btn-primary"
            disabled={
              !podeMarcarPronta || marcarProntaLoading || saveLoading || alteracoesNaoSalvas
            }
            title={
              alteracoesNaoSalvas
                ? 'Salve as alterações antes de marcar pronta.'
                : !podeMarcarPronta
                  ? motivoMarcarProntaBloqueado ||
                    'Resolva as pendências bloqueantes antes de marcar pronta.'
                  : undefined
            }
            onClick={() => void handleMarcarPronta()}
          >
            {marcarProntaLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
            ) : (
              <CheckCircle2 className="h-4 w-4 mr-1 inline" />
            )}
            {ACTION_LABELS.prepararEmissao}
          </button>
        ) : null}
        {podeSalvar && !autorizadaHomolog ? (
          <button
            type="button"
            className="erp-btn-outline"
            disabled={saveLoading || !alteracoesNaoSalvas}
            title={!alteracoesNaoSalvas ? 'Nenhuma alteração pendente para salvar.' : undefined}
            onClick={() => void handleSave()}
          >
            {saveLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1 inline" /> : <Save className="h-4 w-4 mr-1 inline" />}
            Salvar alterações
          </button>
        ) : null}
      </div>
    </div>
  );

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={apresentacao?.titulo_exibicao || `Conferência NF-e ${nfe.numero}`}
      size="2xl"
      footer={footer}
    >
      <div className="sticky top-0 z-10 -mx-4 px-4 py-3 mb-2 bg-card border-b border-border">
        {alteracoesNaoSalvas ? (
          <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 mb-2">
            Há alterações não salvas nesta conferência. Salve antes de validar os dados persistidos ou marcar pronta.
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2 items-center text-sm">
          {autorizadaHomolog ? (
            <>
              <span className={statusBadge.className}>{statusBadge.label}</span>
              {conf.emissao_sefaz?.nfe?.cstat ? (
                <span className="erp-badge-success opacity-90" title="Protocolo SEFAZ">
                  cStat {conf.emissao_sefaz.nfe.cstat}
                </span>
              ) : null}
              {apresentacao?.badges_secundarios?.map((b) => (
                <span key={b.label} className="text-xs text-muted-foreground font-mono">
                  {b.label}
                </span>
              ))}
            </>
          ) : (
            <>
              <span className={statusBadge.className}>{statusBadge.label}</span>
              <span className={prontidaoBadge.className} title="Prontidão da conferência">
                {prontidaoBadge.label}
              </span>
            </>
          )}
          <span className="font-medium truncate max-w-[240px]" title={nfe.cliente_nome}>
            {nfe.cliente_nome}
          </span>
          <span className="text-muted-foreground">·</span>
          <span>{labelOrigemNfe(nfe.origem)}</span>
          {!autorizadaHomolog && nfe.pedido_venda_numero ? (
            <span className="text-muted-foreground">PV {nfe.pedido_venda_numero}</span>
          ) : null}
          <span className="font-semibold ml-auto">{fmtMoeda(nfe.valor_total)}</span>
          <span className={reformaBadge.className}>Reforma: {reformaBadge.label}</span>
          <BotaoAtualizarImpostosNFe
            nfeId={nfeId}
            status={String(nfe.status)}
            podeAtualizar={podeAtualizarImpostos && !autorizadaHomolog}
            itensTotal={itensTotal}
            origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
            className="ml-1"
            onApplied={handleImpostosAtualizados}
          />
        </div>
        {(apresentacao?.linhas_subtitulo?.length ?? 0) > 0 ? (
          <div className="mt-2 space-y-0.5 text-xs text-muted-foreground">
            {apresentacao!.linhas_subtitulo!.map((linha) => (
              <p key={linha}>{linha}</p>
            ))}
          </div>
        ) : null}
        {!complementosEditaveis ? (
          <p className="text-xs text-muted-foreground mt-1">
            {autorizadaHomolog
              ? 'Campos bloqueados — NF-e autorizada em homologação.'
              : 'Campos complementares bloqueados neste status.'}
          </p>
        ) : null}
        {autorizadaHomolog ? (
          <p className="text-xs text-emerald-800 dark:text-emerald-200 mt-2 rounded-md bg-emerald-600/10 px-2 py-1.5 w-full">
            {conf.emissao_sefaz?.mensagem_status_homologacao || mensagemCabecalhoNfeAutorizadaHomolog()}
          </p>
        ) : exibirMensagemPronta ? (
          <p className="text-xs text-emerald-800 dark:text-emerald-200 mt-2 rounded-md bg-emerald-600/10 px-2 py-1.5 w-full">
            {mensagemProntaParaEmissao(ambienteEmissaoNfe)}
          </p>
        ) : orientacaoProntidao ? (
          <p className="text-xs text-muted-foreground mt-2">{orientacaoProntidao}</p>
        ) : null}
      </div>

      <Tabs defaultValue="resumo" className="w-full">
        <TabsList className="sticky top-[4.5rem] z-10 flex flex-wrap h-auto gap-1 mb-3 bg-card/95 backdrop-blur px-1 py-1">
          <TabsTrigger value="resumo">Resumo</TabsTrigger>
          <TabsTrigger value="itens">Itens</TabsTrigger>
          <TabsTrigger value="fiscal">Fiscal atual</TabsTrigger>
          <TabsTrigger value="reforma">Reforma</TabsTrigger>
          <TabsTrigger value="transporte">Transporte</TabsTrigger>
          <TabsTrigger value="obs">Observações</TabsTrigger>
          <TabsTrigger value="financeiro">Financeiro</TabsTrigger>
          <TabsTrigger value="validacao">Validação</TabsTrigger>
          <TabsTrigger value="historico">Histórico</TabsTrigger>
        </TabsList>

        <div className="max-h-[min(58vh,520px)] overflow-y-auto pr-1">
          <TabsContent value="resumo" className="space-y-3 mt-0">
            <AtendimentoOperacionalResumo resumo={resumoOperacional} />
            <AlocacaoAtendimentoGerenciarSection
              nfeSaidaId={nfeId}
              resumoInicial={resumoOperacional}
              compacto
              nfeItens={itens.map((it) => ({
                item_nf_saida_id: it.item_id,
                produto_id: Number((it as { produto_id?: number }).produto_id ?? 0),
                label: String(it.descricao ?? 'Item'),
                quantidade: String(it.quantidade ?? '1'),
              }))}
            />
            {autorizadaHomolog ? (
              <div className="rounded-md border border-emerald-600/30 bg-emerald-600/5 p-4 space-y-2 text-sm">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Identidade fiscal</p>
                <p className="text-lg font-semibold">
                  NF-e {apresentacao?.numero_fiscal || conf.emissao_sefaz?.numero_nfe}
                </p>
                <p>Série {apresentacao?.serie_fiscal || conf.emissao_sefaz?.serie_nfe}</p>
                <p>Ambiente: Homologação</p>
                {conf.emissao_sefaz?.nfe?.cstat ? <p>cStat: {conf.emissao_sefaz.nfe.cstat}</p> : null}
                {conf.emissao_sefaz?.protocolo_autorizacao || apresentacao?.protocolo_autorizacao ? (
                  <p>Protocolo: {conf.emissao_sefaz?.protocolo_autorizacao || apresentacao?.protocolo_autorizacao}</p>
                ) : null}
              </div>
            ) : null}
            {(apresentacao?.numero_faturamento || apresentacao?.numero_pedido_venda) && (
              <div className="rounded-md border border-border p-3 bg-muted/10 text-sm space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Origem operacional</p>
                {apresentacao?.numero_faturamento ? <p>Faturamento: {apresentacao.numero_faturamento}</p> : null}
                {apresentacao?.numero_pedido_venda ? (
                  <p>Pedido de venda: {apresentacao.numero_pedido_venda}</p>
                ) : null}
                {apresentacao?.numero_pedido_cliente ? (
                  <p>Pedido do cliente: {apresentacao.numero_pedido_cliente}</p>
                ) : null}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="rounded-md border border-border p-3 bg-muted/10">
                <span className="text-muted-foreground text-xs">
                  {autorizadaHomolog ? 'Referência interna / Data' : 'Número / Data'}
                </span>
                <p className="font-medium">{nfe.numero}</p>
                <p className="text-muted-foreground">{nfe.data}</p>
              </div>
              <div className="rounded-md border border-border p-3 bg-muted/10">
                <span className="text-muted-foreground text-xs">Emitente</span>
                <p>{nfe.empresa_emitente_nome || '—'}</p>
                <p className="text-xs text-muted-foreground">{nfe.natureza_operacao}</p>
              </div>
              <div className="rounded-md border border-border p-3 bg-muted/10">
                <span className="text-muted-foreground text-xs">Pedido do cliente</span>
                <input
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full h-8 text-sm')}
                  readOnly={!complementosEditaveis}
                  value={nfe.pedido_cliente_numero}
                  onChange={(e) => patchNfe('pedido_cliente_numero', e.target.value)}
                  placeholder="OC / pedido cliente"
                />
              </div>
            </div>
            {permissoes.origem_comercial_travada ? (
              <p className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                Origem comercial travada — cliente, itens e fiscal vêm do pedido/faturamento. Transporte e observações
                podem ser ajustados em rascunho.
              </p>
            ) : null}
            {!autorizadaHomolog && complementosEditaveis ? (
              <div className="rounded-md border border-border p-3 space-y-3 text-sm">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Indicadores fiscais da operação
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className="space-y-1">
                    <span className="text-xs text-muted-foreground">Consumidor final (indFinal)</span>
                    <select
                      className="erp-input w-full h-9"
                      value={String(conf.indicadores_fiscais?.ind_final ?? '1')}
                      onChange={(e) => patchIndicadores('ind_final', e.target.value)}
                    >
                      <option value="1">Sim — consumidor final</option>
                      <option value="0">Não — revenda/industrialização</option>
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="text-xs text-muted-foreground">Indicador de presença (indPres)</span>
                    <select
                      className="erp-input w-full h-9"
                      value={String(conf.indicadores_fiscais?.ind_pres ?? '1')}
                      onChange={(e) => patchIndicadores('ind_pres', e.target.value)}
                    >
                      {(conf.indicadores_fiscais?.ind_pres_opcoes ?? [
                        { valor: '1', label: 'Operação presencial' },
                        { valor: '2', label: 'Operação não presencial, internet' },
                        { valor: '9', label: 'Operação não presencial, outros' },
                      ]).map((op) => (
                        <option key={op.valor} value={op.valor}>
                          {op.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {conf.indicadores_fiscais?.indicadores_fiscais_confirmados ? (
                  <p className="text-xs text-emerald-700 dark:text-emerald-300">Indicadores confirmados e salvos.</p>
                ) : (
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    Salve as alterações para confirmar indFinal e indPres antes da emissão.
                  </p>
                )}
              </div>
            ) : null}
          </TabsContent>

          <TabsContent value="itens" className="mt-0">
            <div className="overflow-x-auto border border-border rounded-md">
              <table className="erp-table text-sm">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th>NCM</th>
                    <th>CFOP</th>
                    <th>Qtd</th>
                    <th>Total</th>
                    <th>Ped. cliente</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {itens.map((it) => (
                    <Fragment key={it.item_id}>
                      <tr
                        className="cursor-pointer hover:bg-muted/20"
                        onClick={() => setExpandedItem(expandedItem === it.item_id ? null : it.item_id)}
                      >
                        <td className="max-w-[200px] truncate">{it.descricao}</td>
                        <td>{it.ncm || '—'}</td>
                        <td>{it.cfop || '—'}</td>
                        <td>{fmtNum(it.quantidade)}</td>
                        <td>{fmtMoeda(it.valor_total)}</td>
                        <td>{it.pedido_cliente_numero || '—'}</td>
                        <td className="text-xs text-muted-foreground">{expandedItem === it.item_id ? '▲' : '▼'}</td>
                      </tr>
                      {expandedItem === it.item_id ? (
                        <tr>
                          <td colSpan={7} className="bg-muted/10 p-3">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                              <div>
                                <span className="text-muted-foreground">CST ICMS</span>
                                <p>{(it.fiscal_atual as { icms?: { cst_icms?: string } }).icms?.cst_icms || '—'}</p>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Reforma</span>
                                <p>{badgeStatusConferencia(it.status_reforma).label}</p>
                              </div>
                            </div>
                            {complementosEditaveis ? (
                              <div className="grid grid-cols-2 gap-2 mt-2">
                                <input
                                  className="erp-input h-8 text-sm"
                                  placeholder="Item pedido cliente"
                                  value={String(it.pedido_cliente_item_editavel ?? it.pedido_cliente_item ?? '')}
                                  onChange={(e) => patchItemComplementar(it.item_id, 'pedido_cliente_item_editavel', e.target.value)}
                                />
                                <input
                                  className="erp-input h-8 text-sm"
                                  placeholder="Obs. item"
                                  value={String(it.observacao_item ?? '')}
                                  onChange={(e) => patchItemComplementar(it.item_id, 'observacao_item', e.target.value)}
                                />
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          <TabsContent value="fiscal" className="space-y-3 mt-0">
            <div className="flex justify-end">
              <BotaoAtualizarImpostosNFe
                nfeId={nfeId}
                status={String(nfe.status)}
                podeAtualizar={podeAtualizarImpostos}
                itensTotal={itensTotal}
                origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
                onApplied={handleImpostosAtualizados}
              />
            </div>
            {fiscalAlertasGerais.length ? (
              <ul className="text-xs text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 list-disc pl-4">
                {fiscalAlertasGerais.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            ) : null}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(conf.fiscal_atual.totais).map(([k, v]) => (
                <div key={k} className="rounded-md border border-border p-2 text-sm">
                  <span className="text-muted-foreground block text-xs capitalize">{k.replace(/_/g, ' ')}</span>
                  <span className="font-medium tabular-nums">{v}</span>
                </div>
              ))}
            </div>
            <h4 className="text-xs font-semibold uppercase text-muted-foreground">Por item</h4>
            <div className="space-y-2">
              {(conf.fiscal_atual.por_item as Array<{
                item_id: number;
                descricao: string;
                ncm?: string;
                cfop?: string;
                alertas?: string[];
                fiscal?: { icms?: { cst_icms?: string }; pis?: { cst?: string } };
              }>).map((row) => (
                <div key={row.item_id} className="border border-border rounded-md p-2 text-sm">
                  <p className="font-medium truncate">{row.descricao}</p>
                  <p className="text-xs text-muted-foreground">
                    NCM {row.ncm || '—'} · CFOP {row.cfop || '—'} · ICMS {row.fiscal?.icms?.cst_icms || '—'} · PIS{' '}
                    {row.fiscal?.pis?.cst || '—'}
                  </p>
                  {row.alertas?.length ? (
                    <ul className="text-xs text-amber-700 dark:text-amber-300 mt-1 list-disc pl-4">
                      {row.alertas.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="reforma" className="space-y-3 mt-0">
            <div className="flex justify-end">
              <BotaoAtualizarImpostosNFe
                nfeId={nfeId}
                status={String(nfe.status)}
                podeAtualizar={podeAtualizarImpostos}
                itensTotal={itensTotal}
                origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
                onApplied={handleImpostosAtualizados}
              />
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={reformaBadge.className}>{reformaBadge.label}</span>
              <span className="rounded-md border border-border px-2 py-0.5">Com reforma: {resumoReforma.itens_com_reforma}</span>
              <span className="rounded-md border border-border px-2 py-0.5">Sem reforma: {resumoReforma.itens_sem_reforma}</span>
              <span className="rounded-md border border-border px-2 py-0.5">Sem CST: {resumoReforma.itens_sem_cst}</span>
              <span className="rounded-md border border-border px-2 py-0.5">
                Sem class.: {resumoReforma.itens_sem_classificacao}
              </span>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span>CBS: {fmtMoeda(conf.reforma_tributaria.totais.valor_cbs)}</span>
              <span>IBS estadual: {fmtMoeda(conf.reforma_tributaria.totais.valor_ibs_estadual)}</span>
              <span>Total IBS/CBS: {fmtMoeda(conf.reforma_tributaria.totais.total_ibs_cbs)}</span>
            </div>
            {conf.reforma_tributaria.itens.map((row) => {
              const diag =
                (row as { diagnostico?: string }).diagnostico ||
                diagnosticoReformaExibicao(undefined, row.status);
              return (
                <div key={row.item_id} className="border border-border rounded-md p-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium flex-1 min-w-0 truncate">{row.descricao}</p>
                    <span className={badgeStatusConferencia(row.status).className}>
                      {badgeStatusConferencia(row.status).label}
                    </span>
                  </div>
                  {diag ? <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">{diag}</p> : null}
                  {(() => {
                    const dados = row.dados as Record<string, string>;
                    const msgBase = mensagemBaseReforma(dados);
                    const badgeBase = badgeStatusBaseReforma(dados.status_base_reforma);
                    return (
                      <>
                        {msgBase ? (
                          <p className="text-xs text-sky-800 dark:text-sky-200 mt-1">{msgBase}</p>
                        ) : null}
                        {dados.status_base_reforma ? (
                          <span className={`${badgeBase.className} text-[10px] mt-1 inline-block`}>
                            {badgeBase.label}
                          </span>
                        ) : null}
                      </>
                    );
                  })()}
                  <p className="text-xs text-muted-foreground mt-0.5">
                    CST {row.dados.cst_ibs_cbs || '—'} · Class. {row.dados.classificacao_tributaria || '—'}
                  </p>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-0.5 list-none">
                    {linhasReformaItemExibicao(row.dados as Record<string, string>).map((linha) => (
                      <li key={linha}>{linha}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </TabsContent>

          <TabsContent value="transporte" className="space-y-3 mt-0">
            {alertasTransp.map((msg) => (
              <p key={msg} className="text-xs text-sky-800 dark:text-sky-200 rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-2">
                {msg}
              </p>
            ))}
            <p className="text-xs text-muted-foreground">{labelModalidadeFrete(modalidadeFrete)}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <div className="md:col-span-2 lg:col-span-3">
                <label className="erp-label">Transportadora</label>
                <TransportadoraNFeField
                  valueId={(transporte.transportadora_id as number) ?? null}
                  selected={selectedTransportadora}
                  disabled={!complementosEditaveis}
                  onSelect={(t) => {
                    setSelectedTransportadora(t);
                    patchField('transporte', 'transportadora_id', t.id);
                    if (modalidadeFrete === '9') {
                      toast.warning(
                        'Você selecionou uma transportadora. Altere a modalidade do frete para uma opção diferente de 9.',
                      );
                    }
                  }}
                  onClear={() => {
                    setSelectedTransportadora(null);
                    patchField('transporte', 'transportadora_id', null);
                  }}
                />
              </div>
              <div>
                <label className="erp-label">Modalidade do frete</label>
                <select
                  className={cn('erp-select mt-1 w-full', !complementosEditaveis && 'opacity-70')}
                  disabled={!complementosEditaveis}
                  value={modalidadeFrete}
                  onChange={(e) => handleModalidadeFreteChange(e.target.value)}
                >
                  {MODALIDADE_FRETE_OPCOES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="erp-label">Valor frete</label>
                <input
                  type="number"
                  step="0.01"
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={Number(transporte.valor_frete) || 0}
                  onChange={(e) => patchField('transporte', 'valor_frete', +e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Qtd. volumes</label>
                <input
                  type="number"
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={Number(transporte.quantidade_volumes) || 0}
                  onChange={(e) => patchField('transporte', 'quantidade_volumes', +e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Espécie volumes</label>
                <input
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={String(transporte.especie_volumes ?? '')}
                  onChange={(e) => patchField('transporte', 'especie_volumes', e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Marca volumes</label>
                <input
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={String(transporte.marca_volumes ?? '')}
                  onChange={(e) => patchField('transporte', 'marca_volumes', e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Numeração volumes</label>
                <input
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={String(transporte.numeracao_volumes ?? '')}
                  onChange={(e) => patchField('transporte', 'numeracao_volumes', e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Peso bruto (kg)</label>
                <input
                  type="number"
                  step="0.001"
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={Number(transporte.peso_bruto) || 0}
                  onChange={(e) => patchField('transporte', 'peso_bruto', +e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Peso líquido (kg)</label>
                <input
                  type="number"
                  step="0.001"
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={Number(transporte.peso_liquido) || 0}
                  onChange={(e) => patchField('transporte', 'peso_liquido', +e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">Placa</label>
                <input
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={String(transporte.placa_veiculo ?? '')}
                  onChange={(e) => patchField('transporte', 'placa_veiculo', e.target.value)}
                />
              </div>
              <div>
                <label className="erp-label">UF veículo</label>
                <input
                  maxLength={2}
                  className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full')}
                  readOnly={!complementosEditaveis}
                  value={String(transporte.uf_veiculo ?? '')}
                  onChange={(e) => patchField('transporte', 'uf_veiculo', e.target.value.toUpperCase())}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="obs" className="space-y-3 mt-0">
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
              <p className="text-xs font-medium text-foreground">
                Informações complementares do cliente (cadastro)
              </p>
              <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                {String(nfe.cliente_informacoes_complementares_nfe || '').trim() ||
                  'Nenhuma informação cadastrada no cliente para NF-e/DANFE.'}
              </p>
              {nfe.cliente_id ? (
                <a
                  href={`/clientes/${nfe.cliente_id}/edit`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  Editar no cadastro do cliente (aba NF-e / DANFE)
                </a>
              ) : null}
            </div>
            <div>
              <label className="erp-label">Informações adicionais (DANFE/XML)</label>
              <textarea
                className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full min-h-[72px]')}
                readOnly={!complementosEditaveis}
                value={conf.observacoes.informacoes_adicionais}
                onChange={(e) => patchField('observacoes', 'informacoes_adicionais', e.target.value)}
              />
            </div>
            <div>
              <label className="erp-label">Informações ao Fisco</label>
              <textarea
                className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full min-h-[72px]')}
                readOnly={!complementosEditaveis}
                value={conf.observacoes.informacoes_fisco}
                onChange={(e) => patchField('observacoes', 'informacoes_fisco', e.target.value)}
              />
            </div>
            <div>
              <label className="erp-label">Observações NF-e</label>
              <textarea
                className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full min-h-[72px]')}
                readOnly={!complementosEditaveis}
                value={conf.observacoes.observacoes_nfe}
                onChange={(e) => patchField('observacoes', 'observacoes_nfe', e.target.value)}
              />
            </div>
            <div>
              <label className="erp-label">Observações internas (somente ERP)</label>
              <textarea
                className={cn(campoEditavel(complementosEditaveis), 'mt-1 w-full min-h-[72px]')}
                readOnly={!complementosEditaveis}
                value={conf.observacoes.observacoes_internas}
                onChange={(e) => patchField('observacoes', 'observacoes_internas', e.target.value)}
              />
            </div>
          </TabsContent>

          <TabsContent value="financeiro" className="space-y-3 mt-0">
            <NFeFinanceiroPanel
              nfeId={nfeId}
              status={String(nfe.status)}
              statusEmissaoSefaz={conf.emissao_sefaz?.status_emissao_sefaz}
              resumoEmissaoSefaz={conf.emissao_sefaz ?? null}
              financeiro={conf.financeiro ?? null}
              numeroNfe={
                apresentacao?.numero_fiscal ||
                conf.emissao_sefaz?.numero_nfe ||
                conf.emissao_producao?.numero_nfe ||
                String(nfe.numero ?? '')
              }
              serieNfe={
                apresentacao?.serie_fiscal ||
                conf.emissao_sefaz?.serie_nfe ||
                conf.emissao_producao?.serie_nfe ||
                ''
              }
              clienteNome={String(nfe.cliente_nome ?? '')}
              valorTotal={nfe.valor_total as number | string | undefined}
              quantidadeParcelas={
                typeof nfe.quantidade_parcelas === 'number' ? nfe.quantidade_parcelas : null
              }
              onGerar={() => setGerarCrOpen(true)}
            />
          </TabsContent>

          <TabsContent value="validacao" className="space-y-3 mt-0">
            <div className="rounded-md border border-border p-3 space-y-2 bg-muted/20">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">Status da conferência</span>
                <span className={prontidaoBadge.className}>{prontidaoBadge.label}</span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {prontidao.total_pendencias} pendência(s) · {prontidao.total_alertas} alerta(s)
                </span>
              </div>
              {prontidao.ultima_validacao_em ? (
                <p className="text-xs text-muted-foreground">
                  Última validação: {new Date(prontidao.ultima_validacao_em).toLocaleString('pt-BR')}
                </p>
              ) : null}
              {prontidao.marcada_pronta_em ? (
                <p className="text-xs text-emerald-800 dark:text-emerald-200">
                  Marcada pronta em: {new Date(prontidao.marcada_pronta_em).toLocaleString('pt-BR')}
                </p>
              ) : null}
              {orientacaoProntidao && !exibirMensagemPronta ? (
                <p className="text-sm text-muted-foreground">{orientacaoProntidao}</p>
              ) : null}
              <div className="flex flex-wrap gap-2 pt-1">
                {podeValidarConferencia && !autorizadaHomolog ? (
                  alteracoesNaoSalvas ? (
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={validacaoLoading || saveLoading || !podeSalvar}
                      onClick={() => void handleSaveAndValidate()}
                    >
                      {validacaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline" /> : null}
                      Salvar e validar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={validacaoLoading}
                      title="Valida os dados já salvos no backend."
                      onClick={() => void handleValidarConferencia()}
                    >
                      {validacaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline" /> : null}
                      Validar dados
                    </button>
                  )
                ) : null}
                {descartePerm.pode && !autorizadaHomolog ? (
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm text-destructive border-destructive/40"
                    disabled={descarteLoading}
                    onClick={() => setDescarteOpen(true)}
                  >
                    Descartar rascunho
                  </button>
                ) : null}
              </div>
            </div>
            <NFeSaidaAcoesContextoBanner contexto={contextoAcao} />
            {!ambienteEmissaoDefinido ? (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
                {MSG_AMBIENTE_NAO_DEFINIDO}
              </div>
            ) : null}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {autorizadaHomolog || contextoAcao.autorizadaProducao
                  ? GRUPO_ACAO_LABELS.documentos
                  : GRUPO_ACAO_LABELS.fiscal}
              </p>
            <NFeSaidaAcoesOperacionais
              nfeId={nfeId}
              autorizadaHomolog={autorizadaHomolog}
              autorizadaProducao={contextoAcao.autorizadaProducao}
              statusConferencia={
                prontidao.status_conferencia ??
                conf.emissao_sefaz?.status_conferencia ??
                conf.emissao_producao?.status_conferencia
              }
              emissaoLoading={emissaoLoading}
              danfeLoading={danfeLoading}
              validarXmlLoading={validarXmlLoading}
              podeTentarEmitirHomolog={podeTentarEmitirHomolog && !autorizadaHomolog}
              podeEmitirHomolog={podeEmitirHomolog && !autorizadaHomolog && !isAmbienteProducaoNfe}
              labelEmitir={labelEmitirHomolog}
              emissaoSefaz={conf.emissao_sefaz}
              danfeMeta={danfeMeta}
              validacaoXsdErros={validacaoXsdErros}
              onEmitir={() => setEmitirHomologConfirmOpen(true)}
              onValidarXmlLocal={() => void executarValidarXmlLocal()}
              onPreviewError={setPreviewError}
              onDanfeMeta={setDanfeMeta}
              onDanfeLoading={setDanfeLoading}
              onXmlPreview={setXmlPreview}
              onXmlModalOpen={setXmlModalOpen}
            >
              {emissaoOrfaPendente ? (
                <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
                  {conf.emissao_sefaz?.mensagem_emissao_pendente ||
                    'Emissão em homologação foi iniciada, mas ainda não há retorno SEFAZ registrado. Aguarde ou tente emitir novamente.'}
                </div>
              ) : null}
              {emissaoMsg ? (
                <div className="w-full rounded-md border border-border bg-muted/20 p-3 text-xs">{emissaoMsg}</div>
              ) : null}
              {podeTentarEmitirHomolog && !podeEmitirHomolog && motivoEmitirHomologBloqueado && !isAmbienteProducaoNfe ? (
                <div className="w-full rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
                  {motivoEmitirHomologBloqueado}
                </div>
              ) : null}
              <BotaoAtualizarImpostosNFe
                nfeId={nfeId}
                status={String(nfe.status)}
                podeAtualizar={podeAtualizarImpostos}
                itensTotal={itensTotal}
                origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
                onApplied={handleImpostosAtualizados}
              />
            </NFeSaidaAcoesOperacionais>
            </div>
            {contextoAcao.exibirPainelEmissaoProducao ? (
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Emissão produção SEFAZ
              </p>
              <NFeSaidaEmissaoProducaoPanel
                nfeId={nfeId}
                emissaoProducao={conf.emissao_producao}
                permissoes={permissoes}
                statusConferencia={
                  prontidao.status_conferencia ??
                  conf.emissao_sefaz?.status_conferencia ??
                  conf.emissao_producao?.status_conferencia
                }
                marcadaProntaEm={prontidao.marcada_pronta_em}
                onEmissaoConcluida={async () => {
                  await load();
                  setHistoricoRefreshKey((k) => k + 1);
                }}
              />
            </div>
            ) : null}
            {acoesFiscaisPosAutorizacao.length ? (
              <div className="rounded-md border border-border p-3 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {GRUPO_ACAO_LABELS.fiscal}
                </p>
                <div className="flex flex-wrap gap-2">
                  {acoesFiscaisPosAutorizacao.map((acao) => (
                    <button
                      key={acao.id}
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      disabled={!acao.habilitada}
                      title={acao.title}
                      onClick={() => {
                        if (acao.id === 'consulta_sefaz') setConsultaSefazOpen(true);
                        if (acao.id === 'carta_correcao') setCartaCorrecaoOpen(true);
                        if (acao.id === 'cancelamento') setCancelamentoOpen(true);
                      }}
                    >
                      {acao.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            {acoesFuturas.length ? (
              <div className="rounded-md border border-border p-3 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {GRUPO_ACAO_LABELS.futuras}
                </p>
                <div className="flex flex-wrap gap-2">
                  {acoesFuturas.map((acao) => (
                    <button
                      key={acao.id}
                      type="button"
                      className="erp-btn-outline erp-btn-sm opacity-50 cursor-not-allowed"
                      disabled
                      title={acao.title}
                    >
                      {acao.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            {previewError ? <p className="text-sm text-destructive">{previewError}</p> : null}
            {conf?.emissao_sefaz?.status_emissao_sefaz ? (
              <div className="space-y-2">
                {rejeicao588 ? (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 space-y-1 text-xs">
                    <p className="font-semibold text-destructive text-sm">
                      Rejeição 588 — Caracteres de edição no XML
                    </p>
                    <p className="text-muted-foreground">
                      A SEFAZ recebeu o lote, mas rejeitou o XML por whitespace, quebras de linha, tabs
                      ou BOM entre tags. Use &quot;Validar XML localmente&quot; e reenvie com XML compacto.
                    </p>
                    {conf.emissao_sefaz.lote?.cstat ? (
                      <p>
                        cStat lote: {conf.emissao_sefaz.lote.cstat} —{' '}
                        {conf.emissao_sefaz.lote.xmotivo || 'Lote processado'}
                      </p>
                    ) : null}
                    {conf.emissao_sefaz.nfe?.cstat ? (
                      <p>
                        cStat NF-e: {conf.emissao_sefaz.nfe.cstat} —{' '}
                        {conf.emissao_sefaz.nfe.xmotivo || '—'}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {rejeicao266 ? (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 space-y-2 text-xs">
                    <p className="font-semibold text-destructive text-sm">
                      Rejeição 266 — Série fora da faixa SEFAZ
                    </p>
                    <p className="text-muted-foreground">
                      Série rejeitada pela SEFAZ. A série 900 está fora da faixa permitida para este Web
                      Service (0–889). Ajuste a série de homologação para 0 a 889 e gere novamente o XML.
                    </p>
                    {podeCorrigirSerie ? (
                      <p className="text-muted-foreground">
                        A NF-e será recalculada com série {serieConfigHomolog} e nova chave de acesso.
                      </p>
                    ) : null}
                    {conf.emissao_sefaz.serie_nfe ? (
                      <p>
                        Série anterior: <span className="font-mono">{conf.emissao_sefaz.serie_nfe}</span>
                        {serieConfigHomolog ? (
                          <>
                            {' '}
                            · Série nova (config):{' '}
                            <span className="font-mono">{serieConfigHomolog}</span>
                          </>
                        ) : null}
                      </p>
                    ) : null}
                    {conf.emissao_sefaz.chave_acesso ? (
                      <p className="font-mono break-all text-[11px]">
                        Chave anterior: {conf.emissao_sefaz.chave_acesso}
                      </p>
                    ) : null}
                    <div className="flex flex-wrap gap-2 pt-1">
                      {podeCorrigirSerie ? (
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={corrigirSerieLoading}
                          onClick={() => setCorrigirSerieConfirmOpen(true)}
                        >
                          {corrigirSerieLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
                          ) : null}
                          Corrigir série homologação para configuração atual
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {rejeicao225 ? (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 space-y-1 text-xs">
                    <p className="font-semibold text-destructive text-sm">
                      Rejeição 225 — Falha no Schema XML do lote de NFe
                    </p>
                    <p className="text-muted-foreground">
                      A SEFAZ recebeu o lote, mas rejeitou o XML por incompatibilidade com o schema.
                      Valide o XML localmente e corrija as tags indicadas antes de reenviar.
                    </p>
                    {conf.emissao_sefaz.lote?.cstat ? (
                      <p>
                        cStat lote: {conf.emissao_sefaz.lote.cstat} —{' '}
                        {conf.emissao_sefaz.lote.xmotivo || 'Lote processado'}
                      </p>
                    ) : null}
                    {conf.emissao_sefaz.nfe?.cstat ? (
                      <p>
                        cStat NF-e: {conf.emissao_sefaz.nfe.cstat} —{' '}
                        {conf.emissao_sefaz.nfe.xmotivo || '—'}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {rejeicao434 ? (
                  <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 space-y-1 text-xs">
                    <p className="font-semibold text-amber-800 dark:text-amber-300 text-sm">
                      Rejeição 434 — Indicativo do intermediador
                    </p>
                    <p className="text-muted-foreground">
                      A SEFAZ exige o campo indIntermed no XML (0 = sem intermediador/marketplace).
                      Gere novamente o XML e use «Tentar emitir novamente em homologação».
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}
            {numeracaoCadastro && ambienteEmissaoDefinido ? (
              <p className="text-xs text-muted-foreground">
                {labelProximaNumeracaoCadastro(ambienteEmissaoNfe)}: série {numeracaoCadastro.serie}, nº{' '}
                {numeracaoCadastro.proximo_numero}
              </p>
            ) : null}
            {emissaoMsg ? <p className="text-sm text-muted-foreground">{emissaoMsg}</p> : null}
            {conf.checklist_desatualizado && !validacao ? (
              <p className="text-sm text-muted-foreground rounded-md border border-border bg-muted/20 p-3">
                Validação não carregada na abertura. Clique em &quot;Validar dados&quot; para executar o
                checklist completo.
              </p>
            ) : null}
            {acaoLoadingMsg ? (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {acaoLoadingMsg}
              </p>
            ) : null}
            <AdvancedSupportSection title="Avançado / Suporte técnico — validação XML">
            <div className="rounded-md border border-border p-3 space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Higienização XML de transmissão
              </p>
              {conf.higienizacao_xml?.tem_xml_transmissao ? (
                <span className="erp-badge-success text-xs">XML de transmissão validado</span>
              ) : conf.higienizacao_xml?.total_pendencias ? (
                <span className="erp-badge-danger text-xs">
                  {conf.higienizacao_xml.total_pendencias} pendência(s)
                </span>
              ) : (
                <span className="erp-badge-warning text-xs">Aguardando geração do XML de transmissão</span>
              )}
              <ul className="text-xs space-y-0.5 pl-3 list-disc max-h-32 overflow-y-auto">
                {(conf.higienizacao_xml?.itens ?? []).map((item, idx) => (
                  <li key={`hig-${idx}`} className={item.tipo === 'PENDENCIA' ? 'text-destructive' : ''}>
                    {item.mensagem}
                  </li>
                ))}
              </ul>
              {!autorizadaHomolog ? (
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={xmlTransmissaoLoading || saveLoading || validacaoLoading}
                  onClick={async () => {
                    setXmlTransmissaoLoading(true);
                    setPreviewError(null);
                    try {
                      const res = await nfeSaidasService.xmlTransmissaoHomologacao(nfeId);
                      setXmlPreview({
                        xml: res.xml,
                        mensagem: res.mensagem,
                        tipo: 'transmissao_homologacao',
                      });
                      setConf((p) =>
                        p
                          ? {
                              ...p,
                              higienizacao_xml: res.higienizacao,
                            }
                          : p,
                      );
                      setXmlModalOpen(true);
                      toast.success('XML de transmissão gerado.');
                    } catch (err) {
                      setPreviewError(apiErrorMessage(err));
                      toast.error(apiErrorMessage(err));
                    } finally {
                      setXmlTransmissaoLoading(false);
                    }
                  }}
                >
                  {xmlTransmissaoLoading ? (
                    <Loader2 className="h-3 w-3 animate-spin inline" />
                  ) : null}
                  Gerar XML transmissão
                </button>
              ) : null}
            </div>
            </AdvancedSupportSection>
            <SeveridadeBloco titulo="Pendências" badgeClass="erp-badge-danger" itens={validacaoAgrupada.pendencias} />
            <SeveridadeBloco titulo="Alertas" badgeClass="erp-badge-warning" itens={validacaoAgrupada.alertas} />
            <SeveridadeBloco titulo="Informações" badgeClass="erp-badge-success" itens={validacaoAgrupada.informacoes} />
          </TabsContent>

          <TabsContent value="historico" className="mt-0">
            <NFeSaidaEfeitosPanel
              key={historicoRefreshKey}
              nfeSaidaId={nfeId}
              nfeNumero={nfe.numero}
              nfeStatus={nfe.status}
              autoLoad
              conferenciaLayout
              onNfeAtualizada={() => void load()}
            />
          </TabsContent>
        </div>
      </Tabs>

      <AlertDialog open={mod9ConfirmOpen} onOpenChange={setMod9ConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Modalidade sem ocorrência de transporte</AlertDialogTitle>
            <AlertDialogDescription>
              Modalidade 9 indica sem ocorrência de transporte. Deseja limpar transportadora, volumes,
              pesos e dados do veículo?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Manter dados e escolher outra modalidade</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                limparDadosTransporte();
                patchField('transporte', 'modalidade_frete', '9');
                setMod9ConfirmOpen(false);
              }}
            >
              Limpar dados de transporte
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={corrigirSerieConfirmOpen} onOpenChange={setCorrigirSerieConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Corrigir série de homologação</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">
                A NF-e será recalculada com série {serieConfigHomolog} e nova chave de acesso. XML, assinatura e
                lote anteriores serão invalidados. O histórico da rejeição 266 será mantido.
              </span>
              {conf?.emissao_sefaz?.serie_nfe ? (
                <span className="block text-xs font-mono">
                  Série anterior: {conf.emissao_sefaz.serie_nfe} → nova: {serieConfigHomolog}
                </span>
              ) : null}
              {conf?.emissao_sefaz?.chave_acesso ? (
                <span className="block text-xs font-mono break-all">
                  Chave anterior: {conf.emissao_sefaz.chave_acesso}
                </span>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={corrigirSerieLoading}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={corrigirSerieLoading}
              onClick={() => void executarCorrigirSerieHomologacao()}
            >
              Confirmar correção de série
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={emitirHomologConfirmOpen} onOpenChange={setEmitirHomologConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {retryEmissaoHomolog ? 'Reenviar NF-e' : 'Emitir NF-e'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {retryEmissaoHomolog && numeroHomologConfirm ? (
                <>
                  A NF-e manterá a série {serieHomologConfirm} e o número {numeroHomologConfirm} já
                  reservados. Nenhum novo número de homologação será consumido. A transmissão será
                  reenviada para a SEFAZ em ambiente de homologação, sem efeitos reais de estoque ou
                  financeiro.
                </>
              ) : (
                <>
                  Esta ação enviará a NF-e para a SEFAZ em ambiente de homologação usando a série{' '}
                  {serieHomologConfirm} e a próxima numeração configurada para homologação. Nenhuma NF-e de
                  produção será emitida. Não haverá movimentação real de estoque ou financeiro nesta fase.
                </>
              )}{' '}
              Deseja continuar?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={emissaoLoading}>Cancelar</AlertDialogCancel>
            <AlertDialogAction disabled={emissaoLoading} onClick={() => void executarEmitirHomologacao()}>
              {retryEmissaoHomolog ? 'Confirmar nova tentativa' : 'Confirmar emissão em homologação'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Modal isOpen={xmlModalOpen} onClose={() => setXmlModalOpen(false)} title="Prévia XML NF-e" size="lg">
        {xmlPreview?.xml ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">{xmlPreview.mensagem ?? 'Prévia sem transmissão SEFAZ'}</p>
            <pre className="max-h-[50vh] overflow-auto text-xs bg-muted p-2 rounded">{xmlPreview.xml}</pre>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => void navigator.clipboard.writeText(xmlPreview.xml)}
            >
              Copiar XML
            </button>
          </div>
        ) : null}
      </Modal>

      <MotivoAcaoDestrutivaModal
        open={descarteOpen}
        onOpenChange={setDescarteOpen}
        title="Descartar NF-e rascunho"
        description="A NF-e será marcada como descartada internamente. O histórico, XML preliminar e DANFE de conferência são preservados."
        avisoSefaz="Nenhum evento será enviado à SEFAZ porque a NF-e não está autorizada."
        detalhes={
          <p className="text-sm text-muted-foreground">
            NF-e: <strong>{apresentacao?.titulo_exibicao || String(nfe.numero)}</strong>
          </p>
        }
        confirmLabel="Descartar rascunho"
        loading={descarteLoading}
        onConfirm={descartarRascunho}
      />

      <GerarContasReceberNfeModal
        open={gerarCrOpen}
        nfeId={nfeId}
        onClose={() => setGerarCrOpen(false)}
        onGenerated={() => {
          toast.success('Contas a receber geradas com sucesso.');
          void load();
        }}
      />

      <NFeConsultaSefazModal
        open={consultaSefazOpen}
        nfeId={nfeId}
        onClose={() => setConsultaSefazOpen(false)}
        onConsultaConcluida={() => {
          void load();
          setHistoricoRefreshKey((k) => k + 1);
        }}
      />

      <NFeCartaCorrecaoModal
        open={cartaCorrecaoOpen}
        nfeId={nfeId}
        homologacao={contextoAcao.autorizadaHomolog}
        contextoInicial={
          conf
            ? buildCartaCorrecaoContextoFromConferencia(conf, contextoAcao.autorizadaHomolog)
            : null
        }
        onClose={() => setCartaCorrecaoOpen(false)}
        onEmitida={() => {
          void load();
          setHistoricoRefreshKey((k) => k + 1);
        }}
      />

      <NFeCancelamentoModal
        open={cancelamentoOpen}
        nfeId={nfeId}
        onClose={() => setCancelamentoOpen(false)}
        onCancelada={() => {
          void load();
          setHistoricoRefreshKey((k) => k + 1);
        }}
      />
    </Modal>
  );
}
