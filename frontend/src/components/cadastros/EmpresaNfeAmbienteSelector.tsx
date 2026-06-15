import { ALERTA_PRODUCAO_NFE, NFE_AMBIENTE_OPCOES, type NfeAmbienteEmpresa } from '@/lib/empresaNfeAmbiente';

type Props = {
  value: NfeAmbienteEmpresa;
  producaoHabilitada?: boolean;
  onChange: (value: NfeAmbienteEmpresa) => void;
  disabled?: boolean;
};

export function EmpresaNfeAmbienteSelector({
  value,
  producaoHabilitada = false,
  onChange,
  disabled = false,
}: Props) {
  return (
    <div className="space-y-3" data-testid="empresa-nfe-ambiente-selector">
      <div>
        <p className="erp-label">Ambiente atual da NF-e</p>
        <p className="text-xs text-muted-foreground mt-1">
          Define o ambiente fiscal desejado para emissão desta empresa. A troca não altera numeração nem reserva
          números automaticamente.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {NFE_AMBIENTE_OPCOES.map((opcao) => {
          const selected = value === opcao.value;
          return (
            <button
              key={opcao.value}
              type="button"
              disabled={disabled}
              data-testid={`nfe-ambiente-${opcao.value}`}
              aria-pressed={selected}
              onClick={() => onChange(opcao.value)}
              className={`rounded-md border p-3 text-left transition-colors ${
                selected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : 'border-border hover:border-primary/40'
              } ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              <p className="font-medium text-sm">{opcao.label}</p>
              <p className="text-xs text-muted-foreground mt-1">{opcao.descricao}</p>
            </button>
          );
        })}
      </div>
      {value === 'producao' ? (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
          data-testid="alerta-producao-nfe"
        >
          {ALERTA_PRODUCAO_NFE}
          {!producaoHabilitada ? (
            <p className="mt-2 font-medium">NFE_PRODUCAO_HABILITADA=false — emissão produção permanece bloqueada.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
