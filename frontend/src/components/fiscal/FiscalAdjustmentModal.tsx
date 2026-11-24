import { useEffect, useId, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  badgeClassStatusFiscalEntrada,
  labelStatusFiscalEntrada,
} from '@/lib/conferenciaNfeLabels';
import { apiErrorMessage, getApiErrorStatus } from '@/services/api/config';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import type {
  AjusteFiscalPayload,
  CampoFiscalAjustavel,
  HistoricoAjustesFiscaisItem,
  ImpostosSnapshotFiscal,
  PreviewFiscalItem,
} from '@/types';

const CAMPOS_FORM: ReadonlyArray<{ chave: CampoFiscalAjustavel; rotulo: string }> = [
  { chave: 'ncm_efetivo', rotulo: 'NCM efetivo' },
  { chave: 'cfop_entrada_efetivo', rotulo: 'CFOP de entrada efetivo' },
  { chave: 'cst_icms_efetivo', rotulo: 'CST ICMS' },
  { chave: 'csosn_efetivo', rotulo: 'CSOSN' },
  { chave: 'cst_ipi_efetivo', rotulo: 'CST IPI' },
  { chave: 'cst_pis_efetivo', rotulo: 'CST PIS' },
  { chave: 'cst_cofins_efetivo', rotulo: 'CST COFINS' },
  { chave: 'origem_mercadoria_efetivo', rotulo: 'Origem da mercadoria' },
  { chave: 'modalidade_bc_icms_efetivo', rotulo: 'Modalidade BC ICMS' },
  { chave: 'codigo_beneficio_efetivo', rotulo: 'Código benefício ICMS' },
  { chave: 'motivo_desoneracao_efetivo', rotulo: 'Motivo desoneração ICMS' },
];

type LinhaPreview = {
  key: keyof ImpostosSnapshotFiscal;
  rotulo: string;
  /** chave usada em `diferencas.campo` (diverge do snapshot nos campos ST). */
  diffKey?: string;
};

const LINHAS_PREVIEW: ReadonlyArray<LinhaPreview> = [
  { key: 'cst_icms', rotulo: 'CST ICMS' },
  { key: 'csosn', rotulo: 'CSOSN' },
  { key: 'modalidade_bc_icms', rotulo: 'Modalidade BC ICMS' },
  { key: 'aliquota_icms', rotulo: 'Alíquota ICMS' },
  { key: 'reducao_bc_icms', rotulo: 'Redução BC ICMS' },
  { key: 'motivo_desoneracao_icms', rotulo: 'Motivo desoneração ICMS' },
  { key: 'codigo_beneficio_icms', rotulo: 'Código benefício ICMS' },
  { key: 'cst_icms_st', rotulo: 'CST ICMS ST', diffKey: 'cst_icms_st_nf' },
  { key: 'aliquota_icms_st', rotulo: 'Alíquota ICMS ST' },
  { key: 'mva_st', rotulo: 'MVA ST' },
  { key: 'reducao_bc_st', rotulo: 'Redução BC ST' },
  { key: 'aliquota_fcp', rotulo: 'Alíquota FCP' },
  { key: 'aliquota_fcp_st', rotulo: 'Alíquota FCP ST' },
  { key: 'cst_ipi', rotulo: 'CST IPI' },
  { key: 'aliquota_ipi', rotulo: 'Alíquota IPI' },
  { key: 'cst_pis', rotulo: 'CST PIS' },
  { key: 'aliquota_pis', rotulo: 'Alíquota PIS' },
  { key: 'reducao_base_pis', rotulo: 'Redução base PIS' },
  { key: 'cst_cofins', rotulo: 'CST COFINS' },
  { key: 'aliquota_cofins', rotulo: 'Alíquota COFINS' },
  { key: 'reducao_base_cofins', rotulo: 'Redução base COFINS' },
];

