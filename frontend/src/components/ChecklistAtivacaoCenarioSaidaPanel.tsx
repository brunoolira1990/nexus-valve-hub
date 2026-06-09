import { useCallback, useState } from 'react';
import { ChevronDown, ChevronRight, ClipboardCheck } from 'lucide-react';
import { labelDestinatario } from '@/lib/regrasFiscaisSaidaHelpers';
import { regrasFiscaisSaidaService } from '@/services/api/regras-fiscais-saida';
import type {
  ChecklistAtivacaoCenarioSaida,
  StatusChecklistAtivacao,
  StatusCriterioChecklist,
} from '@/types';
import { UFS } from '@/types';

function hojeIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function diasAtrasIso(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return d.toISOString().slice(0, 10);
}

function badgeStatusGeral(status: StatusChecklistAtivacao): string {
  switch (status) {
    case 'PODE_ATIVAR':
      return 'erp-badge-success';
    case 'ATENCAO':
      return 'erp-badge-warning';
    default:
      return 'erp-badge-danger';
  }
}

function badgeCriterio(status: StatusCriterioChecklist): string {
  switch (status) {
    case 'OK':
      return 'erp-badge-success';
    case 'ATENCAO':
      return 'erp-badge-warning';
    default:
      return 'erp-badge-danger';
  }
}

function labelValorCriterio(codigo: string, valor: string, limite: string): string {
  if (codigo === 'AMOSTRA_MINIMA') {
    return `${valor} itens (mín. recomendado ${limite})`;
  }
  return `${valor}% (limite ${limite}%)`;
}

type Props = {
  cenarioId?: number;
};

