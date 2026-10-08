import { useEffect, useState, type ReactNode } from 'react';
import {
  analiseFinanceiraService,
  type CapacidadeIntegracoesCredito,
} from '@/services/api/analiseFinanceira';

const CAP_DEFAULT: CapacidadeIntegracoesCredito = {
  cadastral: {
    configurado: false,
    disponivel: false,
    provider: null,
    produto: null,
    permite_consulta: false,
    motivo: 'PROVIDER_NAO_CONFIGURADO',
  },
  buro: {
    configurado: false,
    disponivel: false,
    provider: null,
    produto: null,
    permite_consulta: false,
    motivo: 'BURO_NAO_CONTRATADO',
  },
  decisao_financeira: 'MANUAL',
};

type Props = {
  /** Injeta capability (testes). Se omitido, carrega do endpoint. */
  capacidade?: CapacidadeIntegracoesCredito | null;
  carregarCapability?: boolean;
};

function Section({ title, children, testId }: { title: string; children: ReactNode; testId?: string }) {
  return (
    <section className="rounded border border-border bg-muted/20 p-3 space-y-3" data-testid={testId}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

export function SecoesIntegracoesExternas({ capacidade, carregarCapability = true }: Props) {
  const [cap, setCap] = useState<CapacidadeIntegracoesCredito | null>(capacidade ?? null);
  const [loading, setLoading] = useState(Boolean(carregarCapability && capacidade == null));
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (capacidade != null) {
      setCap(capacidade);
      setLoading(false);
      setErro(null);
      return;
    }
    if (!carregarCapability) {
      setCap(CAP_DEFAULT);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErro(null);
    analiseFinanceiraService
      .capacidadeIntegracoes()
      .then((data) => {
        if (!cancelled) {
          setCap(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setErro('Não foi possível carregar o estado das integrações externas.');
          setCap(CAP_DEFAULT);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [capacidade, carregarCapability]);

  const efetivo = cap || CAP_DEFAULT;
  const cadastralOk = Boolean(efetivo.cadastral?.permite_consulta);
  const buroOk = Boolean(efetivo.buro?.permite_consulta);
  // Fundação: nunca habilitar botões mesmo se capability vier inconsistente.
  const botaoCadastralHabilitado = false;
  const botaoBuroHabilitado = false;

  return (
    <div className="space-y-3" data-testid="dossie-integracoes-externas">
      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="dossie-integracoes-loading">
          Carregando estado das integrações externas…
        </p>
      ) : null}
      {erro ? (
        <p className="text-sm text-muted-foreground" role="status" data-testid="dossie-integracoes-erro">
          {erro}
        </p>
      ) : null}

      <Section title="Consulta cadastral externa" testId="dossie-cadastral">
        <p className="text-xs text-muted-foreground" data-testid="dossie-cadastral-estado">
          Estado: Provider não configurado · Nenhuma consulta realizada
        </p>
        <p className="text-sm text-muted-foreground" data-testid="dossie-cadastral-placeholder">
          A integração cadastral externa ainda não está configurada. Os dados internos do Nexus
          continuam disponíveis para análise manual.
        </p>
        <button
          type="button"
          className="erp-btn-secondary erp-btn-sm"
          disabled={!botaoCadastralHabilitado || Boolean(erro) || !cadastralOk}
          title="Provider não configurado"
          data-testid="dossie-btn-consultar-cadastral"
          aria-disabled="true"
        >
          Consultar dados cadastrais
        </button>
      </Section>

      <Section title="Birô de crédito" testId="dossie-buro">
        <p className="text-xs text-muted-foreground" data-testid="dossie-buro-estado">
          Estado: Birô não contratado · Nenhuma consulta realizada
        </p>
        <p className="text-sm text-muted-foreground" data-testid="dossie-buro-placeholder">
          Não há birô de crédito contratado ou configurado nesta fase.
        </p>
        <button
          type="button"
          className="erp-btn-secondary erp-btn-sm"
          disabled={!botaoBuroHabilitado || Boolean(erro) || !buroOk}
          title="Birô não contratado"
          data-testid="dossie-btn-consultar-buro"
          aria-disabled="true"
        >
          Consultar birô
        </button>
      </Section>

      <p className="text-sm font-medium" data-testid="dossie-decisao-manual">
        Decisão financeira: manual
      </p>
    </div>
  );
}
