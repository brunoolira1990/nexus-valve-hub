import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { empresasService } from '@/services/api/empresas';
import {
  nfeSefazService,
  type CertificadoNfeValidacao,
  type NFeSefazConsultaResponse,
  type NFeSefazStatusConsulta,
} from '@/services/api/nfeSefaz';
import { apiErrorMessage } from '@/services/api/config';
import { nfeSaidasService, type NFeContingenciaStatus } from '@/services/api/fiscal';
import {
  ambienteLabel,
  cStatExibicao,
  consultaFalhou,
  consultaOk,
  empresaPareceFixture,
  escolherEmpresaInicial,
  erroHistoricoResumo,
  formatAmbienteUf,
  mensagemEmpresaBloqueada,
  motivoExibicao,
  resultadoHistoricoLabel,
  rotuloEmpresaSefaz,
  subtituloPaginaSefaz,
  tituloPaginaSefaz,
  tituloUltimoRetorno,
} from '@/lib/nfeSefazUx';
import type { Empresa } from '@/types';

const NFeSefazIntegracao = () => {
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [empresaId, setEmpresaId] = useState<number | ''>('');
  const [uf, setUf] = useState('SP');
  const [homologacao, setHomologacao] = useState(true);
  const [historico, setHistorico] = useState<NFeSefazStatusConsulta[]>([]);
  const [ultimo, setUltimo] = useState<NFeSefazConsultaResponse | null>(null);
  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [validandoCert, setValidandoCert] = useState(false);
  const [certInfo, setCertInfo] = useState<CertificadoNfeValidacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [mostrarErroTecnico, setMostrarErroTecnico] = useState(false);
  const [contingencia, setContingencia] = useState<NFeContingenciaStatus | null>(null);
  const [contingenciaLoading, setContingenciaLoading] = useState(false);
  const [contingenciaAtivando, setContingenciaAtivando] = useState(false);
  const [contingenciaEncerrando, setContingenciaEncerrando] = useState(false);
  const [contingenciaTransmitindo, setContingenciaTransmitindo] = useState(false);
  const [contingenciaMsg, setContingenciaMsg] = useState<string | null>(null);
  const [ativarOpen, setAtivarOpen] = useState(false);
  const [ativarMotivo, setAtivarMotivo] = useState('');
  const [ativarTpEmis, setAtivarTpEmis] = useState('2');
  const [encerrarConfirmOpen, setEncerrarConfirmOpen] = useState(false);

  const load = async () => {
    const [emps, hist] = await Promise.all([
      empresasService.getAll(),
      nfeSefazService.listarHistorico(),
    ]);
    setEmpresas(emps);
    setHistorico(hist);
    if (emps.length && !empresaId) setEmpresaId(escolherEmpresaInicial(emps));
  };

  useEffect(() => {
    load().catch((e) => setErro(apiErrorMessage(e)));
  }, []);

  const carregarContingencia = async (empId: number) => {
    try {
      setContingenciaLoading(true);
      const st = await nfeSaidasService.contingenciaStatus(empId);
      setContingencia(st);
    } catch (e) {
      // Falha de leitura não bloqueia a tela; o card exibe estado neutro.
      setContingencia(null);
    } finally {
      setContingenciaLoading(false);
    }
  };

  useEffect(() => {
    if (empresaId) {
      void carregarContingencia(Number(empresaId));
    } else {
      setContingencia(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empresaId]);

  const empresaSelecionada = empresas.find((e) => e.id === empresaId);
  const empresaFixture = empresaSelecionada ? empresaPareceFixture(empresaSelecionada) : false;
  const consultaBloqueada =
    empresaFixture ||
    !empresaSelecionada?.certificado_arquivo ||
    certInfo?.consulta_sefaz_permitida === false ||
    certInfo?.empresa_fixture_teste === true;

  const handleValidarCert = async () => {
    if (!empresaId) return;
    setValidandoCert(true);
    setErro(null);
    try {
      const r = await nfeSefazService.validarCertificadoEmpresa(Number(empresaId));
      setCertInfo(r);
    } catch (e) {
      setErro(apiErrorMessage(e));
      setCertInfo({ valido: false, erro: apiErrorMessage(e), mensagens: [apiErrorMessage(e)] });
    } finally {
      setValidandoCert(false);
    }
  };

  const handleConsultar = async () => {
    if (!empresaId) return;
    void carregarContingencia(Number(empresaId));
    if (empresaFixture) {
      setErro(mensagemEmpresaBloqueada({ tipo_erro: 'EMPRESA_BLOQUEADA' }));
      return;
    }
    if (certInfo?.consulta_sefaz_permitida === false) {
      setErro(certInfo.consulta_sefaz_motivo || mensagemEmpresaBloqueada({ tipo_erro: 'EMPRESA_BLOQUEADA' }));
      return;
    }
    setLoading(true);
    setErro(null);
    setMostrarErroTecnico(false);
    try {
      const r = await nfeSefazService.consultarStatusServico({
        empresa_id: Number(empresaId),
        uf,
        homologacao,
      });
      const normalizado: NFeSefazConsultaResponse = {
        ...r,
        ok: r.ok ?? r.sucesso,
        c_stat: r.c_stat || r.cstat || '',
        x_motivo: r.motivo || r.x_motivo || '',
        empresa_razao_social:
          r.empresa_razao_social || empresaSelecionada?.razao_social || '',
      };
      setUltimo(normalizado);
      await load();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const handleAtivarContingencia = async () => {
    if (!empresaId) return;
    const motivo = ativarMotivo.trim();
    if (motivo.length < 10) {
      setContingenciaMsg('Informe um motivo com ao menos 10 caracteres (ex.: "SEFAZ-SP indisponível desde as 14h").');
      return;
    }
    setContingenciaAtivando(true);
    setContingenciaMsg(null);
    try {
      const st = await nfeSaidasService.contingenciaAtivar({
        empresa_id: Number(empresaId),
        motivo,
        tp_emis: ativarTpEmis,
      });
      setContingencia(st);
      setAtivarOpen(false);
      setAtivarMotivo('');
      setContingenciaMsg(`Contingência ativada em ${st.tp_emis_label || `tpEmis ${st.tp_emis}`} — inicie a emissão em contingência nas NFs com erro de transmissão.`);
    } catch (e) {
      setContingenciaMsg(apiErrorMessage(e));
    } finally {
      setContingenciaAtivando(false);
    }
  };

  const handleEncerrarContingencia = async () => {
    if (!empresaId) return;
    setEncerrarConfirmOpen(false);
    setContingenciaEncerrando(true);
    setContingenciaMsg(null);
    try {
      await nfeSaidasService.contingenciaEncerrar(Number(empresaId));
      setContingencia(null);
      await carregarContingencia(Number(empresaId));
      setContingenciaMsg('Contingência encerrada. As NFs emitidas em contingência seguem pendentes de transmissão.');
    } catch (e) {
      setContingenciaMsg(apiErrorMessage(e));
    } finally {
      setContingenciaEncerrando(false);
    }
  };

  const handleTransmitirPendentes = async () => {
    if (!empresaId) return;
    setContingenciaTransmitindo(true);
    setContingenciaMsg(null);
    try {
      const res = await nfeSaidasService.contingenciaTransmitirPendentes(Number(empresaId));
      const total = res.total ?? 0;
      const sucesso = Array.isArray(res.sucesso) ? res.sucesso.length : 0;
      const falhas = Array.isArray(res.falhas) ? res.falhas.length : 0;
      if (total === 0) {
        setContingenciaMsg('Não há NFs emitidas em contingência pendentes de transmissão.');
      } else {
        const linhas = [
          `Transmissão concluída: ${sucesso} de ${total} NFs transmitidas com sucesso.`,
          ...(falhas > 0
            ? [`Atenção: ${falhas} NF(s) ainda pendentes — ${res.falhas.slice(0, 3).map((f) => `NF ${f.numero || f.nfe_id}`)}. Verifique a SEFAZ e tente novamente.`]
            : []),
          res.contingencia_encerrada ? 'Contingência encerrada automaticamente (não havia NFs pendentes).' : '',
        ].filter(Boolean);
        setContingenciaMsg(linhas.join(' '));
      }
      await carregarContingencia(Number(empresaId));
      await load();
    } catch (e) {
      setContingenciaMsg(apiErrorMessage(e));
    } finally {
      setContingenciaTransmitindo(false);
    }
  };

  const registroDetalhe =
    detalheId != null
      ? historico.find((h) => h.id === detalheId) ?? (ultimo?.id === detalheId ? ultimo : null)
      : null;

  const cardFalha = ultimo && consultaFalhou(ultimo);

  return (
    <div className="space-y-6">
      <PageHeader
        title={tituloPaginaSefaz(homologacao)}
        subtitle={subtituloPaginaSefaz(homologacao)}
      />

      {erro ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {erro}
        </div>
      ) : null}

      <section className="erp-card p-4 space-y-4">
        <h2 className="text-sm font-semibold">Parâmetros da consulta</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="md:col-span-2">
            <label className="erp-label">Empresa emitente</label>
            <select
              className="erp-select mt-1 w-full"
              value={empresaId}
              onChange={(e) => {
                setEmpresaId(e.target.value ? Number(e.target.value) : '');
                setCertInfo(null);
              }}
            >
              <option value="">Selecione</option>
              {empresas.map((e) => (
                <option key={e.id} value={e.id}>
                  {rotuloEmpresaSefaz(e)}
                </option>
              ))}
            </select>
            {empresaFixture ? (
              <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                Empresa de teste (fixture). Selecione a empresa real com certificado A1 válido.
              </p>
            ) : null}
            {empresaSelecionada && !empresaSelecionada.certificado_arquivo ? (
              <p className="mt-1 text-xs text-destructive">
                Esta empresa não possui certificado A1 cadastrado.
              </p>
            ) : null}
          </div>
          <div>
            <label className="erp-label">UF SEFAZ</label>
            <input
              className="erp-input mt-1 w-full"
              value={uf}
              onChange={(e) => setUf(e.target.value.toUpperCase())}
              maxLength={2}
            />
          </div>
          <div>
            <label className="erp-label">Ambiente</label>
            <select
              className="erp-select mt-1 w-full"
              value={homologacao ? 'homologacao' : 'producao'}
              onChange={(e) => setHomologacao(e.target.value === 'homologacao')}
            >
              <option value="homologacao">Homologação</option>
              <option value="producao">Produção</option>
            </select>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="erp-btn-outline"
            disabled={!empresaId || validandoCert}
            onClick={handleValidarCert}
          >
            {validandoCert ? 'Validando…' : 'Validar certificado A1'}
          </button>
          <button
            type="button"
            className="erp-btn-primary"
            disabled={!empresaId || loading || consultaBloqueada}
            onClick={handleConsultar}
          >
            {loading ? 'Consultando SEFAZ…' : 'Consultar status do serviço (PyNFe)'}
          </button>
        </div>
        {certInfo ? (
          <div
            className={`text-sm rounded border p-3 ${
              certInfo.valido
                ? 'border-green-600/40 bg-green-50 dark:bg-green-950/20'
                : 'border-destructive/40 bg-destructive/10'
            }`}
          >
            <p>
              Certificado:{' '}
              <span className={certInfo.valido ? 'text-green-700 font-medium' : 'text-destructive font-medium'}>
                {certInfo.valido ? 'Válido' : 'Inválido'}
              </span>
            </p>
            {certInfo.titular || certInfo.razao_social ? (
              <p>Titular: {certInfo.titular || certInfo.razao_social}</p>
            ) : null}
            {certInfo.cnpj ? <p>CNPJ: {certInfo.cnpj}</p> : null}
            {certInfo.cpf ? <p>CPF: {certInfo.cpf}</p> : null}
            {certInfo.validade_inicio ? <p>Início validade: {certInfo.validade_inicio}</p> : null}
            {certInfo.validade_fim ? <p>Fim validade: {certInfo.validade_fim}</p> : null}
            {certInfo.dias_para_vencimento != null ? (
              <p>Dias para vencimento: {certInfo.dias_para_vencimento}</p>
            ) : null}
            {certInfo.vencido ? <p className="text-destructive font-medium">Certificado vencido</p> : null}
            {certInfo.erro ? <p className="text-destructive">{certInfo.erro}</p> : null}
            {certInfo.mensagens?.map((m) => (
              <p key={m}>{m}</p>
            ))}
          </div>
        ) : null}
      </section>

      <section className="erp-card p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Contingência SEFAZ (NF-e)</h2>
          {contingenciaLoading ? (
            <span className="text-xs text-muted-foreground">Carregando…</span>
          ) : contingencia ? (
            <span className={contingencia.ativa ? 'erp-badge-danger' : 'erp-badge-success'}>
              {contingencia.ativa ? `Em contingência — ${contingencia.tp_emis_label || `tpEmis ${contingencia.tp_emis}`}` : 'Emissão normal'}
            </span>
          ) : null}
        </div>
        {contingenciaMsg ? (
          <div
            className={`text-sm rounded-md border p-3 ${
              contingenciaMsg.toLowerCase().includes('atenção') ||
              contingenciaMsg.toLowerCase().includes('erro') ||
              contingenciaMsg.toLowerCase().includes('falha') ||
              contingenciaMsg.toLowerCase().includes('ainda pendente')
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
                : 'border-border bg-muted/20'
            }`}
          >
            {contingenciaMsg}
          </div>
        ) : null}
        {contingencia?.ativa ? (
          <div className="text-sm space-y-2">
            <p>
              <span className="font-medium">Modo:</span> {contingencia.tp_emis_label || `tpEmis ${contingencia.tp_emis}`}
            </p>
            <p>
              <span className="font-medium">Motivo:</span> {contingencia.motivo || '—'}
            </p>
            {contingencia.inicio ? (
              <p>
                <span className="font-medium">Início:</span>{' '}
                {new Date(contingencia.inicio).toLocaleString('pt-BR')}
                {contingencia.tempo_ativo_horas != null ? ` (${Number(contingencia.tempo_ativo_horas).toFixed(1)}h ativas)` : ''}
              </p>
            ) : null}
            <p>
              <span className="font-medium">NFs pendentes de transmissão:</span>{' '}
              {contingencia.nfe_pendentes}
            </p>
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
              A NF-e emitida em contingência (EPEC — tpEmis 2) deve ser transmitida à SEFAZ em até 168h
              (7 dias) após o restabelecimento do serviço. Enquanto a contingência estiver ativa, use o
              botão «Emitir em contingência» no modal de conferência das NFs com erro de transmissão.
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="erp-btn-outline"
                disabled={contingenciaTransmitindo}
                onClick={() => void handleTransmitirPendentes()}
              >
                {contingenciaTransmitindo ? 'Transmitindo pendentes…' : `Transmitir pendentes em contingência (${contingencia.nfe_pendentes})`}
              </button>
              <button
                type="button"
                className="erp-btn-outline border-destructive/50 text-destructive hover:bg-destructive/10"
                disabled={contingenciaEncerrando}
                onClick={() => setEncerrarConfirmOpen(true)}
              >
                {contingenciaEncerrando ? 'Encerrando…' : 'Encerrar contingência'}
              </button>
            </div>
          </div>
        ) : (
          <div className="text-sm space-y-2">
            <p className="text-muted-foreground">
              Nenhum modo de contingência ativo para a empresa selecionada. Ative apenas quando a SEFAZ
              de origem (e as SVCs) estiverem indisponíveis — usar contingência com a SEFAZ operando é irregular.
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="erp-btn-outline" disabled={!empresaId} onClick={() => setAtivarOpen(true)}>
                Ativar contingência SEFAZ
              </button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {ativarOpen ? (
            <div className="w-full rounded-md border border-border bg-muted/10 p-4 space-y-3">
              <h3 className="text-sm font-semibold">Ativar contingência SEFAZ</h3>
              <p className="text-xs text-muted-foreground">
                Informe o motivo técnico (obrigatório, mínimo 10 caracteres). O modo EPEC (tpEmis 2) é o
                recomendado para indisponibilidade da SEFAZ de origem e das SVCs.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="erp-label">Motivo da contingência</label>
                  <input
                    className="erp-input mt-1 w-full"
                    placeholder="Ex.: SEFAZ-SP indisponível desde as 14h"
                    value={ativarMotivo}
                    maxLength={200}
                    onChange={(e) => setAtivarMotivo(e.target.value)}
                  />
                </div>
                <div>
                  <label className="erp-label">Modo (tpEmis)</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={ativarTpEmis}
                    onChange={(e) => setAtivarTpEmis(e.target.value)}
                  >
                    <option value="2">EPEC — tpEmis 2 (recomendado)</option>
                    <option value="6">SVC-RS — tpEmis 6 (requer habilitação da UF)</option>
                    <option value="7">SVC-AN — tpEmis 7 (requer habilitação da UF)</option>
                  </select>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="erp-btn-primary"
                  disabled={contingenciaAtivando}
                  onClick={() => void handleAtivarContingencia()}
                >
                  {contingenciaAtivando ? 'Ativando…' : 'Confirmar ativação'}
                </button>
                <button type="button" className="erp-btn-outline" onClick={() => setAtivarOpen(false)}>
                  Cancelar
                </button>
              </div>
            </div>
          ) : null}

          {encerrarConfirmOpen ? (
            <div className="w-full rounded-md border border-amber-500/40 bg-amber-500/10 p-4 space-y-3">
              <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-100">Encerrar contingência?</h3>
              <p className="text-sm">
                Ao encerrar, a emissão volta ao modo normal. As NFs emitidas em contingência ficam pendentes
                de transmissão — use «Transmitir pendentes em contingência» antes de encerrar, ou depois que
                a SEFAZ estiver estável.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="erp-btn-primary"
                  disabled={contingenciaEncerrando}
                  onClick={() => void handleEncerrarContingencia()}
                >
                  {contingenciaEncerrando ? 'Encerrando…' : 'Confirmar encerramento'}
                </button>
                <button type="button" className="erp-btn-outline" onClick={() => setEncerrarConfirmOpen(false)}>
                  Cancelar
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      {ultimo ? (
        <section
          className={`erp-card p-4 space-y-3 ${
            cardFalha ? 'border-amber-500/50 bg-amber-50/50 dark:bg-amber-950/20' : ''
          }`}
        >
          <h2 className={`text-sm font-semibold ${cardFalha ? 'text-amber-800 dark:text-amber-200' : ''}`}>
            {tituloUltimoRetorno(ultimo)}
          </h2>
          {cardFalha ? (
            <div className="text-sm space-y-1">
              <p>
                <span className="font-medium">Tipo de erro:</span>{' '}
                {ultimo.tipo_erro || 'FALHA'}
              </p>
              {ultimo.empresa_razao_social ? (
                <p>
                  <span className="font-medium">Empresa:</span> {ultimo.empresa_razao_social}
                </p>
              ) : null}
              <p>{formatAmbienteUf(ultimo.ambiente || ambienteLabel(homologacao), ultimo.uf)}</p>
              <p>
                <span className="font-medium">Motivo:</span> {motivoExibicao(ultimo)}
              </p>
              {ultimo.tipo_erro === 'PARSE_ERROR' ? (
                <p className="text-xs text-muted-foreground">
                  A resposta não veio como XML/SOAP SEFAZ. Confira endpoint, certificado A1, rede e
                  proxy local (HTTP_PROXY/HTTPS_PROXY).
                </p>
              ) : null}
            </div>
          ) : null}
          <p className="text-sm">
            <span className="font-medium">cStat:</span>{' '}
            {cStatExibicao(ultimo) || (cardFalha ? '—' : '—')}
            {!cardFalha ? (
              <>
                <span className="font-medium ml-3">Motivo SEFAZ:</span> {motivoExibicao(ultimo)}
              </>
            ) : null}
          </p>
          <p className="text-sm text-muted-foreground">
            UF {ultimo.uf} · {ultimo.ambiente} · {ultimo.consultado_em}
            {consultaOk(ultimo) ? ' · Serviço em operação' : ''}
            {ultimo.tipo_erro ? ` · ${ultimo.tipo_erro}` : ''}
          </p>
          {ultimo.endpoint_sefaz ? (
            <p className="text-xs text-muted-foreground break-all">Endpoint: {ultimo.endpoint_sefaz}</p>
          ) : null}
          {ultimo.diagnostico_http?.http_status || ultimo.diagnostico_http?.content_type ? (
            <p className="text-xs text-muted-foreground">
              {ultimo.diagnostico_http.http_status ? `HTTP ${ultimo.diagnostico_http.http_status}` : ''}
              {ultimo.diagnostico_http.http_status && ultimo.diagnostico_http.content_type ? ' · ' : ''}
              {ultimo.diagnostico_http.content_type
                ? `Content-Type: ${ultimo.diagnostico_http.content_type}`
                : ''}
              {ultimo.diagnostico_http.html_titulo
                ? ` · título: ${ultimo.diagnostico_http.html_titulo}`
                : ''}
            </p>
          ) : null}
          {ultimo.ver_aplic ? <p className="text-xs text-muted-foreground">verAplic: {ultimo.ver_aplic}</p> : null}
          {ultimo.erro_tecnico ? (
            <div>
              <button
                type="button"
                className="text-xs text-primary underline"
                onClick={() => setMostrarErroTecnico((v) => !v)}
              >
                {mostrarErroTecnico ? 'Ocultar detalhe técnico' : 'Ver detalhe técnico'}
              </button>
              {mostrarErroTecnico ? (
                <pre className="mt-2 text-xs p-2 rounded bg-muted overflow-x-auto max-h-40 whitespace-pre-wrap">
                  {ultimo.erro_tecnico}
                </pre>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="erp-card overflow-hidden">
        <h2 className="text-sm font-semibold p-4 border-b border-border">Histórico de consultas</h2>
        <div className="overflow-x-auto">
          <table className="erp-table w-full text-sm">
            <thead>
              <tr>
                <th>Data</th>
                <th>Empresa</th>
                <th>UF</th>
                <th>Ambiente</th>
                <th>cStat</th>
                <th>Motivo</th>
                <th>Resultado</th>
                <th>Erro</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {historico.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-4 text-muted-foreground">
                    Nenhuma consulta registrada.
                  </td>
                </tr>
              ) : (
                historico.map((h) => {
                  const resumo = {
                    ok: h.sucesso,
                    sucesso: h.sucesso,
                    c_stat: h.c_stat,
                    x_motivo: h.x_motivo,
                    erro_tecnico: h.erro_tecnico,
                    tipo_erro: h.tipo_erro,
                    servico_operacional: h.servico_operacional,
                  };
                  return (
                    <tr key={h.id}>
                      <td>{new Date(h.consultado_em).toLocaleString('pt-BR')}</td>
                      <td className="max-w-[140px] truncate" title={h.empresa_razao_social}>
                        {h.empresa_razao_social}
                      </td>
                      <td>{h.uf}</td>
                      <td>{h.ambiente}</td>
                      <td>{cStatExibicao(resumo) || (consultaFalhou(resumo) ? '—' : '—')}</td>
                      <td className="max-w-xs truncate" title={motivoExibicao(resumo)}>
                        {motivoExibicao(resumo)}
                      </td>
                      <td>
                        <span
                          className={
                            h.sucesso
                              ? 'text-green-700 font-medium'
                              : 'text-amber-700 dark:text-amber-400 font-medium'
                          }
                        >
                          {resultadoHistoricoLabel(resumo)}
                        </span>
                      </td>
                      <td className="max-w-[120px] truncate text-muted-foreground" title={h.erro_tecnico}>
                        {erroHistoricoResumo(resumo)}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="text-xs text-primary underline"
                          onClick={() => setDetalheId(h.id)}
                        >
                          Ver detalhes
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {registroDetalhe ? (
        <section className="erp-card p-4 space-y-2 border-primary/30">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-semibold">Detalhes da consulta #{registroDetalhe.id}</h2>
            <button type="button" className="text-xs underline" onClick={() => setDetalheId(null)}>
              Fechar
            </button>
          </div>
          <p className="text-sm">
            cStat: {cStatExibicao(registroDetalhe) || '—'} · Motivo: {motivoExibicao(registroDetalhe)}
          </p>
          {registroDetalhe.tipo_erro ? (
            <p className="text-sm">
              Tipo erro: <code>{registroDetalhe.tipo_erro}</code>
            </p>
          ) : null}
          {registroDetalhe.erro_tecnico ? (
            <div>
              <p className="text-xs font-medium text-muted-foreground">Erro técnico</p>
              <pre className="text-xs p-2 rounded bg-muted overflow-x-auto max-h-32 whitespace-pre-wrap">
                {registroDetalhe.erro_tecnico}
              </pre>
            </div>
          ) : null}
          {(registroDetalhe.xml_resposta || registroDetalhe.raw_response) ? (
            <div>
              <p className="text-xs font-medium text-muted-foreground">XML / resposta bruta</p>
              <pre className="text-xs p-2 rounded bg-muted overflow-x-auto max-h-48 whitespace-pre-wrap">
                {(registroDetalhe.xml_resposta || registroDetalhe.raw_response || '').slice(0, 4000)}
              </pre>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {new Date(registroDetalhe.consultado_em).toLocaleString('pt-BR')}
          </p>
        </section>
      ) : null}
    </div>
  );
};

export default NFeSefazIntegracao;
