import { Modal } from '@/components/Modal';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import {
  statusManifestacaoCteExibicao,
  statusXmlCteExibicao,
} from '@/lib/centralDfeUi';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';

const fmtMoney = (v: string | number | null | undefined): string => {
  const n = Number(String(v ?? '0').replace(',', '.'));
  return `R$ ${Number.isFinite(n) ? n.toFixed(2) : '0.00'}`;
};

const fmtData = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = v.slice(0, 10);
  const [y, m, day] = d.split('-');
  if (!y || !m || !day) return v;
  return `${day}/${m}/${y}`;
};

const fmtCnpj = (cnpj: string): string => {
  const d = (cnpj || '').replace(/\D/g, '');
  if (d.length !== 14) return cnpj || '—';
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

function statusEntradaBadge(status: string): string {
  const map: Record<string, string> = {
    PENDENTE_ENTRADA: 'pendente',
    IMPORTADO_BASE: 'importado',
    CONFERIDO: 'conferida',
    PREPARADO: 'preparada',
    DIVERGENTE: 'divergente',
    IGNORADO: 'ignorada',
    JA_LANCADO: 'processado',
  };
  return map[status] || 'pendente';
}

type Props = {
  open: boolean;
  row: CentralDfeDocumento | null;
  onClose: () => void;
};

export function CentralDfeCteDetalheModal({ open, row, onClose }: Props) {
  if (!row) return null;

  const manifestacaoStatus = statusManifestacaoCteExibicao();
  const xmlStatus = statusXmlCteExibicao(row);

  return (
    <Modal isOpen={open} onClose={onClose} title="CT-e Transportadora — Central DF-e" size="md">
      <div className="space-y-4 text-sm">
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 text-xs">
          CT-e não possui Manifestação do Destinatário.
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="text-muted-foreground block text-xs">Tipo</span>
            <span className="font-medium">{row.tipo_label || 'CT-e Transportadora'}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">Número / Série</span>
            <span className="font-medium">
              {row.numero || '—'}
              {row.serie ? ` / ${row.serie}` : ''}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">Emitente (transportadora)</span>
            <span>{row.emitente_nome || '—'}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">CNPJ emitente</span>
            <span className="font-mono">{fmtCnpj(row.emitente_cnpj)}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">Data de emissão</span>
            <span>{fmtData(row.data_emissao)}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">Valor</span>
            <span className="tabular-nums">{fmtMoney(row.valor_total)}</span>
          </div>
          <div className="sm:col-span-2">
            <span className="text-muted-foreground block text-xs">Chave de acesso</span>
            <span className="font-mono text-xs break-all" title={row.chave_acesso}>
              {row.chave_acesso || row.chave_resumida || chaveNfeResumida(row.chave_acesso)}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs mb-1">Status entrada / conferência</span>
            <StatusBadge status={statusEntradaBadge(row.status_entrada)}>
              {row.status_entrada_label || row.status_entrada}
            </StatusBadge>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs mb-1">Status XML</span>
            <StatusBadge status={xmlStatus.badge}>{xmlStatus.label}</StatusBadge>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs mb-1">Manifestação</span>
            <StatusBadge status={manifestacaoStatus.badge}>{manifestacaoStatus.label}</StatusBadge>
          </div>
          {row.data_importacao && (
            <div>
              <span className="text-muted-foreground block text-xs">Importado em</span>
              <span>{fmtData(row.data_importacao)}</span>
            </div>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Use &quot;Abrir na Base CT-e Importada&quot; na listagem para abrir o registro completo na base importada.
        </p>
      </div>
    </Modal>
  );
}
