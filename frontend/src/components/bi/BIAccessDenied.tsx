import { Link } from 'react-router-dom';
import { ShieldOff } from 'lucide-react';

export function BIAccessDenied({
  modulo,
  message,
}: {
  modulo?: string;
  message?: string;
}) {
  const titulo = modulo ? `Painel ${modulo}` : 'Painel BI';
  return (
    <div className="erp-card max-w-lg mx-auto mt-8 p-8 text-center">
      <ShieldOff className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
      <h2 className="text-lg font-semibold text-foreground mb-2">Acesso restrito</h2>
      <p className="text-sm text-muted-foreground mb-6">
        {message ?? `Você não tem permissão para visualizar o ${titulo}.`}
      </p>
      <Link to="/dashboard" className="erp-btn-primary erp-btn-sm inline-flex">
        Voltar ao dashboard
      </Link>
    </div>
  );
}
