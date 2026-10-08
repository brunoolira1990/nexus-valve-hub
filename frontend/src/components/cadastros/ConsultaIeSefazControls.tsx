import { CadastroButton } from '@/components/ui/cadastro';
import { ConsultaIeSefazPanel } from '@/components/cadastros/ConsultaIeSefazPanel';
import type { UseConsultaIeSefazReturn } from '@/hooks/useConsultaIeSefaz';
import {
  labelAcaoSecundariaConsultaIe,
  MENSAGEM_IE_PREENCHIDA_SEFAZ,
  MENSAGEM_UF_PENDENTE_IE,
  mensagemIePreenchidaNoFormulario,
  podeConsultarIeSefaz,
  resolverEstadoUiConsultaIe,
} from '@/lib/consultaIeCadastro';

type Props = {
  consultaIe: UseConsultaIeSefazReturn;
  getCnpj: () => string;
  getUf: () => string;
  getIeAtual: () => string;
  onAplicarIe: (valor: string) => void;
  className?: string;
};

function AcaoSecundariaConsultaIe({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export function ConsultaIeSefazControls({
  consultaIe,
  getCnpj,
  getUf,
  getIeAtual,
  onAplicarIe,
  className,
}: Props) {
  const {
    ieLookupLoading,
    ieLookupMessage,
    ieSugestao,
    ieOpcoes,
    iePreenchidaPelaSefaz,
    setIePreenchidaPelaSefaz,
    runIeLookupManual,
    aplicarIeSugestao,
    setIeLookupMessage,
    setIeOpcoes,
  } = consultaIe;

  const cnpjAtual = getCnpj();
  const ufAtual = (getUf() || '').trim();
  const ieAtual = (getIeAtual() || '').trim();
  const bloqueioConsulta = podeConsultarIeSefaz(cnpjAtual, ufAtual);
  const podeConsultar = !bloqueioConsulta && !ieLookupLoading;

  const estado = resolverEstadoUiConsultaIe({
    loading: ieLookupLoading,
    uf: ufAtual,
    ieAtual,
    preenchidaPelaSefaz: iePreenchidaPelaSefaz,
    ieSugestao,
    ieOpcoes,
    mensagem: ieLookupMessage,
  });

  const handleConsultar = () => {
    if (!podeConsultar) {
      if (bloqueioConsulta) setIeLookupMessage(bloqueioConsulta);
      return;
    }
    void runIeLookupManual(cnpjAtual, ufAtual, ieAtual, onAplicarIe);
  };

  const handleAplicar = (valor: string) => {
    onAplicarIe(valor);
    aplicarIeSugestao();
    setIeOpcoes([]);
    setIePreenchidaPelaSefaz(true);
    setIeLookupMessage(mensagemIePreenchidaNoFormulario(valor));
  };

  const labelSecundaria = labelAcaoSecundariaConsultaIe(estado);
  const mensagemExibida = ieLookupLoading
    ? 'Consultando IE na SEFAZ…'
    : estado === 'preenchida_sefaz'
      ? MENSAGEM_IE_PREENCHIDA_SEFAZ
      : estado === 'uf_pendente'
        ? MENSAGEM_UF_PENDENTE_IE
        : ieLookupMessage ??
          (ufAtual
            ? `UF ${ufAtual.toUpperCase()} será usada na consulta SEFAZ.`
            : MENSAGEM_UF_PENDENTE_IE);

  const mensagemDestaque =
    estado === 'preenchida_sefaz'
      ? 'text-emerald-700 dark:text-emerald-300'
      : estado === 'erro' || estado === 'uf_pendente'
        ? 'text-amber-700 dark:text-amber-300'
        : 'text-muted-foreground';

  return (
    <div className={className ?? 'md:col-span-2 space-y-2'} data-testid="consulta-ie-sefaz-controls">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span className={mensagemDestaque}>{mensagemExibida}</span>

        {estado === 'principal' ? (
          <CadastroButton
            type="button"
            variant="outline"
            disabled={!podeConsultar}
            onClick={handleConsultar}
          >
            Consultar IE na SEFAZ
          </CadastroButton>
        ) : null}

        {estado !== 'principal' && estado !== 'loading' && estado !== 'opcoes' ? (
          <AcaoSecundariaConsultaIe
            label={labelSecundaria}
            disabled={!podeConsultar}
            onClick={handleConsultar}
          />
        ) : null}
      </div>

      <ConsultaIeSefazPanel sugestao={ieSugestao} opcoes={ieOpcoes} onAplicarIe={handleAplicar} />
    </div>
  );
}
