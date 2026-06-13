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
