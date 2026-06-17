import { useRef, useState } from 'react';
import { consultaIe, type ConsultaIeResponse, type InscricaoEstadualSefazItem } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { normalizeCnpj } from '@/lib/cnpj';
import {
  deveDispararConsultaIeAutomatica,
  mensagemConsultaIe,
  mensagemIePreenchidaNoFormulario,
  montarChaveConsultaIe,
  MENSAGEM_UF_PENDENTE_IE,
  podeConsultarIeSefaz,
  resolverAplicacaoIe,
  type SugestaoIeCampo,
} from '@/lib/consultaIeCadastro';

export type ConsultaIeLookupResult = {
  aplicarDireto: string | null;
  dados: ConsultaIeResponse | null;
};

export function useConsultaIeSefaz() {
  const [ieLookupLoading, setIeLookupLoading] = useState(false);
  const [ieLookupMessage, setIeLookupMessage] = useState<string | null>(null);
  const [ieSugestao, setIeSugestao] = useState<SugestaoIeCampo | null>(null);
  const [ieOpcoes, setIeOpcoes] = useState<InscricaoEstadualSefazItem[]>([]);
  const [iePreenchidaPelaSefaz, setIePreenchidaPelaSefaz] = useState(false);
  const ultimaAutoChaveRef = useRef<string | null>(null);

  const limparIeConsulta = () => {
    setIeLookupMessage(null);
    setIeSugestao(null);
    setIeOpcoes([]);
    setIePreenchidaPelaSefaz(false);
    ultimaAutoChaveRef.current = null;
  };

  const aplicarResultadoLookup = (
    result: ConsultaIeLookupResult,
    onAplicarIe: (valor: string) => void,
  ) => {
    if (result.aplicarDireto) {
      onAplicarIe(result.aplicarDireto);
      setIeSugestao(null);
      setIeOpcoes([]);
      setIePreenchidaPelaSefaz(true);
      setIeLookupMessage(mensagemIePreenchidaNoFormulario(result.aplicarDireto));
    }
  };

  const runIeLookup = async (
    cnpjRaw: string,
    ufRaw: string,
    ieAtual: string,
  ): Promise<ConsultaIeLookupResult> => {
    const bloqueio = podeConsultarIeSefaz(cnpjRaw, ufRaw);
    if (bloqueio) {
      setIeLookupMessage(bloqueio);
      setIeSugestao(null);
      setIeOpcoes([]);
      return { aplicarDireto: null, dados: null };
    }
    if (ieLookupLoading) return { aplicarDireto: null, dados: null };

    setIeLookupLoading(true);
    setIeLookupMessage(null);
    setIeSugestao(null);
    setIeOpcoes([]);
    try {
      const cnpj = normalizeCnpj(cnpjRaw);
      const uf = (ufRaw || '').trim().toUpperCase();
      const { data } = await consultaIe({ cnpj, uf });
      setIeLookupMessage(mensagemConsultaIe(data));

      const resolucao = resolverAplicacaoIe(ieAtual, data);
      if (resolucao.tipo === 'direta') {
        return { aplicarDireto: resolucao.valor, dados: data };
      }
      if (resolucao.tipo === 'opcoes') {
        setIeOpcoes(resolucao.opcoes);
        return { aplicarDireto: null, dados: data };
      }
      if (resolucao.tipo === 'sugestao') {
        setIeSugestao(resolucao.sugestao);
        return { aplicarDireto: null, dados: data };
      }
      return { aplicarDireto: null, dados: data };
    } catch (err) {
      const msg = apiErrorMessage(err, {
        fallback: 'Consulta SEFAZ indisponível no momento.',
      });
      setIeLookupMessage(msg);
      return { aplicarDireto: null, dados: null };
    } finally {
      setIeLookupLoading(false);
    }
  };

  const runIeLookupManual = async (
    cnpjRaw: string,
    ufRaw: string,
    ieAtual: string,
    onAplicarIe: (valor: string) => void,
  ) => {
    const result = await runIeLookup(cnpjRaw, ufRaw, ieAtual);
    ultimaAutoChaveRef.current = montarChaveConsultaIe(cnpjRaw, ufRaw);
    aplicarResultadoLookup(result, onAplicarIe);
    return result;
  };

  const tryAutoConsultaIe = async (
    cnpjRaw: string,
    ufRaw: string,
    ieAtual: string,
    onAplicarIe: (valor: string) => void,
  ) => {
    const uf = (ufRaw || '').trim();
    if (!uf) {
      setIeLookupMessage(MENSAGEM_UF_PENDENTE_IE);
      return { aplicarDireto: null, dados: null };
    }

    const bloqueio = podeConsultarIeSefaz(cnpjRaw, ufRaw);
    if (bloqueio) {
      return { aplicarDireto: null, dados: null };
    }

    const chave = montarChaveConsultaIe(cnpjRaw, ufRaw);
    if (!deveDispararConsultaIeAutomatica(chave, ultimaAutoChaveRef.current, ieLookupLoading)) {
      return { aplicarDireto: null, dados: null };
    }

    ultimaAutoChaveRef.current = chave;
    const result = await runIeLookup(cnpjRaw, ufRaw, ieAtual);
    aplicarResultadoLookup(result, onAplicarIe);
    return result;
  };

  const aplicarIeSugestao = () => {
    setIeSugestao(null);
    setIeOpcoes([]);
  };

  return {
    ieLookupLoading,
    ieLookupMessage,
    ieSugestao,
    ieOpcoes,
    iePreenchidaPelaSefaz,
    setIePreenchidaPelaSefaz,
    runIeLookup,
    runIeLookupManual,
    tryAutoConsultaIe,
    limparIeConsulta,
    aplicarIeSugestao,
    setIeLookupMessage,
    setIeSugestao,
    setIeOpcoes,
  };
}

export type UseConsultaIeSefazReturn = ReturnType<typeof useConsultaIeSefaz>;
