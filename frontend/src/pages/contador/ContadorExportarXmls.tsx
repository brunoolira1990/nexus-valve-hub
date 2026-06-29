import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { apiErrorMessage } from '@/services/api/config';
import { contadorService } from '@/services/api/contador';

const TIPOS = [
  { value: 'todos', label: 'Todos os tipos' },
  { value: 'nfe_saida', label: 'NF-e Saída' },
  { value: 'nfe_entrada', label: 'NF-e Entrada' },
  { value: 'cte', label: 'CT-e' },
] as const;

function primeiroDiaMesAtual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function ContadorExportarXmls() {
  const defaults = useMemo(
    () => ({ inicio: primeiroDiaMesAtual(), fim: hojeIso(), tipo: 'todos' as const }),
    [],
  );
  const [inicio, setInicio] = useState(defaults.inicio);
  const [fim, setFim] = useState(defaults.fim);
  const [tipo, setTipo] = useState<(typeof TIPOS)[number]['value']>(defaults.tipo);
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const blob = await contadorService.exportarXmls({ inicio, fim, tipo });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nexus-xmls-${inicio}-${fim}-${tipo}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Pacote ZIP gerado com sucesso.');
    } catch (err) {
      toast.error(apiErrorMessage(err, { fallback: 'Não foi possível exportar os XMLs.' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader
        title="Exportar XMLs"
        description="Gere um pacote ZIP com os XMLs fiscais armazenados no período selecionado, organizados em pastas por tipo (NF-e saída, NF-e entrada e CT-e)."
      />

      <div className="erp-card p-6 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1.5 block">
            <span className="text-sm font-medium">Data inicial</span>
            <input
              type="date"
              className="erp-input w-full"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
            />
          </label>
          <label className="space-y-1.5 block">
            <span className="text-sm font-medium">Data final</span>
            <input
              type="date"
              className="erp-input w-full"
              value={fim}
              onChange={(e) => setFim(e.target.value)}
            />
          </label>
        </div>

        <label className="space-y-1.5 block">
          <span className="text-sm font-medium">Tipo de documento</span>
          <select className="erp-input w-full" value={tipo} onChange={(e) => setTipo(e.target.value as typeof tipo)}>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        <p className="text-xs text-muted-foreground leading-relaxed">
          O ZIP é organizado em pastas (<span className="font-mono">nfe-saida/</span>,{' '}
          <span className="font-mono">nfe-entrada/</span>, <span className="font-mono">cte/</span>) — só as que
          tiverem documentos no período. Inclui NF-e de saída autorizadas, NF-e de entrada operacional e bases
          importadas, além de CT-e da base importada com XML armazenado.
        </p>

        <NexusButton type="button" onClick={() => void handleExport()} disabled={loading || !inicio || !fim}>
          {loading ? 'Gerando ZIP…' : 'Baixar pacote ZIP'}
        </NexusButton>
      </div>
    </div>
  );
}
