/**
 * Workspace do Certificado de Qualidade (CQ).
 *
 * Fase 3a-Frontend — etapa 3a: cabecalho funcional.
 * Proximas etapas vao portar (do antigo Certificados.tsx):
 *  - Etapa 3b: busca de NF-e elegivel (AsyncAutocomplete)
 *  - Etapa 3c: prontidao tecnica + origem documental + avisos
 *  - Etapa 4:  tabela de itens
 *  - Etapa 5:  editor de item (componentes, composicao, ensaios)
 *  - Etapa 6:  modal de corridas CF
 *  - Etapa 7:  rastreabilidade + PDF
 *  - Etapa 8:  ajustar Certificados.tsx para navegar em vez de modal
 */

import { useCallback, useEffect, useState } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import {
  certificadosQualidadeService,
  type NfeElegivelCqOpcao,
} from '@/services/api/qualidade';
import { apiErrorMessage } from '@/services/api/config';
import { emptyForm, LABEL_OBRIGATORIO_EMITIR } from '@/lib/certificadoQualidadeConstants';
import type {
  CertificadoQualidade,
  CertificadoQualidadeStatus,
} from '@/types';

type Props = {
  certificadoId: number | null;
  onSaved: () => void;
  onCancel: () => void;
};

type FormState = Omit<
  CertificadoQualidade,
  'id' | 'criado_em' | 'atualizado_em' | 'numero_formatado'
>;

