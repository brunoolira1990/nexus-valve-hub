import { StatusBadge } from '@/components/nexus/StatusBadge';

export type ClassificacaoDfe = {
  categoria?: string;
  homologacao?: boolean;
  pode_entrar_apuracao?: boolean;
  pode_alimentar_precificacao?: boolean;
  pode_gerar_efeito_operacional?: boolean;
  conferencia_status?: string | null;
  badges?: string[];
};

const BADGE_ORDER = [
  'base_importada',
  'operacional',
  'homologacao',
  'producao',
  'apura',
  'fora_apuracao',
  'sem_valor_fiscal',
  'sem_efeito_operacional_automatico',
  'alimenta_precificacao',
  'conferida',
  'preparada',
  'divergente',
  'cancelada',
] as const;

type Props = {
  classificacao?: ClassificacaoDfe | null;
  max?: number;
};

export function DfeClassificacaoBadges({ classificacao, max = 4 }: Props) {
  if (!classificacao) return null;

  const raw = classificacao.badges?.length
    ? classificacao.badges
    : [
        classificacao.categoria === 'BASE_DFE_IMPORTADA' ? 'base_importada' : null,
        classificacao.categoria === 'OPERACIONAL' ? 'operacional' : null,
        classificacao.homologacao ? 'homologacao' : null,
        classificacao.homologacao ? 'fora_apuracao' : null,
        classificacao.pode_entrar_apuracao ? 'apura' : classificacao.homologacao ? null : 'fora_apuracao',
        classificacao.pode_alimentar_precificacao ? 'alimenta_precificacao' : null,
        classificacao.pode_gerar_efeito_operacional === false && classificacao.categoria === 'BASE_DFE_IMPORTADA'
          ? 'sem_efeito_operacional_automatico'
          : null,
        classificacao.conferencia_status === 'CONFERIDA' ? 'conferida' : null,
        classificacao.conferencia_status === 'PREPARADA' ? 'preparada' : null,
        classificacao.conferencia_status === 'DIVERGENTE' ? 'divergente' : null,
      ].filter(Boolean);

  const ordered = BADGE_ORDER.filter((b) => raw.includes(b));
  const extras = raw.filter((b) => !BADGE_ORDER.includes(b as (typeof BADGE_ORDER)[number]));
  const tokens = [...ordered, ...extras].slice(0, max);

  if (!tokens.length) return null;

  return (
    <span className="inline-flex flex-wrap gap-1">
      {tokens.map((t) => (
        <StatusBadge key={t} status={t} />
      ))}
    </span>
  );
}
