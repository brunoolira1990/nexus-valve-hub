import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { colaboradoresService } from '@/services/api/colaboradores';
import { apiErrorMessage } from '@/services/api/config';
import { consultaCep } from '@/services/api/consulta';
import { toast } from 'sonner';
import type { Colaborador, Dependente } from '@/types';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { ColaboradorAcessoSection } from '@/components/cadastros/ColaboradorAcessoSection';
import { User, Briefcase, Key, MapPin, Phone, FileText, Users, Pencil, Trash2 } from 'lucide-react';
import { InlinePanel } from '@/components/workspace/InlinePanel';
import type { EventoVinculo, Vinculo } from '@/types';

import { WorkspaceLayout } from '@/components/workspace/WorkspaceLayout';
import { WorkspaceSection } from '@/components/workspace/WorkspaceSection';
import { WorkspaceField } from '@/components/workspace/WorkspaceField';

type ColaboradorForm = {
  nome: string;
  codigo: string;
  email: string;
  telefone: string;
  cargo: string;
  departamento: string;
  ativo: boolean;
  observacoes: string;
  nome_social: string;
  tipo_pessoa: string;
  cpf: string;
  cnpj: string;
  identidade_tipo: string;
  identidade_numero: string;
  identidade_orgao: string;
  identidade_uf: string;
  identidade_emissao: string;
  identidade_validade: string;
  data_nascimento: string;
  sexo: string;
  estado_civil: string;
  nacionalidade: string;
  naturalidade_cidade: string;
  naturalidade_uf: string;
  nome_mae: string;
  nome_pai: string;
  celular: string;
  email_pessoal: string;
  emergencia_nome: string;
  emergencia_telefone: string;
  emergencia_parentesco: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  ctps_numero: string;
  ctps_serie: string;
  ctps_uf: string;
  ctps_emissao: string;
  pis_pasep: string;
  titulo_numero: string;
  titulo_zona: string;
  titulo_secao: string;
  titulo_uf: string;
  cnh_numero: string;
  cnh_categoria: string;
  cnh_validade: string;
  reservista_numero: string;
  eh_vendedor: boolean;
  eh_comprador: boolean;
  eh_responsavel_fiscal: boolean;
  eh_responsavel_financeiro: boolean;
  eh_responsavel_estoque: boolean;
  eh_responsavel_qualidade: boolean;
  eh_administrador: boolean;
};

const FUNCAO_CAMPOS: { key: keyof ColaboradorForm; label: string }[] = [
  { key: 'eh_vendedor', label: 'Vendedor' },
  { key: 'eh_comprador', label: 'Comprador' },
  { key: 'eh_responsavel_fiscal', label: 'Fiscal' },
  { key: 'eh_responsavel_financeiro', label: 'Financeiro' },
  { key: 'eh_responsavel_estoque', label: 'Estoque' },
  { key: 'eh_responsavel_qualidade', label: 'Qualidade' },
  { key: 'eh_administrador', label: 'Admin' },
];

type ColaboradorWorkspaceProps = {
  colaborador: Colaborador | null;
  onClose: () => void;
};

const formularioInicial: ColaboradorForm = {
  nome: '',
  codigo: '',
  email: '',
  telefone: '',
  cargo: '',
  departamento: '',
  ativo: true,
  observacoes: '',
  nome_social: '',
  tipo_pessoa: 'FISICA',
  cpf: '',
  cnpj: '',
  identidade_tipo: '',
  identidade_numero: '',
  identidade_orgao: '',
  identidade_uf: '',
  identidade_emissao: '',
  identidade_validade: '',
  data_nascimento: '',
  sexo: '',
  estado_civil: '',
  nacionalidade: '',
  naturalidade_cidade: '',
  naturalidade_uf: '',
  nome_mae: '',
  nome_pai: '',
  celular: '',
  email_pessoal: '',
  emergencia_nome: '',
  emergencia_telefone: '',
  emergencia_parentesco: '',
  cep: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: '',
  cidade: '',
  uf: '',
  ctps_numero: '',
  ctps_serie: '',
  ctps_uf: '',
  ctps_emissao: '',
  pis_pasep: '',
  titulo_numero: '',
  titulo_zona: '',
  titulo_secao: '',
  titulo_uf: '',
  cnh_numero: '',
  cnh_categoria: '',
  cnh_validade: '',
  reservista_numero: '',
  eh_vendedor: false,
  eh_comprador: false,
  eh_responsavel_fiscal: false,
  eh_responsavel_financeiro: false,
  eh_responsavel_estoque: false,
  eh_responsavel_qualidade: false,
  eh_administrador: false,
};

type VinculoPainel =
  | { tipo: 'novo' }
  | { tipo: 'editar'; vinculo: Vinculo }
  | { tipo: 'evento'; vinculo: Vinculo }
  | null;

const formatarData = (value?: string | null) => (value ? value.split('-').reverse().join('/') : '—');

