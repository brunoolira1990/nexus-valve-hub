import type { CentralDfeDocumento } from '@/services/api/centralDfe';

export type SerieNumeroChaveDfe = {
  serie: string;
  numero: string;
  modelo: string;
};

/** Extrai série e número da chave NF-e/CT-e (modelos 55 e 57). */
export function extrairSerieNumeroDaChaveDfe(chave?: string | null): SerieNumeroChaveDfe | null {
  const digits = (chave || '').replace(/\D/g, '');
  if (digits.length !== 44) return null;
  const modelo = digits.slice(20, 22);
  if (modelo !== '55' && modelo !== '57') return null;
  const serie = String(parseInt(digits.slice(22, 25), 10));
  const numero = String(parseInt(digits.slice(25, 34), 10));
  if (!Number.isFinite(Number(serie)) || !Number.isFinite(Number(numero))) return null;
  return { serie, numero, modelo };
}

export type NumeroSerieInboxExibicao = {
  numero: string;
  serie: string;
  viaChave: boolean;
  aguardandoXml: boolean;
};

export function resolverNumeroSerieInbox(
  row: Pick<
    CentralDfeDocumento,
    'numero' | 'serie' | 'chave_acesso' | 'xml_armazenado' | 'numero_via_chave'
  >,
): NumeroSerieInboxExibicao {
  const num = (row.numero || '').trim();
  const ser = (row.serie || '').trim();
  if (num && num !== '—') {
    return {
      numero: num,
      serie: ser,
      viaChave: Boolean(row.numero_via_chave),
      aguardandoXml: false,
    };
  }
  const ext = extrairSerieNumeroDaChaveDfe(row.chave_acesso);
  if (ext) {
    return {
      numero: ext.numero,
      serie: ext.serie,
      viaChave: true,
      aguardandoXml: !row.xml_armazenado,
    };
  }
  if (!row.xml_armazenado) {
    return { numero: '', serie: '', viaChave: false, aguardandoXml: true };
  }
  return { numero: '—', serie: '', viaChave: false, aguardandoXml: false };
}

export function formatNumeroSerieInbox(
  row: Pick<
    CentralDfeDocumento,
    'numero' | 'serie' | 'chave_acesso' | 'xml_armazenado' | 'numero_via_chave'
  >,
): string {
  const info = resolverNumeroSerieInbox(row);
  if (info.aguardandoXml) return 'Aguardando XML';
  if (!info.numero || info.numero === '—') return '—';
  return info.serie ? `${info.numero} / ${info.serie}` : info.numero;
}
