import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { ClienteComercialField } from '@/components/comercial/ClienteComercialField';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { fornecedoresService } from '@/services/api/fornecedores';
import { transportadorasService } from '@/services/api/transportadoras';
import { expedicaoService } from '@/services/api/expedicao';
import { nfeSaidasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { Cliente, Fornecedor, NFeSaida, NFeSaidaListItem, Transportadora } from '@/types';
import {
  STATUS_EXPEDICAO,
  TIPOS_OPERACAO_EXPEDICAO,
  type ExpedicaoItem,
  type ExpedicaoPayload,
  type StatusExpedicao,
  type TipoOperacaoExpedicao,
} from '@/types/expedicao';
import { LABEL_STATUS_EXPEDICAO, LABEL_TIPO_OPERACAO } from '@/lib/expedicaoUi';

type Props = {
  expedicaoId: number | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
};

type FormState = {
  tipo_operacao: TipoOperacaoExpedicao;
  status: StatusExpedicao;
  motorista_nome: string;
  motorista_documento: string;
  telefone_motorista: string;
  placa_veiculo: string;
  volumes: string;
  peso_bruto: string;
  peso_liquido: string;
  data_prevista_retirada: string;
  data_prevista_entrega: string;
  data_hora_retirada_real: string;
  data_hora_entrega_real: string;
  observacoes: string;
  ocorrencia_descricao: string;
  pedido_venda: string;
  pedido_compra: string;
  faturamento: string;
  nfe_saida: string;
  alocacao_atendimento: string;
  nfe_entrada: string;
  cte_entrada: string;
};

const emptyForm = (): FormState => ({
  tipo_operacao: 'RETIRADA_FORNECEDOR',
  status: 'RASCUNHO',
  motorista_nome: '',
  motorista_documento: '',
  telefone_motorista: '',
  placa_veiculo: '',
  volumes: '',
  peso_bruto: '',
  peso_liquido: '',
  data_prevista_retirada: '',
  data_prevista_entrega: '',
  data_hora_retirada_real: '',
  data_hora_entrega_real: '',
  observacoes: '',
  ocorrencia_descricao: '',
  pedido_venda: '',
  pedido_compra: '',
  faturamento: '',
  nfe_saida: '',
  alocacao_atendimento: '',
  nfe_entrada: '',
  cte_entrada: '',
});

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return '';
  if (iso.length >= 16 && iso.includes('T')) return iso.slice(0, 16);
  return iso.slice(0, 10);
}

function formatNfeDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}

function nfeOptionLabel(nfe: NFeSaidaListItem): string {
  return nfe.listagem_resumo?.titulo || nfe.numero || `NF-e #${nfe.id}`;
}

function nfeOptionFromExpedicao(item: ExpedicaoItem): NFeSaidaListItem | null {
  if (!item.nfe_saida) return null;
  return {
    id: item.nfe_saida,
    numero: item.nfe_saida_numero || `#${item.nfe_saida}`,
    cliente_id: item.cliente ?? 0,
    cliente_nome: item.cliente_nome || '',
    data: '',
    valor_total: 0,
    status: 'AUTORIZADA_PRODUCAO',
  };
}

function parseId(v: string): number | null {
  const n = Number(v.trim());
  return Number.isFinite(n) && n > 0 ? n : null;
}

function parseDecimalField(v: string): string | null {
  const s = v.trim().replace(',', '.');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 ? s : null;
}

function parseVolumes(v: string): number {
  const s = v.trim();
  if (!s) return 0;
  const n = Number(s.replace(',', '.'));
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : 0;
}

function toApiDateTime(v: string): string | null {
  const s = v.trim();
  if (!s) return null;
  return s.length === 16 ? `${s}:00` : s;
}

