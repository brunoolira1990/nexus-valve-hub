import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { Textarea } from '@/components/ui/textarea';
import {
  nfeNumeracoesService,
  nfeSaidasService,
  type NFeInutilizacaoDadosResponse,
  type NFeInutilizacaoResponse,
} from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';

export const TAMANHO_MINIMO_JUSTIFICATIVA_INUT = 15;
export const TEXTO_CONFIRMACAO_PRODUCAO_INUT = 'INUTILIZAR';

type Etapa = 'formulario' | 'confirmacao' | 'transmitindo' | 'resultado' | 'erro';

type Props =
  | {
      mode: 'config';
      open: boolean;
      configuracaoId: number | null;
      onClose: () => void;
      onInutilizada?: (res: NFeInutilizacaoResponse) => void;
      nfeId?: never;
    }
  | {
      mode: 'nfe';
      open: boolean;
      nfeId: number | null;
      onClose: () => void;
      onInutilizada?: (res: NFeInutilizacaoResponse) => void;
      configuracaoId?: never;
    };

export function NFeInutilizacaoModal(props: Props) {
  const { open, onClose, onInutilizada, mode } = props;
  const entityId = mode === 'config' ? props.configuracaoId : props.nfeId;

  const [etapa, setEtapa] = useState<Etapa>('formulario');
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [dados, setDados] = useState<NFeInutilizacaoDadosResponse | null>(null);
  const [justificativa, setJustificativa] = useState('');
  const [numeroInicial, setNumeroInicial] = useState('');
  const [numeroFinal, setNumeroFinal] = useState('');
  const [confirmarProducao, setConfirmarProducao] = useState(false);
  const [textoConfirmacao, setTextoConfirmacao] = useState('');
  const [resultado, setResultado] = useState<NFeInutilizacaoResponse | null>(null);

  useEffect(() => {
    if (!open || !entityId) {
      setEtapa('formulario');
      setDados(null);
      setJustificativa('');
      setNumeroInicial('');
      setNumeroFinal('');
      setConfirmarProducao(false);
      setTextoConfirmacao('');
      setErro(null);
      setResultado(null);
      return;
    }
    setLoading(true);
    setErro(null);
    const load =
      mode === 'config'
        ? nfeNumeracoesService.inutilizacaoDados(entityId)
        : nfeSaidasService.inutilizacaoDados(entityId);
    void load
      .then((payload) => {
        setDados(payload);
        const ini = payload.numero_inicial_sugerido;
        const fim = payload.numero_final_sugerido ?? ini;
        if (ini != null) setNumeroInicial(String(ini));
        if (fim != null) setNumeroFinal(String(fim));
        if (!payload.pode_inutilizar) {
          setErro(payload.motivo_bloqueio || 'Inutilização indisponível.');
        }
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar dados da inutilização.' }));
      })
      .finally(() => setLoading(false));
  }, [open, entityId, mode]);

  const justificativaValida = justificativa.trim().length >= TAMANHO_MINIMO_JUSTIFICATIVA_INUT;
  const faixaValida = useMemo(() => {
    const ini = Number(numeroInicial);
    const fim = Number(numeroFinal);
    return Number.isFinite(ini) && Number.isFinite(fim) && ini >= 1 && fim >= ini;
  }, [numeroFinal, numeroInicial]);

  const confirmacaoProducaoOk = useMemo(() => {
    if (!dados?.exige_confirmacao_producao) return true;
    return confirmarProducao && textoConfirmacao.trim().toUpperCase() === TEXTO_CONFIRMACAO_PRODUCAO_INUT;
  }, [confirmarProducao, dados?.exige_confirmacao_producao, textoConfirmacao]);

  const podeAvancarConfirmacao = Boolean(dados?.pode_inutilizar) && justificativaValida && faixaValida;

  const transmitir = async () => {
    if (!entityId || !dados?.pode_inutilizar) return;
    if (!confirmacaoProducaoOk) {
      setErro('Confirme a inutilização em produção antes de transmitir.');
      return;
    }
    const ini = Number(numeroInicial);
    const fim = Number(numeroFinal);
    setEtapa('transmitindo');
    setErro(null);
    try {
      const body = {
        justificativa: justificativa.trim(),
        numero_inicial: ini,
        numero_final: fim,
        confirmar_inutilizacao_producao: dados.exige_confirmacao_producao ? true : undefined,
        confirmar_texto: dados.exige_confirmacao_producao ? textoConfirmacao.trim() : undefined,
      };
      const res =
        mode === 'config'
          ? await nfeNumeracoesService.inutilizar(entityId, body)
          : await nfeSaidasService.inutilizarNfe(entityId, body);
      setResultado(res);
      if (res.ok) {
        setEtapa('resultado');
        onInutilizada?.(res);
      } else {
        setErro(res.mensagem || 'SEFAZ não homologou a inutilização.');
        setEtapa('erro');
      }
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Falha ao transmitir inutilização à SEFAZ.' }));
      setEtapa('erro');
    }
  };

  const footer =
    etapa === 'formulario' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        <button
          type="button"
          className="erp-btn-destructive"
          disabled={!podeAvancarConfirmacao}
          onClick={() => setEtapa('confirmacao')}
        >
          Continuar
        </button>
      </div>
    ) : etapa === 'confirmacao' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={() => setEtapa('formulario')}>
          Voltar
        </button>
        <button
          type="button"
          className="erp-btn-destructive"
          disabled={!confirmacaoProducaoOk}
          onClick={() => void transmitir()}
        >
          Transmitir inutilização
        </button>
      </div>
    ) : etapa === 'resultado' ? (
      <div className="flex justify-end">
        <button type="button" className="erp-btn-primary" onClick={onClose}>
          Fechar
        </button>
      </div>
    ) : etapa === 'erro' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        <button type="button" className="erp-btn-outline" onClick={() => setEtapa('confirmacao')}>
          Tentar novamente
        </button>
      </div>
    ) : null;

  return (
    <Modal isOpen={open} onClose={onClose} title="Inutilizar numeração NF-e" size="lg" footer={footer}>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando dados…
        </div>
      ) : null}

      {dados && etapa === 'formulario' ? (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Ambiente</p>
            <p className="text-sm font-semibold">{dados.ambiente_label}</p>
            {dados.empresa_razao_social ? (
              <p className="text-sm text-muted-foreground mt-1">{dados.empresa_razao_social}</p>
            ) : null}
          </div>

          {dados.alerta_producao ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive flex gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{dados.alerta_producao}</span>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 rounded-md border p-3">
            <div>
              <label className="erp-label">Série</label>
              <p className="text-sm mt-1">{dados.serie}</p>
            </div>
            {mode === 'nfe' && dados.nfe ? (
              <div>
                <label className="erp-label">NF-e</label>
                <p className="text-sm mt-1">
                  nº {dados.nfe.numero_nfe} — {dados.nfe.status}
                </p>
              </div>
            ) : (
              <div>
                <label className="erp-label">Próximo nº</label>
                <p className="text-sm mt-1">{dados.proximo_numero ?? '—'}</p>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="erp-label" htmlFor="numero-inicial-inut">
                Número inicial
              </label>
              <input
                id="numero-inicial-inut"
                type="number"
                min={1}
                className="erp-input mt-1 w-full"
                value={numeroInicial}
                onChange={(e) => setNumeroInicial(e.target.value)}
                disabled={mode === 'nfe'}
              />
            </div>
            <div>
              <label className="erp-label" htmlFor="numero-final-inut">
                Número final
              </label>
              <input
                id="numero-final-inut"
                type="number"
                min={1}
                className="erp-input mt-1 w-full"
                value={numeroFinal}
                onChange={(e) => setNumeroFinal(e.target.value)}
                disabled={mode === 'nfe'}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="justificativa-inut">
              Justificativa <span className="text-destructive">*</span>
            </label>
            <Textarea
              id="justificativa-inut"
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              rows={4}
              placeholder={`Mínimo ${TAMANHO_MINIMO_JUSTIFICATIVA_INUT} caracteres (regra SEFAZ).`}
              disabled={!dados.pode_inutilizar}
            />
            <p className="text-xs text-muted-foreground">{justificativa.trim().length} caracteres</p>
          </div>

          {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        </div>
      ) : null}

      {dados && etapa === 'confirmacao' ? (
        <div className="space-y-4">
          <p className="text-sm">
            Confirme a inutilização da série <strong>{dados.serie}</strong>, números{' '}
            <strong>
              {numeroInicial}–{numeroFinal}
            </strong>{' '}
            em <strong>{dados.ambiente_label}</strong>.
          </p>
          <div className="rounded-md border p-3 text-sm bg-muted/20">
            <p className="text-xs text-muted-foreground mb-1">Justificativa</p>
            <p>{justificativa.trim()}</p>
          </div>

          {dados.exige_confirmacao_producao ? (
            <div className="space-y-3 rounded-md border border-destructive/30 p-3">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={confirmarProducao}
                  onChange={(e) => setConfirmarProducao(e.target.checked)}
                />
                <span>
                  Estou ciente de que esta ação transmite inutilização fiscal real em produção para a SEFAZ.
                </span>
              </label>
              <div className="space-y-1">
                <label className="text-sm font-medium" htmlFor="confirmar-texto-inut">
                  Digite <strong>{TEXTO_CONFIRMACAO_PRODUCAO_INUT}</strong> para confirmar
                </label>
                <input
                  id="confirmar-texto-inut"
                  className="erp-input w-full"
                  value={textoConfirmacao}
                  onChange={(e) => setTextoConfirmacao(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">O pedido será transmitido ao ambiente de homologação da SEFAZ.</p>
          )}

          {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        </div>
      ) : null}

      {etapa === 'transmitindo' ? (
        <div className="flex flex-col items-center gap-3 py-10 text-sm text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          Transmitindo inutilização à SEFAZ…
        </div>
      ) : null}

      {etapa === 'resultado' && resultado ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="h-5 w-5" />
            <p className="font-medium">Inutilização homologada na SEFAZ</p>
          </div>
          <p className="text-sm">{resultado.mensagem}</p>
          {resultado.protocolo_inutilizacao ? (
            <p className="text-sm text-muted-foreground">Protocolo: {resultado.protocolo_inutilizacao}</p>
          ) : null}
        </div>
      ) : null}

      {etapa === 'erro' ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="font-medium">Inutilização não concluída</p>
          </div>
          <p className="text-sm text-destructive">{erro}</p>
        </div>
      ) : null}
    </Modal>
  );
}