const ROTULOS_CAMPOS: Record<string, string> = {
  ncm_efetivo: 'NCM',
  cfop_entrada_efetivo: 'CFOP de entrada',
  cst_icms_efetivo: 'CST ICMS',
  csosn_efetivo: 'CSOSN',
  cst_ipi_efetivo: 'CST IPI',
  cst_pis_efetivo: 'CST PIS',
  cst_cofins_efetivo: 'CST COFINS',
  cst_icms_st_efetivo: 'CST ICMS ST',
  origem_mercadoria_efetivo: 'Origem da mercadoria',
  modalidade_bc_icms_efetivo: 'Modalidade BC ICMS',
  codigo_beneficio_efetivo: 'Código benefício ICMS',
  motivo_desoneracao_efetivo: 'Motivo desoneração ICMS',
  base_icms_efetivo: 'Base ICMS',
  aliquota_icms_efetivo: 'Alíquota ICMS',
  valor_icms_efetivo: 'Valor ICMS',
  reducao_bc_icms_efetivo: 'Redução BC ICMS',
  base_icms_st_efetivo: 'Base ICMS ST',
  aliquota_icms_st_efetivo: 'Alíquota ICMS ST',
  valor_icms_st_efetivo: 'Valor ICMS ST',
  mva_st_efetivo: 'MVA ST',
  reducao_bc_st_efetivo: 'Redução BC ST',
  aliquota_fcp_efetivo: 'Alíquota FCP',
  valor_fcp_efetivo: 'Valor FCP',
  aliquota_fcp_st_efetivo: 'Alíquota FCP ST',
  valor_fcp_st_efetivo: 'Valor FCP ST',
  base_ipi_efetivo: 'Base IPI',
  aliquota_ipi_efetivo: 'Alíquota IPI',
  valor_ipi_efetivo: 'Valor IPI',
  base_pis_efetivo: 'Base PIS',
  aliquota_pis_efetivo: 'Alíquota PIS',
  valor_pis_efetivo: 'Valor PIS',
  reducao_base_pis_efetivo: 'Redução base PIS',
  base_cofins_efetivo: 'Base COFINS',
  aliquota_cofins_efetivo: 'Alíquota COFINS',
  valor_cofins_efetivo: 'Valor COFINS',
  reducao_base_cofins_efetivo: 'Redução base COFINS',
};

function placeholderXml(valor: string | undefined): string {
  return valor ? `(${valor})` : '(XML/regra)';
}

// Default = valor efetivo atual; cai no XML quando o snapshot efetivo não traz a chave.
function valorEfetivoInicial(preview: PreviewFiscalItem, chave: CampoFiscalAjustavel): string {
  const ef = preview.impostos_efetivos;
  const xml = preview.impostos_xml;
  switch (chave) {
    case 'ncm_efetivo':
      return preview.ncm_efetivo || preview.ncm_xml || '';
    case 'cfop_entrada_efetivo':
      return preview.cfop_entrada_efetivo || preview.cfop_entrada_xml || '';
    case 'cst_icms_efetivo':
      return ef.cst_icms || xml.cst_icms || '';
    case 'csosn_efetivo':
      return ef.csosn || xml.csosn || '';
    case 'cst_ipi_efetivo':
      return ef.cst_ipi || xml.cst_ipi || '';
    case 'cst_pis_efetivo':
      return ef.cst_pis || xml.cst_pis || '';
    case 'cst_cofins_efetivo':
      return ef.cst_cofins || xml.cst_cofins || '';
    case 'modalidade_bc_icms_efetivo':
      return ef.modalidade_bc_icms || xml.modalidade_bc_icms || '';
    case 'codigo_beneficio_efetivo':
      return ef.codigo_beneficio_icms || xml.codigo_beneficio_icms || '';
    case 'motivo_desoneracao_efetivo':
      return ef.motivo_desoneracao_icms || xml.motivo_desoneracao_icms || '';
    // O contrato de preview não expõe origem da mercadoria: sem valor inventado.
    case 'origem_mercadoria_efetivo':
      return '';
    default:
      return '';
  }
}

