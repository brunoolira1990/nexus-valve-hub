import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import { centralDfeService } from '@/services/api/centralDfe';
import {
  manifestacaoDestinatarioService,
  type EventoManifestacaoDestinatario,
  type FechamentoManifestacaoPreview,
  type NFeDestinadaDetalhe,
  type NFeDestinadaDocumento,
} from '@/services/api/manifestacaoDestinatario';
import { apiErrorMessage } from '@/services/api/config';

/**
 * Hook de manifestação do destinatário.
 *
 * Sync automático (Central DF-e): use apenas `sincronizarResumosDestinados` e `carregarManifestacao`.
 * Eventos fiscais: use `executarManifestacao` / `executarBaixarXml` somente após clique do usuário.
 */
export function useManifestacaoDestinatario(
  empresaId: number | undefined,
  periodo: { inicio: string; fim: string },
) {
  const [manifestacaoMap, setManifestacaoMap] = useState<Map<string, NFeDestinadaDocumento>>(new Map());
  const [manifestacaoSomenteResumo, setManifestacaoSomenteResumo] = useState<NFeDestinadaDocumento[]>([]);
  const [fechamento, setFechamento] = useState<FechamentoManifestacaoPreview | null>(null);
  const [detalhe, setDetalhe] = useState<NFeDestinadaDetalhe | null>(null);
  const [manifestRow, setManifestRow] = useState<NFeDestinadaDocumento | null>(null);
  const [manifestModalKey, setManifestModalKey] = useState(0);
  const [confirmBaixar, setConfirmBaixar] = useState<NFeDestinadaDocumento | null>(null);
  const [confirmArmazenar, setConfirmArmazenar] = useState<{
    row: CentralDfeDocumento;
    manifestacao: NFeDestinadaDocumento | null;
    somenteResumo: boolean;
  } | null>(null);
  const [confirmArmazenarCte, setConfirmArmazenarCte] = useState<CentralDfeDocumento | null>(null);
  const [dfeDetalheRow, setDfeDetalheRow] = useState<CentralDfeDocumento | null>(null);
  const [loadingSyncResumos, setLoadingSyncResumos] = useState(false);
  const [loadingAcaoManual, setLoadingAcaoManual] = useState(false);

  const abrirModalManifestacao = useCallback((doc: NFeDestinadaDocumento) => {
    setManifestModalKey((k) => k + 1);
    setManifestRow(doc);
    setDfeDetalheRow(null);
  }, []);

  const registrarDocumentoLocal = useCallback((doc: NFeDestinadaDocumento) => {
    setManifestacaoMap((prev) => {
      const next = new Map(prev);
      next.set(doc.chave_acesso, doc);
      return next;
    });
    setManifestacaoSomenteResumo((prev) => prev.filter((row) => row.chave_acesso !== doc.chave_acesso));
  }, []);

  const aplicarArmazenamentoXmlNfeLocal = useCallback(
    (
      chaveAcesso: string,
      payload: { nf_entrada_historica_id: number; manifestacao_id?: number },
    ) => {
      setManifestacaoMap((prev) => {
        const atual = prev.get(chaveAcesso);
        if (!atual) return prev;
        const next = new Map(prev);
        next.set(chaveAcesso, {
          ...atual,
          status_xml: 'BAIXADO',
          nf_entrada_historica_id: payload.nf_entrada_historica_id,
        });
        return next;
      });
      setManifestacaoSomenteResumo((prev) =>
        prev.map((row) =>
          row.chave_acesso === chaveAcesso
            ? {
                ...row,
                status_xml: 'BAIXADO',
                nf_entrada_historica_id: payload.nf_entrada_historica_id,
              }
            : row,
        ),
      );
    },
    [],
  );

  const carregarManifestacao = useCallback(
    async (chavesCentral: Set<string>) => {
      if (!empresaId) {
        setManifestacaoMap(new Map());
        setManifestacaoSomenteResumo([]);
        return;
      }
      try {
        const map = new Map<string, NFeDestinadaDocumento>();
        const somenteResumo: NFeDestinadaDocumento[] = [];
        let page = 1;
        let totalPages = 1;
        const params: Record<string, string | number> = {
          empresa_id: empresaId,
          page_size: 100,
        };
        if (periodo.inicio) params.data_inicio = periodo.inicio;
        if (periodo.fim) params.data_fim = periodo.fim;

        while (page <= totalPages) {
          const data = await manifestacaoDestinatarioService.listPaginated({ ...params, page });
          totalPages = data.total_pages || 1;
          for (const row of data.results) {
            map.set(row.chave_acesso, row);
            if (!chavesCentral.has(row.chave_acesso)) {
              somenteResumo.push(row);
            }
          }
          page += 1;
        }
        setManifestacaoMap(map);
        setManifestacaoSomenteResumo(somenteResumo);
      } catch (e) {
        toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar status de manifestação.' }));
      }
    },
    [empresaId, periodo.inicio, periodo.fim],
  );

  const carregarFechamento = useCallback(async () => {
    if (!empresaId || !periodo.inicio || !periodo.fim) {
      setFechamento(null);
      return;
    }
    try {
      const data = await manifestacaoDestinatarioService.fechamentoPreview({
        empresa_id: empresaId,
        data_inicio: periodo.inicio,
        data_fim: periodo.fim,
      });
      setFechamento(data);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar fechamento.' }));
    }
  }, [empresaId, periodo.inicio, periodo.fim]);

  useEffect(() => {
    void carregarFechamento();
  }, [carregarFechamento]);

  const abrirDetalheManifestacao = async (row: NFeDestinadaDocumento) => {
    try {
      const data = await manifestacaoDestinatarioService.get(row.id);
      setDetalhe(data);
      setDfeDetalheRow(null);
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível carregar histórico de manifestação.' }));
    }
  };

  /**
   * Prepara registro por chave (somente clique manual). Não envia evento fiscal.
   */
  const prepararManifestacaoPorDfe = useCallback(
    async (row: CentralDfeDocumento): Promise<NFeDestinadaDocumento | null> => {
      if (!empresaId || row.tipo_documento !== 'NFE_ENTRADA' || !row.chave_acesso) {
        toast.error('NF-e de fornecedor inválida para manifestação.');
        return null;
      }

      const existente = manifestacaoMap.get(row.chave_acesso);
      if (existente) return existente;

      setLoadingAcaoManual(true);
      try {
        const resp = await manifestacaoDestinatarioService.iniciarPorChave({
          empresa_id: empresaId,
          chave_acesso: row.chave_acesso,
          nf_entrada_historica_id: row.id,
        });
        registrarDocumentoLocal(resp.documento);
        await carregarFechamento();
        return resp.documento;
      } catch (e) {
        toast.error(apiErrorMessage(e, { fallback: 'Não foi possível preparar manifestação.' }));
        return null;
      } finally {
        setLoadingAcaoManual(false);
      }
    },
    [empresaId, manifestacaoMap, registrarDocumentoLocal, carregarFechamento, abrirModalManifestacao],
  );

  const iniciarManifestacaoManual = async (
    row: CentralDfeDocumento,
    manifestacao: NFeDestinadaDocumento | null,
  ) => {
    const doc = manifestacao ?? (await prepararManifestacaoPorDfe(row));
    if (!doc) return;
    abrirModalManifestacao(doc);
  };

  const iniciarArmazenarXmlManual = async (
    row: CentralDfeDocumento,
    manifestacao: NFeDestinadaDocumento | null,
    somenteResumo = false,
  ) => {
    if (row.xml_armazenado) return;
    let doc = manifestacao;
    if (!doc && row.tipo_documento === 'NFE_ENTRADA') {
      doc = await prepararManifestacaoPorDfe(row);
    }
    setConfirmArmazenar({ row, manifestacao: doc, somenteResumo });
  };

  const iniciarBaixarXmlManual = iniciarArmazenarXmlManual;

  const abrirDetalheDfeNfe = (row: CentralDfeDocumento, manifestacao: NFeDestinadaDocumento | null) => {
    if (manifestacao) {
      void abrirDetalheManifestacao(manifestacao);
      return;
    }
    setDetalhe(null);
    setDfeDetalheRow(row);
  };

  /**
   * Sync automático permitido: consulta resumos destinados (dist NSU).
   * NÃO chama manifestar/ nem baixar-xml/.
   */
  const sincronizarResumosDestinados = useCallback(
    async (
      chavesCentral?: Set<string>,
      options?: { silent?: boolean },
    ): Promise<boolean> => {
      if (!empresaId) {
        if (!options?.silent) toast.error('Empresa ativa não identificada.');
        return false;
      }
      setLoadingSyncResumos(true);
      try {
        await manifestacaoDestinatarioService.consultarResumosDestinados({ empresa_id: empresaId });
        await carregarManifestacao(chavesCentral ?? new Set());
        await carregarFechamento();
        return true;
      } catch (e) {
        if (!options?.silent) {
          toast.error(apiErrorMessage(e, { fallback: 'Falha ao consultar resumos destinados.' }));
        }
        return false;
      } finally {
        setLoadingSyncResumos(false);
      }
    },
    [empresaId, carregarManifestacao, carregarFechamento],
  );

  /** Ação manual exclusiva — envia evento fiscal SEFAZ. */
  const executarManifestacao = async (
    evento: EventoManifestacaoDestinatario,
    justificativa: string,
    onAfter?: () => void | Promise<void>,
    chavesCentral?: Set<string>,
  ) => {
    if (!manifestRow) return;
    const manifestId = manifestRow.id;
    setLoadingAcaoManual(true);
    try {
      const resp = await manifestacaoDestinatarioService.manifestar(manifestRow.id, {
        evento,
        justificativa,
        confirmacao_explicita: true,
      });
      if (resp.documento?.chave_acesso) {
        registrarDocumentoLocal(resp.documento);
      }
      if (detalhe?.id === manifestId) {
        if (resp.documento?.eventos) {
          setDetalhe(resp.documento);
        } else {
          const fresh = await manifestacaoDestinatarioService.get(manifestId);
          setDetalhe(fresh);
        }
      }
      const msgSucesso =
        resp.xmotivo ||
        resp.status_manifestacao_label ||
        resp.documento?.status_manifestacao_label ||
        'Manifestação registrada.';
      toast.success(msgSucesso);
      setManifestRow(null);
      await carregarManifestacao(chavesCentral ?? new Set());
      await carregarFechamento();
      await onAfter?.();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível manifestar.' }));
      await carregarManifestacao(chavesCentral ?? new Set());
    } finally {
      setLoadingAcaoManual(false);
    }
  };

  /** Ação manual — armazena XML NF-e na Base NF-e Entrada Importada. */
  const executarArmazenarXmlNfe = async (onAfter?: () => void | Promise<void>, chavesCentral?: Set<string>) => {
    if (!confirmArmazenar || !empresaId) return;
    const { row, manifestacao, somenteResumo } = confirmArmazenar;
    const documentoId = somenteResumo && manifestacao ? manifestacao.id : row.id;
    const chaveAcesso = (row.chave_acesso || manifestacao?.chave_acesso || '').trim();
    setLoadingAcaoManual(true);
    try {
      const resp = await centralDfeService.armazenarXmlNfe(documentoId, {
        empresa_id: empresaId,
        confirmacao_explicita: true,
      });
      if (!resp.xml_armazenado || !resp.nf_entrada_historica_id) {
        throw new Error(resp.mensagem || 'XML não foi persistido na Base NF-e Entrada Importada.');
      }
      if (chaveAcesso) {
        aplicarArmazenamentoXmlNfeLocal(chaveAcesso, {
          nf_entrada_historica_id: resp.nf_entrada_historica_id,
          manifestacao_id: resp.manifestacao_id,
        });
      }
      toast.success(resp.mensagem || 'XML importado e armazenado na Base NF-e Entrada Importada.');
      setConfirmArmazenar(null);
      setConfirmBaixar(null);
      await onAfter?.();
      const chavesAtualizadas = chavesCentral ?? new Set<string>();
      if (chaveAcesso) chavesAtualizadas.add(chaveAcesso);
      await carregarManifestacao(chavesAtualizadas);
      await carregarFechamento();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível armazenar XML da NF-e.' }));
    } finally {
      setLoadingAcaoManual(false);
    }
  };

  const executarBaixarXml = executarArmazenarXmlNfe;

  const executarArmazenarXmlCte = async (onAfter?: () => void | Promise<void>) => {
    if (!confirmArmazenarCte || !empresaId) return;
    setLoadingAcaoManual(true);
    try {
      await centralDfeService.armazenarXmlCte(confirmArmazenarCte.id, {
        empresa_id: empresaId,
        confirmacao_explicita: true,
      });
      toast.success('XML confirmado na Base CT-e Importada.');
      setConfirmArmazenarCte(null);
      await carregarFechamento();
      await onAfter?.();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível armazenar XML do CT-e.' }));
    } finally {
      setLoadingAcaoManual(false);
    }
  };

  return {
    manifestacaoMap,
    manifestacaoSomenteResumo,
    fechamento,
    detalhe,
    setDetalhe,
    manifestRow,
    setManifestRow,
    manifestModalKey,
    abrirModalManifestacao,
    confirmBaixar,
    setConfirmBaixar,
    confirmArmazenar,
    setConfirmArmazenar,
    confirmArmazenarCte,
    setConfirmArmazenarCte,
    dfeDetalheRow,
    setDfeDetalheRow,
    loadingSyncResumos,
    loadingAcaoManual,
    carregarManifestacao,
    abrirDetalheManifestacao,
    abrirDetalheDfeNfe,
    prepararManifestacaoPorDfe,
    iniciarManifestacaoManual,
    iniciarArmazenarXmlManual,
    iniciarBaixarXmlManual,
    sincronizarResumosDestinados,
    executarManifestacao,
    executarArmazenarXmlNfe,
    executarBaixarXml,
    executarArmazenarXmlCte,
  };
}