function buildPayload(
  form: FormState,
  clienteId: number | null,
  fornecedorId: number | null,
  transportadoraId: number | null,
): ExpedicaoPayload {
  return {
    tipo_operacao: form.tipo_operacao,
    status: form.status,
    cliente: clienteId,
    fornecedor: fornecedorId,
    transportadora: transportadoraId,
    motorista_nome: form.motorista_nome.trim(),
    motorista_documento: form.motorista_documento.trim(),
    telefone_motorista: form.telefone_motorista.trim(),
    placa_veiculo: form.placa_veiculo.trim(),
    volumes: parseVolumes(form.volumes),
    peso_bruto: parseDecimalField(form.peso_bruto),
    peso_liquido: parseDecimalField(form.peso_liquido),
    data_prevista_retirada: form.data_prevista_retirada || null,
    data_prevista_entrega: form.data_prevista_entrega || null,
    data_hora_retirada_real: toApiDateTime(form.data_hora_retirada_real),
    data_hora_entrega_real: toApiDateTime(form.data_hora_entrega_real),
    observacoes: form.observacoes.trim(),
    ocorrencia_descricao: form.ocorrencia_descricao.trim(),
    pedido_venda: parseId(form.pedido_venda),
    pedido_compra: parseId(form.pedido_compra),
    faturamento: parseId(form.faturamento),
    nfe_saida: parseId(form.nfe_saida),
    alocacao_atendimento: parseId(form.alocacao_atendimento),
    nfe_entrada: parseId(form.nfe_entrada),
    cte_entrada: parseId(form.cte_entrada),
  };
}

function formFromItem(item: ExpedicaoItem): FormState {
  return {
    tipo_operacao: item.tipo_operacao,
    status: item.status,
    motorista_nome: item.motorista_nome || '',
    motorista_documento: item.motorista_documento || '',
    telefone_motorista: item.telefone_motorista || '',
    placa_veiculo: item.placa_veiculo || '',
    volumes: item.volumes != null ? String(item.volumes) : '',
    peso_bruto: item.peso_bruto ?? '',
    peso_liquido: item.peso_liquido ?? '',
    data_prevista_retirada: toLocalInput(item.data_prevista_retirada),
    data_prevista_entrega: toLocalInput(item.data_prevista_entrega),
    data_hora_retirada_real: toLocalInput(item.data_hora_retirada_real),
    data_hora_entrega_real: toLocalInput(item.data_hora_entrega_real),
    observacoes: item.observacoes || '',
    ocorrencia_descricao: item.ocorrencia_descricao || '',
    pedido_venda: item.pedido_venda ? String(item.pedido_venda) : '',
    pedido_compra: item.pedido_compra ? String(item.pedido_compra) : '',
    faturamento: item.faturamento ? String(item.faturamento) : '',
    nfe_saida: item.nfe_saida ? String(item.nfe_saida) : '',
    alocacao_atendimento: item.alocacao_atendimento ? String(item.alocacao_atendimento) : '',
    nfe_entrada: item.nfe_entrada ? String(item.nfe_entrada) : '',
    cte_entrada: item.cte_entrada ? String(item.cte_entrada) : '',
  };
}

