import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/Modal';
import {
  MSG_DADOS_PROPRIOS_PENDENTES_CQ,
  MSG_DADOS_PROPRIOS_MANUAIS_CQ,
  MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ,
  MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ,
  TITULO_MODAL_CORRIDAS_CF_CQ,
  errosSelecaoCorridasCfCq,
  resumoDistribuicaoCorridasCfCq,
  type CorridaCfParaCq,
  type CorridasCfParaCqResponse,
  type ModoDadosTecnicosCorridaCq,
  type SelecaoCorridaCfCq,
} from '@/lib/cqCorridasCfUi';

type SelecaoEstado = {
  selecionada: boolean;
  quantidade: string;
  dadosTecnicos: ModoDadosTecnicosCorridaCq;
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
  dados: CorridasCfParaCqResponse | null;
  carregando: boolean;
  erroCarregamento: string | null;
  quantidadeTotalItem: number;
  selecoesIniciais: SelecaoCorridaCfCq[];
  /** Identidade do contexto (item/produto/CF). Troca limpa seleções anteriores. */
  contextoChave?: string;
  /** Retorna false quando o editor cancela a confirmação de substituição. */
  onAplicar: (selecoes: SelecaoCorridaCfCq[]) => boolean;
};

const estadoInicial = (_linha: CorridaCfParaCq): SelecaoEstado => ({
  selecionada: false,
  quantidade: '',
  dadosTecnicos: 'herdados',
});

/**
 * Seleção de corridas do CF/item EXATOS vinculados ao item do CQ, com quantidade
 * por corrida e escolha de dados técnicos (herdados × próprios) por linha.
 */