function placeholderDoCampo(preview: PreviewFiscalItem, chave: CampoFiscalAjustavel): string {
  const xml = preview.impostos_xml;
  switch (chave) {
    case 'ncm_efetivo':
      return placeholderXml(preview.ncm_xml);
    case 'cfop_entrada_efetivo':
      return placeholderXml(preview.cfop_entrada_xml);
    case 'cst_icms_efetivo':
      return placeholderXml(xml.cst_icms);
    case 'csosn_efetivo':
      return placeholderXml(xml.csosn);
    case 'cst_ipi_efetivo':
      return placeholderXml(xml.cst_ipi);
    case 'cst_pis_efetivo':
      return placeholderXml(xml.cst_pis);
    case 'cst_cofins_efetivo':
      return placeholderXml(xml.cst_cofins);
    case 'modalidade_bc_icms_efetivo':
      return placeholderXml(xml.modalidade_bc_icms);
    case 'codigo_beneficio_efetivo':
      return placeholderXml(xml.codigo_beneficio_icms);
    case 'motivo_desoneracao_efetivo':
      return placeholderXml(xml.motivo_desoneracao_icms);
    case 'origem_mercadoria_efetivo':
      return '(XML/regra)';
    default:
      return '(XML/regra)';
  }
}

function codigoErroApi(error: unknown): string | null {
  const data = (error as { response?: { data?: { code?: unknown } } })?.response?.data;
  return typeof data?.code === 'string' ? data.code : null;
}

function formatarData(iso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return iso || '—';
  return data.toLocaleString('pt-BR');
}

type AjusteProps = {
  open: boolean;
  itemId: number | null;
  numeroItem: number | string;
  onOpenChange: (open: boolean) => void;
  onApplied: () => void | Promise<void>;
};

