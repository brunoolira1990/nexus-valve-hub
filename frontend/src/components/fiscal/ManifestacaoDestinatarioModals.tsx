import { Loader2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import {
  EVENTOS_MANIFESTACAO,
  podeArmazenarXmlNfe,
  podeManifestarNfe,
  statusManifestacaoExibicao,
  statusXmlExibicao,
} from '@/lib/manifestacaoDestinatarioUi';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import {
  DESCRICAO_EVENTO_MANIFESTACAO,
  LABEL_EVENTO_MANIFESTACAO,
  type EventoManifestacaoDestinatario,
  type NFeDestinadaDetalhe,
  type NFeDestinadaDocumento,
} from '@/services/api/manifestacaoDestinatario';

const fmtData = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = v.slice(0, 10);
  const [y, m, day] = d.split('-');
  if (!y || !m || !day) return v;
  return `${day}/${m}/${y}`;
};

const fmtMoney = (v: string | number | null | undefined): string => {
  const n = Number(String(v ?? '0').replace(',', '.'));
  return `R$ ${Number.isFinite(n) ? n.toFixed(2) : '0.00'}`;
};

type Props = {
  manifestRow: NFeDestinadaDocumento | null;
  onManifestRowChange: (row: NFeDestinadaDocumento | null) => void;
  eventoSel: EventoManifestacaoDestinatario | '';
  onEventoSelChange: (ev: EventoManifestacaoDestinatario | '') => void;
  justificativa: string;
  onJustificativaChange: (v: string) => void;
  detalhe: NFeDestinadaDetalhe | null;
  onDetalheChange: (d: NFeDestinadaDetalhe | null) => void;
  dfeDetalheRow: CentralDfeDocumento | null;
  onDfeDetalheRowChange: (row: CentralDfeDocumento | null) => void;
  manifestacaoDetalhe: NFeDestinadaDocumento | null;
  onIniciarManifestacao: () => void;
  onIniciarBaixarXml: () => void;
  onAbrirManifestacaoDocumento: (doc: NFeDestinadaDocumento) => void;
  onAbrirHistoricoDocumento: (doc: NFeDestinadaDocumento) => void;
  confirmBaixar: NFeDestinadaDocumento | null;
  onConfirmBaixarChange: (row: NFeDestinadaDocumento | null) => void;
  confirmArmazenarAberto?: boolean;
  loadingAcao: boolean;
  onExecutarManifestacao: () => void;
  onExecutarBaixarXml: () => void;
};