const formatarSalario = (value?: string | number | null) => {
  if (value === null || value === undefined || value === '') return null;
  return Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

function VinculosTab({ colaboradorId }: { colaboradorId: number | null }) {
  const [vinculos, setVinculos] = useState<Vinculo[]>([]);
  const [vinculosLoading, setVinculosLoading] = useState(false);
  const [painelVinculo, setPainelVinculo] = useState<VinculoPainel>(null);

  const carregarVinculos = useCallback(async () => {
    if (!colaboradorId) return;
    setVinculosLoading(true);
    try {
      const dados = await colaboradoresService.listVinculos(colaboradorId);
      const lista = Array.isArray(dados) ? dados : (dados as { results?: Vinculo[] }).results ?? [];
      setVinculos(lista);
    } finally {
      setVinculosLoading(false);
    }
  }, [colaboradorId]);

  useEffect(() => {
    void carregarVinculos();
  }, [carregarVinculos]);

  if (!colaboradorId) {
    return (
      <WorkspaceSection title="Histórico de vínculos">
        <p className="text-sm text-muted-foreground">Salve o colaborador antes de cadastrar vínculos.</p>
      </WorkspaceSection>
    );
  }

  const recarregarAposSucesso = () => {
    setPainelVinculo(null);
    void carregarVinculos();
  };

  return (
    <div className="space-y-4">
      {painelVinculo?.tipo === 'novo' ? (
        <VinculoForm
          colaboradorId={colaboradorId}
          onClose={() => setPainelVinculo(null)}
          onSuccess={recarregarAposSucesso}
        />
      ) : painelVinculo?.tipo === 'editar' ? (
        <VinculoForm
          colaboradorId={colaboradorId}
          vinculoExistente={painelVinculo.vinculo}
          onClose={() => setPainelVinculo(null)}
          onSuccess={recarregarAposSucesso}
        />
      ) : painelVinculo?.tipo === 'evento' ? (
        <EventoVinculoForm
          vinculo={painelVinculo.vinculo}
          onClose={() => setPainelVinculo(null)}
          onSuccess={recarregarAposSucesso}
        />
      ) : (
        <WorkspaceSection
          title="Histórico de vínculos"
          description="Admissões, promoções, aumentos e encerramentos."
          actions={
            <button
              type="button"
              className="erp-btn-primary erp-btn-sm"
              onClick={() => setPainelVinculo({ tipo: 'novo' })}
            >
              + Novo vínculo
            </button>
          }
        >
          {vinculosLoading ? (
            <p className="text-sm text-muted-foreground">Carregando vínculos...</p>
          ) : vinculos.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum vínculo registrado. Clique em &quot;+ Novo vínculo&quot; para começar.
            </p>
          ) : (
            <div className="space-y-3">
              {vinculos.map((vinculo) => (
                <VinculoCard
                  key={vinculo.id}
                  vinculo={vinculo}
                  onEdit={() => setPainelVinculo({ tipo: 'editar', vinculo })}
                  onEvento={() => setPainelVinculo({ tipo: 'evento', vinculo })}
                />
              ))}
            </div>
          )}
        </WorkspaceSection>
      )}
    </div>
  );
}