export function FiscalAdjustmentModal({
  open,
  itemId,
  numeroItem,
  onOpenChange,
  onApplied,
}: AjusteProps) {
  const campoId = useId();
  const [preview, setPreview] = useState<PreviewFiscalItem | null>(null);
  const [iniciais, setIniciais] = useState<Partial<Record<CampoFiscalAjustavel, string>> | null>(null);
  const [valores, setValores] = useState<Partial<Record<CampoFiscalAjustavel, string>>>({});
  const [motivo, setMotivo] = useState('');
  const [carregando, setCarregando] = useState(false);
  const [erroCarregamento, setErroCarregamento] = useState('');
  const [aplicando, setAplicando] = useState(false);
  const [erroGeral, setErroGeral] = useState('');
  const [erroMotivo, setErroMotivo] = useState('');
  const [bloqueio, setBloqueio] = useState('');
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    setPreview(null);
    setIniciais(null);
    setValores({});
    setMotivo('');
    setErroCarregamento('');
    setErroGeral('');
    setErroMotivo('');
    setBloqueio('');
    setReloadTick(0);
    setCarregando(false);
  }, [open, itemId]);

  // fiscal-preview é GET do estado SALVO; não recalcula proposta.
  useEffect(() => {
    if (!open || !itemId) return;
    let cancelado = false;
    setCarregando(true);
    const timer = window.setTimeout(() => {
      void nfeEntradaConferenciaService
        .previewFiscal(itemId)
        .then((data) => {
          if (cancelado) return;
          setPreview(data);
          setErroCarregamento('');
        })
        .catch((error) => {
          if (!cancelado) setErroCarregamento(apiErrorMessage(error));
        })
        .finally(() => {
          if (!cancelado) setCarregando(false);
        });
    }, 350);
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [open, itemId, reloadTick]);

  useEffect(() => {
    if (!preview || iniciais) return;
    const base = Object.fromEntries(
      CAMPOS_FORM.map(({ chave }) => [chave, valorEfetivoInicial(preview, chave)]),
    ) as Partial<Record<CampoFiscalAjustavel, string>>;
    setIniciais(base);
    setValores(base);
  }, [preview, iniciais]);

  const pendentes = useMemo(() => {
    if (!iniciais) return [];
    return CAMPOS_FORM.flatMap(({ chave, rotulo }) => {
      const de = (iniciais[chave] ?? '').trim();
      const para = (valores[chave] ?? '').trim();
      return de === para ? [] : [{ chave, rotulo, de, para }];
    });
  }, [iniciais, valores]);

  const bloqueado = Boolean(preview?.estoque_ja_aplicado || bloqueio);
  const podeAplicar =
    Boolean(preview) && !aplicando && !bloqueado && pendentes.length > 0 && Boolean(motivo.trim());

  const atualizarCampo = (chave: CampoFiscalAjustavel, valor: string) => {
    setValores((atual) => ({ ...atual, [chave]: valor }));
    setErroGeral('');
    setReloadTick((tick) => tick + 1);
  };

  const fechar = () => {
    if (aplicando) return;
    onOpenChange(false);
  };

  const aplicar = async () => {
    if (!itemId || !preview) return;
    if (pendentes.length === 0) {
      setErroGeral('Nenhuma alteração fiscal em relação ao XML/regra atual.');
      return;
    }
    if (!motivo.trim()) {
      setErroMotivo('Informe a justificativa do ajuste fiscal.');
      return;
    }
    const payload: AjusteFiscalPayload = { motivo_ajuste_fiscal: motivo.trim() };
    for (const pendente of pendentes) {
      payload[pendente.chave] = pendente.para ? pendente.para : null;
    }
    setAplicando(true);
    setErroGeral('');
    setErroMotivo('');
    setBloqueio('');
    try {
      const resultado = await nfeEntradaConferenciaService.ajustarFiscal(itemId, payload);
      toast.success(
        resultado.total_alteracoes === 1
          ? 'Ajuste fiscal aplicado.'
          : `${resultado.total_alteracoes} ajustes fiscais aplicados.`,
      );
      try {
        await onApplied();
      } catch {
        // O ajuste já foi gravado; a falha foi apenas no refetch do painel.
      }
      onOpenChange(false);
    } catch (error) {
      const codigo = codigoErroApi(error);
      if (getApiErrorStatus(error) === 409 || codigo === 'ESTOQUE_JA_APLICADO') {
        setBloqueio(
          apiErrorMessage(error, {
            fallback: 'Estoque já aplicado; ajuste fiscal bloqueado para preservar o custo da entrada.',
          }),
        );
      } else if (codigo === 'MOTIVO_OBRIGATORIO') {
        setErroMotivo(
          apiErrorMessage(error, { fallback: 'Informe a justificativa do ajuste fiscal.' }),
        );
      } else if (codigo === 'NENHUM_AJUSTE') {
        setErroGeral(
          apiErrorMessage(error, { fallback: 'Nenhuma alteração fiscal em relação ao XML/regra atual.' }),
        );
      } else {
        setErroGeral(apiErrorMessage(error));
      }
    } finally {
      setAplicando(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? onOpenChange(true) : fechar())}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Ajuste Fiscal — Item {numeroItem}</DialogTitle>
          <DialogDescription>
            Altera a classificação fiscal usada na regra de entrada. O ajuste é auditado e passa a
            prevalecer sobre o XML do fornecedor.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <p className="text-[11px] text-muted-foreground">
            A permissão <span className="font-mono">can_adjust_fiscal_classification</span> é validada
            no servidor — o contexto do frontend ainda não expõe essa flag. O preview abaixo reflete o
            estado salvo; o recálculo efetivo acontece ao aplicar.
          </p>

          {bloqueado ? (
            <p role="alert" className="rounded-md border border-warning bg-surface-muted px-3 py-2">
              {bloqueio ||
                'Estoque já aplicado; ajuste fiscal bloqueado para preservar o custo da entrada.'}
            </p>
          ) : null}

          {carregando && !preview ? (
            <p className="text-muted-foreground">Carregando preview fiscal…</p>
          ) : null}

          {erroCarregamento && !preview ? (
            <p role="alert" className="text-sm text-destructive">
              {erroCarregamento}
            </p>
          ) : null}

          {preview ? (
            <>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span
                  className={`${badgeClassStatusFiscalEntrada(preview.status_fiscal || 'SEM_REGRA')} text-[10px]`}
                >
                  Fiscal: {labelStatusFiscalEntrada(preview.status_fiscal || 'SEM_REGRA')}
                </span>
                <span className="text-muted-foreground">
                  Regra: {preview.regra.nome || '—'}
                  {preview.regra.codigo ? ` (${preview.regra.codigo})` : ''}
                </span>
              </div>

              <div className="overflow-x-auto rounded-md border border-border">
                <table className="w-full text-xs">
                  <thead className="bg-surface-muted">
                    <tr>
                      <th className="px-2 py-1 text-left font-medium">Tributo</th>
                      <th className="px-2 py-1 text-left font-medium">XML</th>
                      <th className="px-2 py-1 text-left font-medium">Efetivo</th>
                      <th className="px-2 py-1 text-left font-medium">Esperado (regra)</th>
                      <th className="px-2 py-1 text-left font-medium">Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {LINHAS_PREVIEW.map((linha) => {
                      const valorXml = preview.impostos_xml[linha.key] ?? '';
                      const valorEfetivo = preview.impostos_efetivos[linha.key] ?? '';
                      const valorEsperado = preview.impostos_esperados[linha.key] ?? '';
                      const diferenca = preview.diferencas.find(
                        (d) => d.campo === (linha.diffKey ?? linha.key),
                      );
                      const divergente = preview.divergencias.some(
                        (d) => d.campo === linha.key,
                      );
                      if (!valorXml && !valorEfetivo && !valorEsperado && !diferenca && !divergente) {
                        return null;
                      }
                      return (
                        <tr key={linha.key} className="border-t border-border">
                          <td className="px-2 py-1">
                            <span className="flex flex-wrap items-center gap-1">
                              {linha.rotulo}
                              {divergente ? (
                                <span className="erp-badge-warning text-[9px]">Divergente</span>
                              ) : null}
                            </span>
                          </td>
                          <td className="px-2 py-1 font-mono">{valorXml || '—'}</td>
                          <td className="px-2 py-1 font-mono">{valorEfetivo || '—'}</td>
                          <td className="px-2 py-1 font-mono">{valorEsperado || '—'}</td>
                          <td className="px-2 py-1 font-mono">
                            {diferenca ? diferenca.diferenca || '≠' : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {CAMPOS_FORM.map(({ chave, rotulo }) => (
                  <div key={chave} className="space-y-1">
                    <label
                      htmlFor={`${campoId}-${chave}`}
                      className="text-xs text-muted-foreground"
                    >
                      {rotulo}
                    </label>
                    <input
                      id={`${campoId}-${chave}`}
                      className="erp-input w-full font-mono text-xs"
                      value={valores[chave] ?? ''}
                      placeholder={placeholderDoCampo(preview, chave)}
                      disabled={aplicando || bloqueado}
                      onChange={(event) => atualizarCampo(chave, event.target.value)}
                    />
                  </div>
                ))}
              </div>

              {pendentes.length > 0 ? (
                <div className="rounded-md border border-border bg-surface-muted p-3 text-xs">
                  <p className="font-medium">Alterações não salvas ({pendentes.length})</p>
                  <ul className="mt-1 space-y-0.5">
                    {pendentes.map((pendente) => (
                      <li key={pendente.chave} className="flex flex-wrap justify-between gap-2">
                        <span className="text-muted-foreground">{pendente.rotulo}</span>
                        <span className="font-mono text-right">
                          {pendente.de || 'XML/regra'} → {pendente.para || 'XML/regra'}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-muted-foreground">
                    A tabela acima mostra o estado salvo. Essas alterações só afetam a regra após
                    aplicar no servidor.
                  </p>
                </div>
              ) : null}
            </>
          ) : null}

          <div className="space-y-1">
            <label htmlFor={`${campoId}-motivo`} className="text-xs text-muted-foreground">
              Motivo do ajuste
            </label>
            <textarea
              id={`${campoId}-motivo`}
              className="erp-input w-full min-h-[76px]"
              value={motivo}
              placeholder="Descreva por que a classificação fiscal do XML será alterada"
              disabled={aplicando || bloqueado}
              onChange={(event) => {
                setMotivo(event.target.value);
                setErroMotivo('');
              }}
            />
            {erroMotivo ? (
              <p role="alert" className="text-xs text-destructive">
                {erroMotivo}
              </p>
            ) : null}
          </div>

          {erroGeral ? (
            <p role="alert" className="text-sm text-destructive">
              {erroGeral}
            </p>
          ) : null}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <button type="button" className="erp-btn-outline" disabled={aplicando} onClick={fechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary"
            disabled={!podeAplicar}
            onClick={() => void aplicar()}
          >
            {aplicando ? 'Aplicando…' : 'Aplicar Ajuste'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type HistoricoProps = {
  open: boolean;
  itemId: number | null;
  numeroItem: number | string;
  onOpenChange: (open: boolean) => void;
};

export function FiscalHistoricoModal({ open, itemId, numeroItem, onOpenChange }: HistoricoProps) {
  const [dados, setDados] = useState<HistoricoAjustesFiscaisItem | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    if (!open || !itemId) {
      setDados(null);
      setErro('');
      return;
    }
    let cancelado = false;
    setCarregando(true);
    setErro('');
    void nfeEntradaConferenciaService
      .historicoFiscal(itemId)
      .then((data) => {
        if (!cancelado) setDados(data);
      })
      .catch((error) => {
        if (!cancelado) setErro(apiErrorMessage(error));
      })
      .finally(() => {
        if (!cancelado) setCarregando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [open, itemId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Histórico de ajustes fiscais — Item {numeroItem}</DialogTitle>
          <DialogDescription>
            Trilha de auditoria das alterações manuais de classificação fiscal deste item.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          {carregando ? <p className="text-muted-foreground">Carregando histórico…</p> : null}

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}

          {!carregando && !erro && dados && dados.total === 0 ? (
            <p className="text-muted-foreground">Nenhum ajuste fiscal registrado para este item.</p>
          ) : null}

          {dados && dados.total > 0 ? (
            <ul className="space-y-2">
              {dados.ajustes.map((ajuste) => (
                <li key={ajuste.id} className="rounded-md border border-border p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">
                      {ROTULOS_CAMPOS[ajuste.campo] || ajuste.campo}
                    </span>
                    <span className="text-muted-foreground">
                      {formatarData(ajuste.criado_em)}
                    </span>
                  </div>
                  <p className="mt-1 font-mono">
                    {ajuste.valor_anterior || '—'} → {ajuste.valor_novo || '—'}
                  </p>
                  <p className="mt-1 text-muted-foreground">Motivo: {ajuste.motivo || '—'}</p>
                  <p className="text-muted-foreground">Usuário: {ajuste.usuario_nome || '—'}</p>
                </li>
              ))}
            </ul>
          ) : null}

          {dados?.motivo_ajuste_fiscal ? (
            <p className="text-xs text-muted-foreground">
              Última justificativa registrada: {dados.motivo_ajuste_fiscal}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <button type="button" className="erp-btn-outline" onClick={() => onOpenChange(false)}>
            Fechar
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