export function ModalCorridasCertificadoFornecedor({
  isOpen,
  onClose,
  dados,
  carregando,
  erroCarregamento,
  quantidadeTotalItem,
  selecoesIniciais,
  contextoChave = '',
  onAplicar,
}: Props) {
  const [estados, setEstados] = useState<Record<string, SelecaoEstado>>({});
  const [aplicando, setAplicando] = useState(false);

  const linhas = dados?.linhas ?? [];

  useEffect(() => {
    if (!isOpen) {
      setEstados({});
      setAplicando(false);
      return;
    }
    // Sem payload (carregando/erro) ou troca de contexto: não reaproveitar seleção antiga.
    if (!dados) {
      setEstados({});
      setAplicando(false);
      return;
    }
    setAplicando(false);
    setEstados(Object.fromEntries(
      dados.linhas.map((linha) => {
        const existente = selecoesIniciais.find(
          (selecao) => selecao.linha.chave_origem === linha.chave_origem,
        );
        return [
          linha.chave_origem,
          existente
            ? {
                selecionada: true,
                quantidade: existente.quantidade,
                dadosTecnicos: existente.dadosTecnicos,
              }
            : estadoInicial(linha),
        ];
      }),
    ));
  }, [dados, isOpen, selecoesIniciais, contextoChave]);

  const estadoDe = (linha: CorridaCfParaCq): SelecaoEstado =>
    estados[linha.chave_origem] ?? estadoInicial(linha);

  const patchEstado = (linha: CorridaCfParaCq, patch: Partial<SelecaoEstado>) =>
    setEstados((prev) => ({
      ...prev,
      [linha.chave_origem]: { ...estadoDe(linha), ...patch },
    }));

  const selecoes: SelecaoCorridaCfCq[] = useMemo(
    () =>
      linhas
        .filter((l) => estadoDe(l).selecionada)
        .map((l) => {
          const e = estadoDe(l);
          return { linha: l, quantidade: e.quantidade, dadosTecnicos: e.dadosTecnicos };
        }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [linhas, estados],
  );

  const erros = useMemo(
    () => errosSelecaoCorridasCfCq(quantidadeTotalItem, selecoes),
    [quantidadeTotalItem, selecoes],
  );
  const resumo = resumoDistribuicaoCorridasCfCq(quantidadeTotalItem, selecoes);
  const podeAplicar = (
    !carregando
    && !erroCarregamento
    && !aplicando
    && selecoes.length > 0
    && erros.length === 0
  );

  const aplicar = () => {
    if (!podeAplicar || aplicando) return;
    setAplicando(true);
    const ok = onAplicar(selecoes);
    if (ok) {
      setEstados({});
      // Mantém `aplicando` até fechar/trocar contexto — impede reenvio se o modal
      // permanecer montado por um instante após a aplicação.
      return;
    }
    setAplicando(false);
  };

  const fechar = () => {
    setEstados({});
    setAplicando(false);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={fechar}
      title={TITULO_MODAL_CORRIDAS_CF_CQ}
      size="xl"
      stacked
      footer={
        <div className="p-3 flex flex-col gap-2">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <span>Total do item do CQ: <strong>{resumo.quantidadeTotal}</strong></span>
            <span>Total distribuído: <strong>{resumo.totalDistribuido}</strong></span>
            <span>Saldo a distribuir: <strong>{resumo.saldoRestante}</strong></span>
          </div>
          {selecoes.length > 0 && erros.length > 0 ? (
            <ul className="text-sm text-destructive list-disc pl-5" role="alert">
              {erros.map((e) => <li key={e}>{e}</li>)}
            </ul>
          ) : null}
          <div className="flex justify-end gap-2">
            <button type="button" className="erp-btn-outline" onClick={fechar} disabled={aplicando}>
              Cancelar
            </button>
            <button
              type="button"
              className="erp-btn-primary"
              disabled={!podeAplicar}
              aria-disabled={!podeAplicar}
              onClick={aplicar}
            >
              {aplicando ? 'Aplicando…' : 'Aplicar corridas selecionadas'}
            </button>
          </div>
        </div>
      }
    >
      {carregando ? (
        <p className="text-sm text-muted-foreground">Carregando corridas do certificado…</p>
      ) : erroCarregamento ? (
        <p className="text-sm text-destructive" role="alert">{erroCarregamento}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Somente corridas do Certificado de Fornecedor e item exatos já vinculados a este item do CQ.
            Cada corrida selecionada vira um item independente do certificado, com quantidade própria.
            A confirmação abaixo altera apenas o editor; use o salvamento normal do CQ para persistir.
          </p>
          {(dados?.avisos ?? []).map((aviso) => (
            <p key={aviso} className="text-xs text-amber-700 dark:text-amber-300" role="status">
              {aviso}
            </p>
          ))}
          {linhas.length === 0 ? (
            <p className="text-sm text-muted-foreground" role="status">
              {MSG_ESTADO_VAZIO_CORRIDAS_CF_CQ}
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-border">
                  <th className="py-1 pr-2">Selecionar</th>
                  <th className="py-1 pr-2">Corrida</th>
                  <th className="py-1 pr-2">Lote</th>
                  <th className="py-1 pr-2 text-right">Quantidade registrada no CF</th>
                  <th className="py-1 pr-2">Origem técnica</th>
                  <th className="py-1 pr-2">Quantidade no CQ</th>
                  <th className="py-1">Dados técnicos</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha) => {
                  const estado = estadoDe(linha);
                  return (
                    <tr key={linha.chave_origem} className="border-b border-border/60 align-top">
                      <td className="py-2 pr-2">
                        <input
                          type="checkbox"
                          aria-label={`Selecionar corrida ${linha.corrida}${linha.lote ? `/${linha.lote}` : ''}`}
                          checked={estado.selecionada}
                          onChange={(e) => patchEstado(linha, { selecionada: e.target.checked })}
                        />
                      </td>
                      <td className="py-2 pr-2 font-medium">{linha.corrida || '—'}</td>
                      <td className="py-2 pr-2">{linha.lote || '—'}</td>
                      <td className="py-2 pr-2 text-right">
                        {linha.quantidade_no_certificado != null
                          ? `${linha.quantidade_no_certificado} ${linha.unidade || ''}`.trim()
                          : 'Não registrada'}
                        <span className="block text-[11px] text-muted-foreground">Sugestão documental</span>
                      </td>
                      <td className="py-2 pr-2">
                        <span className="text-xs">{linha.origem_tecnica_label}</span>
                      </td>
                      <td className="py-2 pr-2">
                        {estado.selecionada ? (
                          <input
                            className="erp-input w-28"
                            inputMode="decimal"
                            aria-label={`Quantidade da corrida ${linha.corrida}${linha.lote ? `/${linha.lote}` : ''}`}
                            value={estado.quantidade}
                            onChange={(e) => patchEstado(linha, { quantidade: e.target.value })}
                          />
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="py-2">
                        {estado.selecionada ? (
                          <div className="flex flex-col gap-1 text-xs">
                            <label className="inline-flex items-center gap-1">
                              <input
                                type="radio"
                                name={`dt-${linha.chave_origem}`}
                                checked={estado.dadosTecnicos === 'herdados'}
                                onChange={() => patchEstado(linha, { dadosTecnicos: 'herdados' })}
                              />
                              Usar dados técnicos herdados do item principal do CF
                            </label>
                            <label className="inline-flex items-center gap-1">
                              <input
                                type="radio"
                                name={`dt-${linha.chave_origem}`}
                                checked={estado.dadosTecnicos === 'proprios'}
                                onChange={() => patchEstado(linha, { dadosTecnicos: 'proprios' })}
                              />
                              Preencher dados técnicos próprios desta corrida
                            </label>
                            {estado.dadosTecnicos === 'proprios' ? (
                              <>
                                <span className="text-amber-700 dark:text-amber-300">
                                  {MSG_DADOS_PROPRIOS_MANUAIS_CQ}
                                </span>
                                <span className="text-amber-700 dark:text-amber-300">
                                  {MSG_DADOS_PROPRIOS_PENDENTES_CQ}
                                </span>
                              </>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <p className="text-xs text-muted-foreground">
            {dados?.mensagem_origem_fisica || MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ}
          </p>
          {dados?.limitacao_itens_independentes ? (
            <p className="text-xs text-muted-foreground">{dados.limitacao_itens_independentes}</p>
          ) : null}
        </div>
      )}
    </Modal>
  );
}
