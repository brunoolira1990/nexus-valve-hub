/**
 * Editor de item do Certificado de Qualidade.
 *
 * Etapa 5b-1 — subconjunto do editor do modal antigo:
 *  - Inputs basicos (ordem, codigo, descricao, qtd, un, norma, lote, ncm)
 *  - Tipo de dados tecnicos
 *  - Incluir no certificado + motivo/observacao
 *
 * Proximas sub-etapas:
 *  - 5b-2: corrida/lote + rastreabilidade por produto
 *  - 5b-3: composicao + ensaios
 *  - 5b-4: componentes de valvula
 *  - Etapa 6: corridas CF (via modal existente)
 */
import type {
  CorridaDisponivelCertificadoQualidade,
  ItemCertificadoQualidade,
  Produto,
} from '@/types';
import {
  LABEL_OBRIGATORIO_EMITIR,
  MOTIVOS_NAO_INCLUSAO,
  coerceProdutoItemId,
} from '@/lib/certificadoQualidadeConstants';
import {
  origemFisicaCqBadge,
  origemFisicaCqItem,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';

export type CorridasProps = {
  produtoBusca?: string;
  produtoResultados: Produto[];
  corridasDisponiveis: CorridaDisponivelCertificadoQualidade[];
  onBuscarProdutos: (term: string) => void;
  onVincularProduto: (p: Produto) => void;
  onCarregarCorridas: () => void;
  onAplicarCorrida: (valorSelecao: string) => void;
};

type Props = {
  item: ItemCertificadoQualidade;
  idx: number;
  disabled?: boolean;
  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;
  corridas?: CorridasProps;
};

export function ItemEditor({ item: it, idx, disabled, onChange, corridas }: Props) {
  const incl = it.incluir_no_certificado !== false;

  return (
    <details
      open
      className={`rounded border p-3 ${!incl ? 'border-amber-300 bg-amber-50/30 dark:border-amber-700 dark:bg-amber-900/10' : 'border-border'}`}
    >
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2 flex-wrap">
          <span>
            Item {it.ordem || idx + 1} - {it.codigo_produto || 'Sem codigo'} -{' '}
            {it.descricao_material || 'Sem descricao'}
          </span>
          {!incl ? (
            <span className="erp-badge-warning">Nao incluido</span>
          ) : (
            <span className="erp-badge-success">Incluido</span>
          )}
          {incl && it.rastreabilidade_status ? (
            <span
              className={`${rastreabilidadeCqBadge(it.rastreabilidade_status).className} text-[10px]`}
              title="Prontidao tecnica: dados exigidos para emissao do CQ. Nao comprova a origem fisica do material."
            >
              {it.rastreabilidade_label || rastreabilidadeCqBadge(it.rastreabilidade_status).label}
            </span>
          ) : null}
          {incl ? (
            <span
              className={`${origemFisicaCqBadge(origemFisicaCqItem(it)).className} text-[10px]`}
              title="Origem documental: vinculo com Certificado de Fornecedor e corrida/lote registrados."
            >
              {origemFisicaCqBadge(origemFisicaCqItem(it)).label}
            </span>
          ) : null}
        </span>
      </summary>

      {incl && (it.rastreabilidade_avisos?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-sky-800 dark:text-sky-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_avisos!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      {incl && (it.rastreabilidade_mensagens?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-amber-800 dark:text-amber-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_mensagens!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mt-3">
        <div>
          <label className="erp-label">Ordem</label>
          <input
            className="erp-input mt-1"
            value={it.ordem}
            disabled={disabled}
            onChange={(e) => onChange({ ordem: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Codigo</label>
          <input
            className="erp-input mt-1"
            value={it.codigo_produto}
            disabled={disabled}
            onChange={(e) => onChange({ codigo_produto: e.target.value })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="erp-label">Descricao{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.descricao_material}
            disabled={disabled}
            onChange={(e) => onChange({ descricao_material: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Qtd</label>
          <input
            className="erp-input mt-1"
            value={it.quantidade}
            disabled={disabled}
            onChange={(e) => onChange({ quantidade: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Un</label>
          <input
            className="erp-input mt-1"
            value={it.unidade}
            disabled={disabled}
            onChange={(e) => onChange({ unidade: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Norma{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.norma}
            disabled={disabled}
            onChange={(e) => onChange({ norma: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Lote{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.lote || ''}
            disabled={disabled}
            onChange={(e) => onChange({ lote: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">NCM</label>
          <input
            className="erp-input mt-1"
            value={it.ncm || ''}
            disabled={disabled}
            onChange={(e) => onChange({ ncm: e.target.value })}
          />
        </div>
        <div className="md:col-span-3">
          <label className="erp-label">Tipo de dados tecnicos</label>
          <select
            className="erp-select mt-1 w-full"
            value={it.tipo_dados_tecnicos || 'PADRAO_ITEM'}
            disabled={disabled}
            onChange={(e) =>
              onChange({
                tipo_dados_tecnicos: e.target.value as 'PADRAO_ITEM' | 'VALVULA_COMPONENTES',
              })
            }
          >
            <option value="PADRAO_ITEM">Dados por item</option>
            <option value="VALVULA_COMPONENTES">Dados por componentes de valvula</option>
          </select>
        </div>

        {corridas ? (
          <div className="md:col-span-6 rounded border border-border p-2 bg-muted/10">
            <p className="text-xs font-semibold mb-2">Rastreabilidade por produto cadastrado + Corrida/Lote</p>
            {it.produto ? (
              <div className="text-xs mb-2">
                <p>
                  Produto cadastrado: {it.produto_codigo || '—'} - {it.produto_descricao || '—'}
                  {it.produto_ncm_efetivo ? ` | NCM efetivo: ${it.produto_ncm_efetivo}` : ''}
                </p>
              </div>
            ) : (
              <p className="text-xs text-amber-700 dark:text-amber-300 mb-2">
                Este item da NF-e ainda nao esta vinculado a um produto cadastrado. Vincule o produto para listar corridas disponiveis.
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div className="md:col-span-2">
                <label className="erp-label">Selecionar produto cadastrado (autocomplete)</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Digite codigo ou descricao"
                  value={
                    corridas.produtoBusca ??
                    (it.produto ? `${it.produto_codigo || ''} - ${it.produto_descricao || ''}` : '')
                  }
                  disabled={disabled}
                  onChange={(e) => corridas.onBuscarProdutos(e.target.value)}
                />
                {corridas.produtoResultados.length > 0 ? (
                  <div className="mt-1 rounded border border-border max-h-32 overflow-auto bg-background">
                    {corridas.produtoResultados.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        className="w-full text-left px-2 py-1 text-xs hover:bg-muted"
                        onClick={() => corridas.onVincularProduto(p)}
                      >
                        {p.codigo_completo} - {p.descricao}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="flex items-end">
                <button
                  type="button"
                  className="erp-btn-outline w-full"
                  disabled={!it.produto || disabled}
                  onClick={corridas.onCarregarCorridas}
                >
                  Listar corridas
                </button>
              </div>
            </div>
            <div className="mt-2">
              <label className="erp-label">Corrida/Lote disponivel</label>
              <select
                className="erp-select mt-1 w-full"
                disabled={!coerceProdutoItemId(it.produto) || disabled}
                value={(() => {
                  const list = corridas.corridasDisponiveis || [];
                  const corrEff = it.corrida || it.corrida_snapshot || '';
                  const loteEff = it.lote || it.lote_snapshot || '';
                  const match = list.find(
                    (c) => c.corrida === corrEff && (c.lote || '') === (loteEff || ''),
                  );
                  return match?.valor_selecao || `${corrEff}||${loteEff}`;
                })()}
                onChange={(e) => {
                  const selected = e.target.value;
                  if (!selected) {
                    onChange({ corrida: '', lote: '' });
                    return;
                  }
                  const [cPart, lPart] = selected.split('||');
                  onChange({ corrida: cPart || '', lote: lPart || '' });
                  corridas.onAplicarCorrida(selected);
                }}
              >
                <option value="">Selecione a corrida disponivel...</option>
                {(() => {
                  const list = corridas.corridasDisponiveis || [];
                  const corrEff = it.corrida || it.corrida_snapshot || '';
                  const loteEff = it.lote || it.lote_snapshot || '';
                  const manualVal = `${corrEff}||${loteEff}`;
                  const inList = list.some(
                    (c) => (c.valor_selecao || `${c.corrida}||${c.lote || ''}`) === manualVal,
                  );
                  const extra =
                    (corrEff || loteEff) && !inList && manualVal !== '||' ? (
                      <option key={`__manual_cq__-${idx}`} value={manualVal}>
                        Corrida/lote manual: {corrEff}
                        {loteEff ? ` / ${loteEff}` : ''}
                      </option>
                    ) : null;
                  return (
                    <>
                      {extra}
                      {list.map((c) => (
                        <option
                          key={c.valor_selecao || `${c.corrida}-${c.lote || ''}`}
                          value={c.valor_selecao || `${c.corrida}||${c.lote || ''}`}
                        >
                          {c.corrida}
                          {c.lote ? `/${c.lote}` : ''}
                          {c.saldo ? ` - Saldo: ${c.saldo} ${c.unidade || ''}` : ''}
                          {c.fornecedor ? ` - ${c.fornecedor}` : ''}
                        </option>
                      ))}
                    </>
                  );
                })()}
              </select>
              {coerceProdutoItemId(it.produto) &&
              (corridas.corridasDisponiveis || []).length === 0 ? (
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.
                </p>
              ) : null}
            </div>
            <div className="flex flex-col sm:flex-row gap-2 mt-2">
              <div className="flex-1">
                <label className="erp-label">Corrida manual{LABEL_OBRIGATORIO_EMITIR}</label>
                <input
                  className="erp-input mt-1"
                  placeholder="Ex.: HEN-001"
                  value={it.corrida || it.corrida_snapshot || ''}
                  disabled={disabled}
                  onChange={(e) => {
                    const v = e.target.value;
                    onChange({
                      corrida: v,
                      origem_rastreabilidade_tipo: 'manual',
                      ...(v.trim() === '' ? { corrida_snapshot: '' } : {}),
                    });
                  }}
                />
              </div>
              <div className="flex-1">
                <label className="erp-label">Lote manual</label>
                <input
                  className="erp-input mt-1"
                  value={it.lote || it.lote_snapshot || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ lote: e.target.value })}
                />
              </div>
            </div>
          </div>
        ) : null}

        <div className="md:col-span-6 rounded border border-border p-2">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={incl}
              disabled={disabled}
              onChange={(e) => onChange({ incluir_no_certificado: e.target.checked })}
            />
            Incluir no certificado
          </label>
          {!incl ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              <div>
                <label className="erp-label">Motivo da nao inclusao</label>
                <select
                  className="erp-select mt-1 w-full"
                  value={it.motivo_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ motivo_nao_inclusao: e.target.value })}
                >
                  <option value="">Selecione...</option>
                  {MOTIVOS_NAO_INCLUSAO.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="erp-label">Observacao interna</label>
                <input
                  className="erp-input mt-1"
                  value={it.observacao_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ observacao_nao_inclusao: e.target.value })}
                />
              </div>
              <div className="md:col-span-2 text-xs text-amber-700 dark:text-amber-300">
                Nao incluido
                {it.motivo_nao_inclusao ? ` - Motivo: ${it.motivo_nao_inclusao}` : ''}.
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </details>
  );
}
