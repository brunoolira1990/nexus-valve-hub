import { useEffect, useState } from 'react';
import { CatalogCodigoFiscalSelect } from '@/components/fiscal/CatalogCodigoFiscalSelect';
import { CatalogCfopSearchSelect } from '@/components/fiscal/CatalogCfopSearchSelect';
import { RecomendacoesNfeSaidaEditor } from '@/components/fiscal/RecomendacoesNfeSaidaEditor';
import { ReformaTributariaSaidaEditor } from '@/components/fiscal/ReformaTributariaSaidaEditor';
import {
  AVISO_PRESET_APLICADO,
  BOOL_TRI_OPCOES,
  CONSUMIDOR_FINAL_OPCOES,
  CAMPOS_ICMS_PRESET,
  CBENEF_SEM_CODIGO_LITERAL,
  CST_ICMS_OPCOES,
  CST_IPI_OPCOES,
  CST_PIS_COFINS_OPCOES,
  CSOSN_OPCOES,
  HINT_EDITOR_FISCAL_SAIDA,
  HINT_CFOP_SAIDA,
  MODALIDADE_BC_ICMS_OPCOES,
  MOTIVO_DESONERACAO_ICMS_OPCOES,
  PRESETS_ICMS_SAIDA,
  TIPO_CALCULO_TRIBUTO_OPCOES,
  ehMarcadorCbenefNaoFiscal,
  labelDestinatarioConfig,
  type PatchPresetIcms,
  type PresetIcmsSaida,
} from '@/lib/catalogosFiscais';
import { DESTINATARIO_OPCOES, TIPOS_OP_SAIDA } from '@/lib/regrasFiscaisSaidaHelpers';
import type { AbaFormRegraFiscalSaida, FormRegraFiscalSaida } from '@/lib/regraFiscalSaidaForm';
import type { DestinatarioContribuinteSaida, TipoOperacaoFiscalSaida } from '@/types';
import { UFS } from '@/types';

type Props = {
  abaForm: AbaFormRegraFiscalSaida;
  form: FormRegraFiscalSaida;
  setForm: React.Dispatch<React.SetStateAction<FormRegraFiscalSaida>>;
};

function icmsPresetConflita(form: FormRegraFiscalSaida, patch: PatchPresetIcms): boolean {
  return CAMPOS_ICMS_PRESET.some((k) => {
    const novo = patch[k];
    if (novo === undefined) return false;
    const atual = String(form[k] ?? '').trim();
    return atual !== '' && atual !== novo;
  });
}

function resolveModoCodigoBeneficio(val: string): '' | '__CUSTOM__' {
  const t = (val || '').trim();
  if (!t || ehMarcadorCbenefNaoFiscal(t) || t === CBENEF_SEM_CODIGO_LITERAL) return '';
  return '__CUSTOM__';
}

