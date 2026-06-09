import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  DollarSign,
  FileText,
  TrendingUp,
} from 'lucide-react';
import { dashboardService, type DashboardResumo } from '@/services/api/dashboard';
import { ErrorState, LoadingState } from '@/components/list/ListStates';

function moneyBr(v: string | number | undefined) {
  const n = Number(v ?? 0);
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function CardLink({
  to,
  label,
  value,
  icon: Icon,
  color,
}: {
  to: string;
  label: string;
  value: string;
  icon: typeof DollarSign;
  color: string;
}) {
  return (
    <Link to={to} className="erp-card p-5 flex items-center gap-4 hover:border-primary/40 transition-colors">
      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-xl font-bold text-foreground">{value}</p>
      </div>
    </Link>
  );
}

function Block({
  title,
  to,
  children,
}: {
  title: string;
  to?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="erp-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">{title}</h3>
        {to ? (
          <Link to={to} className="text-sm text-primary hover:underline">
            Ver todos
          </Link>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function severityClass(sev: string) {
  if (sev === 'critico') return 'border-destructive/40 bg-destructive/10 text-destructive';
  if (sev === 'aviso') return 'border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100';
  return 'border-border bg-muted/40 text-muted-foreground';
}

const Dashboard = () => {
  const [data, setData] = useState<DashboardResumo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await dashboardService.getResumo());
    } catch {
      setData(null);
      setError('Não foi possível carregar o dashboard.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  if (loading) return <LoadingState message="Carregando dashboard…" />;
  if (error || !data) return <ErrorState message={error ?? 'Erro ao carregar dashboard.'} onRetry={() => void load()} />;

  const cards = data.cards_principais;
  const com = data.comercial;
  const fis = data.fiscal;
  const fin = data.financeiro;
  const est = data.estoque;

  return (
    <div>
      <h1 className="text-2xl font-bold text-foreground mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <CardLink
          to="/pedidos-venda?status=aberto"
          label="Valor a faturar"
          value={moneyBr(cards.valor_a_faturar)}
          icon={DollarSign}
          color="text-emerald-600 bg-emerald-50"
        />
        <CardLink
          to="/pedidos-venda?status=aberto"
          label="Pedidos abertos"
          value={String(cards.pedidos_abertos)}
          icon={FileText}
          color="text-blue-600 bg-blue-50"
        />
        <CardLink
          to="/nfe-saida?status_emissao=rejeitada_homologacao"
          label="NF-e pendentes/rejeitadas"
          value={String(cards.nfe_pendentes_rejeitadas)}
          icon={TrendingUp}
          color="text-violet-600 bg-violet-50"
        />
        <CardLink
          to="/estoque?filtro=baixo_estoque"
          label="Estoque baixo"
          value={`${cards.estoque_baixo} itens`}
          icon={AlertTriangle}
          color="text-amber-600 bg-amber-50"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Block title="Comercial" to="/pedidos-venda">
          <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
            <div><span className="text-muted-foreground">Abertos</span><p className="font-semibold">{com.pedidos_abertos}</p></div>
            <div><span className="text-muted-foreground">Parciais</span>
              <p className="font-semibold">
                <Link to="/pedidos-venda?status=parcialmente_faturado" className="hover:underline">
                  {com.pedidos_parcialmente_faturados}
                </Link>
              </p>
            </div>
            <div><span className="text-muted-foreground">Faturados no mês</span><p className="font-semibold">{com.pedidos_faturados_mes}</p></div>
            <div><span className="text-muted-foreground">Faturado mês</span><p className="font-semibold">{moneyBr(com.valor_faturado_mes)}</p></div>
          </div>
          {com.ultimos_pedidos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum pedido de venda encontrado.</p>
          ) : (
            <table className="erp-table text-sm">
              <thead><tr><th>PV</th><th>Cliente</th><th>Valor</th><th>Status</th></tr></thead>
              <tbody>
                {com.ultimos_pedidos.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/pedidos-venda?pedido=${p.id}`} className="text-primary hover:underline">{p.numero}</Link></td>
                    <td>{p.cliente}</td>
                    <td>{moneyBr(p.valor_total)}</td>
                    <td>{p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Block>

        <Block title="Fiscal" to="/nfe-saida">
          <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
            <div><span className="text-muted-foreground">Rascunhos</span><p className="font-semibold">{fis.nfe_saida_rascunhos}</p></div>
            <div><span className="text-muted-foreground">Autorizadas homolog.</span><p className="font-semibold">{fis.nfe_saida_autorizadas_homologacao}</p></div>
            <div><span className="text-muted-foreground">Rejeitadas homolog.</span><p className="font-semibold">{fis.nfe_saida_rejeitadas_homologacao}</p></div>
            <div><span className="text-muted-foreground">Erro transmissão</span><p className="font-semibold">{fis.nfe_saida_erro_transmissao}</p></div>
          </div>
          {fis.sefaz_ultimo_status ? (
            <p className="text-xs text-muted-foreground mb-3">
              SEFAZ {fis.sefaz_ultimo_status.ambiente}: cStat {fis.sefaz_ultimo_status.cstat} — {fis.sefaz_ultimo_status.xmotivo}
            </p>
          ) : null}
          {fis.ultimas_nfe_saida.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma NF-e encontrada.</p>
          ) : (
            <table className="erp-table text-sm">
              <thead><tr><th>NF-e</th><th>Cliente</th><th>Status</th><th>Valor</th></tr></thead>
              <tbody>
                {fis.ultimas_nfe_saida.map((n) => (
                  <tr key={n.id}>
                    <td>
                      <Link to={`/nfe-saida?nfe=${n.id}`} className="text-primary hover:underline">{n.titulo}</Link>
                      {n.subtitulo ? <p className="text-xs text-muted-foreground">{n.subtitulo}</p> : null}
                    </td>
                    <td>{n.cliente}</td>
                    <td>{n.status}{n.cstat ? ` (${n.cstat})` : ''}</td>
                    <td>{moneyBr(n.valor_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Block>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Block title="Financeiro">
          {fin.modulo === 'em_preparacao' ? (
            <p className="text-sm text-muted-foreground">{fin.mensagem}</p>
          ) : null}
          <div className="grid grid-cols-2 gap-3 text-sm mt-2">
            <div><span className="text-muted-foreground">A receber aberto</span><p className="font-semibold">{moneyBr(fin.contas_receber_aberto)}</p></div>
            <div><span className="text-muted-foreground">A pagar aberto</span><p className="font-semibold">{moneyBr(fin.contas_pagar_aberto)}</p></div>
          </div>
          <p className="text-xs text-muted-foreground mt-3">Financeiro ainda não possui títulos gerados.</p>
        </Block>

        <Block title="Estoque" to="/estoque">
          <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
            <div><span className="text-muted-foreground">Produtos</span><p className="font-semibold">{est.produtos_cadastrados}</p></div>
            <div><span className="text-muted-foreground">Sem NCM</span>
              <p className="font-semibold">
                <Link to="/produtos?sem_ncm=1" className="hover:underline">{est.produtos_sem_ncm}</Link>
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Estoque baixo</span>
              <p className="font-semibold">
                <Link to="/estoque?filtro=baixo_estoque" className="hover:underline">{est.produtos_estoque_baixo}</Link>
              </p>
            </div>
          </div>
          {est.alertas_estoque.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum alerta de estoque.</p>
          ) : (
            <table className="erp-table text-sm">
              <thead><tr><th>Produto</th><th>Saldo</th><th>Mínimo</th></tr></thead>
              <tbody>
                {est.alertas_estoque.map((a) => (
                  <tr key={a.produto_id}>
                    <td><Link to={`/produtos?produto=${a.produto_id}`} className="text-primary hover:underline">{a.codigo || a.descricao}</Link></td>
                    <td className="text-destructive font-medium">{a.saldo}</td>
                    <td>{a.minimo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Block>
      </div>

      <Block title="Alertas operacionais">
        {data.alertas.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum alerta crítico no momento.</p>
        ) : (
          <ul className="space-y-2">
            {data.alertas.map((a, i) => (
              <li key={`${a.tipo}-${i}`} className={`rounded-md border px-3 py-2 text-sm ${severityClass(a.severidade)}`}>
                <Link to={a.link} className="hover:underline">{a.mensagem}</Link>
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  );
};

export default Dashboard;
