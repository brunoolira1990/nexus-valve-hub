import { useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { StatusPipeline, type StatusStep } from '@/components/layout/StatusPipeline';
import {
  nfeSaidaStatusToSteps,
  pedidoVendaStatusToSteps,
  propostaStatusToSteps,
  type StatusPipelineState,
} from '@/lib/statusPipelineHelpers';

interface DemoConfig {
  titulo: string;
  opcoes: Array<{ valor: string; label: string }>;
  passoParaStatus: Record<string, string>;
  toSteps: (status: string) => StatusPipelineState;
}

const demos: DemoConfig[] = [
  {
    titulo: 'Proposta',
    opcoes: [
      { valor: 'PENDENTE', label: 'Pendente (Cotação)' },
      { valor: 'APROVADA', label: 'Aprovada' },
      { valor: 'CONVERTIDA', label: 'Convertida (Pedido de Venda)' },
      { valor: 'PARCIALMENTE_CONVERTIDA', label: 'Parcialmente convertida' },
      { valor: 'REABERTA', label: 'Reaberta' },
      { valor: 'REJEITADA', label: 'Rejeitada' },
      { valor: 'CANCELADA', label: 'Cancelada' },
    ],
    passoParaStatus: { cotacao: 'PENDENTE', aprovada: 'APROVADA', pedido_venda: 'CONVERTIDA' },
    toSteps: (status) => propostaStatusToSteps({ status }),
  },
  {
    titulo: 'Pedido de Venda',
    opcoes: [
      { valor: 'ABERTO', label: 'Aberto' },
      { valor: 'APROVADO', label: 'Aprovado' },
      { valor: 'EM_FATURAMENTO', label: 'Em faturamento' },
      { valor: 'PARCIALMENTE_FATURADO', label: 'Parcialmente faturado' },
      { valor: 'FATURADO', label: 'Faturado' },
      { valor: 'CANCELADO', label: 'Cancelado' },
    ],
    passoParaStatus: {
      aberto: 'ABERTO',
      aprovado: 'APROVADO',
      em_faturamento: 'EM_FATURAMENTO',
      faturado: 'FATURADO',
    },
    toSteps: (status) => pedidoVendaStatusToSteps({ status }),
  },
  {
    titulo: 'NF-e Saída',
    opcoes: [
      { valor: 'RASCUNHO', label: 'Rascunho' },
      { valor: 'PRONTA', label: 'Pronta para emissão' },
      { valor: 'AUTORIZADA', label: 'Autorizada' },
      { valor: 'AUTORIZADA_HOMOLOGACAO', label: 'Autorizada (homologação)' },
      { valor: 'REJEITADA', label: 'Rejeitada' },
      { valor: 'CANCELADA', label: 'Cancelada' },
    ],
    passoParaStatus: { rascunho: 'RASCUNHO', pronta: 'PRONTA', autorizada: 'AUTORIZADA' },
    toSteps: (status) => nfeSaidaStatusToSteps({ status }),
  },
];

function DemoBloco({ config }: { config: DemoConfig }) {
  const [status, setStatus] = useState(config.opcoes[0].valor);
  const { steps, currentKey } = config.toSteps(status);

  return (
    <section className="erp-card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-700">{config.titulo}</h2>
        <label className="flex items-center gap-2 text-xs text-slate-500">
          status bruto
          <select
            className="erp-select rounded border border-slate-300 px-2 py-1 text-xs"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {config.opcoes.map((opcao) => (
              <option key={opcao.valor} value={opcao.valor}>
                {opcao.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <StatusPipeline
        steps={steps}
        currentKey={currentKey}
        onChange={(key) => {
          const novo = config.passoParaStatus[key];
          if (novo) setStatus(novo);
        }}
      />
      <div className="flex flex-wrap items-center gap-4">
        <span className="text-xs text-slate-500">variantes:</span>
        {(['arrow', 'pill'] as const).map((variant) => (
          <StatusPipeline key={variant} steps={steps as StatusStep[]} currentKey={currentKey} variant={variant} />
        ))}
      </div>
    </section>
  );
}

export default function StatusPipelineDemo() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="StatusPipeline — demo"
        description="Rota temporária de desenvolvimento (/_status-pipeline-demo). componente universal de estágios estilo Odoo."
      />
      {demos.map((config) => (
        <DemoBloco key={config.titulo} config={config} />
      ))}
      <section className="erp-card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-slate-700">Somente leitura</h2>
        <StatusPipeline
          steps={propostaStatusToSteps({ status: 'APROVADA' }).steps}
          currentKey="aprovada"
          somenteLeitura
        />
      </section>
    </div>
  );
}