function VinculoCard({
  vinculo,
  onEdit,
  onEvento,
}: {
  vinculo: Vinculo;
  onEdit: () => void;
  onEvento: () => void;
}) {
  const ativo = !vinculo.data_demissao;
  const [eventos, setEventos] = useState<EventoVinculo[]>([]);
  const [eventosLoading, setEventosLoading] = useState(false);

  useEffect(() => {
    let ativoNaTela = true;
    setEventosLoading(true);
    void colaboradoresService
      .listEventosVinculo(vinculo.id)
      .then((dados) => {
        if (ativoNaTela) setEventos(Array.isArray(dados) ? dados : []);
      })
      .finally(() => {
        if (ativoNaTela) setEventosLoading(false);
      });
    return () => {
      ativoNaTela = false;
    };
  }, [vinculo.id]);

  return (
    <div
      className={`rounded-lg border p-4 ${ativo ? 'border-primary/30 bg-primary/5 cursor-pointer' : 'border-border bg-muted/30'}`}
      onClick={ativo ? onEdit : undefined}
      role={ativo ? 'button' : undefined}
      tabIndex={ativo ? 0 : undefined}
      onKeyDown={ativo ? (event) => event.key === 'Enter' && onEdit() : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex h-2 w-2 rounded-full ${ativo ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
            <span className="font-semibold text-foreground">{vinculo.cargo || '(cargo não informado)'}</span>
            <span className="text-xs bg-muted px-1.5 py-0.5 rounded">{ativo ? 'Ativo' : 'Encerrado'}</span>
            {vinculo.tipo_contrato && (
              <span className="text-xs bg-muted px-1.5 py-0.5 rounded">{vinculo.tipo_contrato}</span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-xs text-muted-foreground mt-2">
            <div>
              <span className="block uppercase tracking-wide text-[10px]">Admissão</span>
              <span className="text-foreground">{formatarData(vinculo.data_admissao)}</span>
            </div>
            {vinculo.data_demissao && (
              <div>
                <span className="block uppercase tracking-wide text-[10px]">Demissão</span>
                <span className="text-foreground">{formatarData(vinculo.data_demissao)}</span>
              </div>
            )}
            {vinculo.departamento && (
              <div>
                <span className="block uppercase tracking-wide text-[10px]">Departamento</span>
                <span className="text-foreground">{vinculo.departamento}</span>
              </div>
            )}
            {formatarSalario(vinculo.salario_base) && (
              <div>
                <span className="block uppercase tracking-wide text-[10px]">Salário</span>
                <span className="text-foreground">{formatarSalario(vinculo.salario_base)}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          {ativo && (
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={(event) => {
                event.stopPropagation();
                onEvento();
              }}
              title="Registrar evento (promoção, aumento, etc)"
            >
              + Evento
            </button>
          )}
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={(event) => {
              event.stopPropagation();
              onEdit();
            }}
            title="Editar vínculo"
          >
            Editar
          </button>
        </div>
      </div>
      {(eventosLoading || eventos.length > 0) && (
        <div className="mt-4 border-t border-border/70 pt-3">
          <p className="text-xs font-semibold text-muted-foreground mb-2">Timeline de eventos</p>
          {eventosLoading ? (
            <p className="text-xs text-muted-foreground">Carregando eventos...</p>
          ) : (
            <div className="space-y-2 border-l border-primary/30 pl-3">
              {eventos.map((evento) => (
                <div key={evento.id} className="relative text-xs">
                  <span className="absolute -left-[19px] top-1 h-2 w-2 rounded-full bg-primary" />
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium text-foreground">{evento.tipo}</span>
                    <span className="text-muted-foreground">{formatarData(evento.data_efetiva)}</span>
                  </div>
                  {evento.motivo && <p className="text-muted-foreground">{evento.motivo}</p>}
                  {evento.observacao && <p className="text-muted-foreground">{evento.observacao}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VinculoForm({
  colaboradorId,
  vinculoExistente,
  onClose,
  onSuccess,
}: {
  colaboradorId: number;
  vinculoExistente?: Vinculo;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const editing = Boolean(vinculoExistente?.id);
  const [form, setForm] = useState({
    tipo_contrato: vinculoExistente?.tipo_contrato ?? '',
    cargo: vinculoExistente?.cargo ?? '',
    departamento: vinculoExistente?.departamento ?? '',
    data_admissao: vinculoExistente?.data_admissao ?? '',
    data_demissao: vinculoExistente?.data_demissao ?? '',
    salario_base: vinculoExistente?.salario_base ?? '',
    salario_tipo: vinculoExistente?.salario_tipo ?? '',
    jornada_horas: vinculoExistente?.jornada_horas ?? '',
    jornada_turno: vinculoExistente?.jornada_turno ?? '',
    matricula: vinculoExistente?.matricula ?? '',
    cbo: vinculoExistente?.cbo ?? '',
    local_trabalho: vinculoExistente?.local_trabalho ?? '',
    observacoes: vinculoExistente?.observacoes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        colaborador: colaboradorId,
        ...form,
        data_admissao: form.data_admissao || null,
        data_demissao: form.data_demissao || null,
        salario_base: form.salario_base || null,
        jornada_horas: form.jornada_horas || null,
      };
      if (editing && vinculoExistente?.id) {
        await colaboradoresService.updateVinculo(vinculoExistente.id, payload);
      } else {
        await colaboradoresService.createVinculo(
          payload as Parameters<typeof colaboradoresService.createVinculo>[0],
        );
      }
      onSuccess();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <InlinePanel
      title={editing ? 'Editar vínculo' : 'Novo vínculo'}
      onCancel={onClose}
      onSave={handleSave}
      saving={saving}
      saveLabel={editing ? 'Salvar' : 'Criar vínculo'}
      error={error}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <WorkspaceField label="Tipo de contrato">
          <select className="erp-select" value={form.tipo_contrato} onChange={(e) => setForm((p) => ({ ...p, tipo_contrato: e.target.value as typeof p.tipo_contrato }))}>
            <option value="">Não informado</option>
            <option value="CLT">CLT</option>
            <option value="PJ">PJ</option>
            <option value="ESTAGIO">Estágio</option>
            <option value="SOCIO">Sócio</option>
            <option value="AUTONOMO">Autônomo</option>
            <option value="TEMPORARIO">Temporário</option>
            <option value="APRENDIZ">Aprendiz</option>
          </select>
        </WorkspaceField>
        <WorkspaceField label="Data de admissão">
          <input type="date" className="erp-input" value={form.data_admissao ?? ''} onChange={(e) => setForm((p) => ({ ...p, data_admissao: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Data de demissão" help="Preencha só quando encerrar">
          <input type="date" className="erp-input" value={form.data_demissao ?? ''} onChange={(e) => setForm((p) => ({ ...p, data_demissao: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Cargo" className="md:col-span-2">
          <input className="erp-input" value={form.cargo} onChange={(e) => setForm((p) => ({ ...p, cargo: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Departamento">
          <input className="erp-input" value={form.departamento} onChange={(e) => setForm((p) => ({ ...p, departamento: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Salário base">
          <input type="number" step="0.01" className="erp-input" value={form.salario_base ?? ''} onChange={(e) => setForm((p) => ({ ...p, salario_base: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Tipo de salário">
          <select className="erp-select" value={form.salario_tipo} onChange={(e) => setForm((p) => ({ ...p, salario_tipo: e.target.value as typeof p.salario_tipo }))}>
            <option value="">Não informado</option>
            <option value="MENSAL">Mensal</option>
            <option value="HORISTA">Horista</option>
            <option value="DIARIO">Diário</option>
            <option value="COMISSAO">Por comissão</option>
          </select>
        </WorkspaceField>
        <WorkspaceField label="Jornada (h/semana)">
          <input type="number" step="0.5" className="erp-input" value={form.jornada_horas ?? ''} onChange={(e) => setForm((p) => ({ ...p, jornada_horas: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Turno">
          <select className="erp-select" value={form.jornada_turno} onChange={(e) => setForm((p) => ({ ...p, jornada_turno: e.target.value as typeof p.jornada_turno }))}>
            <option value="">Não informado</option>
            <option value="MANHA">Manhã</option>
            <option value="TARDE">Tarde</option>
            <option value="NOITE">Noite</option>
            <option value="INTEGRAL">Integral</option>
            <option value="COMERCIAL">Comercial</option>
          </select>
        </WorkspaceField>
        <WorkspaceField label="Matrícula">
          <input className="erp-input" value={form.matricula} onChange={(e) => setForm((p) => ({ ...p, matricula: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="CBO">
          <input className="erp-input" value={form.cbo} onChange={(e) => setForm((p) => ({ ...p, cbo: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Local de trabalho">
          <input className="erp-input" value={form.local_trabalho} onChange={(e) => setForm((p) => ({ ...p, local_trabalho: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Observações" className="md:col-span-3">
          <textarea className="erp-input min-h-[6rem]" rows={3} value={form.observacoes} onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))} />
        </WorkspaceField>
      </div>
    </InlinePanel>
  );
}

function EventoVinculoForm({
  vinculo,
  onClose,
  onSuccess,
}: {
  vinculo: Vinculo;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState({
    tipo: 'PROMOCAO' as EventoVinculo['tipo'],
    data_efetiva: new Date().toISOString().slice(0, 10),
    motivo: '',
    observacao: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await colaboradoresService.createEventoVinculo({ vinculo: vinculo.id, ...form });
      onSuccess();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <InlinePanel
      title={`Registrar evento — ${vinculo.cargo || 'vínculo'}`}
      onCancel={onClose}
      onSave={handleSave}
      saving={saving}
      saveLabel="Registrar"
      error={error}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <WorkspaceField label="Tipo de evento">
          <select className="erp-select" value={form.tipo} onChange={(e) => setForm((p) => ({ ...p, tipo: e.target.value as EventoVinculo['tipo'] }))}>
            <option value="ADMISSAO">Admissão</option>
            <option value="PROMOCAO">Promoção</option>
            <option value="AUMENTO">Aumento</option>
            <option value="TRANSFERENCIA">Transferência</option>
            <option value="MUDANCA_JORNADA">Mudança de jornada</option>
            <option value="MUDANCA_GESTOR">Mudança de gestor</option>
            <option value="AFASTAMENTO">Afastamento</option>
            <option value="RETORNO">Retorno de afastamento</option>
            <option value="ENCERRAMENTO">Encerramento</option>
            <option value="OUTRO">Outro</option>
          </select>
        </WorkspaceField>
        <WorkspaceField label="Data efetiva">
          <input type="date" className="erp-input" value={form.data_efetiva} onChange={(e) => setForm((p) => ({ ...p, data_efetiva: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Motivo" className="md:col-span-3">
          <input className="erp-input" value={form.motivo} onChange={(e) => setForm((p) => ({ ...p, motivo: e.target.value }))} placeholder="Ex: Mérito anual, promoção interna..." />
        </WorkspaceField>
        <WorkspaceField label="Observação" className="md:col-span-3">
          <textarea className="erp-input min-h-[6rem]" rows={3} value={form.observacao} onChange={(e) => setForm((p) => ({ ...p, observacao: e.target.value }))} />
        </WorkspaceField>
      </div>
    </InlinePanel>
  );
}

function DependentesTab({ colaboradorId }: { colaboradorId: number | null }) {
  const [dependentes, setDependentes] = useState<Dependente[]>([]);
  const [loading, setLoading] = useState(false);
  const [painel, setPainel] = useState<
    | { tipo: 'novo' }
    | { tipo: 'editar'; dependente: Dependente }
    | null
  >(null);
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    if (!colaboradorId) {
      setDependentes([]);
      return;
    }
    setLoading(true);
    try {
      const dados = await colaboradoresService.listDependentes(colaboradorId);
      const lista = Array.isArray(dados) ? dados : (dados as { results?: Dependente[] }).results ?? [];
      setDependentes(lista);
    } finally {
      setLoading(false);
    }
  }, [colaboradorId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const handleExcluir = async (id: number) => {
    setConfirmandoId(null);
    await colaboradoresService.deleteDependente(id);
    void carregar();
  };

  if (!colaboradorId) {
    return <p className="text-sm text-muted-foreground">Salve o colaborador antes de cadastrar dependentes.</p>;
  }

  if (painel?.tipo === 'novo' || painel?.tipo === 'editar') {
    return (
      <DependenteForm
        colaboradorId={colaboradorId}
        dependenteExistente={painel.tipo === 'editar' ? painel.dependente : undefined}
        onClose={() => setPainel(null)}
        onSuccess={() => {
          setPainel(null);
          void carregar();
        }}
      />
    );
  }

  return (
    <WorkspaceSection
      title="Dependentes"
      description="Dependentes para fins de IR e plano de saúde."
      actions={
        <button
          type="button"
          className="erp-btn-primary erp-btn-sm"
          onClick={() => setPainel({ tipo: 'novo' })}
        >
          + Novo dependente
        </button>
      }
    >
      {loading ? (
        <p className="text-sm text-muted-foreground">Carregando...</p>
      ) : dependentes.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum dependente cadastrado.</p>
      ) : (
        <div className="divide-y divide-border">
          {dependentes.map((dependente) => (
            <div key={dependente.id} className="py-3 flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-foreground">{dependente.nome}</div>
                <div className="text-xs text-muted-foreground mt-0.5 flex flex-wrap gap-3">
                  {dependente.parentesco && <span>{dependente.parentesco}</span>}
                  {dependente.cpf && <span>CPF: {dependente.cpf}</span>}
                  {dependente.data_nascimento && <span>Nasc: {dependente.data_nascimento}</span>}
                  <span>IR: {dependente.dependente_ir ? 'Sim' : 'Não'}</span>
                  <span>Saúde: {dependente.dependente_saude ? 'Sim' : 'Não'}</span>
                </div>
              </div>
              {confirmandoId === dependente.id ? (
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-destructive font-medium whitespace-nowrap">Excluir?</span>
                  <button
                    type="button"
                    className="erp-btn-destructive erp-btn-sm"
                    onClick={() => void handleExcluir(dependente.id)}
                  >
                    Sim
                  </button>
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm"
                    onClick={() => setConfirmandoId(null)}
                  >
                    Não
                  </button>
                </div>
              ) : (
                <div className="flex gap-1">
                  <button
                    type="button"
                    className="erp-btn-ghost erp-btn-sm text-foreground/70 hover:text-primary"
                    onClick={() => setPainel({ tipo: 'editar', dependente })}
                    title="Editar"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    className="erp-btn-ghost erp-btn-sm text-foreground/70 hover:text-destructive"
                    onClick={() => setConfirmandoId(dependente.id)}
                    title="Excluir"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </WorkspaceSection>
  );
}

function DependenteForm({
  colaboradorId,
  dependenteExistente,
  onClose,
  onSuccess,
}: {
  colaboradorId: number;
  dependenteExistente?: Dependente;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const editing = Boolean(dependenteExistente?.id);
  const [form, setForm] = useState({
    nome: dependenteExistente?.nome ?? '',
    cpf: dependenteExistente?.cpf ?? '',
    data_nascimento: dependenteExistente?.data_nascimento ?? '',
    parentesco: dependenteExistente?.parentesco ?? '',
    dependente_ir: dependenteExistente?.dependente_ir ?? false,
    dependente_saude: dependenteExistente?.dependente_saude ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!form.nome.trim()) {
      setError('Nome é obrigatório.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        colaborador: colaboradorId,
        ...form,
        nome: form.nome.trim(),
        data_nascimento: form.data_nascimento || null,
      };
      if (editing && dependenteExistente?.id) {
        await colaboradoresService.updateDependente(dependenteExistente.id, payload);
      } else {
        await colaboradoresService.createDependente(
          payload as Parameters<typeof colaboradoresService.createDependente>[0],
        );
      }
      onSuccess();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <InlinePanel
      title={editing ? 'Editar dependente' : 'Novo dependente'}
      onCancel={onClose}
      onSave={handleSave}
      saving={saving}
      saveLabel={editing ? 'Salvar' : 'Adicionar'}
      error={error}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <WorkspaceField label="Nome completo" required className="md:col-span-2">
          <input className="erp-input" value={form.nome} onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="CPF">
          <input className="erp-input" value={form.cpf} onChange={(e) => setForm((p) => ({ ...p, cpf: e.target.value }))} placeholder="000.000.000-00" />
        </WorkspaceField>
        <WorkspaceField label="Data de nascimento">
          <input type="date" className="erp-input" value={form.data_nascimento ?? ''} onChange={(e) => setForm((p) => ({ ...p, data_nascimento: e.target.value }))} />
        </WorkspaceField>
        <WorkspaceField label="Parentesco" className="md:col-span-2">
          <input className="erp-input" value={form.parentesco} onChange={(e) => setForm((p) => ({ ...p, parentesco: e.target.value }))} placeholder="Filho(a), Cônjuge, Enteado(a)..." />
        </WorkspaceField>
        <div className="md:col-span-2 flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.dependente_ir} onChange={(e) => setForm((p) => ({ ...p, dependente_ir: e.target.checked }))} />
            <span>Dependente para Imposto de Renda</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.dependente_saude} onChange={(e) => setForm((p) => ({ ...p, dependente_saude: e.target.checked }))} />
            <span>Dependente para Plano de Saúde</span>
          </label>
        </div>
      </div>
    </InlinePanel>
  );
}

export default function ColaboradorWorkspace({ colaborador, onClose }: ColaboradorWorkspaceProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<ColaboradorForm>(formularioInicial);
  const [saving, setSaving] = useState(false);
  const [salvarError, setSalvarError] = useState<string | null>(null);
  const [modalTab, setModalTab] = useState<'dados' | 'endereco' | 'contato' | 'documentos' | 'vinculos' | 'dependentes' | 'funcoes' | 'acesso'>('dados');
  const [colaboradorAtual, setColaboradorAtual] = useState<Colaborador | null>(colaborador);
  const [colaboradorLoading, setColaboradorLoading] = useState(false);
  const [cepLookupLoading, setCepLookupLoading] = useState(false);
  const [cepLookupMessage, setCepLookupMessage] = useState<string | null>(null);

  useEffect(() => {
    setColaboradorAtual(colaborador);
  }, [colaborador]);

  useEffect(() => {
    if (colaborador) {
      setForm({
        nome: colaborador.nome ?? '',
        codigo: colaborador.codigo ?? '',
        email: colaborador.email ?? '',
        telefone: colaborador.telefone ?? '',
        cargo: colaborador.cargo ?? '',
        departamento: colaborador.departamento ?? '',
        ativo: Boolean(colaborador.ativo),
        observacoes: colaborador.observacoes ?? '',
        nome_social: colaborador.nome_social ?? '',
        tipo_pessoa: colaborador.tipo_pessoa ?? 'FISICA',
        cpf: colaborador.cpf ?? '',
        cnpj: colaborador.cnpj ?? '',
        identidade_tipo: colaborador.identidade_tipo ?? '',
        identidade_numero: colaborador.identidade_numero ?? '',
        identidade_orgao: colaborador.identidade_orgao ?? '',
        identidade_uf: colaborador.identidade_uf ?? '',
        identidade_emissao: colaborador.identidade_emissao ?? '',
        identidade_validade: colaborador.identidade_validade ?? '',
        data_nascimento: colaborador.data_nascimento ?? '',
        sexo: colaborador.sexo ?? '',
        estado_civil: colaborador.estado_civil ?? '',
        nacionalidade: colaborador.nacionalidade ?? '',
        naturalidade_cidade: colaborador.naturalidade_cidade ?? '',
        naturalidade_uf: colaborador.naturalidade_uf ?? '',
        nome_mae: colaborador.nome_mae ?? '',
        nome_pai: colaborador.nome_pai ?? '',
        celular: colaborador.celular ?? '',
        email_pessoal: colaborador.email_pessoal ?? '',
        emergencia_nome: colaborador.emergencia_nome ?? '',
        emergencia_telefone: colaborador.emergencia_telefone ?? '',
        emergencia_parentesco: colaborador.emergencia_parentesco ?? '',
        cep: colaborador.cep ?? '',
        logradouro: colaborador.logradouro ?? '',
        numero: colaborador.numero ?? '',
        complemento: colaborador.complemento ?? '',
        bairro: colaborador.bairro ?? '',
        cidade: colaborador.cidade ?? '',
        uf: colaborador.uf ?? '',
        ctps_numero: colaborador.ctps_numero ?? '',
        ctps_serie: colaborador.ctps_serie ?? '',
        ctps_uf: colaborador.ctps_uf ?? '',
        ctps_emissao: colaborador.ctps_emissao ?? '',
        pis_pasep: colaborador.pis_pasep ?? '',
        titulo_numero: colaborador.titulo_numero ?? '',
        titulo_zona: colaborador.titulo_zona ?? '',
        titulo_secao: colaborador.titulo_secao ?? '',
        titulo_uf: colaborador.titulo_uf ?? '',
        cnh_numero: colaborador.cnh_numero ?? '',
        cnh_categoria: colaborador.cnh_categoria ?? '',
        cnh_validade: colaborador.cnh_validade ?? '',
        reservista_numero: colaborador.reservista_numero ?? '',
        eh_vendedor: Boolean(colaborador.eh_vendedor),
        eh_comprador: Boolean(colaborador.eh_comprador),
        eh_responsavel_fiscal: Boolean(colaborador.eh_responsavel_fiscal),
        eh_responsavel_financeiro: Boolean(colaborador.eh_responsavel_financeiro),
        eh_responsavel_estoque: Boolean(colaborador.eh_responsavel_estoque),
        eh_responsavel_qualidade: Boolean(colaborador.eh_responsavel_qualidade),
        eh_administrador: Boolean(colaborador.eh_administrador),
      });
    } else {
      setForm(formularioInicial);
    }
    setSalvarError(null);
  }, [colaborador]);

  useEffect(() => {
    if (colaborador?.id) {
      setModalTab('dados');
    }
  }, [colaborador?.id]);

  const handleSave = async () => {
    if (!form.nome.trim()) {
      setSalvarError('Nome é obrigatório.');
      return;
    }

    setSaving(true);
    setSalvarError(null);

    try {
      const payload = {
        ...form,
        nome: form.nome.trim(),
        codigo: form.codigo.trim(),
        email: form.email.trim(),
        telefone: form.telefone.trim(),
        cargo: form.cargo.trim(),
        departamento: form.departamento.trim(),
        observacoes: form.observacoes.trim(),
        identidade_emissao: form.identidade_emissao || null,
        identidade_validade: form.identidade_validade || null,
        data_nascimento: form.data_nascimento || null,
        ctps_emissao: form.ctps_emissao || null,
        cnh_validade: form.cnh_validade || null,
      };

      const salvo = colaboradorAtual?.id
        ? await colaboradoresService.update(colaboradorAtual.id, payload)
        : await colaboradoresService.create(payload);

      toast.success('Colaborador salvo');

      if (!colaboradorAtual?.id) {
        navigate(`/colaboradores/${salvo.id}`);
      }
    } catch (err) {
      setSalvarError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const reload = async () => {
    if (!colaboradorAtual?.id) return;

    setColaboradorLoading(true);
    try {
      const atualizado = await colaboradoresService.getById(colaboradorAtual.id);
      setColaboradorAtual(atualizado);
      setForm({
        nome: atualizado.nome ?? '',
        codigo: atualizado.codigo ?? '',
        email: atualizado.email ?? '',
        telefone: atualizado.telefone ?? '',
        cargo: atualizado.cargo ?? '',
        departamento: atualizado.departamento ?? '',
        ativo: Boolean(atualizado.ativo),
        observacoes: atualizado.observacoes ?? '',
        nome_social: atualizado.nome_social ?? '',
        tipo_pessoa: atualizado.tipo_pessoa ?? 'FISICA',
        cpf: atualizado.cpf ?? '',
        cnpj: atualizado.cnpj ?? '',
        identidade_tipo: atualizado.identidade_tipo ?? '',
        identidade_numero: atualizado.identidade_numero ?? '',
        identidade_orgao: atualizado.identidade_orgao ?? '',
        identidade_uf: atualizado.identidade_uf ?? '',
        identidade_emissao: atualizado.identidade_emissao ?? '',
        identidade_validade: atualizado.identidade_validade ?? '',
        data_nascimento: atualizado.data_nascimento ?? '',
        sexo: atualizado.sexo ?? '',
        estado_civil: atualizado.estado_civil ?? '',
        nacionalidade: atualizado.nacionalidade ?? '',
        naturalidade_cidade: atualizado.naturalidade_cidade ?? '',
        naturalidade_uf: atualizado.naturalidade_uf ?? '',
        nome_mae: atualizado.nome_mae ?? '',
        nome_pai: atualizado.nome_pai ?? '',
        celular: atualizado.celular ?? '',
        email_pessoal: atualizado.email_pessoal ?? '',
        emergencia_nome: atualizado.emergencia_nome ?? '',
        emergencia_telefone: atualizado.emergencia_telefone ?? '',
        emergencia_parentesco: atualizado.emergencia_parentesco ?? '',
        cep: atualizado.cep ?? '',
        logradouro: atualizado.logradouro ?? '',
        numero: atualizado.numero ?? '',
        complemento: atualizado.complemento ?? '',
        bairro: atualizado.bairro ?? '',
        cidade: atualizado.cidade ?? '',
        uf: atualizado.uf ?? '',
        ctps_numero: atualizado.ctps_numero ?? '',
        ctps_serie: atualizado.ctps_serie ?? '',
        ctps_uf: atualizado.ctps_uf ?? '',
        ctps_emissao: atualizado.ctps_emissao ?? '',
        pis_pasep: atualizado.pis_pasep ?? '',
        titulo_numero: atualizado.titulo_numero ?? '',
        titulo_zona: atualizado.titulo_zona ?? '',
        titulo_secao: atualizado.titulo_secao ?? '',
        titulo_uf: atualizado.titulo_uf ?? '',
        cnh_numero: atualizado.cnh_numero ?? '',
        cnh_categoria: atualizado.cnh_categoria ?? '',
        cnh_validade: atualizado.cnh_validade ?? '',
        reservista_numero: atualizado.reservista_numero ?? '',
        eh_vendedor: Boolean(atualizado.eh_vendedor),
        eh_comprador: Boolean(atualizado.eh_comprador),
        eh_responsavel_fiscal: Boolean(atualizado.eh_responsavel_fiscal),
        eh_responsavel_financeiro: Boolean(atualizado.eh_responsavel_financeiro),
        eh_responsavel_estoque: Boolean(atualizado.eh_responsavel_estoque),
        eh_responsavel_qualidade: Boolean(atualizado.eh_responsavel_qualidade),
        eh_administrador: Boolean(atualizado.eh_administrador),
      });
    } finally {
      setColaboradorLoading(false);
    }
  };

  const onCepBlur = async (rawValue: string) => {
    const cep = rawValue.replace(/\D/g, '').slice(0, 8);
    if (cep.length !== 8) {
      setCepLookupMessage('CEP deve ter 8 dígitos.');
      return;
    }
    setCepLookupLoading(true);
    setCepLookupMessage(null);
    try {
      const resp = await consultaCep(cep);
      const dados = resp.data;
      setForm((p) => ({
        ...p,
        logradouro: dados.logradouro || p.logradouro,
        complemento: p.complemento || dados.complemento || '',
        bairro: dados.bairro || p.bairro,
        cidade: dados.cidade || p.cidade,
        uf: dados.uf || p.uf,
      }));
    } catch (err) {
      setCepLookupMessage('Não foi possível consultar o CEP.');
    } finally {
      setCepLookupLoading(false);
    }
  };

  return (
    <WorkspaceLayout
      title={colaboradorAtual?.id ? 'Editar colaborador' : 'Novo colaborador'}
      subtitle="Cadastro de colaborador com funções e perfil de acesso ao sistema."
      breadcrumbs={[
        { label: 'Cadastros', path: '/colaboradores' },
        { label: 'Colaboradores', path: '/colaboradores' },
        { label: colaboradorAtual?.id ? 'Editar' : 'Novo' }
      ]}
      onSave={handleSave}
      onClose={onClose}
      saving={saving}
      saveLabel="Salvar colaborador"
      error={salvarError}
      meta={[
        { label: 'Código', value: form.codigo || '—' },
        { label: 'E-mail', value: form.email || '—' },
        { label: 'Cargo', value: form.cargo || '—' },
        { label: 'Status', value: <StatusBadge status={form.ativo ? 'Ativo' : 'Inativo'} className="mt-0.5" /> },
      ]}
      tabs={[
        {
          value: 'dados',
          label: 'Dados pessoais',
          icon: User,
          content: (
            <div className="space-y-4">
              <WorkspaceSection title="Identificação" description="Dados que constam em documentos e no cadastro fiscal.">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Nome completo" required className="md:col-span-2">
                    <input className="erp-input" value={form.nome} onChange={(e) => setForm((p) => ({ ...p, nome: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Tipo de pessoa">
                    <select className="erp-select" value={form.tipo_pessoa} onChange={(e) => setForm((p) => ({ ...p, tipo_pessoa: e.target.value }))}>
                      <option value="FISICA">Pessoa Física</option>
                      <option value="JURIDICA">Pessoa Jurídica</option>
                    </select>
                  </WorkspaceField>
                  <WorkspaceField label="Nome social">
                    <input className="erp-input" value={form.nome_social} onChange={(e) => setForm((p) => ({ ...p, nome_social: e.target.value }))} />
                  </WorkspaceField>
                  {form.tipo_pessoa === 'FISICA' ? (
                    <WorkspaceField label="CPF">
                      <input className="erp-input" value={form.cpf} onChange={(e) => setForm((p) => ({ ...p, cpf: e.target.value }))} placeholder="000.000.000-00" />
                    </WorkspaceField>
                  ) : (
                    <WorkspaceField label="CNPJ">
                      <input className="erp-input" value={form.cnpj} onChange={(e) => setForm((p) => ({ ...p, cnpj: e.target.value }))} placeholder="00.000.000/0000-00" />
                    </WorkspaceField>
                  )}
                  <WorkspaceField label="Código">
                    <input className="erp-input" value={form.codigo} onChange={(e) => setForm((p) => ({ ...p, codigo: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Ativo">
                    <label className="flex items-center gap-2 text-sm pt-1.5">
                      <input type="checkbox" checked={form.ativo} onChange={(e) => setForm((p) => ({ ...p, ativo: e.target.checked }))} />
                      <span>{form.ativo ? 'Ativo' : 'Inativo'}</span>
                    </label>
                  </WorkspaceField>
                </div>
              </WorkspaceSection>

              <WorkspaceSection title="Identidade" description="RG, CIN ou outro documento de identidade. CIN usa o CPF como número.">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Tipo">
                    <select className="erp-select" value={form.identidade_tipo} onChange={(e) => setForm((p) => ({ ...p, identidade_tipo: e.target.value }))}>
                      <option value="">Não informado</option>
                      <option value="RG">RG (legado)</option>
                      <option value="CIN">CIN</option>
                      <option value="OUTRO">Outro</option>
                    </select>
                  </WorkspaceField>
                  <WorkspaceField label="Número" className="md:col-span-2">
                    <input className="erp-input" value={form.identidade_numero} onChange={(e) => setForm((p) => ({ ...p, identidade_numero: e.target.value }))} disabled={form.identidade_tipo === 'CIN'} placeholder={form.identidade_tipo === 'CIN' ? '(preenchido com CPF)' : ''} />
                  </WorkspaceField>
                  <WorkspaceField label="Órgão emissor">
                    <input className="erp-input" value={form.identidade_orgao} onChange={(e) => setForm((p) => ({ ...p, identidade_orgao: e.target.value }))} placeholder="SSP, IFP..." />
                  </WorkspaceField>
                  <WorkspaceField label="UF">
                    <input className="erp-input" maxLength={2} value={form.identidade_uf} onChange={(e) => setForm((p) => ({ ...p, identidade_uf: e.target.value.toUpperCase() }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Data emissão">
                    <input type="date" className="erp-input" value={form.identidade_emissao} onChange={(e) => setForm((p) => ({ ...p, identidade_emissao: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Validade" help="Apenas CIN">
                    <input type="date" className="erp-input" value={form.identidade_validade} onChange={(e) => setForm((p) => ({ ...p, identidade_validade: e.target.value }))} />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>

              <WorkspaceSection title="Dados pessoais">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Data de nascimento">
                    <input type="date" className="erp-input" value={form.data_nascimento} onChange={(e) => setForm((p) => ({ ...p, data_nascimento: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Sexo">
                    <select className="erp-select" value={form.sexo} onChange={(e) => setForm((p) => ({ ...p, sexo: e.target.value }))}>
                      <option value="">Não informado</option>
                      <option value="M">Masculino</option>
                      <option value="F">Feminino</option>
                      <option value="OUTRO">Outro</option>
                      <option value="NAO_INFORMAR">Prefiro não informar</option>
                    </select>
                  </WorkspaceField>
                  <WorkspaceField label="Estado civil">
                    <select className="erp-select" value={form.estado_civil} onChange={(e) => setForm((p) => ({ ...p, estado_civil: e.target.value }))}>
                      <option value="">Não informado</option>
                      <option value="SOLTEIRO">Solteiro(a)</option>
                      <option value="CASADO">Casado(a)</option>
                      <option value="DIVORCIADO">Divorciado(a)</option>
                      <option value="VIUVO">Viúvo(a)</option>
                      <option value="UNIAO_ESTAVEL">União Estável</option>
                    </select>
                  </WorkspaceField>
                  <WorkspaceField label="Nacionalidade">
                    <input className="erp-input" value={form.nacionalidade} onChange={(e) => setForm((p) => ({ ...p, nacionalidade: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Naturalidade — cidade">
                    <input className="erp-input" value={form.naturalidade_cidade} onChange={(e) => setForm((p) => ({ ...p, naturalidade_cidade: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Naturalidade — UF">
                    <input className="erp-input" maxLength={2} value={form.naturalidade_uf} onChange={(e) => setForm((p) => ({ ...p, naturalidade_uf: e.target.value.toUpperCase() }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Nome da mãe" className="md:col-span-2">
                    <input className="erp-input" value={form.nome_mae} onChange={(e) => setForm((p) => ({ ...p, nome_mae: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Nome do pai" className="md:col-span-2">
                    <input className="erp-input" value={form.nome_pai} onChange={(e) => setForm((p) => ({ ...p, nome_pai: e.target.value }))} />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>

            </div>
          ),
        },
        {
          value: 'endereco',
          label: 'Endereço',
          icon: MapPin,
          content: (
            <WorkspaceSection title="Endereço residencial">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <WorkspaceField label="CEP">
                  <input
                    className="erp-input"
                    value={form.cep}
                    onChange={(e) => {
                      setForm((p) => ({ ...p, cep: e.target.value }));
                    }}
                    onBlur={(e) => onCepBlur(e.target.value)}
                    placeholder="00000-000"
                  />
                  {cepLookupLoading && <p className="text-[11px] text-muted-foreground mt-1">Consultando CEP...</p>}
                  {cepLookupMessage && <p className="text-[11px] text-destructive mt-1">{cepLookupMessage}</p>}
                </WorkspaceField>
                <WorkspaceField label="Logradouro" className="md:col-span-3">
                  <input className="erp-input" value={form.logradouro} onChange={(e) => setForm((p) => ({ ...p, logradouro: e.target.value }))} />
                </WorkspaceField>
                <WorkspaceField label="Número">
                  <input className="erp-input" value={form.numero} onChange={(e) => setForm((p) => ({ ...p, numero: e.target.value }))} />
                </WorkspaceField>
                <WorkspaceField label="Complemento" className="md:col-span-3">
                  <input className="erp-input" value={form.complemento} onChange={(e) => setForm((p) => ({ ...p, complemento: e.target.value }))} />
                </WorkspaceField>
                <WorkspaceField label="Bairro" className="md:col-span-2">
                  <input className="erp-input" value={form.bairro} onChange={(e) => setForm((p) => ({ ...p, bairro: e.target.value }))} />
                </WorkspaceField>
                <WorkspaceField label="Cidade">
                  <input className="erp-input" value={form.cidade} onChange={(e) => setForm((p) => ({ ...p, cidade: e.target.value }))} />
                </WorkspaceField>
                <WorkspaceField label="UF">
                  <input className="erp-input" maxLength={2} value={form.uf} onChange={(e) => setForm((p) => ({ ...p, uf: e.target.value.toUpperCase() }))} />
                </WorkspaceField>
              </div>
            </WorkspaceSection>
          ),
        },
        {
          value: 'contato',
          label: 'Contato',
          icon: Phone,
          content: (
            <div className="space-y-4">
              <WorkspaceSection title="Contato">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <WorkspaceField label="E-mail corporativo">
                    <input type="email" className="erp-input" value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="E-mail pessoal">
                    <input type="email" className="erp-input" value={form.email_pessoal} onChange={(e) => setForm((p) => ({ ...p, email_pessoal: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Telefone fixo">
                    <input className="erp-input" value={form.telefone} onChange={(e) => setForm((p) => ({ ...p, telefone: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Celular">
                    <input className="erp-input" value={form.celular} onChange={(e) => setForm((p) => ({ ...p, celular: e.target.value }))} />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>
              <WorkspaceSection title="Contato de emergência">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Nome">
                    <input className="erp-input" value={form.emergencia_nome} onChange={(e) => setForm((p) => ({ ...p, emergencia_nome: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Telefone">
                    <input className="erp-input" value={form.emergencia_telefone} onChange={(e) => setForm((p) => ({ ...p, emergencia_telefone: e.target.value }))} />
                  </WorkspaceField>
                  <WorkspaceField label="Parentesco">
                    <input className="erp-input" value={form.emergencia_parentesco} onChange={(e) => setForm((p) => ({ ...p, emergencia_parentesco: e.target.value }))} />
                  </WorkspaceField>
                </div>
              </WorkspaceSection>
            </div>
          ),
        },
        {
          value: 'documentos',
          label: 'Documentos',
          icon: FileText,
          content: (
            <div className="space-y-4">
              <WorkspaceSection title="Carteira de Trabalho (CTPS)">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <WorkspaceField label="Número"><input className="erp-input" value={form.ctps_numero} onChange={(e) => setForm((p) => ({ ...p, ctps_numero: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="Série"><input className="erp-input" value={form.ctps_serie} onChange={(e) => setForm((p) => ({ ...p, ctps_serie: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="UF"><input className="erp-input" maxLength={2} value={form.ctps_uf} onChange={(e) => setForm((p) => ({ ...p, ctps_uf: e.target.value.toUpperCase() }))} /></WorkspaceField>
                  <WorkspaceField label="Data emissão"><input type="date" className="erp-input" value={form.ctps_emissao} onChange={(e) => setForm((p) => ({ ...p, ctps_emissao: e.target.value }))} /></WorkspaceField>
                </div>
              </WorkspaceSection>
              <WorkspaceSection title="PIS / PASEP">
                <WorkspaceField label="Número do PIS/PASEP">
                  <input className="erp-input" value={form.pis_pasep} onChange={(e) => setForm((p) => ({ ...p, pis_pasep: e.target.value }))} />
                </WorkspaceField>
              </WorkspaceSection>
              <WorkspaceSection title="Título de eleitor">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <WorkspaceField label="Número"><input className="erp-input" value={form.titulo_numero} onChange={(e) => setForm((p) => ({ ...p, titulo_numero: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="Zona"><input className="erp-input" value={form.titulo_zona} onChange={(e) => setForm((p) => ({ ...p, titulo_zona: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="Seção"><input className="erp-input" value={form.titulo_secao} onChange={(e) => setForm((p) => ({ ...p, titulo_secao: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="UF"><input className="erp-input" maxLength={2} value={form.titulo_uf} onChange={(e) => setForm((p) => ({ ...p, titulo_uf: e.target.value.toUpperCase() }))} /></WorkspaceField>
                </div>
              </WorkspaceSection>
              <WorkspaceSection title="CNH">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <WorkspaceField label="Número"><input className="erp-input" value={form.cnh_numero} onChange={(e) => setForm((p) => ({ ...p, cnh_numero: e.target.value }))} /></WorkspaceField>
                  <WorkspaceField label="Categoria"><input className="erp-input" value={form.cnh_categoria} onChange={(e) => setForm((p) => ({ ...p, cnh_categoria: e.target.value.toUpperCase() }))} /></WorkspaceField>
                  <WorkspaceField label="Validade"><input type="date" className="erp-input" value={form.cnh_validade} onChange={(e) => setForm((p) => ({ ...p, cnh_validade: e.target.value }))} /></WorkspaceField>
                </div>
              </WorkspaceSection>
              <WorkspaceSection title="Reservista">
                <WorkspaceField label="Número do reservista">
                  <input className="erp-input" value={form.reservista_numero} onChange={(e) => setForm((p) => ({ ...p, reservista_numero: e.target.value }))} />
                </WorkspaceField>
              </WorkspaceSection>
            </div>
          ),
        },
        {
          value: 'vinculos',
          label: 'Vínculos',
          icon: Briefcase,
          content: <VinculosTab colaboradorId={colaboradorAtual?.id ?? null} />,
        },
        {
          value: 'dependentes',
          label: 'Dependentes',
          icon: Users,
          content: <DependentesTab colaboradorId={colaboradorAtual?.id ?? null} />,
        },
        {
          value: 'funcoes',
          label: 'Funções',
          icon: Briefcase,
          content: (
            <WorkspaceSection
              title="Funções internas"
              description="Indicam como o colaborador participa da operação interna. Não substituem o perfil de acesso ao sistema."
            >
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {FUNCAO_CAMPOS.map((f) => (
                  <label
                    key={f.key}
                    className={
                      `flex items-center gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${form[f.key]
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-border hover:bg-muted/30'}`
                    }
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(form[f.key])}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, [f.key]: e.target.checked }))
                      }
                    />
                    <span className="text-sm">{f.label}</span>
                  </label>
                ))}
              </div>
            </WorkspaceSection>
          ),
        },
        {
          value: 'acesso',
          label: 'Acesso',
          icon: Key,
          content: (
            <ColaboradorAcessoSection
              colaborador={colaboradorAtual}
              onRefresh={() => void reload()}
            />
          ),
        },
      ]}
      activeTab={modalTab}
      onTabChange={setModalTab}
    />
  );
}