export const EditorRegraFiscalSaidaForm = ({ abaForm, form, setForm }: Props) => {
  const [presetAviso, setPresetAviso] = useState('');
  const [modoCodigoBeneficio, setModoCodigoBeneficio] = useState<'' | '__CUSTOM__'>(
    () => resolveModoCodigoBeneficio(form.codigo_beneficio_icms),
  );

  useEffect(() => {
    setModoCodigoBeneficio(resolveModoCodigoBeneficio(form.codigo_beneficio_icms));
  }, [form.codigo, form.codigo_beneficio_icms]);

  const f = <K extends keyof FormRegraFiscalSaida>(k: K, v: FormRegraFiscalSaida[K]) =>
    setForm((p) => ({ ...p, [k]: v }));

  const aplicarPresetIcms = (preset: PresetIcmsSaida) => {
    if (icmsPresetConflita(form, preset.patch)) {
      const ok = window.confirm(
        `Aplicar o preset "${preset.label}" e substituir os campos fiscais da aba ICMS?`,
      );
      if (!ok) return;
    }
    setForm((p) => ({ ...p, ...preset.patch }));
    setPresetAviso(AVISO_PRESET_APLICADO);
  };

  return (
    <div className="space-y-4 text-sm max-h-[60vh] overflow-y-auto pr-1">
      <ul className="text-[10px] text-muted-foreground list-disc list-inside space-y-0.5 border border-border/60 rounded px-2 py-1.5 bg-muted/20">
        {HINT_EDITOR_FISCAL_SAIDA.map((h) => (
          <li key={h}>{h}</li>
        ))}
      </ul>
      {presetAviso ? (
        <p className="text-[10px] text-amber-700 dark:text-amber-400 border border-amber-500/30 bg-amber-500/10 rounded px-2 py-1">
          {presetAviso}
        </p>
      ) : null}

      {abaForm === 'cfop' ? (
        <section>
          <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">CFOP e critérios</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
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
            <CatalogCodigoFiscalSelect
              label="Destinatário"
              value={form.destinatario_contribuinte}
              onChange={(v) => f('destinatario_contribuinte', v as DestinatarioContribuinteSaida)}
              opcoes={DESTINATARIO_OPCOES}
              allowEmpty={false}
            />
            <div>
              <label className="erp-label">Consumidor final</label>
              <select
                className="erp-select mt-1"
                value={form.consumidor_final_tri}
                onChange={(e) => f('consumidor_final_tri', e.target.value as '' | 'sim' | 'nao')}
              >
                {CONSUMIDOR_FINAL_OPCOES.map((o) => (
                  <option key={o.value || 'indif'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <CatalogCodigoFiscalSelect
              label="Tipo operação"
              value={form.tipo_operacao}
              onChange={(v) => f('tipo_operacao', v as TipoOperacaoFiscalSaida)}
              opcoes={TIPOS_OP_SAIDA.filter((o) => o.value !== '')}
              emptyLabel="— Qualquer —"
            />
            <CatalogCfopSearchSelect
              label="CFOP venda"
              value={form.cfop_venda}
              onChange={(v) => f('cfop_venda', v)}
              ufOrigem={form.uf_origem}
              ufDestino={form.uf_destino}
              hint={HINT_CFOP_SAIDA}
            />
            <CatalogCfopSearchSelect
              label="CFOP venda ST"
              value={form.cfop_venda_st}
              onChange={(v) => f('cfop_venda_st', v)}
              ufOrigem={form.uf_origem}
              ufDestino={form.uf_destino}
              hint={HINT_CFOP_SAIDA}
            />
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.ativo} onChange={(e) => f('ativo', e.target.checked)} />
                Ativo
              </label>
            </div>
            <div>
              <label className="erp-label">Prioridade</label>
              <input
                type="number"
                className="erp-input mt-1"
                value={form.prioridade}
                onChange={(e) => f('prioridade', Number(e.target.value))}
              />
            </div>
          </div>
        </section>
      ) : null}

      {abaForm === 'icms' ? (
        <section>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="text-xs text-muted-foreground">Configuração para:</span>
            <span className="erp-badge-info text-[10px]">
              {labelDestinatarioConfig(form.destinatario_contribuinte)}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-4">
            <div className="rounded border border-dashed border-border/80 p-2 text-[10px] text-muted-foreground">
              Operação de venda/revenda
              <p className="mt-1 text-[9px]">Use o destinatário na aba CFOP para perfil contribuinte ou não.</p>
            </div>
            <div className="rounded border border-dashed border-border/80 p-2 text-[10px] text-muted-foreground">
              Consumo final — contribuinte
              <p className="mt-1 text-[9px]">Destinatário = Contribuinte na aba CFOP.</p>
            </div>
            <div className="rounded border border-dashed border-border/80 p-2 text-[10px] text-muted-foreground">
              Consumo final — não contribuinte
              <p className="mt-1 text-[9px]">Destinatário = Não contribuinte na aba CFOP.</p>
            </div>
          </div>
          <div className="mb-3">
            <p className="text-[10px] text-muted-foreground mb-1.5">Presets rápidos (aba ICMS)</p>
            <div className="flex flex-wrap gap-1">
              {PRESETS_ICMS_SAIDA.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className="erp-btn-outline erp-btn-sm text-[10px]"
                  title={preset.descricao}
                  onClick={() => aplicarPresetIcms(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">ICMS</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <CatalogCodigoFiscalSelect
              label="CST ICMS"
              value={form.cst_icms}
              onChange={(v) => f('cst_icms', v)}
              opcoes={CST_ICMS_OPCOES}
            />
            <CatalogCodigoFiscalSelect
              label="CSOSN"
              value={form.csosn}
              onChange={(v) => f('csosn', v)}
              opcoes={CSOSN_OPCOES}
            />
            <CatalogCodigoFiscalSelect
              label="Modalidade BC ICMS"
              value={form.modalidade_bc_icms}
              onChange={(v) => f('modalidade_bc_icms', v)}
              opcoes={MODALIDADE_BC_ICMS_OPCOES}
            />
            <div>
              <label className="erp-label">Alíquota ICMS (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_icms} onChange={(e) => f('aliquota_icms', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Redução BC (%)</label>
              <input className="erp-input mt-1" value={form.reducao_bc_icms} onChange={(e) => f('reducao_bc_icms', e.target.value)} />
            </div>
            <CatalogCodigoFiscalSelect
              label="Motivo desoneração"
              value={form.motivo_desoneracao_icms}
              onChange={(v) => f('motivo_desoneracao_icms', v)}
              opcoes={MOTIVO_DESONERACAO_ICMS_OPCOES}
            />
            <div className="md:col-span-2">
              <label className="erp-label">Cód. benefício ICMS (cBenef)</label>
              <select
                className="erp-select mt-1"
                value={modoCodigoBeneficio}
                onChange={(e) => {
                  const v = e.target.value as '' | '__CUSTOM__';
                  setModoCodigoBeneficio(v);
                  if (v === '') f('codigo_beneficio_icms', '');
                  else if (ehMarcadorCbenefNaoFiscal(form.codigo_beneficio_icms)) {
                    f('codigo_beneficio_icms', '');
                  }
                }}
              >
                <option value="">— Não informar (omite cBenef no XML) —</option>
                <option value="__CUSTOM__">Código específico (ex.: SP020120)</option>
              </select>
              {modoCodigoBeneficio === '__CUSTOM__' ? (
                <input
                  className="erp-input mt-2"
                  value={
                    ehMarcadorCbenefNaoFiscal(form.codigo_beneficio_icms)
                      ? ''
                      : form.codigo_beneficio_icms
                  }
                  onChange={(e) => f('codigo_beneficio_icms', e.target.value)}
                  placeholder="Ex.: SP020120 (Artigo 12 / informado pelo contador)"
                />
              ) : null}
              <p className="mt-1 text-[10px] text-muted-foreground">
                Não use textos como «SEM CBENEF» — a SEFAZ rejeita (cStat 946). Sem benefício,
                deixe em branco para omitir a tag.
              </p>
            </div>
            <div>
              <label className="erp-label">ICMS ST aplicável</label>
              <select
                className="erp-select mt-1"
                value={form.icms_st_aplicavel}
                onChange={(e) => f('icms_st_aplicavel', e.target.value as '' | 'sim' | 'nao')}
              >
                {BOOL_TRI_OPCOES.map((o) => (
                  <option key={o.value || 'nc'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <CatalogCodigoFiscalSelect
              label="CST ICMS ST"
              value={form.cst_icms_st}
              onChange={(v) => f('cst_icms_st', v)}
              opcoes={CST_ICMS_OPCOES}
            />
            <div>
              <label className="erp-label">Alíquota ST (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_icms_st} onChange={(e) => f('aliquota_icms_st', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">MVA ST (%)</label>
              <input className="erp-input mt-1" value={form.mva_st} onChange={(e) => f('mva_st', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Redução BC ST (%)</label>
              <input className="erp-input mt-1" value={form.reducao_bc_st} onChange={(e) => f('reducao_bc_st', e.target.value)} />
            </div>
          </div>
          <h4 className="font-medium text-xs mt-4 mb-2 text-muted-foreground">DIFAL (venda interestadual — não contribuinte)</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <div>
              <label className="erp-label">DIFAL aplicável</label>
              <select
                className="erp-select mt-1"
                value={form.difal_aplicavel}
                onChange={(e) => f('difal_aplicavel', e.target.value as '' | 'sim' | 'nao')}
              >
                {BOOL_TRI_OPCOES.map((o) => (
                  <option key={o.value || 'nc'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="erp-label">Alíquota ICMS interestadual (%)</label>
              <input
                className="erp-input mt-1"
                value={form.aliquota_icms_interestadual}
                onChange={(e) => f('aliquota_icms_interestadual', e.target.value)}
                placeholder="Ex.: 12"
              />
            </div>
            <div>
              <label className="erp-label">Alíquota ICMS interna UF destino (%)</label>
              <input
                className="erp-input mt-1"
                value={form.aliquota_icms_interna_destino}
                onChange={(e) => f('aliquota_icms_interna_destino', e.target.value)}
                placeholder="Ex.: 20"
              />
            </div>
          </div>
          <h4 className="font-medium text-xs mt-4 mb-2 text-muted-foreground">FCP</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="erp-label">FCP aplicável</label>
              <select
                className="erp-select mt-1"
                value={form.fcp_aplicavel}
                onChange={(e) => f('fcp_aplicavel', e.target.value as '' | 'sim' | 'nao')}
              >
                {BOOL_TRI_OPCOES.map((o) => (
                  <option key={o.value || 'nc'} value={o.value}>
                    {o.label}
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
            <CatalogCodigoFiscalSelect label="CST IPI" value={form.cst_ipi} onChange={(v) => f('cst_ipi', v)} opcoes={CST_IPI_OPCOES} />
            <CatalogCodigoFiscalSelect
              label="Tipo cálculo"
              value={form.tipo_calculo_ipi}
              onChange={(v) => f('tipo_calculo_ipi', v)}
              opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
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
            <CatalogCodigoFiscalSelect label="CST PIS" value={form.cst_pis} onChange={(v) => f('cst_pis', v)} opcoes={CST_PIS_COFINS_OPCOES} />
            <CatalogCodigoFiscalSelect
              label="Tipo cálculo"
              value={form.tipo_calculo_pis}
              onChange={(v) => f('tipo_calculo_pis', v)}
              opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
            />
            <div>
              <label className="erp-label">Alíquota PIS (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_pis} onChange={(e) => f('aliquota_pis', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Redução base (%)</label>
              <input className="erp-input mt-1" value={form.reducao_base_pis} onChange={(e) => f('reducao_base_pis', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Valor mín./unidade</label>
              <input className="erp-input mt-1" value={form.valor_minimo_pis_unidade} onChange={(e) => f('valor_minimo_pis_unidade', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Alíquota PIS ST (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_pis_st} onChange={(e) => f('aliquota_pis_st', e.target.value)} />
            </div>
          </div>
          <div className="mt-3 rounded border border-border/70 bg-muted/20 p-3">
            <p className="text-xs font-medium mb-2">Base de cálculo do PIS</p>
            <label className="flex items-start gap-2 text-xs">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={form.deduzir_icms_base_pis}
                onChange={(e) => f('deduzir_icms_base_pis', e.target.checked)}
              />
              <span>
                Deduzir ICMS da base do PIS
                <span className="block text-[10px] text-muted-foreground mt-0.5">
                  Use conforme orientação fiscal/contábil. Esta opção altera a base de cálculo usada em propostas quando o
                  cenário fiscal estiver ativo.
                </span>
              </span>
            </label>
          </div>
        </section>
      ) : null}

      {abaForm === 'cofins' ? (
        <section>
          <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">COFINS</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <CatalogCodigoFiscalSelect
              label="CST COFINS"
              value={form.cst_cofins}
              onChange={(v) => f('cst_cofins', v)}
              opcoes={CST_PIS_COFINS_OPCOES}
            />
            <CatalogCodigoFiscalSelect
              label="Tipo cálculo"
              value={form.tipo_calculo_cofins}
              onChange={(v) => f('tipo_calculo_cofins', v)}
              opcoes={TIPO_CALCULO_TRIBUTO_OPCOES}
            />
            <div>
              <label className="erp-label">Alíquota COFINS (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_cofins} onChange={(e) => f('aliquota_cofins', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Redução base (%)</label>
              <input className="erp-input mt-1" value={form.reducao_base_cofins} onChange={(e) => f('reducao_base_cofins', e.target.value)} />
            </div>
            <div>
              <label className="erp-label">Valor mín./unidade</label>
              <input
                className="erp-input mt-1"
                value={form.valor_minimo_cofins_unidade}
                onChange={(e) => f('valor_minimo_cofins_unidade', e.target.value)}
              />
            </div>
            <div>
              <label className="erp-label">Alíquota COFINS ST (%)</label>
              <input className="erp-input mt-1" value={form.aliquota_cofins_st} onChange={(e) => f('aliquota_cofins_st', e.target.value)} />
            </div>
          </div>
          <div className="mt-3 rounded border border-border/70 bg-muted/20 p-3">
            <p className="text-xs font-medium mb-2">Base de cálculo da COFINS</p>
            <label className="flex items-start gap-2 text-xs">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={form.deduzir_icms_base_cofins}
                onChange={(e) => f('deduzir_icms_base_cofins', e.target.checked)}
              />
              <span>
                Deduzir ICMS da base da COFINS
                <span className="block text-[10px] text-muted-foreground mt-0.5">
                  Use conforme orientação fiscal/contábil. Esta opção altera a base de cálculo usada em propostas quando o
                  cenário fiscal estiver ativo.
                </span>
              </span>
            </label>
          </div>
        </section>
      ) : null}

      {abaForm === 'reforma' ? (
        <ReformaTributariaSaidaEditor
          reforma={form.reforma_tributaria}
          onChange={(reforma) => f('reforma_tributaria', reforma)}
        />
      ) : null}

      {abaForm === 'recomendacoes_nfe' ? (
        <RecomendacoesNfeSaidaEditor
          recomendacoes={form.recomendacoes_nfe}
          onChange={(recomendacoes_nfe) => f('recomendacoes_nfe', recomendacoes_nfe)}
        />
      ) : null}

      {abaForm === 'efeitos' ? (
        <section>
          <h3 className="font-semibold text-sm mb-2 border-b border-border pb-1">Efeitos operacionais</h3>
          <div className="flex flex-wrap gap-4 mb-3">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.movimenta_estoque} onChange={(e) => f('movimenta_estoque', e.target.checked)} />
              Movimenta estoque
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.gera_financeiro} onChange={(e) => f('gera_financeiro', e.target.checked)} />
              Gera financeiro (contas a receber)
            </label>
          </div>
          <div className="mb-3">
            <label className="erp-label">Informações complementares (NF)</label>
            <textarea
              className="erp-input mt-1 min-h-[72px] w-full"
              value={form.informacoes_complementares}
              onChange={(e) => f('informacoes_complementares', e.target.value)}
            />
          </div>
          <div>
            <label className="erp-label">Observações</label>
            <textarea className="erp-input mt-1 min-h-[72px] w-full" value={form.observacoes} onChange={(e) => f('observacoes', e.target.value)} />
          </div>
        </section>
      ) : null}
    </div>
  );
};