export function ManifestacaoDestinatarioModals({
  manifestRow,
  onManifestRowChange,
  eventoSel,
  onEventoSelChange,
  justificativa,
  onJustificativaChange,
  detalhe,
  onDetalheChange,
  dfeDetalheRow,
  onDfeDetalheRowChange,
  manifestacaoDetalhe,
  onIniciarManifestacao,
  onIniciarBaixarXml,
  onAbrirManifestacaoDocumento,
  onAbrirHistoricoDocumento,
  confirmBaixar,
  onConfirmBaixarChange,
  confirmArmazenarAberto = false,
  loadingAcao,
  onExecutarManifestacao,
  onExecutarBaixarXml,
}: Props) {
  const fecharModalManifestacao = () => {
    onEventoSelChange('');
    onJustificativaChange('');
    onManifestRowChange(null);
  };

  return (
    <>
      <Dialog open={Boolean(manifestRow)} onOpenChange={(open) => !open && fecharModalManifestacao()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manifestar NF-e destinada</DialogTitle>
          </DialogHeader>
          {manifestRow && (
          <div key={`manifestacao-${manifestRow.id}-${manifestRow.chave_acesso}`}>
          <p className="text-sm text-muted-foreground">
            Chave: {chaveNfeResumida(manifestRow.chave_acesso)}
          </p>
          <p className="text-xs text-muted-foreground border rounded-md p-2 bg-muted/40">
            A atualização da Central DF-e não envia eventos fiscais. Escolha o evento abaixo e confirme
            explicitamente para manifestar esta NF-e.
          </p>
          <div className="space-y-3">
            <Label>Selecione o evento (sem pré-seleção automática)</Label>
            <div className="space-y-2" role="radiogroup" aria-label="Evento de manifestação">
              {EVENTOS_MANIFESTACAO.map((ev) => (
                <button
                  key={ev}
                  type="button"
                  role="radio"
                  aria-checked={eventoSel === ev}
                  className={`flex w-full items-start gap-2 border rounded-md p-3 text-left transition-colors ${
                    eventoSel === ev
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted/40'
                  }`}
                  onClick={() => onEventoSelChange(ev)}
                >
                  <span
                    className={`mt-0.5 h-4 w-4 shrink-0 rounded-full border ${
                      eventoSel === ev ? 'border-primary bg-primary' : 'border-muted-foreground/50'
                    }`}
                    aria-hidden
                  />
                  <span>
                    <span className="font-medium block">{LABEL_EVENTO_MANIFESTACAO[ev]}</span>
                    <span className="text-xs text-muted-foreground">{DESCRICAO_EVENTO_MANIFESTACAO[ev]}</span>
                  </span>
                </button>
              ))}
            </div>
            {eventoSel === 'OPERACAO_NAO_REALIZADA' && (
              <div>
                <Label>Justificativa (obrigatória)</Label>
                <Textarea value={justificativa} onChange={(e) => onJustificativaChange(e.target.value)} rows={3} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={fecharModalManifestacao}>Cancelar</Button>
            <Button disabled={!eventoSel || loadingAcao} onClick={onExecutarManifestacao}>
              {loadingAcao ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Confirmar manifestação
            </Button>
          </DialogFooter>
          </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(detalhe)} onOpenChange={(open) => !open && onDetalheChange(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Manifestação do Destinatário</DialogTitle>
          </DialogHeader>
          {detalhe && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><span className="text-muted-foreground">Emitente:</span> {detalhe.razao_social_emitente}</div>
                <div><span className="text-muted-foreground">Valor:</span> {fmtMoney(detalhe.valor_nf)}</div>
                <div><span className="text-muted-foreground">Emissão:</span> {fmtData(detalhe.dh_emissao)}</div>
                <div><span className="text-muted-foreground">Manifestação:</span> {detalhe.status_manifestacao_label}</div>
                <div><span className="text-muted-foreground">XML:</span> {detalhe.status_xml_label}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {podeManifestarNfe(detalhe, { tipo_documento: 'NFE_ENTRADA' }) && (
                  <Button
                    type="button"
                    size="sm"
                    disabled={loadingAcao}
                    onClick={() => {
                      onDetalheChange(null);
                      onAbrirManifestacaoDocumento(detalhe);
                    }}
                  >
                    Manifestar
                  </Button>
                )}
                {podeArmazenarXmlNfe(detalhe, { tipo_documento: 'NFE_ENTRADA', xml_armazenado: detalhe.status_xml === 'BAIXADO', xml_status: detalhe.status_xml === 'BAIXADO' ? 'ARMAZENADO' : 'PENDENTE' }) && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={loadingAcao}
                    onClick={() => {
                      onDetalheChange(null);
                      onConfirmBaixarChange(detalhe);
                    }}
                  >
                    Armazenar XML
                  </Button>
                )}
              </div>
              <div>
                <p className="font-medium mb-2">Histórico de eventos</p>
                {detalhe.eventos.length === 0 ? (
                  <p className="text-muted-foreground text-xs">Nenhum evento registrado.</p>
                ) : (
                  <ul className="space-y-2 max-h-48 overflow-auto">
                    {detalhe.eventos.map((ev) => (
                      <li key={ev.id} className="border rounded p-2">
                        <div className="font-medium">{ev.tipo_acao} — {ev.resultado_resumido || ev.cstat}</div>
                        <div className="text-muted-foreground text-xs">{ev.descricao}</div>
                        <div className="text-xs">{fmtData(ev.criado_em)} · {ev.usuario_nome || 'Sistema'}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(dfeDetalheRow)} onOpenChange={(open) => !open && onDfeDetalheRowChange(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>DF-e recebido — NF-e Fornecedor</DialogTitle>
          </DialogHeader>
          {dfeDetalheRow && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><span className="text-muted-foreground">Documento:</span> {dfeDetalheRow.numero}{dfeDetalheRow.serie ? ` / ${dfeDetalheRow.serie}` : ''}</div>
                <div><span className="text-muted-foreground">Emitente:</span> {dfeDetalheRow.emitente_nome || '—'}</div>
                <div><span className="text-muted-foreground">Emissão:</span> {fmtData(dfeDetalheRow.data_emissao)}</div>
                <div><span className="text-muted-foreground">Valor:</span> {fmtMoney(dfeDetalheRow.valor_total)}</div>
                <div className="col-span-2 font-mono text-xs text-muted-foreground" title={dfeDetalheRow.chave_acesso}>
                  Chave: {chaveNfeResumida(dfeDetalheRow.chave_acesso)}
                </div>
              </div>

              <div className="border rounded-md p-3 space-y-3 bg-muted/30">
                <p className="font-medium">Manifestação do Destinatário</p>
                <p className="text-xs text-muted-foreground">
                  Ações manuais — a atualização automática da Central DF-e não envia eventos fiscais.
                </p>
                <div className="flex flex-wrap gap-3">
                  <div>
                    <span className="text-xs text-muted-foreground block mb-1">Status manifestação</span>
                    <StatusBadge status={statusManifestacaoExibicao(manifestacaoDetalhe, dfeDetalheRow).badge}>
                      {statusManifestacaoExibicao(manifestacaoDetalhe, dfeDetalheRow).label}
                    </StatusBadge>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block mb-1">Status XML</span>
                    <StatusBadge status={statusXmlExibicao(manifestacaoDetalhe, dfeDetalheRow).badge}>
                      {statusXmlExibicao(manifestacaoDetalhe, dfeDetalheRow).label}
                    </StatusBadge>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {podeManifestarNfe(manifestacaoDetalhe, dfeDetalheRow) && (
                    <Button type="button" size="sm" disabled={loadingAcao} onClick={onIniciarManifestacao}>
                      Manifestar
                    </Button>
                  )}
                  {podeArmazenarXmlNfe(manifestacaoDetalhe, dfeDetalheRow) && (
                    <Button type="button" size="sm" variant="outline" disabled={loadingAcao} onClick={onIniciarBaixarXml}>
                      Armazenar XML
                    </Button>
                  )}
                  {manifestacaoDetalhe && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={loadingAcao}
                      onClick={() => {
                        onDfeDetalheRowChange(null);
                        onAbrirHistoricoDocumento(manifestacaoDetalhe);
                      }}
                    >
                      Ver histórico
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirmArmazenarAberto || Boolean(confirmBaixar)}
        onOpenChange={(open) => !open && onConfirmBaixarChange(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Armazenar XML da NF-e?</AlertDialogTitle>
            <AlertDialogDescription>
              O XML será baixado (quando necessário) e armazenado na Base NF-e Entrada Importada, sem gerar
              financeiro, estoque ou apuração automática.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loadingAcao}>Cancelar</AlertDialogCancel>
            <AlertDialogAction disabled={loadingAcao} onClick={onExecutarBaixarXml}>
              {loadingAcao ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Armazenar XML
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
