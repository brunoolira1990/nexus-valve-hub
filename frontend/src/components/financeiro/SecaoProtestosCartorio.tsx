import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import {
  analiseFinanceiraService,
  type ProtestoManualRegistro,
  type ProtestoManualResultado,
} from '@/services/api/analiseFinanceira';
import { apiErrorMessage } from '@/services/api/config';

/** URL pública fixa — sem CNPJ, token ou query dinâmica. */
export const URL_PESQUISA_PROTESTO = 'https://www.pesquisaprotesto.com.br/';

export const AVISO_COBERTURA_PROTESTO =
  'Esta consulta abrange protestos em cartório e não representa todas as dívidas ou restrições financeiras da empresa.';

const LABELS: Record<ProtestoManualResultado, string> = {
  SEM_PROTESTOS_INFORMADOS: 'Sem protestos informados',
  COM_PROTESTOS_INFORMADOS: 'Com protestos informados',
  CONSULTA_INCONCLUSIVA: 'Consulta inconclusiva',
};

type Props = {
  analiseId: number | null | undefined;
  podeVer?: boolean;
  podeRegistrar?: boolean;
  /** Injeta histórico (testes). */
  historicoInicial?: ProtestoManualRegistro[] | null;
  carregarHistorico?: boolean;
};

function Section({ title, children, testId }: { title: string; children: ReactNode; testId?: string }) {
  return (
    <section className="rounded border border-border bg-muted/20 p-3 space-y-3" data-testid={testId}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
}

function resultadoDe(reg: ProtestoManualRegistro | null | undefined): ProtestoManualResultado | null {
  const r = reg?.resultado_normalizado?.resultado;
  if (
    r === 'SEM_PROTESTOS_INFORMADOS' ||
    r === 'COM_PROTESTOS_INFORMADOS' ||
    r === 'CONSULTA_INCONCLUSIVA'
  ) {
    return r;
  }
  return null;
}

function unwrapList(
  data: { count?: number; results?: ProtestoManualRegistro[] } | ProtestoManualRegistro[],
): ProtestoManualRegistro[] {
  if (Array.isArray(data)) return data;
  return data.results || [];
}

export function SecaoProtestosCartorio({
  analiseId,
  podeVer = false,
  podeRegistrar = false,
  historicoInicial = null,
  carregarHistorico = true,
}: Props) {
  const [itens, setItens] = useState<ProtestoManualRegistro[]>(historicoInicial || []);
  const [loading, setLoading] = useState(Boolean(carregarHistorico && historicoInicial == null && podeVer && analiseId));
  const [erro, setErro] = useState<string | null>(null);
  const [formAberto, setFormAberto] = useState(false);
  const [historicoAberto, setHistoricoAberto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formErro, setFormErro] = useState<string | null>(null);

  const [resultado, setResultado] = useState<ProtestoManualResultado>('SEM_PROTESTOS_INFORMADOS');
  const [quantidade, setQuantidade] = useState('');
  const [ufs, setUfs] = useState('');
  const [cartorios, setCartorios] = useState('');
  const [observacao, setObservacao] = useState('');
  const [consultadoEm, setConsultadoEm] = useState('');
  const [corrigir, setCorrigir] = useState(false);
  const [motivoCorrecao, setMotivoCorrecao] = useState('');

  const carregar = useCallback(async () => {
    if (!podeVer || !analiseId || !carregarHistorico) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const data = await analiseFinanceiraService.listProtestosManuais(analiseId);
      setItens(unwrapList(data));
    } catch (e) {
      setErro(apiErrorMessage(e));
      setItens([]);
    } finally {
      setLoading(false);
    }
  }, [analiseId, carregarHistorico, podeVer]);

  useEffect(() => {
    if (historicoInicial != null) {
      setItens(historicoInicial);
      setLoading(false);
      return;
    }
    void carregar();
  }, [carregar, historicoInicial]);

  const recente = itens[0] || null;
  const anteriores = itens.slice(1);
  const resultadoRecente = resultadoDe(recente);

  const resetForm = () => {
    setResultado('SEM_PROTESTOS_INFORMADOS');
    setQuantidade('');
    setUfs('');
    setCartorios('');
    setObservacao('');
    setConsultadoEm('');
    setCorrigir(false);
    setMotivoCorrecao('');
    setFormErro(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!analiseId || !podeRegistrar) return;
    setBusy(true);
    setFormErro(null);
    try {
      const qRaw = quantidade.trim();
      let quantidade_informada: number | null | undefined;
      if (qRaw === '') {
        quantidade_informada = null;
      } else {
        const n = Number(qRaw);
        if (!Number.isInteger(n) || n < 0) {
          setFormErro('Quantidade inválida.');
          setBusy(false);
          return;
        }
        if (resultado === 'COM_PROTESTOS_INFORMADOS' && n === 0) {
          setFormErro('Com protestos informados, a quantidade (quando informada) deve ser maior que zero.');
          setBusy(false);
          return;
        }
        quantidade_informada = n;
      }
      if (resultado === 'CONSULTA_INCONCLUSIVA' && !observacao.trim()) {
        setFormErro('Consulta inconclusiva exige observação.');
        setBusy(false);
        return;
      }
      if (corrigir && recente && !motivoCorrecao.trim()) {
        setFormErro('Correção exige motivo.');
        setBusy(false);
        return;
      }
      await analiseFinanceiraService.registrarProtestoManual(analiseId, {
        resultado,
        quantidade_informada,
        ufs_informadas: ufs.trim() ? ufs.split(/[,;]/).map((x) => x.trim()).filter(Boolean) : [],
        cartorios_informados: cartorios.trim() || null,
        observacao: observacao.trim() || null,
        consultado_em: consultadoEm.trim()
          ? new Date(consultadoEm).toISOString()
          : undefined,
        registro_anterior_id: corrigir && recente ? recente.id : null,
        motivo_correcao: corrigir ? motivoCorrecao.trim() : null,
      });
      setFormAberto(false);
      resetForm();
      await carregar();
    } catch (err) {
      const msg = apiErrorMessage(err);
      // Erro da API do Nexus não deve ser convertido em “sem protestos”.
      setFormErro(msg || 'Não foi possível registrar o resultado.');
    } finally {
      setBusy(false);
    }
  };

  if (!podeVer) {
    return null;
  }

  return (
    <Section title="Protestos em cartório" testId="dossie-protestos-cartorio">
      <p className="text-xs text-muted-foreground" data-testid="dossie-protestos-aviso-cobertura">
        {AVISO_COBERTURA_PROTESTO}
      </p>
      <p className="text-xs text-muted-foreground" data-testid="dossie-protestos-aviso-manual">
        A consulta é realizada manualmente em portal externo.
      </p>

      <div className="flex flex-wrap gap-2">
        <a
          href={URL_PESQUISA_PROTESTO}
          target="_blank"
          rel="noopener noreferrer"
          className="erp-btn-outline erp-btn-sm inline-flex items-center"
          data-testid="dossie-btn-abrir-pesquisa-protesto"
        >
          Abrir Pesquisa Protesto
        </a>
        {podeRegistrar ? (
          <button
            type="button"
            className="erp-btn-secondary erp-btn-sm"
            data-testid="dossie-btn-registrar-protesto"
            onClick={() => {
              resetForm();
              setFormAberto(true);
            }}
          >
            Registrar resultado
          </button>
        ) : null}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="dossie-protestos-loading">
          Carregando registros…
        </p>
      ) : null}
      {erro ? (
        <p className="text-sm text-destructive" role="alert" data-testid="dossie-protestos-erro">
          {erro}
        </p>
      ) : null}

      {!loading && !erro && !recente ? (
        <p className="text-sm text-muted-foreground" data-testid="dossie-protestos-vazio">
          Nenhuma consulta manual registrada.
        </p>
      ) : null}

      {recente && resultadoRecente ? (
        <div className="space-y-1 text-sm" data-testid="dossie-protestos-recente">
          <p className="font-medium" data-testid="dossie-protestos-recente-status">
            {LABELS[resultadoRecente]}
            <span className="ml-2 text-xs font-normal text-muted-foreground">Registro manual</span>
          </p>
          {recente.resultado_normalizado?.quantidade_informada != null ? (
            <p data-testid="dossie-protestos-quantidade">
              Quantidade informada: {recente.resultado_normalizado.quantidade_informada}
            </p>
          ) : null}
          {(recente.resultado_normalizado?.ufs_informadas || []).length > 0 ? (
            <p data-testid="dossie-protestos-ufs">
              UFs: {(recente.resultado_normalizado?.ufs_informadas || []).join(', ')}
            </p>
          ) : null}
          {recente.resultado_normalizado?.cartorios_informados ? (
            <p data-testid="dossie-protestos-cartorios">
              Cartórios: {recente.resultado_normalizado.cartorios_informados}
            </p>
          ) : null}
          <p data-testid="dossie-protestos-consultado-em">
            Consultado em: {formatDateTime(recente.resultado_normalizado?.consultado_em)}
          </p>
          <p data-testid="dossie-protestos-registrado-em">
            Registrado em: {formatDateTime(recente.resultado_normalizado?.registrado_em || recente.solicitada_em)}
          </p>
          <p data-testid="dossie-protestos-responsavel">
            Responsável: {recente.resultado_normalizado?.registrado_por?.nome_exibicao || '—'}
          </p>
          {recente.resultado_normalizado?.observacao ? (
            <p data-testid="dossie-protestos-observacao">Observação: {recente.resultado_normalizado.observacao}</p>
          ) : null}
          {recente.resultado_normalizado?.motivo_correcao ? (
            <p data-testid="dossie-protestos-motivo-correcao">
              Motivo da correção: {recente.resultado_normalizado.motivo_correcao}
            </p>
          ) : null}
        </div>
      ) : null}

      {anteriores.length > 0 ? (
        <div>
          <button
            type="button"
            className="text-sm underline text-muted-foreground"
            data-testid="dossie-protestos-toggle-historico"
            onClick={() => setHistoricoAberto((v) => !v)}
          >
            {historicoAberto ? 'Ocultar histórico' : `Ver histórico (${anteriores.length})`}
          </button>
          {historicoAberto ? (
            <ul className="mt-2 space-y-2" data-testid="dossie-protestos-historico">
              {anteriores.map((item) => {
                const res = resultadoDe(item);
                return (
                  <li key={item.id} className="text-xs text-muted-foreground border-t border-border pt-2">
                    <span>{res ? LABELS[res] : item.status}</span>
                    {' · '}
                    {item.resultado_normalizado?.registrado_por?.nome_exibicao || '—'}
                    {' · '}
                    {formatDateTime(item.resultado_normalizado?.registrado_em || item.solicitada_em)}
                    {item.resultado_normalizado?.motivo_correcao
                      ? ` · Correção: ${item.resultado_normalizado.motivo_correcao}`
                      : null}
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}

      {formAberto && podeRegistrar ? (
        <form className="space-y-2 border-t border-border pt-3" onSubmit={onSubmit} data-testid="dossie-protestos-form">
          <label className="block text-sm">
            Resultado
            <select
              className="erp-input mt-1"
              value={resultado}
              onChange={(e) => setResultado(e.target.value as ProtestoManualResultado)}
              data-testid="dossie-protestos-campo-resultado"
            >
              <option value="SEM_PROTESTOS_INFORMADOS">Sem protestos informados</option>
              <option value="COM_PROTESTOS_INFORMADOS">Com protestos informados</option>
              <option value="CONSULTA_INCONCLUSIVA">Consulta inconclusiva</option>
            </select>
          </label>
          <label className="block text-sm">
            Quantidade informada (opcional)
            <input
              className="erp-input mt-1"
              type="number"
              min={0}
              value={quantidade}
              onChange={(e) => setQuantidade(e.target.value)}
              data-testid="dossie-protestos-campo-quantidade"
            />
          </label>
          <label className="block text-sm">
            UFs informadas (opcional, separadas por vírgula)
            <input
              className="erp-input mt-1"
              value={ufs}
              onChange={(e) => setUfs(e.target.value)}
              data-testid="dossie-protestos-campo-ufs"
            />
          </label>
          <label className="block text-sm">
            Cartórios informados (opcional)
            <input
              className="erp-input mt-1"
              value={cartorios}
              onChange={(e) => setCartorios(e.target.value)}
              data-testid="dossie-protestos-campo-cartorios"
            />
          </label>
          <label className="block text-sm">
            Observação {resultado === 'CONSULTA_INCONCLUSIVA' ? '(obrigatória)' : '(opcional)'}
            <textarea
              className="erp-input mt-1 min-h-[60px]"
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
              data-testid="dossie-protestos-campo-observacao"
            />
          </label>
          <label className="block text-sm">
            Consultado em (opcional)
            <input
              className="erp-input mt-1"
              type="datetime-local"
              value={consultadoEm}
              onChange={(e) => setConsultadoEm(e.target.value)}
              data-testid="dossie-protestos-campo-consultado-em"
            />
          </label>
          {recente ? (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={corrigir}
                onChange={(e) => setCorrigir(e.target.checked)}
                data-testid="dossie-protestos-campo-corrigir"
              />
              Correção do registro mais recente
            </label>
          ) : null}
          {corrigir ? (
            <label className="block text-sm">
              Motivo da correção
              <input
                className="erp-input mt-1"
                value={motivoCorrecao}
                onChange={(e) => setMotivoCorrecao(e.target.value)}
                data-testid="dossie-protestos-campo-motivo-correcao"
              />
            </label>
          ) : null}
          {formErro ? (
            <p className="text-sm text-destructive" role="alert" data-testid="dossie-protestos-form-erro">
              {formErro}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className="erp-btn-primary erp-btn-sm" disabled={busy} data-testid="dossie-protestos-salvar">
              Salvar registro
            </button>
            <button
              type="button"
              className="erp-btn-ghost erp-btn-sm"
              disabled={busy}
              onClick={() => {
                setFormAberto(false);
                resetForm();
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : null}
    </Section>
  );
}
