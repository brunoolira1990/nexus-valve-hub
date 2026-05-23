import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ClipboardCheck, Loader2, Save } from 'lucide-react';
import { BotaoAtualizarImpostosNFe } from '@/components/fiscal/NFeSaidaAtualizarImpostosModal';
import { NFeSaidaEfeitosPanel } from '@/components/fiscal/NFeSaidaEfeitosPanel';
import { TransportadoraNFeField } from '@/components/fiscal/TransportadoraNFeField';
import { Modal } from '@/components/Modal';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { apiErrorMessage } from '@/services/api/config';
import {
  nfeSaidasService,
  type NFeSaidaConferenciaPayload,
  type NFeSaidaPreviewXmlResponse,
  type ValidacaoNFeSaidaItem,
  type ValidacaoNFeSaidaResponse,
} from '@/services/api/fiscal';
import {
  badgeNfeSaidaStatus,
  nfeSalvarFormularioBloqueado,
} from '@/lib/nfeSaidaUi';
import {
  GRUPO_VALIDACAO_LABELS,
  badgeStatusConferencia,
  fmtMoeda,
  fmtNum,
  labelOrigemNfe,
} from '@/lib/nfeSaidaConferencia';
import { montarItensComplementaresConferencia } from '@/lib/nfeSaidaConferenciaSave';
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
  const [historicoRefreshKey, setHistoricoRefreshKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await nfeSaidasService.conferencia(nfeId);
      setConf(data);
      setValidacao(data.checklist as ValidacaoNFeSaidaResponse);
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
    }
  }, [nfeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const validacaoAgrupada = useMemo(() => agruparValidacaoPorSeveridade(validacao), [validacao]);

  if (loading || !conf) {
    return (
      <Modal isOpen onClose={onClose} title="Conferência NF-e Saída" size="2xl">
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </Modal>
    );
  }

  const { nfe, permissoes } = conf;
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
    setValidacao(res.validacao);
    onSaved();
  };

  const handleValidarConferencia = async () => {
    setValidacaoLoading(true);
    setSaveError(null);
    try {
      const res = await nfeSaidasService.validarConferencia(nfeId);
      aplicarRespostaProntidao(res);
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setValidacaoLoading(false);
    }
  };

  const handleMarcarPronta = async () => {
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
  const prontidaoBadge = badgeStatusConferenciaNFe(prontidao.status_conferencia);
  const orientacaoProntidao = mensagemOrientacaoProntidao(prontidao.status_conferencia);
  const podeValidarConferencia = Boolean(permissoes.pode_validar_conferencia ?? prontidao.pode_validar);
  const podeMarcarPronta = Boolean(permissoes.pode_marcar_pronta ?? prontidao.pode_marcar_pronta);
  const transporte = conf.transporte as Record<string, unknown>;
  const modalidadeFrete = String(transporte.modalidade_frete ?? '9');
  const alertasTransp = alertasTransporteLocal({
    modalidade_frete: modalidadeFrete,
    transportadora_id: transporte.transportadora_id as number | null | undefined,
    quantidade_volumes: Number(transporte.quantidade_volumes) || 0,
    peso_bruto: Number(transporte.peso_bruto) || 0,
    peso_liquido: Number(transporte.peso_liquido) || 0,
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
    if (!podeSalvar) return;
    setSaveLoading(true);
    setSaveError(null);
    try {
      const payload: Record<string, unknown> = {
        pedido_cliente_numero: conf.nfe.pedido_cliente_numero,
        pedido_cliente_observacao: conf.nfe.pedido_cliente_observacao,
        transportadora_id: conf.transporte.transportadora_id,
        modalidade_frete: conf.transporte.modalidade_frete,
        valor_frete: conf.transporte.valor_frete,
        quantidade_volumes: conf.transporte.quantidade_volumes,
        peso_bruto: conf.transporte.peso_bruto,
        peso_liquido: conf.transporte.peso_liquido,
        especie_volumes: conf.transporte.especie_volumes,
        marca_volumes: conf.transporte.marca_volumes,
        numeracao_volumes: conf.transporte.numeracao_volumes,
        placa_veiculo: conf.transporte.placa_veiculo,
        uf_veiculo: conf.transporte.uf_veiculo,
        observacoes_nfe: conf.observacoes.observacoes_nfe,
        informacoes_adicionais: conf.observacoes.informacoes_adicionais,
        informacoes_fisco: conf.observacoes.informacoes_fisco,
        observacoes_internas: conf.observacoes.observacoes_internas,
      };
      const itensPayload = montarItensComplementaresConferencia(
        conf.itens as Parameters<typeof montarItensComplementaresConferencia>[0],
        Boolean(permissoes.origem_comercial_travada),
      );
      if (itensPayload !== undefined) {
        payload.itens = itensPayload;
      }
      await nfeSaidasService.update(nfeId, payload);
      onSaved();
      onClose();
    } catch (err) {
      setSaveError(apiErrorMessage(err));
    } finally {
      setSaveLoading(false);
    }
  };

  const statusBadge = badgeNfeSaidaStatus(nfe.status);
  const reformaBadge = badgeStatusConferencia(conf.reforma_tributaria.resumo.status);
  const resumoReforma = conf.reforma_tributaria.resumo as Record<string, number | string>;
  const fiscalAlertasGerais = (conf.fiscal_atual as { alertas_gerais?: string[] }).alertas_gerais || [];

  const footer = (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-4">
      {saveError ? <p className="text-sm text-destructive sm:mr-auto">{saveError}</p> : <span className="flex-1" />}
      <div className="flex flex-wrap justify-end gap-2 shrink-0">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        {podeValidarConferencia ? (
          <button
            type="button"
            className="erp-btn-outline"
            disabled={validacaoLoading || saveLoading}
            onClick={() => void handleValidarConferencia()}
          >
            {validacaoLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
            ) : (
              <ClipboardCheck className="h-4 w-4 mr-1 inline" />
            )}
            Validar conferência
          </button>
        ) : null}
        {podeValidarConferencia ? (
          <button
            type="button"
            className="erp-btn-primary"
            disabled={!podeMarcarPronta || marcarProntaLoading || saveLoading}
            title={
              !podeMarcarPronta
                ? 'Resolva as pendências bloqueantes antes de marcar pronta.'
                : undefined
            }
            onClick={() => void handleMarcarPronta()}
          >
            {marcarProntaLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1 inline" />
            ) : (
              <CheckCircle2 className="h-4 w-4 mr-1 inline" />
            )}
            Marcar pronta para emissão
          </button>
        ) : null}
        {podeSalvar ? (
          <button type="button" className="erp-btn-outline" disabled={saveLoading} onClick={() => void handleSave()}>
            {saveLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1 inline" /> : <Save className="h-4 w-4 mr-1 inline" />}
            Salvar conferência
          </button>
        ) : null}
      </div>
    </div>
  );

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Conferência NF-e ${nfe.numero}`}
      size="2xl"
      footer={footer}
    >
      <div className="sticky top-0 z-10 -mx-4 px-4 py-3 mb-2 bg-card border-b border-border">
        <div className="flex flex-wrap gap-2 items-center text-sm">
          <span className={statusBadge.className}>{statusBadge.label}</span>
          <span className={prontidaoBadge.className} title="Prontidão da conferência">
            {prontidaoBadge.label}
          </span>
          <span className="font-medium truncate max-w-[240px]" title={nfe.cliente_nome}>
            {nfe.cliente_nome}
          </span>
          <span className="text-muted-foreground">·</span>
          <span>{labelOrigemNfe(nfe.origem)}</span>
          {nfe.pedido_venda_numero ? <span className="text-muted-foreground">PV {nfe.pedido_venda_numero}</span> : null}
          <span className="font-semibold ml-auto">{fmtMoeda(nfe.valor_total)}</span>
          <span className={reformaBadge.className}>Reforma: {reformaBadge.label}</span>
          <BotaoAtualizarImpostosNFe
            nfeId={nfeId}
            status={String(nfe.status)}
            podeAtualizar={podeAtualizarImpostos}
            itensTotal={itensTotal}
            origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
            className="ml-1"
            onApplied={handleImpostosAtualizados}
          />
        </div>
        {!complementosEditaveis ? (
          <p className="text-xs text-muted-foreground mt-1">Campos complementares bloqueados neste status.</p>
        ) : null}
        {prontidao.status_conferencia === 'PRONTA_PARA_EMISSAO' ? (
          <p className="text-xs text-emerald-800 dark:text-emerald-200 mt-2 rounded-md bg-emerald-600/10 px-2 py-1.5 w-full">
            NF-e pronta para emissão futura. Nenhuma transmissão SEFAZ foi realizada.
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
          <TabsTrigger value="validacao">Validação</TabsTrigger>
          <TabsTrigger value="historico">Histórico</TabsTrigger>
        </TabsList>

        <div className="max-h-[min(58vh,520px)] overflow-y-auto pr-1">
          <TabsContent value="resumo" className="space-y-3 mt-0">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="rounded-md border border-border p-3 bg-muted/10">
                <span className="text-muted-foreground text-xs">Número / Data</span>
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
                  <p className="text-xs text-muted-foreground mt-0.5">
                    CST {row.dados.cst_ibs_cbs || '—'} · Class. {row.dados.classificacao_tributaria || '—'} · CBS{' '}
                    {row.dados.valor_cbs}
                  </p>
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
                  onChange={(e) => patchField('transporte', 'modalidade_frete', e.target.value)}
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
              {orientacaoProntidao ? (
                <p className="text-sm text-muted-foreground">{orientacaoProntidao}</p>
              ) : null}
              <div className="flex flex-wrap gap-2 pt-1">
                {podeValidarConferencia ? (
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm"
                    disabled={validacaoLoading}
                    onClick={() => void handleValidarConferencia()}
                  >
                    {validacaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline" /> : null}
                    Validar conferência
                  </button>
                ) : null}
                {podeValidarConferencia ? (
                  <button
                    type="button"
                    className="erp-btn-primary erp-btn-sm"
                    disabled={!podeMarcarPronta || marcarProntaLoading}
                    title={
                      !podeMarcarPronta
                        ? 'Resolva as pendências bloqueantes antes de marcar pronta.'
                        : undefined
                    }
                    onClick={() => void handleMarcarPronta()}
                  >
                    {marcarProntaLoading ? <Loader2 className="h-3 w-3 animate-spin inline" /> : null}
                    Marcar pronta para emissão
                  </button>
                ) : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <BotaoAtualizarImpostosNFe
                nfeId={nfeId}
                status={String(nfe.status)}
                podeAtualizar={podeAtualizarImpostos}
                itensTotal={itensTotal}
                origemComercialTravada={Boolean(permissoes.origem_comercial_travada)}
                onApplied={handleImpostosAtualizados}
              />
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={validacaoLoading}
                onClick={async () => {
                  setValidacaoLoading(true);
                  try {
                    setValidacao(await nfeSaidasService.validarEmissao(nfeId));
                    await load();
                  } finally {
                    setValidacaoLoading(false);
                  }
                }}
              >
                {validacaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline" /> : null}
                Atualizar validação
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                onClick={async () => {
                  setPreviewError(null);
                  try {
                    setXmlPreview(await nfeSaidasService.previewXml(nfeId));
                    setXmlModalOpen(true);
                  } catch (err) {
                    setPreviewError(apiErrorMessage(err));
                  }
                }}
              >
                Prévia XML
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                title="Layout oficial NF-e 4.00 (nfelib) — não transmitir"
                onClick={async () => {
                  setPreviewError(null);
                  try {
                    setXmlPreview(await nfeSaidasService.previewXmlOficial(nfeId));
                    setXmlModalOpen(true);
                  } catch (err) {
                    setPreviewError(apiErrorMessage(err));
                  }
                }}
              >
                XML oficial 4.00
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                onClick={async () => {
                  setPreviewError(null);
                  try {
                    const b = await nfeSaidasService.previewDanfeBlob(nfeId);
                    const u = URL.createObjectURL(b);
                    window.open(u, '_blank', 'noopener,noreferrer');
                    setTimeout(() => URL.revokeObjectURL(u), 60_000);
                  } catch (err) {
                    setPreviewError(apiErrorMessage(err));
                  }
                }}
              >
                DANFE Conferência
              </button>
            </div>
            {previewError ? <p className="text-sm text-destructive">{previewError}</p> : null}
            <p className="text-xs text-muted-foreground">
              Documento de conferência com layout DANFE modelo 55. Ainda sem autorização SEFAZ, sem chave oficial e sem valor fiscal.
            </p>
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
    </Modal>
  );
}
