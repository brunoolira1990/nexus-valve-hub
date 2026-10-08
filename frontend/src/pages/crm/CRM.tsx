import { Link } from 'react-router-dom';
import { ArrowRight, BriefcaseBusiness, KanbanSquare, UsersRound } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { NexusCard } from '@/components/nexus/NexusCard';

const CRM = () => (
  <div>
    <PageHeader
      title="CRM"
      description="Relacionamento comercial, leads e oportunidades da Nexus Válvulas."
    />

    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Link to="/crm/leads" className="group">
        <NexusCard className="h-full transition-colors group-hover:border-primary/50">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="mb-3 inline-flex rounded-lg bg-primary/10 p-2 text-primary">
                <UsersRound className="h-5 w-5" />
              </div>
              <h2 className="text-base font-semibold">Leads</h2>
              <p className="mt-1 text-sm text-muted-foreground">Cadastre e qualifique novos prospects comerciais.</p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
          </div>
        </NexusCard>
      </Link>

      <Link to="/crm/oportunidades" className="group">
        <NexusCard className="h-full transition-colors group-hover:border-primary/50">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="mb-3 inline-flex rounded-lg bg-primary/10 p-2 text-primary">
                <KanbanSquare className="h-5 w-5" />
              </div>
              <h2 className="text-base font-semibold">Oportunidades</h2>
              <p className="mt-1 text-sm text-muted-foreground">Acompanhe negociações, etapas e previsão de fechamento.</p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
          </div>
        </NexusCard>
      </Link>

      <NexusCard className="h-full">
        <div className="mb-3 inline-flex rounded-lg bg-muted p-2 text-muted-foreground">
          <BriefcaseBusiness className="h-5 w-5" />
        </div>
        <h2 className="text-base font-semibold">Próxima evolução</h2>
        <p className="mt-1 text-sm text-muted-foreground">Atividades, timeline e conversão para proposta serão adicionadas na próxima fase.</p>
      </NexusCard>
    </div>

    <NexusCard className="mt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-semibold">Base comercial integrada</h2>
          <p className="mt-1 text-sm text-muted-foreground">O CRM reutiliza Cliente, Colaborador e Proposta, evitando cadastros duplicados.</p>
        </div>
        <div className="text-sm text-muted-foreground">CRM 1 · Leads e Oportunidades</div>
      </div>
    </NexusCard>
  </div>
);

export default CRM;
