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
import { useState } from 'react';

import type {
  CorridaDisponivelCertificadoQualidade,
  ItemCertificadoQualidade,
  ItemCertificadoQualidadeComponente,
  Produto,
} from '@/types';
import {
  COMPOSICAO_FIELDS,
  IMPACTO_FIELDS,
  LABEL_OBRIGATORIO_EMITIR,
  MOTIVOS_NAO_INCLUSAO,
  TRACAO_FIELDS,
  coerceProdutoItemId,
  ensureMap,
  normNumeric,
  parseBlockValues,
} from '@/lib/certificadoQualidadeConstants';
import {
  origemFisicaCqBadge,
  origemFisicaCqItem,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';
import { TITULO_MODAL_CORRIDAS_CF_CQ } from '@/lib/cqCorridasCfUi';

export type LinhaDivisaoCorrida = {
  corrida: string;
  lote: string;
  quantidade: string;
  valorSelecao: string;
};

export type CorridasProps = {
  produtoBusca?: string;
  produtoResultados: Produto[];
  corridasDisponiveis: CorridaDisponivelCertificadoQualidade[];
  onBuscarProdutos: (term: string) => void;
  onVincularProduto: (p: Produto) => void;
  onCarregarCorridas: () => void;
  onAplicarCorrida: (valorSelecao: string) => void;
  dividindo: LinhaDivisaoCorrida[];
  temCorridaDuplicada: boolean;
  onAddLinha: () => void;
  onRemoveLinha: (linhaIdx: number) => void;
  onUpdateLinha: (linhaIdx: number, patch: Partial<LinhaDivisaoCorrida>) => void;
  onAplicarDistribuicao: () => void;
  onAbrirModalCorridasCf: () => void;
};

export type ComponentesProps = {
  lista: ItemCertificadoQualidadeComponente[];
  onAdd: (nome?: string) => void;
  onAddPadrao: () => void;
  onRemove: (compIdx: number) => void;
  onDuplicar: (compIdx: number) => void;
  onCopiarAnterior: (compIdx: number) => void;
  onUpdate: (
    compIdx: number,
    patch: Partial<ItemCertificadoQualidadeComponente>,
  ) => void;
  onUpdateJson: (
    compIdx: number,
    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',
    key: string,
    value: string,
  ) => void;
};

type Props = {
  item: ItemCertificadoQualidade;
  idx: number;
  disabled?: boolean;
  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;
  corridas?: CorridasProps;
  componentes?: ComponentesProps;
};

export function ItemEditor({
  item: it,
  idx,
  disabled,
  onChange,
  corridas,
  componentes,
}: Props) {
  const incl = it.incluir_no_certificado !== false;
  const [pasteCompOpen, setPasteCompOpen] = useState(false);
  const [pasteCompText, setPasteCompText] = useState('');

  const updateJson = (
    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',
    key: string,
    value: string,
  ) => {
    const current = ensureMap(it[group]);
    onChange({ [group]: { ...current, [key]: value } });
  };

  const applyCompositionBlock = () => {
    const values = parseBlockValues(pasteCompText);
    if (!values.length) return;
    const next = { ...ensureMap(it.composicao_json) };
    COMPOSICAO_FIELDS.forEach((field, i) => {
      if (values[i] != null) next[field] = normNumeric(values[i]);
    });
    onChange({ composicao_json: next });
    setPasteCompOpen(false);
    setPasteCompText('');
  };

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
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm"
                disabled={
                  disabled ||
                  !it.certificado_fornecedor_origem_id ||
                  !it.item_certificado_fornecedor_origem_id
                }
                title={
                  !it.certificado_fornecedor_origem_id ||
                  !it.item_certificado_fornecedor_origem_id
                    ? 'Vincule este item ao Certificado de Fornecedor e ao item exato do CF antes de adicionar corridas.'
                    : 'Distribui este item em uma linha por corrida do CF vinculado, com quantidade e dados tecnicos por corrida.'
                }
                onClick={corridas.onAbrirModalCorridasCf}
              >
                {TITULO_MODAL_CORRIDAS_CF_CQ}
              </button>
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

        {corridas ? (
          <div className="md:col-span-6 rounded border border-border p-3 bg-muted/20">
            <p className="text-sm font-semibold mb-2">Dividir item em varias corridas</p>
            {corridas.dividindo.length > 0 ? (
              <p className="text-xs text-amber-800 dark:text-amber-300 mb-2">
                Este item sera substituido por {corridas.dividindo.length} itens, um por corrida.
              </p>
            ) : null}
            {corridas.dividindo.length === 0 && !it.tem_corrida_lote ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm w-full"
                  disabled={disabled}
                  onClick={corridas.onAddLinha}
                >
                  + Adicionar corrida a lista
                </button>
              </div>
            ) : null}
            {corridas.dividindo.length > 0 ? (
              <>
                <div className="overflow-auto max-h-[200px]">
                  <div className="grid grid-cols-12 gap-2 text-xs border-b border-border pb-2 px-1 items-center">
                    <div className="col-span-5">Corrida</div>
                    <div className="col-span-3">Lote</div>
                    <div className="col-span-2">Quantidade</div>
                    <div className="col-span-2 text-right">Acoes</div>
                  </div>
                  {corridas.dividindo.map((linha, linhaIdx) => (
                    <div
                      key={linhaIdx}
                      className="grid grid-cols-12 gap-2 py-2 border-b border-border items-center px-1"
                    >
                      <div className="col-span-5">
                        <select
                          className="erp-select"
                          value={linha.valorSelecao || ''}
                          disabled={disabled}
                          onChange={(e) =>
                            corridas.onUpdateLinha(linhaIdx, { valorSelecao: e.target.value })
                          }
                        >
                          <option value="">Selecione...</option>
                          {corridas.corridasDisponiveis.map((c) => (
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
                        </select>
                      </div>
                      <div className="col-span-3">
                        <input
                          className="erp-input w-full"
                          placeholder="Lote (opcional)"
                          value={linha.lote || ''}
                          disabled={disabled}
                          onChange={(e) =>
                            corridas.onUpdateLinha(linhaIdx, { lote: e.target.value })
                          }
                        />
                      </div>
                      <div className="col-span-2">
                        <input
                          className="erp-input w-full"
                          inputMode="decimal"
                          placeholder="0,000"
                          value={linha.quantidade}
                          disabled={disabled}
                          onChange={(e) =>
                            corridas.onUpdateLinha(linhaIdx, { quantidade: e.target.value })
                          }
                        />
                      </div>
                      <div className="col-span-2 flex justify-end">
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={disabled}
                          onClick={() => corridas.onRemoveLinha(linhaIdx)}
                          title="Remover linha"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 p-3 rounded border border-border bg-muted/20">
                  {(() => {
                    const soma = corridas.dividindo.reduce(
                      (s, l) => s + parseFloat(l.quantidade || '0'),
                      0,
                    );
                    const total = it.quantidade || 0;
                    const saldo = total - soma;
                    const somaOk = Math.abs(saldo) < 0.001;
                    return (
                      <>
                        <div className="flex flex-col sm:flex-row justify-between items-center text-sm gap-2">
                          <span>Total do item: {total}</span>
                          <span>Soma: {soma.toFixed(3)}</span>
                          <span className={somaOk ? '' : 'text-red-600'}>
                            Saldo: {saldo.toFixed(3)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="erp-btn-primary w-full mt-2"
                          disabled={!somaOk || corridas.temCorridaDuplicada || disabled}
                          onClick={corridas.onAplicarDistribuicao}
                        >
                          Aplicar distribuicao
                        </button>
                      </>
                    );
                  })()}
                </div>
              </>
            ) : null}
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

        {incl && it.tipo_dados_tecnicos !== 'VALVULA_COMPONENTES' ? (
          <>
            <div className="md:col-span-6 rounded border border-border p-2">
              <div className="flex items-center justify-between mb-2 gap-2">
                <p className="text-xs font-semibold">Composição química{LABEL_OBRIGATORIO_EMITIR}</p>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={disabled}
                  onClick={() => {
                    setPasteCompOpen((cur) => !cur);
                    setPasteCompText('');
                  }}
                >
                  Colar composição em bloco
                </button>
              </div>
              {pasteCompOpen ? (
                <div className="mb-2 rounded border border-border p-2 bg-muted/20">
                  <p className="text-xs text-muted-foreground mb-1">
                    Cole uma linha (Excel/tabulado) na ordem: {COMPOSICAO_FIELDS.join(', ')}.
                  </p>
                  <textarea
                    className="erp-input h-16"
                    value={pasteCompText}
                    onChange={(e) => setPasteCompText(e.target.value)}
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      onClick={applyCompositionBlock}
                    >
                      Aplicar na grade
                    </button>
                    <button
                      type="button"
                      className="erp-btn-outline erp-btn-sm"
                      onClick={() => {
                        setPasteCompOpen(false);
                        setPasteCompText('');
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : null}
              <div className="grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2">
                {COMPOSICAO_FIELDS.map((el) => (
                  <div key={el}>
                    <label className="erp-label">{el}</label>
                    <input
                      className="erp-input mt-1"
                      placeholder="***"
                      disabled={disabled}
                      value={ensureMap(it.composicao_json)[el] || ''}
                      onChange={(e) => updateJson('composicao_json', el, normNumeric(e.target.value))}
                    />
                  </div>
                ))}
              </div>
            </div>
            <div className="md:col-span-6 rounded border border-border p-2">
              <p className="text-xs font-semibold mb-2">Teste de tração{LABEL_OBRIGATORIO_EMITIR}</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {TRACAO_FIELDS.map((f) => (
                  <div key={f.key}>
                    <label className="erp-label">{f.label}</label>
                    <input
                      className="erp-input mt-1"
                      disabled={disabled}
                      value={ensureMap(it.ensaio_tracao_json)[f.key] || ''}
                      onChange={(e) => updateJson('ensaio_tracao_json', f.key, normNumeric(e.target.value))}
                    />
                  </div>
                ))}
              </div>
            </div>
            <div className="md:col-span-6 rounded border border-border p-2">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold">Teste de impacto</p>
                <label className="text-xs flex items-center gap-1">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={ensureMap(it.ensaio_impacto_json).informar_impacto === 'true'}
                    onChange={(e) => {
                      const map = ensureMap(it.ensaio_impacto_json);
                      map.informar_impacto = e.target.checked ? 'true' : '';
                      if (!e.target.checked) {
                        IMPACTO_FIELDS.forEach((f) => {
                          map[f.key] = '';
                        });
                        map.nao_aplicavel = 'true';
                      } else {
                        map.nao_aplicavel = '';
                      }
                      onChange({ ensaio_impacto_json: map });
                    }}
                  />
                  Informar teste de impacto
                </label>
              </div>
              {ensureMap(it.ensaio_impacto_json).informar_impacto !== 'true' ? (
                <p className="text-xs text-muted-foreground">
                  Impacto oculto por padrão (não aplicável no uso diário).
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {IMPACTO_FIELDS.map((f) => (
                    <div key={f.key}>
                      <label className="erp-label">{f.label}</label>
                      <input
                        className="erp-input mt-1"
                        disabled={disabled}
                        value={ensureMap(it.ensaio_impacto_json)[f.key] || ''}
                        onChange={(e) => updateJson('ensaio_impacto_json', f.key, normNumeric(e.target.value))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}

        {incl && it.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' && componentes ? (
          <div className="md:col-span-6 rounded border border-border p-2 bg-muted/10">
            <div className="flex flex-wrap gap-2 items-center justify-between mb-2">
              <p className="text-xs font-semibold">Componentes da valvula</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={disabled}
                  onClick={componentes.onAddPadrao}
                >
                  Adicionar componentes padrao
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={disabled}
                  onClick={() => componentes.onAdd()}
                >
                  Adicionar componente
                </button>
              </div>
            </div>
            {componentes.lista.length === 0 ? (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                Este item esta marcado como valvula, mas ainda nao possui componentes.
              </p>
            ) : (
              <div className="space-y-2">
                {componentes.lista.map((cp, cidx) => (
                  <details key={cidx} className="rounded border border-border p-2" open>
                    <summary className="cursor-pointer text-xs font-medium">
                      Componente {cp.ordem} - {cp.nome_componente || 'Sem nome'}
                    </summary>
                    <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mt-2">
                      <div>
                        <label className="erp-label">Ordem</label>
                        <input
                          className="erp-input mt-1"
                          disabled={disabled}
                          value={cp.ordem}
                          onChange={(e) =>
                            componentes.onUpdate(cidx, { ordem: +e.target.value })
                          }
                        />
                      </div>
                      <div>
                        <label className="erp-label">Componente</label>
                        <input
                          className="erp-input mt-1"
                          disabled={disabled}
                          value={cp.nome_componente}
                          onChange={(e) =>
                            componentes.onUpdate(cidx, { nome_componente: e.target.value })
                          }
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="erp-label">Descricao</label>
                        <input
                          className="erp-input mt-1"
                          disabled={disabled}
                          value={cp.descricao_componente || ''}
                          onChange={(e) =>
                            componentes.onUpdate(cidx, { descricao_componente: e.target.value })
                          }
                        />
                      </div>
                      <div>
                        <label className="erp-label">Norma</label>
                        <input
                          className="erp-input mt-1"
                          disabled={disabled}
                          value={cp.norma || ''}
                          onChange={(e) =>
                            componentes.onUpdate(cidx, { norma: e.target.value })
                          }
                        />
                      </div>
                      <div>
                        <label className="erp-label">Corrida</label>
                        <input
                          className="erp-input mt-1"
                          disabled={disabled}
                          value={cp.corrida || ''}
                          onChange={(e) =>
                            componentes.onUpdate(cidx, { corrida: e.target.value })
                          }
                        />
                      </div>
                      <div className="md:col-span-6 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={disabled || cidx === 0}
                          onClick={() => componentes.onCopiarAnterior(cidx)}
                        >
                          Copiar componente anterior
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={disabled}
                          onClick={() => componentes.onDuplicar(cidx)}
                        >
                          Duplicar componente
                        </button>
                        <button
                          type="button"
                          className="erp-btn-outline erp-btn-sm"
                          disabled={disabled}
                          onClick={() => componentes.onRemove(cidx)}
                        >
                          Remover componente
                        </button>
                      </div>
                      <div className="md:col-span-6 rounded border border-border p-2">
                        <p className="text-xs font-semibold mb-2">Composicao quimica do componente</p>
                        <div className="grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2">
                          {COMPOSICAO_FIELDS.map((el) => (
                            <div key={el}>
                              <label className="erp-label">{el}</label>
                              <input
                                className="erp-input mt-1"
                                placeholder="***"
                                disabled={disabled}
                                value={ensureMap(cp.composicao_json)[el] || ''}
                                onChange={(e) =>
                                  componentes.onUpdateJson(
                                    cidx,
                                    'composicao_json',
                                    el,
                                    normNumeric(e.target.value),
                                  )
                                }
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="md:col-span-6 rounded border border-border p-2">
                        <p className="text-xs font-semibold mb-2">Tracao do componente</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {TRACAO_FIELDS.map((f) => (
                            <div key={f.key}>
                              <label className="erp-label">{f.label}</label>
                              <input
                                className="erp-input mt-1"
                                disabled={disabled}
                                value={ensureMap(cp.ensaio_tracao_json)[f.key] || ''}
                                onChange={(e) =>
                                  componentes.onUpdateJson(
                                    cidx,
                                    'ensaio_tracao_json',
                                    f.key,
                                    normNumeric(e.target.value),
                                  )
                                }
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </details>
  );
}
