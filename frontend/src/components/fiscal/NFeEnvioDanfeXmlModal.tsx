import { useEffect, useState, type FormEvent } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, Mail, Paperclip } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { formatDateTimeBr } from '@/lib/nfeSaidaUi';
import { emailOperacionalValido } from '@/lib/validacaoSenha';
import { nfeSaidasService, type NFeEnvioEmailDadosResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { toast } from 'sonner';

const FORM_ID = 'nfe-envio-danfe-xml-form';

type Props = {
  open: boolean;
  nfeId: number | null;
  onClose: () => void;
  onEnviado?: () => void;
};

function CampoResumo({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={cn('text-sm break-words', mono && 'font-mono text-xs')}>{value || '—'}</p>
    </div>
  );
}

function parseEmailList(value: string): string[] {
  return value
    .split(/[,;]/)
    .map((parte) => parte.trim())
    .filter(Boolean);
}

function validarListaEmails(
  value: string,
  { obrigatorio, campo }: { obrigatorio: boolean; campo: 'para' | 'cc' },
): string | null {
  const emails = parseEmailList(value);
  if (obrigatorio && emails.length === 0) {
    return 'Informe o e-mail do destinatário.';
  }
  for (const email of emails) {
    if (!emailOperacionalValido(email)) {
      return campo === 'cc' ? `E-mail inválido em Cc: ${email}` : 'Informe um e-mail válido.';
    }
  }
  return null;
}

/** Garante shape estável mesmo com campos opcionais/null da API. */
function normalizeEnvioEmailDados(raw: unknown): NFeEnvioEmailDadosResponse {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const nfe = (r.nfe && typeof r.nfe === 'object' ? r.nfe : {}) as Record<string, unknown>;
  const anexos = (r.anexos && typeof r.anexos === 'object' ? r.anexos : {}) as Record<string, unknown>;
  const ultimo =
    r.ultimo_envio && typeof r.ultimo_envio === 'object'
      ? (r.ultimo_envio as NFeEnvioEmailDadosResponse['ultimo_envio'])
      : null;
  const podeEnviar = Boolean(r.pode_enviar ?? r.ok);

  return {
    ok: podeEnviar,
    pode_enviar: podeEnviar,
    motivo_bloqueio: String(r.motivo_bloqueio ?? ''),
    ambiente: String(r.ambiente ?? ''),
    ambiente_label: String(r.ambiente_label ?? ''),
    homologacao: Boolean(r.homologacao),
    alerta_homologacao: String(r.alerta_homologacao ?? ''),
    destinatario_sugerido: String(r.destinatario_sugerido ?? ''),
    assunto_sugerido: String(r.assunto_sugerido ?? ''),
    mensagem_sugerida: String(r.mensagem_sugerida ?? ''),
    anexos: {
      xml_autorizado: Boolean(anexos.xml_autorizado),
      danfe_pdf: Boolean(anexos.danfe_pdf),
    },
    nfe: {
      id: Number(nfe.id ?? 0),
      numero: String(nfe.numero ?? ''),
      serie: String(nfe.serie ?? ''),
      chave_acesso: String(nfe.chave_acesso ?? ''),
      status: String(nfe.status ?? ''),
      status_emissao_sefaz: String(nfe.status_emissao_sefaz ?? ''),
      cliente_nome: String(nfe.cliente_nome ?? ''),
      protocolo_autorizacao: String(nfe.protocolo_autorizacao ?? ''),
    },
    ultimo_envio: ultimo,
    historico_recente: Array.isArray(r.historico_recente)
      ? (r.historico_recente as NFeEnvioEmailDadosResponse['historico_recente'])
      : [],
  };
}

function validarFormularioEnvio(
  dados: NFeEnvioEmailDadosResponse,
  para: string,
  cc: string,
  assunto: string,
  mensagem: string,
  confirmar: boolean,
): string | null {
  if (!dados.pode_enviar) {
    return dados.motivo_bloqueio || 'Envio indisponível para esta NF-e.';
  }

  if (!dados.anexos.xml_autorizado || !dados.anexos.danfe_pdf) {
    return 'XML autorizado e DANFE PDF precisam estar disponíveis para envio.';
  }

  const erroPara = validarListaEmails(para, { obrigatorio: true, campo: 'para' });
  if (erroPara) return erroPara;

  const erroCc = validarListaEmails(cc, { obrigatorio: false, campo: 'cc' });
  if (erroCc) return erroCc;

  const assuntoLimpo = assunto.trim();
  if (!assuntoLimpo) {
    return 'Informe o assunto.';
  }

  if (dados.homologacao && !assuntoLimpo.toUpperCase().includes('HOMOLOG')) {
    return 'Em homologação, o assunto deve indicar HOMOLOGAÇÃO / sem valor fiscal.';
  }

  if (!mensagem.trim()) {
    return 'Informe a mensagem.';
  }

  if (!confirmar) {
    return 'Confirme o envio do DANFE e XML.';
  }

  return null;
}

export function NFeEnvioDanfeXmlModal({ open, nfeId, onClose, onEnviado }: Props) {
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [erroCarregamento, setErroCarregamento] = useState<string | null>(null);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [avisoBloqueio, setAvisoBloqueio] = useState<string | null>(null);
  const [dados, setDados] = useState<NFeEnvioEmailDadosResponse | null>(null);
  const [envioNfeId, setEnvioNfeId] = useState<number | null>(null);
  const [para, setPara] = useState('');
  const [cc, setCc] = useState('');
  const [assunto, setAssunto] = useState('');
  const [mensagem, setMensagem] = useState('');
  const [confirmar, setConfirmar] = useState(false);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (!open) {
      setLoading(false);
      setSending(false);
      setDados(null);
      setEnvioNfeId(null);
      setPara('');
      setCc('');
      setAssunto('');
      setMensagem('');
      setConfirmar(false);
      setErroCarregamento(null);
      setErroEnvio(null);
      setAvisoBloqueio(null);
      setSucesso(false);
      return;
    }

    const idCarregar = nfeId;
    if (!idCarregar) return;

    let cancelled = false;
    setLoading(true);
    setErroCarregamento(null);
    setErroEnvio(null);
    setAvisoBloqueio(null);
    setSucesso(false);
    setDados(null);
    setEnvioNfeId(idCarregar);

    void nfeSaidasService
      .envioEmailDados(idCarregar)
      .then((payload) => {
        if (cancelled) return;
        const normalized = normalizeEnvioEmailDados(payload);
        const idResolvido = normalized.nfe.id || idCarregar;
        setEnvioNfeId(idResolvido);
        setDados(normalized);
        setPara(normalized.destinatario_sugerido || '');
        setAssunto(normalized.assunto_sugerido || '');
        setMensagem(normalized.mensagem_sugerida || '');
        if (!normalized.pode_enviar) {
          setAvisoBloqueio(normalized.motivo_bloqueio || 'Envio indisponível para esta NF-e.');
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setDados(null);
        setErroCarregamento(apiErrorMessage(e, { fallback: 'Não foi possível carregar dados do envio.' }));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, nfeId]);

  const podeClicarEnviar = Boolean(dados) && !loading && !sending && !sucesso;

  const enviar = async () => {
    if (sending) return;

    const idEnvio = envioNfeId ?? dados?.nfe?.id ?? nfeId;
    if (!dados) {
      setErroEnvio('Aguarde o carregamento dos dados do envio.');
      return;
    }
    if (!idEnvio) {
      setErroEnvio('NF-e não identificada para envio. Feche e abra o modal novamente.');
      return;
    }

    const erroValidacao = validarFormularioEnvio(dados, para, cc, assunto, mensagem, confirmar);
    if (erroValidacao) {
      setErroEnvio(erroValidacao);
      return;
    }

    setSending(true);
    setErroEnvio(null);
    try {
      const res = await nfeSaidasService.envioEmailEnviar(idEnvio, {
        para: para.trim(),
        cc: cc.trim(),
        assunto: assunto.trim(),
        mensagem: mensagem.trim(),
        confirmar_envio: true,
      });
      if (res.ok) {
        setSucesso(true);
        toast.success(res.mensagem || 'E-mail enviado com sucesso.');
        onEnviado?.();
      } else {
        setErroEnvio(res.mensagem || 'Não foi possível enviar o e-mail.');
      }
    } catch (e) {
      setErroEnvio(apiErrorMessage(e, { fallback: 'Não foi possível enviar o e-mail.' }));
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void enviar();
  };

  const nfe = dados?.nfe;
  const anexos = dados?.anexos;
  const ultimo = dados?.ultimo_envio;
  const formularioBloqueado = !dados?.pode_enviar || sending;

  const limparErroEnvio = () => {
    if (erroEnvio) setErroEnvio(null);
  };

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Enviar DANFE/XML por e-mail"
      size="lg"
      stacked
      footer={
        <div className="p-4 space-y-3">
          {erroEnvio ? (
            <div
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              {erroEnvio}
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <button type="button" className="erp-btn-secondary" onClick={onClose} disabled={sending}>
              {sucesso ? 'Fechar' : 'Cancelar'}
            </button>
            {!sucesso ? (
              <button
                type="submit"
                form={FORM_ID}
                className="erp-btn-primary"
                disabled={!podeClicarEnviar}
              >
                {sending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin inline mr-1" />
                    Enviando…
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4 inline mr-1" />
                    Enviar e-mail
                  </>
                )}
              </button>
            ) : null}
          </div>
        </div>
      }
    >
      <div className="min-h-[200px]">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando dados do envio…
          </div>
        ) : null}

        {!loading && erroCarregamento && !dados ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-3 text-sm text-destructive">
            {erroCarregamento}
          </div>
        ) : null}

        {!loading && dados ? (
          <form id={FORM_ID} className="space-y-4" onSubmit={handleSubmit} noValidate>
            {dados.homologacao && dados.alerta_homologacao ? (
              <div className="rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100 flex gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{dados.alerta_homologacao}</span>
              </div>
            ) : null}

            {avisoBloqueio ? (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {avisoBloqueio}
              </div>
            ) : null}

            {sucesso ? (
              <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm flex gap-2 items-start">
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>E-mail enviado com os anexos XML autorizado e DANFE PDF.</span>
              </div>
            ) : null}

            <div className="grid grid-cols-2 gap-3">
              <CampoResumo label="NF-e" value={`${nfe?.numero ?? '—'} / Série ${nfe?.serie ?? '—'}`} />
              <CampoResumo label="Ambiente" value={dados.ambiente_label} />
              <CampoResumo label="Cliente" value={nfe?.cliente_nome ?? ''} />
              <CampoResumo label="Status" value={nfe?.status ?? ''} />
              <CampoResumo label="Chave" value={nfe?.chave_acesso ?? ''} mono />
              <CampoResumo label="Protocolo" value={nfe?.protocolo_autorizacao ?? ''} />
            </div>

            <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-xs space-y-1">
              <p className="font-medium flex items-center gap-1">
                <Paperclip className="h-3.5 w-3.5" />
                Anexos previstos
              </p>
              <ul className="list-disc pl-5 text-muted-foreground">
                <li>{anexos?.xml_autorizado ? 'XML autorizado' : 'XML autorizado — indisponível'}</li>
                <li>{anexos?.danfe_pdf ? 'DANFE PDF' : 'DANFE PDF — indisponível'}</li>
              </ul>
            </div>

            {!sucesso ? (
              <>
                <div>
                  <label className="erp-label" htmlFor="envio-email-para">
                    Para
                  </label>
                  <input
                    id="envio-email-para"
                    className="erp-input mt-1 w-full"
                    value={para}
                    disabled={formularioBloqueado}
                    onChange={(e) => {
                      setPara(e.target.value);
                      limparErroEnvio();
                    }}
                    placeholder="e-mail do destinatário"
                    autoComplete="email"
                  />
                </div>
                <div>
                  <label className="erp-label" htmlFor="envio-email-cc">
                    Cc (opcional)
                  </label>
                  <input
                    id="envio-email-cc"
                    className="erp-input mt-1 w-full"
                    value={cc}
                    disabled={formularioBloqueado}
                    onChange={(e) => {
                      setCc(e.target.value);
                      limparErroEnvio();
                    }}
                    placeholder="cópias separadas por vírgula"
                    autoComplete="email"
                  />
                </div>
                <div>
                  <label className="erp-label" htmlFor="envio-email-assunto">
                    Assunto
                  </label>
                  <input
                    id="envio-email-assunto"
                    className="erp-input mt-1 w-full"
                    value={assunto}
                    disabled={formularioBloqueado}
                    onChange={(e) => {
                      setAssunto(e.target.value);
                      limparErroEnvio();
                    }}
                  />
                </div>
                <div>
                  <label className="erp-label" htmlFor="envio-email-mensagem">
                    Mensagem
                  </label>
                  <Textarea
                    id="envio-email-mensagem"
                    className="mt-1 min-h-[120px]"
                    value={mensagem}
                    disabled={formularioBloqueado}
                    onChange={(e) => {
                      setMensagem(e.target.value);
                      limparErroEnvio();
                    }}
                  />
                </div>
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={confirmar}
                    disabled={formularioBloqueado}
                    onChange={(e) => {
                      setConfirmar(e.target.checked);
                      limparErroEnvio();
                    }}
                  />
                  <span>
                    Confirmo o envio do DANFE e XML desta NF-e para os destinatários informados.
                  </span>
                </label>
              </>
            ) : null}

            {ultimo ? (
              <div className="text-xs text-muted-foreground border-t border-border pt-3 space-y-1">
                <p className="font-medium text-foreground">Último envio</p>
                <p>
                  {formatDateTimeBr(ultimo.enviado_em)} — {ultimo.usuario_nome || 'Usuário'} →{' '}
                  {ultimo.destinatario}
                  {ultimo.status_envio === 'SUCESSO' ? ' (sucesso)' : ' (erro)'}
                </p>
                {ultimo.status_envio === 'ERRO' && ultimo.mensagem_erro ? (
                  <p className="text-destructive">{ultimo.mensagem_erro}</p>
                ) : null}
              </div>
            ) : null}
          </form>
        ) : null}

        {!loading && !dados && !erroCarregamento ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            Não foi possível exibir os dados do envio. Tente fechar e abrir novamente.
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
