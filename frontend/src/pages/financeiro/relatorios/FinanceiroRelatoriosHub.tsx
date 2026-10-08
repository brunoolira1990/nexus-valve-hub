import { Link } from 'react-router-dom';
import { BarChart3, ChevronRight } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { RELATORIOS_HUB } from '@/lib/relatorioFinanceiro';

export default function FinanceiroRelatoriosHub() {
  return (
    <div>
      <PageHeader
        title="Relatórios"
        description="Relatórios para acompanhar recebimentos, pagamentos, vencimentos e resultados financeiros previstos."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {RELATORIOS_HUB.map((rel) => (
          <Link
            key={rel.id}
            to={rel.path}
            className="erp-card p-5 hover:border-primary/40 transition-colors flex items-start gap-4 group"
          >
            <BarChart3 className="h-8 w-8 text-primary/70 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h2 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                {rel.titulo}
              </h2>
              <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{rel.descricao}</p>
              <span className="text-xs text-primary mt-3 inline-flex items-center gap-1">
                Abrir relatório
                <ChevronRight className="h-3 w-3" />
              </span>
            </div>
          </Link>
        ))}
      </div>

      <p className="text-xs text-muted-foreground mt-8 max-w-2xl">
        Relatórios operacionais somente leitura. O fluxo previsto não utiliza saldo bancário real e não
        substitui conciliação. Não é demonstração de resultados (DRE) contábil.
      </p>
    </div>
  );
}