export function CertificadoQualidadeWorkspace({ certificadoId, onSaved, onCancel }: Props) {
  const [editing, setEditing] = useState<CertificadoQualidade | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [nfeOpcaoSelecionada, setNfeOpcaoSelecionada] = useState<NfeElegivelCqOpcao | null>(null);
  const [mensagens, setMensagens] = useState<string[]>([]);
  const [carregandoNfe, setCarregandoNfe] = useState(false);

  // Carrega CQ existente (ou reseta para novo)
  useEffect(() => {
    if (!certificadoId) {
      setEditing(null);
      setForm(emptyForm());
      setSaveError(null);
      setNfeOpcaoSelecionada(null);
      setMensagens([]);
      return;
    }
    setLoading(true);
    certificadosQualidadeService
      .getById(certificadoId)
      .then((row) => {
        setEditing(row);
        setForm({
          numero: row.numero || '',
          serie: row.serie || '',
          cliente: row.cliente ?? null,
          cliente_nome_snapshot: row.cliente_nome_snapshot || '',
          cliente_cnpj_snapshot: row.cliente_cnpj_snapshot || '',
          pedido_cliente: row.pedido_cliente || '',
          nota_fiscal_numero: row.nota_fiscal_numero || '',
          nota_fiscal: row.nota_fiscal ?? null,
          nota_fiscal_historica: row.nota_fiscal_historica ?? null,
          data_emissao: row.data_emissao || '',
          observacoes: row.observacoes || '',
          texto_padrao: row.texto_padrao || '',
          status: row.status || 'rascunho',
          tipo_certificado: row.tipo_certificado || 'PADRAO_POR_NFE',
          itens: row.itens || [],
        });
        setSaveError(null);
        setNfeOpcaoSelecionada(null);
        if (row.nota_fiscal) {
          void certificadosQualidadeService.obterNfeOpcao(row.nota_fiscal).then((opt) => {
            if (opt) setNfeOpcaoSelecionada(opt);
            else {
              setNfeOpcaoSelecionada({
                id: row.nota_fiscal!,
                label_principal: row.nota_fiscal_numero
                  ? `NF-e ${row.nota_fiscal_numero}`
                  : `NF-e vinculada #${row.nota_fiscal}`,
                label_secundario: 'Documento legado — verifique elegibilidade',
                ambiente_badge: null,
                numero_nfe: '',
                serie_nfe: '',
                cliente_nome: row.cliente_nome_snapshot || '',
                data_emissao: row.data_emissao || null,
                status_emissao_sefaz: '',
                elegivel: false,
              });
            }
          });
        }
      })
      .catch((e) => setSaveError(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [certificadoId]);

  const setF = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const buscaNfesElegiveis = useCallback(
    (term: string, limit?: number) =>
      certificadosQualidadeService.buscarNfesElegiveis(term, limit ?? 20),
    [],
  );

  const selecionarNfe = useCallback(
    (id: number | string | null, option?: NfeElegivelCqOpcao | null) => {
      const nextId = id == null || id === '' ? null : Number(id);
      const trocando = nextId !== form.nota_fiscal;
      if (option && !option.elegivel && trocando) return;
      const temItens = (form.itens?.length ?? 0) > 0;
      if (trocando && temItens) {
        const ok = window.confirm(
          'Trocar a NF-e limpara os itens e dados tecnicos ja carregados desta nota. Continuar?',
        );
        if (!ok) return;
      }
      setNfeOpcaoSelecionada(option ?? null);
      setForm((p) => ({
        ...p,
        nota_fiscal: nextId,
        nota_fiscal_historica: null,
        nota_fiscal_numero:
          option && option.numero_nfe
            ? `${option.numero_nfe}${option.serie_nfe ? `/${option.serie_nfe}` : ''}`
            : nextId
              ? p.nota_fiscal_numero
              : '',
        ...(trocando
          ? {
              itens: [],
              cliente: null,
              cliente_nome_snapshot: '',
              cliente_cnpj_snapshot: '',
              pedido_cliente: '',
              data_emissao: '',
            }
          : {}),
      }));
      setMensagens([]);
    },
    [form.nota_fiscal, form.itens],
  );

  const carregarPorNFe = async () => {
    setSaveError(null);
    setMensagens([]);
    setCarregandoNfe(true);
    try {
      const data = await certificadosQualidadeService.preencherPorNfe({
        nf_saida_id: form.nota_fiscal || undefined,
        nf_saida_historica_id: form.nota_fiscal_historica || undefined,
      });
      setForm((p) => ({
        ...p,
        cliente: data.cliente ?? p.cliente,
        cliente_nome_snapshot: data.cliente_nome_snapshot ?? p.cliente_nome_snapshot,
        cliente_cnpj_snapshot: data.cliente_cnpj_snapshot ?? p.cliente_cnpj_snapshot,
        pedido_cliente: data.pedido_cliente ?? p.pedido_cliente,
        nota_fiscal_numero: data.nota_fiscal_numero ?? p.nota_fiscal_numero,
        nota_fiscal: data.nota_fiscal ?? p.nota_fiscal,
        nota_fiscal_historica: data.nota_fiscal_historica ?? p.nota_fiscal_historica,
        data_emissao: data.data_emissao ?? p.data_emissao,
      }));
      if (data.nota_fiscal) {
        void certificadosQualidadeService.obterNfeOpcao(data.nota_fiscal).then((opt) => {
          if (opt) setNfeOpcaoSelecionada(opt);
        });
      }
      const msg = [...(data.mensagens || [])];
      const nItens = Array.isArray((data as { itens?: unknown[] }).itens) ? ((data as { itens?: unknown[] }).itens as unknown[]).length : 0;
      if (nItens > 0) {
        msg.push(
          `${nItens} item(ns) retornado(s) pela NF-e. A tabela de itens sera portada na Etapa 4.`,
        );
      }
      setMensagens(msg);
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    } finally {
      setCarregandoNfe(false);
    }
  };

  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');

  const salvar = async (novoStatus?: CertificadoQualidadeStatus) => {
    setSaving(true);
    setSaveError(null);
    try {
      const payload: FormState = {
        ...form,
        status: novoStatus ?? form.status,
      };
      if (editing) {
        const updated = await certificadosQualidadeService.update(editing.id, payload);
        setEditing(updated);
        setForm((prev) => ({ ...prev, status: updated.status }));
      } else {
        const created = await certificadosQualidadeService.create(payload);
        setEditing(created);
        setForm((prev) => ({ ...prev, numero: created.numero || prev.numero }));
      }
      onSaved();
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-muted-foreground">Carregando certificado...</div>
    );
  }

  return (
    <div className="space-y-4">
      {saveError ? (
        <p className="text-sm text-destructive">{saveError}</p>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="erp-label">Número</label>
          <input
            className="erp-input mt-1 bg-muted/40 read-only:cursor-default"
            readOnly
            value={form.numero || editing?.numero_formatado || ''}
            placeholder="Número gerado automaticamente ao salvar."
          />
          {!editing ? (
            <p className="text-xs text-muted-foreground mt-1">
              Número gerado automaticamente ao salvar.
            </p>
          ) : null}
        </div>
        <div>
          <label className="erp-label">Série</label>
          <input
            className="erp-input mt-1"
            value={form.serie}
            onChange={(e) => setF('serie', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Data{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            type="date"
            className="erp-input mt-1"
            value={form.data_emissao || ''}
            onChange={(e) => setF('data_emissao', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Status</label>
          <select
            className="erp-select mt-1 w-full"
            value={form.status}
            disabled={editing?.status === 'cancelado'}
            onChange={(e) => setF('status', e.target.value as CertificadoQualidadeStatus)}
          >
            <option value="rascunho">Rascunho</option>
            <option value="emitido">Emitido</option>
            <option value="cancelado">Cancelado</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="erp-label">Cliente{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={form.cliente_nome_snapshot}
            onChange={(e) => setF('cliente_nome_snapshot', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">CNPJ Cliente</label>
          <input
            className="erp-input mt-1"
            value={form.cliente_cnpj_snapshot || ''}
            onChange={(e) => setF('cliente_cnpj_snapshot', e.target.value)}
          />
        </div>
        <div>
          <label className="erp-label">Pedido Cliente</label>
          <input
            className="erp-input mt-1"
            value={form.pedido_cliente || ''}
            onChange={(e) => setF('pedido_cliente', e.target.value)}
          />
        </div>
        <div className="md:col-span-4">
          <label className="erp-label">Observações</label>
          <textarea
            className="erp-input mt-1 min-h-[60px]"
            value={form.observacoes || ''}
            onChange={(e) => setF('observacoes', e.target.value)}
          />
        </div>
        <div className="md:col-span-4">
          <label className="erp-label">Texto padrão</label>
          <textarea
            className="erp-input mt-1 min-h-[80px]"
            value={form.texto_padrao || ''}
            onChange={(e) => setF('texto_padrao', e.target.value)}
          />
        </div>
      </div>

      <div className="rounded border border-border bg-muted/20 p-3">
        <p className="text-sm font-medium mb-2">NF-e de saída vinculada</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="erp-label">NF-e de saída</label>
            <AsyncAutocomplete<NfeElegivelCqOpcao>
              value={form.nota_fiscal}
              selectedOption={nfeOpcaoSelecionada}
              placeholder="Buscar por número da NF-e ou cliente..."
              emptyMessage="Nenhuma NF-e autorizada encontrada."
              minChars={2}
              limit={20}
              disabled={nfeBloqueada}
              search={buscaNfesElegiveis}
              getOptionValue={(o) => o.id}
              getOptionLabel={(o) => o.label_principal}
              renderOption={(o) => (
                <div className="flex flex-col gap-0.5 py-0.5">
                  <span className="font-medium text-sm">{o.label_principal}</span>
                  <span className="text-xs text-muted-foreground flex flex-wrap items-center gap-1">
                    {o.label_secundario}
                    {o.ambiente_badge ? (
                      <span
                        className={
                          o.ambiente_badge === 'Produção'
                            ? 'erp-badge-success text-[10px]'
                            : 'erp-badge-warning text-[10px]'
                        }
                      >
                        {o.ambiente_badge}
                      </span>
                    ) : null}
                  </span>
                </div>
              )}
              onChange={selecionarNfe}
            />
            {nfeOpcaoSelecionada && !nfeOpcaoSelecionada.elegivel ? (
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                {nfeOpcaoSelecionada.ambiente_badge === 'Homologação'
                  ? 'Esta NF-e vinculada foi autorizada em homologação e não pode ser usada em novo CQ de saída. O registro legado é preservado; selecione uma NF-e autorizada em produção para alterar o vínculo.'
                  : 'Esta NF-e vinculada não está elegível pelas regras atuais (ex.: rascunho, cancelada ou sem autorização fiscal em produção). O registro legado é preservado; selecione uma NF-e autorizada em produção para alterar o vínculo.'}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-1">
                Somente NF-e de saída autorizadas em produção, com número e série fiscais.
              </p>
            )}
          </div>
          <div className="flex items-end">
            <button
              type="button"
              className="erp-btn-outline w-full md:w-auto"
              onClick={() => void carregarPorNFe()}
              disabled={
                carregandoNfe ||
                nfeBloqueada ||
                (!form.nota_fiscal && !form.nota_fiscal_historica)
              }
            >
              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}
            </button>
          </div>
        </div>

        {mensagens.length > 0 ? (
          <ul className="mt-2 space-y-1">
            {mensagens.map((m, i) => (
              <li key={i} className="text-xs text-muted-foreground">
                {m}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Itens, prontidão técnica e rastreabilidade serão portados nas próximas etapas</p>
        <p>Etapa 3c: prontidão/origem · Etapa 4: tabela de itens · Etapa 5: editor · Etapa 7: rastreabilidade/PDF</p>
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="erp-btn-outline"
          onClick={onCancel}
          disabled={saving}
        >
          Voltar
        </button>
        <button
          type="button"
          className="erp-btn-outline"
          onClick={() => void salvar('emitido')}
          disabled={saving}
        >
          Salvar e emitir
        </button>
        <button
          type="button"
          className="erp-btn"
          onClick={() => void salvar()}
          disabled={saving}
        >
          {saving ? 'Salvando...' : 'Salvar'}
        </button>
      </div>
    </div>
  );
}