export const ChecklistAtivacaoCenarioSaidaPanel = ({ cenarioId }: Props) => {
  const [aberto, setAberto] = useState(false);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState('');
  const [dados, setDados] = useState<ChecklistAtivacaoCenarioSaida | null>(null);

  const [dataInicial, setDataInicial] = useState(() => diasAtrasIso(90));
  const [dataFinal, setDataFinal] = useState(hojeIso);
  const [propostaId, setPropostaId] = useState('');
  const [ncm, setNcm] = useState('');
  const [ufOrigem, setUfOrigem] = useState('');
  const [ufDestino, setUfDestino] = useState('');

  const verificar = useCallback(async () => {
    setLoading(true);
    setErro('');
    try {
      const r = await regrasFiscaisSaidaService.checklistAtivacao({
        data_inicial: dataInicial || undefined,
        data_final: dataFinal || undefined,
        proposta_id: propostaId.trim() ? Number(propostaId) : undefined,
        ncm: ncm.trim() || undefined,
        uf_origem: ufOrigem || undefined,
        uf_destino: ufDestino || undefined,
        limite: 500,
        cenario_id: cenarioId,
      });
      setDados(r);
    } catch {
      setErro('Não foi possível verificar a prontidão agora.');
      setDados(null);
    } finally {
      setLoading(false);
    }
  }, [cenarioId, dataFinal, dataInicial, ncm, propostaId, ufDestino, ufOrigem]);

  return (
    <div className="mt-4 border border-border rounded-md overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left bg-muted/30 hover:bg-muted/50 text-sm font-medium"
        onClick={() => setAberto((v) => !v)}
      >
        {aberto ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        <ClipboardCheck className="h-4 w-4 shrink-0 text-muted-foreground" />
        Checklist para ativação global
      </button>
      {aberto ? (
        <div className="p-3 space-y-4 border-t border-border">
          <p className="text-[11px] text-muted-foreground leading-snug max-w-3xl">
            Este checklist não ativa a flag global. Ele apenas ajuda a decidir se o cenário fiscal de saída está pronto
            para ser usado como fonte oficial nas propostas. Para ativar globalmente, ajuste{' '}
            <code className="text-[10px]">USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=true</code> no backend e{' '}
            <code className="text-[10px]">VITE_USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=true</code> no frontend.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
            <div>
              <label className="text-[10px] text-muted-foreground">Data inicial</label>
              <input
                type="date"
                className="erp-input h-8 text-xs mt-0.5 w-full"
                value={dataInicial}
                onChange={(e) => setDataInicial(e.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground">Data final</label>
              <input
                type="date"
                className="erp-input h-8 text-xs mt-0.5 w-full"
                value={dataFinal}
                onChange={(e) => setDataFinal(e.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground">Proposta (id)</label>
              <input
                className="erp-input h-8 text-xs mt-0.5 w-full"
                value={propostaId}
                onChange={(e) => setPropostaId(e.target.value)}
                placeholder="Opcional"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground">NCM</label>
              <input
                className="erp-input h-8 text-xs mt-0.5 w-full font-mono"
                value={ncm}
                onChange={(e) => setNcm(e.target.value)}
                placeholder="Opcional"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground">UF origem</label>
              <select
                className="erp-input h-8 text-xs mt-0.5 w-full"
                value={ufOrigem}
                onChange={(e) => setUfOrigem(e.target.value)}
              >
                <option value="">Todas</option>
                {UFS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground">UF destino</label>
              <select
                className="erp-input h-8 text-xs mt-0.5 w-full"
                value={ufDestino}
                onChange={(e) => setUfDestino(e.target.value)}
              >
                <option value="">Todas</option>
                {UFS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="button"
            className="erp-btn-primary erp-btn-sm"
            disabled={loading}
            onClick={() => void verificar()}
          >
            {loading ? 'Verificando…' : 'Verificar prontidão para ativação global'}
          </button>

          {erro ? <p className="text-xs text-destructive">{erro}</p> : null}

          {dados ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">Status geral:</span>
                <span className={`${badgeStatusGeral(dados.status)} text-xs px-2 py-0.5`}>{dados.label}</span>
              </div>

              {dados.status === 'PODE_ATIVAR' ? (
                <p className="text-[11px] text-emerald-800 dark:text-emerald-300 border border-emerald-500/30 bg-emerald-500/10 rounded px-3 py-2">
                  O cenário fiscal parece pronto para ativação global, mas a decisão final ainda deve ser feita via
                  configuração de ambiente.
                </p>
              ) : null}
              {dados.status === 'NAO_RECOMENDADO' ? (
                <p className="text-[11px] text-destructive border border-destructive/30 bg-destructive/5 rounded px-3 py-2">
                  Não recomendamos ativar a flag global ainda. Corrija as lacunas e divergências indicadas.
                </p>
              ) : null}

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                <div className="erp-card p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">Cobertura cenário</p>
                  <p className="text-sm font-semibold">{dados.resumo.percentual_cobertura_cenario}%</p>
                </div>
                <div className="erp-card p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">Divergências</p>
                  <p className="text-sm font-semibold">{dados.resumo.percentual_divergentes}%</p>
                </div>
                <div className="erp-card p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">Sem cenário</p>
                  <p className="text-sm font-semibold">{dados.resumo.percentual_sem_cenario}%</p>
                </div>
                <div className="erp-card p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">Amostra</p>
                  <p className="text-sm font-semibold">{dados.resumo.total_itens} itens</p>
                </div>
                <div className="erp-card p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">Iguais</p>
                  <p className="text-sm font-semibold">{dados.resumo.iguais}</p>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Critérios</h4>
                <ul className="space-y-2">
                  {dados.criterios.map((c) => (
                    <li
                      key={c.codigo}
                      className="flex flex-wrap items-start gap-2 text-xs border border-border rounded px-2 py-1.5"
                    >
                      <span className={`${badgeCriterio(c.status)} text-[10px] shrink-0`}>{c.status}</span>
                      <div className="min-w-0 flex-1">
                        <span className="font-medium">{c.label}</span>
                        <span className="text-muted-foreground ml-1">
                          {labelValorCriterio(c.codigo, c.valor, c.limite)}
                        </span>
                        <p className="text-muted-foreground mt-0.5">{c.mensagem}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {dados.recomendacoes.length > 0 ? (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                    Recomendações
                  </h4>
                  <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
                    {dados.recomendacoes.map((rec) => (
                      <li key={rec}>{rec}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {dados.lacunas_prioritarias.length > 0 ? (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                    Lacunas prioritárias
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="erp-table text-xs w-full min-w-[640px]">
                      <thead>
                        <tr>
                          <th>NCM</th>
                          <th>UF</th>
                          <th>Perfil</th>
                          <th>Qtd</th>
                          <th>Ação sugerida</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dados.lacunas_prioritarias.map((lac) => (
                          <tr key={`${lac.ncm}-${lac.uf_origem}-${lac.uf_destino}`}>
                            <td className="font-mono">{lac.ncm}</td>
                            <td>
                              {lac.uf_origem}→{lac.uf_destino}
                            </td>
                            <td>
                              {lac.destinatario_contribuinte
                                ? labelDestinatario(lac.destinatario_contribuinte)
                                : '—'}
                            </td>
                            <td>{lac.quantidade_itens}</td>
                            <td className="text-muted-foreground">{lac.acao_sugerida}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};
