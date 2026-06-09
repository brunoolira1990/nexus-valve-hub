import { useCallback, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { labelDestinatario } from '@/lib/regrasFiscaisSaidaHelpers';
import { regrasFiscaisSaidaService } from '@/services/api/regras-fiscais-saida';
import type { CoberturaPropostasFiscalSaida, LacunaCoberturaProposta, StatusComparativoFiscalSaida } from '@/types';
import { UFS } from '@/types';

function hojeIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function diasAtrasIso(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return d.toISOString().slice(0, 10);
}

function labelStatusComparativo(status: StatusComparativoFiscalSaida): string {
  switch (status) {
    case 'IGUAL':
      return 'Igual';
    case 'DIVERGENTE':
      return 'Divergente';
    case 'CENARIO_NAO_ENCONTRADO':
      return 'Cenário não encontrado';
    case 'LEGADO_NAO_ENCONTRADO':
      return 'Legado não encontrado';
    case 'AMBOS_NAO_ENCONTRADOS':
      return 'Nenhum encontrado';
    default:
      return status;
  }
}

function badgeStatus(status: StatusComparativoFiscalSaida): string {
  switch (status) {
    case 'IGUAL':
      return 'erp-badge-success';
    case 'DIVERGENTE':
      return 'erp-badge-warning';
    default:
      return 'erp-badge-secondary';
  }
}

function resumoDivergencias(
  divergencias: { label: string; legado: string; cenario: string }[],
): string {
  if (!divergencias.length) return '—';
  return divergencias
    .slice(0, 2)
    .map((d) => `${d.label}: legado ${d.legado} · cenário ${d.cenario}`)
    .join(' · ');
}

type Props = {
  cenarioId?: number;
  onCriarRegraLacuna?: (lacuna: LacunaCoberturaProposta) => void;
};

export const HomologacaoCenarioSaidaPanel = ({ cenarioId, onCriarRegraLacuna }: Props) => {
  const [aberto, setAberto] = useState(false);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState('');
  const [dados, setDados] = useState<CoberturaPropostasFiscalSaida | null>(null);

  const [dataInicial, setDataInicial] = useState(() => diasAtrasIso(90));
  const [dataFinal, setDataFinal] = useState(hojeIso);
  const [propostaId, setPropostaId] = useState('');
  const [ncm, setNcm] = useState('');
  const [ufOrigem, setUfOrigem] = useState('');
  const [ufDestino, setUfDestino] = useState('');
  const [somenteDivergentes, setSomenteDivergentes] = useState(false);
  const [somenteSemCenario, setSomenteSemCenario] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro('');
    try {
      const r = await regrasFiscaisSaidaService.coberturaPropostas({
        data_inicial: dataInicial || undefined,
        data_final: dataFinal || undefined,
        proposta_id: propostaId.trim() ? Number(propostaId) : undefined,
        ncm: ncm.trim() || undefined,
        uf_origem: ufOrigem || undefined,
        uf_destino: ufDestino || undefined,
        somente_divergentes: somenteDivergentes,
        somente_sem_cenario: somenteSemCenario,
        limite: 50,
        cenario_id: cenarioId,
      });
      setDados(r);
    } catch {
      setErro('Não foi possível carregar a cobertura fiscal agora.');
      setDados(null);
    } finally {
      setLoading(false);
    }
  }, [
    cenarioId,
    dataFinal,
    dataInicial,
    ncm,
    propostaId,
    somenteDivergentes,
    somenteSemCenario,
    ufDestino,
    ufOrigem,
  ]);

  const resumoCards = useMemo(() => {
    if (!dados) return [];
    const s = dados.resumo;
    return [
      { label: 'Total analisado', value: s.total_itens },
      { label: 'Iguais', value: s.iguais },
      { label: 'Divergentes', value: s.divergentes },
      { label: 'Cenário não encontrado', value: s.cenario_nao_encontrado },
      { label: 'Legado não encontrado', value: s.legado_nao_encontrado },
      { label: 'Nenhum encontrado', value: s.ambos_nao_encontrados },
      { label: 'Cobertura cenário', value: `${s.percentual_cobertura_cenario}%` },
      { label: 'Iguais (ambos achados)', value: `${s.percentual_iguais_entre_encontrados}%` },
    ];
  }, [dados]);

  return (
    <div className="mt-4 border border-border rounded-md overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left bg-muted/30 hover:bg-muted/50 text-sm font-medium"
        onClick={() => setAberto((v) => !v)}
      >
        {aberto ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        Homologação do cenário fiscal (propostas)
      </button>
      {aberto ? (
        <div className="p-3 space-y-4 border-t border-border">
          <p className="text-[11px] text-muted-foreground leading-snug max-w-3xl">
            Este painel é apenas para homologação. O cálculo oficial das propostas continua usando a regra fiscal
            legada enquanto a feature flag estiver desligada. Após validar a cobertura, ative o cenário em propostas
            específicas (fonte fiscal da proposta) antes de ligar a flag global. Divergências não bloqueiam propostas
            nesta fase.
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

          <div className="flex flex-wrap items-center gap-4 text-xs">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={somenteDivergentes}
                onChange={(e) => setSomenteDivergentes(e.target.checked)}
              />
              Somente divergentes
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={somenteSemCenario}
                onChange={(e) => setSomenteSemCenario(e.target.checked)}
              />
              Somente sem cenário
            </label>
            <button
              type="button"
              className="erp-btn-primary erp-btn-sm flex items-center gap-1"
              disabled={loading}
              onClick={() => void carregar()}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Carregando…' : 'Analisar cobertura'}
            </button>
          </div>

          {erro ? <p className="text-xs text-destructive">{erro}</p> : null}

          {dados ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
                {resumoCards.map((c) => (
                  <div key={c.label} className="erp-card p-2 text-center">
                    <p className="text-[10px] text-muted-foreground">{c.label}</p>
                    <p className="text-sm font-semibold mt-0.5">{c.value}</p>
                  </div>
                ))}
              </div>
              {dados.resumo.itens_ignorados_sem_contexto > 0 ? (
                <p className="text-[10px] text-muted-foreground">
                  {dados.resumo.itens_ignorados_sem_contexto} item(ns) ignorado(s) por NCM/UF incompletos no período
                  analisado.
                </p>
              ) : null}

              {dados.itens.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Nenhum item encontrado para os filtros informados.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="erp-table text-xs w-full min-w-[720px]">
                    <thead>
                      <tr>
                        <th>Proposta</th>
                        <th>Produto</th>
                        <th>NCM</th>
                        <th>UF</th>
                        <th>Status</th>
                        <th>Divergências</th>
                        <th>Cenário</th>
                        <th>Legado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dados.itens.map((row) => (
                        <tr key={row.item_id}>
                          <td>{row.proposta_numero}</td>
                          <td>
                            <span className="font-mono text-[10px]">{row.produto_codigo || '—'}</span>
                            <br />
                            <span className="text-muted-foreground">{row.produto_descricao || '—'}</span>
                          </td>
                          <td className="font-mono">{row.ncm}</td>
                          <td>
                            {row.uf_origem}→{row.uf_destino}
                          </td>
                          <td>
                            <span className={`${badgeStatus(row.status)} text-[10px]`}>
                              {labelStatusComparativo(row.status)}
                            </span>
                          </td>
                          <td className="max-w-[200px] truncate" title={resumoDivergencias(row.divergencias)}>
                            {resumoDivergencias(row.divergencias)}
                          </td>
                          <td>
                            {row.cenario.encontrado
                              ? `#${row.cenario.regra_id} CFOP ${row.cenario.cfop}`
                              : '—'}
                          </td>
                          <td>
                            {row.legado.encontrado ? `#${row.legado.regra_id} CFOP ${row.legado.cfop}` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {dados.lacunas.length > 0 ? (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                    Lacunas de cadastro no cenário
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="erp-table text-xs w-full min-w-[640px]">
                      <thead>
                        <tr>
                          <th>NCM</th>
                          <th>UF origem</th>
                          <th>UF destino</th>
                          <th>Perfil</th>
                          <th>Qtd itens</th>
                          <th>Status</th>
                          <th>Ação</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dados.lacunas.map((lac) => (
                          <tr key={`${lac.ncm}-${lac.uf_origem}-${lac.uf_destino}-${lac.destinatario_contribuinte}`}>
                            <td className="font-mono">{lac.ncm}</td>
                            <td>{lac.uf_origem}</td>
                            <td>{lac.uf_destino}</td>
                            <td>
                              {lac.destinatario_contribuinte
                                ? labelDestinatario(lac.destinatario_contribuinte)
                                : '—'}
                            </td>
                            <td>{lac.quantidade_itens}</td>
                            <td>{labelStatusComparativo(lac.status_predominante)}</td>
                            <td>
                              {onCriarRegraLacuna ? (
                                <button
                                  type="button"
                                  className="erp-btn-ghost erp-btn-sm h-7 text-[10px]"
                                  onClick={() => onCriarRegraLacuna(lac)}
                                >
                                  Criar regra no cenário
                                </button>
                              ) : (
                                <span className="text-muted-foreground">{lac.acao_sugerida}</span>
                              )}
                            </td>
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