export function ExpedicaoFormModal({ expedicaoId, open, onClose, onSaved }: Props) {
  const isEdit = expedicaoId != null;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [selCliente, setSelCliente] = useState<Cliente | null>(null);
  const [selFornecedor, setSelFornecedor] = useState<Fornecedor | null>(null);
  const [selTransportadora, setSelTransportadora] = useState<Transportadora | null>(null);
  const [selNfeSaida, setSelNfeSaida] = useState<NFeSaidaListItem | null>(null);
  const [nfeLoading, setNfeLoading] = useState(false);
  const [codigo, setCodigo] = useState('');

  const buscarFornecedor = useCallback(
    (term: string, limit?: number) => fornecedoresService.search(term, limit ?? 25),
    [],
  );
  const buscarTransportadora = useCallback(
    (term: string, limit?: number) => transportadorasService.search(term, limit ?? 25),
    [],
  );
  const buscarNfeSaida = useCallback(
    async (term: string, limit?: number) => {
      const response = await nfeSaidasService.listPaginated({
        search: term,
        status_emissao: 'AUTORIZADA_PRODUCAO',
        page_size: limit ?? 25,
      });
      return response.results.filter(
        (nfe) => nfe.listagem_resumo?.fiscal_resumo?.badge === 'Produção autorizada',
      );
    },
    [],
  );

  const aplicarDadosNfe = useCallback((nfe: NFeSaida) => {
    setSelNfeSaida({
      id: nfe.id,
      numero: nfe.numero,
      cliente_id: nfe.cliente_id,
      cliente_nome: nfe.cliente_nome,
      data: nfe.data,
      valor_total: nfe.valor_total,
      status: nfe.status,
      status_emissao_sefaz: nfe.status_emissao_sefaz,
      listagem_resumo: nfe.listagem_resumo,
    });
    setSelCliente(
      nfe.cliente_id
        ? ({ id: nfe.cliente_id, razao_social: nfe.cliente_nome } as Cliente)
        : null,
    );
    setSelTransportadora(
      nfe.transportadora_id
        ? ({ id: nfe.transportadora_id, razao_social: nfe.transportadora_nome || '' } as Transportadora)
        : null,
    );
    setForm((prev) => ({
      ...prev,
      nfe_saida: String(nfe.id),
      volumes: nfe.quantidade_volumes ? String(nfe.quantidade_volumes) : '',
      peso_bruto: nfe.peso_bruto ? String(nfe.peso_bruto) : '',
      peso_liquido: nfe.peso_liquido ? String(nfe.peso_liquido) : '',
    }));
  }, []);

  const selecionarNfeSaida = useCallback(async (option: NFeSaidaListItem | null) => {
    if (!option) {
      setSelNfeSaida(null);
      setForm((prev) => ({ ...prev, nfe_saida: '' }));
      return;
    }
    setNfeLoading(true);
    try {
      const detail = await nfeSaidasService.getById(option.id);
      aplicarDadosNfe(detail);
      toast.success('NF-e autorizada vinculada à expedição.');
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar os dados da NF-e.' }));
    } finally {
      setNfeLoading(false);
    }
  }, [aplicarDadosNfe]);

  const load = useCallback(async () => {
    if (!expedicaoId) return;
    setLoading(true);
    try {
      const data = await expedicaoService.getById(expedicaoId);
      setCodigo(data.codigo);
      setForm(formFromItem(data));
      setSelNfeSaida(nfeOptionFromExpedicao(data));
      setSelCliente(
        data.cliente
          ? ({ id: data.cliente, razao_social: data.cliente_nome } as Cliente)
          : null,
      );
      setSelFornecedor(
        data.fornecedor
          ? ({ id: data.fornecedor, razao_social: data.fornecedor_nome } as Fornecedor)
          : null,
      );
      setSelTransportadora(
        data.transportadora
          ? ({ id: data.transportadora, razao_social: data.transportadora_nome } as Transportadora)
          : null,
      );
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar a expedição.' }));
      onClose();
    } finally {
      setLoading(false);
    }
  }, [expedicaoId, onClose]);

  useEffect(() => {
    if (open && isEdit) void load();
    if (open && !isEdit) {
      setForm(emptyForm());
      setSelCliente(null);
      setSelFornecedor(null);
      setSelTransportadora(null);
      setSelNfeSaida(null);
      setCodigo('');
    }
    if (!open) {
      setForm(emptyForm());
      setCodigo('');
    }
  }, [open, isEdit, load]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = buildPayload(form, selCliente?.id ?? null, selFornecedor?.id ?? null, selTransportadora?.id ?? null);
      if (isEdit && expedicaoId) {
        await expedicaoService.update(expedicaoId, payload);
        toast.success('Expedição atualizada.');
      } else {
        await expedicaoService.create(payload);
        toast.success('Expedição criada.');
      }
      onSaved();
      onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível salvar a expedição.' }));
    } finally {
      setSaving(false);
    }
  };

  const readOnly = isEdit && form.status === 'CANCELADO';

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title={isEdit ? `Editar expedição ${codigo}` : 'Nova expedição'}
      size="xl"
      footer={
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 p-4">
          <button type="button" className="erp-btn-secondary" onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button type="button" className="erp-btn-primary" onClick={() => void handleSave()} disabled={saving || loading || nfeLoading || readOnly}>
            {saving ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      }
    >
      {loading ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}
      {!loading ? (
        <div className="space-y-6">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Operação</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="erp-label">Tipo de operação</label>
                <select
                  className="erp-select mt-1 w-full"
                  value={form.tipo_operacao}
                  disabled={readOnly}
                  onChange={(e) => setField('tipo_operacao', e.target.value as TipoOperacaoExpedicao)}
                >
                  {TIPOS_OPERACAO_EXPEDICAO.map((t) => (
                    <option key={t} value={t}>
                      {LABEL_TIPO_OPERACAO[t]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="erp-label">Status</label>
                <select
                  className="erp-select mt-1 w-full"
                  value={form.status}
                  disabled={readOnly}
                  onChange={(e) => setField('status', e.target.value as StatusExpedicao)}
                >
                  {STATUS_EXPEDICAO.map((s) => (
                    <option key={s} value={s}>
                      {LABEL_STATUS_EXPEDICAO[s]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Partes envolvidas</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="erp-label">Cliente</label>
                <ClienteComercialField
                  valueId={selCliente?.id ?? null}
                  selectedCliente={selCliente}
                  disabled={readOnly}
                  onSelect={setSelCliente}
                  onClear={() => setSelCliente(null)}
                />
              </div>
              <div>
                <label className="erp-label">Fornecedor</label>
                <AsyncAutocomplete<Fornecedor>
                  wrapClassName="w-full mt-1"
                  value={selFornecedor?.id ?? null}
                  selectedOption={selFornecedor}
                  placeholder="Buscar fornecedor..."
                  disabled={readOnly}
                  minChars={2}
                  search={buscarFornecedor}
                  getOptionValue={(f) => f.id}
                  getOptionLabel={(f) => f.razao_social}
                  onChange={(_v, opt) => setSelFornecedor(opt ?? null)}
                />
              </div>
              <div>
                <label className="erp-label">Transportadora</label>
                <AsyncAutocomplete<Transportadora>
                  wrapClassName="w-full mt-1"
                  value={selTransportadora?.id ?? null}
                  selectedOption={selTransportadora}
                  placeholder="Buscar transportadora..."
                  disabled={readOnly}
                  minChars={2}
                  search={buscarTransportadora}
                  getOptionValue={(t) => t.id}
                  getOptionLabel={(t) => t.razao_social}
                  onChange={(_v, opt) => setSelTransportadora(opt ?? null)}
                />
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Motorista / veículo</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="erp-label">Nome motorista</label>
                <input className="erp-input mt-1 w-full" value={form.motorista_nome} disabled={readOnly} onChange={(e) => setField('motorista_nome', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Documento</label>
                <input className="erp-input mt-1 w-full" value={form.motorista_documento} disabled={readOnly} onChange={(e) => setField('motorista_documento', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Telefone</label>
                <input className="erp-input mt-1 w-full" value={form.telefone_motorista} disabled={readOnly} onChange={(e) => setField('telefone_motorista', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Placa</label>
                <input className="erp-input mt-1 w-full" value={form.placa_veiculo} disabled={readOnly} onChange={(e) => setField('placa_veiculo', e.target.value)} />
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Volumes e pesos</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="erp-label">Volumes</label>
                <input type="number" min={0} className="erp-input mt-1 w-full" value={form.volumes} disabled={readOnly} onChange={(e) => setField('volumes', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Peso bruto (kg)</label>
                <input className="erp-input mt-1 w-full" value={form.peso_bruto} disabled={readOnly} onChange={(e) => setField('peso_bruto', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Peso líquido (kg)</label>
                <input className="erp-input mt-1 w-full" value={form.peso_liquido} disabled={readOnly} onChange={(e) => setField('peso_liquido', e.target.value)} />
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Datas</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="erp-label">Prev. retirada</label>
                <input type="date" className="erp-input mt-1 w-full" value={form.data_prevista_retirada} disabled={readOnly} onChange={(e) => setField('data_prevista_retirada', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Prev. entrega</label>
                <input type="date" className="erp-input mt-1 w-full" value={form.data_prevista_entrega} disabled={readOnly} onChange={(e) => setField('data_prevista_entrega', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Retirada real</label>
                <input type="datetime-local" className="erp-input mt-1 w-full" value={form.data_hora_retirada_real} disabled={readOnly} onChange={(e) => setField('data_hora_retirada_real', e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Entrega real</label>
                <input type="datetime-local" className="erp-input mt-1 w-full" value={form.data_hora_entrega_real} disabled={readOnly} onChange={(e) => setField('data_hora_entrega_real', e.target.value)} />
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Vínculos referenciais</h3>
            <p className="text-xs text-muted-foreground">
              NF-e de saída autorizada pode ser localizada por número, chave ou cliente. Os demais vínculos continuam opcionais.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="md:col-span-2">
                <label className="erp-label">NF-e saída autorizada</label>
                <AsyncAutocomplete<NFeSaidaListItem>
                  wrapClassName="w-full"
                  value={selNfeSaida?.id ?? null}
                  selectedOption={selNfeSaida}
                  placeholder="Buscar por número, chave ou cliente..."
                  disabled={readOnly || nfeLoading}
                  minChars={2}
                  limit={25}
                  search={buscarNfeSaida}
                  getOptionValue={(nfe) => nfe.id}
                  getOptionLabel={nfeOptionLabel}
                  renderOption={(nfe) => (
                    <div className="space-y-0.5">
                      <div className="font-medium">{nfeOptionLabel(nfe)}</div>
                      <div className="text-xs text-muted-foreground">
                        {nfe.cliente_nome || 'Cliente não informado'}
                        {nfe.data ? ` · ${formatNfeDate(nfe.data)}` : ''}
                      </div>
                    </div>
                  )}
                  onChange={(_value, option) => void selecionarNfeSaida(option ?? null)}
                />
                {nfeLoading ? <p className="mt-1 text-xs text-muted-foreground">Carregando dados da NF-e…</p> : null}
              </div>
              {(
                [
                  ['pedido_venda', 'Pedido venda'],
                  ['pedido_compra', 'Pedido compra'],
                  ['faturamento', 'Faturamento'],
                  ['alocacao_atendimento', 'Atendimento op.'],
                  ['nfe_entrada', 'NF-e entrada'],
                  ['cte_entrada', 'CT-e entrada'],
                ] as const
              ).map(([key, label]) => (
                <div key={key}>
                  <label className="erp-label">{label}</label>
                  <input
                    className="erp-input mt-1 w-full"
                    value={form[key]}
                    disabled={readOnly}
                    onChange={(e) => setField(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Observações</h3>
            <textarea
              className="erp-input mt-1 w-full min-h-[80px]"
              value={form.observacoes}
              disabled={readOnly}
              onChange={(e) => setField('observacoes', e.target.value)}
            />
            {form.status === 'OCORRENCIA' ? (
              <div>
                <label className="erp-label">Descrição da ocorrência</label>
                <textarea
                  className="erp-input mt-1 w-full min-h-[60px]"
                  value={form.ocorrencia_descricao}
                  disabled={readOnly}
                  onChange={(e) => setField('ocorrencia_descricao', e.target.value)}
                />
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </Modal>
  );
}
