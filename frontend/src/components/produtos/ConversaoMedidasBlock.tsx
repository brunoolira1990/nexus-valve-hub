import type { ReactNode } from 'react';
import {
  mensagensFatoresFaltando,
  previewLinhasConversao,
  TIPO_CONTROLE_OPTIONS,
  TIPO_FISICO_OPTIONS,
  toggleUnidadeLista,
  UNIDADES_CATALOGO,
  unidadesSugeridasChapa,
  unidadesSugeridasLinear,
  visibilidadePorTipoFisico,
} from '@/lib/conversaoMedidasUx';

export type CampoHeranca =
  | 'tipo_fisico'
  | 'tipo_controle_unidade'
  | 'unidade_estoque'
  | 'unidade_venda'
  | 'unidade_compra'
  | 'unidade_fiscal'
  | 'unidades_venda'
  | 'unidades_compra'
  | 'comprimento'
  | 'peso_metro'
  | 'peso_peca'
  | 'peso_chapa'
  | 'densidade'
  | 'observacoes';

type Props = {
  usaConversao: boolean;
  onUsaConversaoChange: (v: boolean) => void;
  tipoFisicoEfetivo: string;
  tipoFisicoProduto: string;
  onTipoFisicoProdutoChange: (v: string) => void;
  tipoControleProduto: string;
  onTipoControleProdutoChange: (v: string) => void;
  unidadeEstoque: string;
  onUnidadeEstoqueChange: (v: string) => void;
  unidadeVenda: string;
  onUnidadeVendaChange: (v: string) => void;
  unidadeCompra: string;
  onUnidadeCompraChange: (v: string) => void;
  unidadeFiscal: string;
  onUnidadeFiscalChange: (v: string) => void;
  unidadesVenda: string[];
  onUnidadesVendaChange: (list: string[]) => void;
  unidadesCompra: string[];
  onUnidadesCompraChange: (list: string[]) => void;
  familiaUnidadesVenda?: string[];
  familiaUnidadesCompra?: string[];
  comprimentoBarra: number | null;
  onComprimentoBarraChange: (v: number | null) => void;
  pesoMetro: number | null;
  onPesoMetroChange: (v: number | null) => void;
  pesoPeca: number | null;
  onPesoPecaChange: (v: number | null) => void;
  pesoChapa: number | null;
  onPesoChapaChange: (v: number | null) => void;
  densidade: number | null;
  onDensidadeChange: (v: number | null) => void;
  observacoes: string;
  onObservacoesChange: (v: string) => void;
  /** Herança família → produto (opcional) */
  heranca?: {
    isOverride: (campo: CampoHeranca) => boolean;
    onUsarFamilia: (campo: CampoHeranca) => void;
    valorFamiliaTexto: (campo: CampoHeranca) => string | null;
  };
  rotulos?: { limparUnidades?: string };
  /** Oculta unidade fiscal quando editada em outra aba (ex.: Fiscal). */
  ocultarUnidadeFiscal?: boolean;
};

function BadgeHeranca({ texto, variante }: { texto: string; variante: 'familia' | 'override' }) {
  const cls =
    variante === 'familia'
      ? 'bg-muted text-muted-foreground border-border'
      : 'bg-primary/10 text-primary border-primary/30';
  return <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cls}`}>{texto}</span>;
}

function LinhaHeranca({
  campo,
  heranca,
  children,
}: {
  campo: CampoHeranca;
  heranca?: Props['heranca'];
  children: ReactNode;
}) {
  if (!heranca) return <>{children}</>;
  const over = heranca.isOverride(campo);
  const vf = heranca.valorFamiliaTexto(campo);
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2 min-h-[22px]">
        {over ? (
          <BadgeHeranca texto="Sobrescrito no produto" variante="override" />
        ) : vf ? (
          <BadgeHeranca texto="Usando valor da família" variante="familia" />
        ) : null}
        {!over && vf ? <span className="text-[11px] text-muted-foreground">Família: {vf}</span> : null}
        {over ? (
          <button
            type="button"
            className="text-[11px] underline text-primary hover:no-underline"
            onClick={() => heranca.onUsarFamilia(campo)}
          >
            Usar padrão da família
          </button>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function GrupoCheckboxesUnidades({
  titulo,
  selecionados,
  familiaBase,
  onChange,
  sugestao,
  limparLabel,
}: {
  titulo: string;
  selecionados: string[];
  familiaBase: string[] | undefined;
  onChange: (list: string[]) => void;
  sugestao: string[];
  limparLabel: string;
}) {
  const baseLista = selecionados.length > 0 ? selecionados : [...(familiaBase || [])];
  const toggle = (cod: string) => onChange(toggleUnidadeLista(baseLista, cod));
  return (
    <div>
      <p className="text-xs font-medium text-foreground mb-1.5">{titulo}</p>
      <div className="flex flex-wrap gap-3">
        {UNIDADES_CATALOGO.map((u) => (
          <label key={u} className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" checked={baseLista.includes(u)} onChange={() => toggle(u)} />
            {u}
          </label>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" className="erp-btn-outline erp-btn-sm text-xs" onClick={() => onChange([...sugestao])}>
          Sugestão linear (M, BR, KG, TON)
        </button>
        <button type="button" className="erp-btn-outline erp-btn-sm text-xs" onClick={() => onChange([...unidadesSugeridasChapa()])}>
          Sugestão chapa (CH, KG, TON…)
        </button>
        <button type="button" className="erp-btn-ghost erp-btn-sm text-xs" onClick={() => onChange([])}>
          {limparLabel}
        </button>
      </div>
    </div>
  );
}

export function ConversaoMedidasBlock({
  usaConversao,
  onUsaConversaoChange,
  tipoFisicoEfetivo,
  tipoFisicoProduto,
  onTipoFisicoProdutoChange,
  tipoControleProduto,
  onTipoControleProdutoChange,
  unidadeEstoque,
  onUnidadeEstoqueChange,
  unidadeVenda,
  onUnidadeVendaChange,
  unidadeCompra,
  onUnidadeCompraChange,
  unidadeFiscal,
  onUnidadeFiscalChange,
  unidadesVenda,
  onUnidadesVendaChange,
  unidadesCompra,
  onUnidadesCompraChange,
  familiaUnidadesVenda,
  familiaUnidadesCompra,
  comprimentoBarra,
  onComprimentoBarraChange,
  pesoMetro,
  onPesoMetroChange,
  pesoPeca,
  onPesoPecaChange,
  pesoChapa,
  onPesoChapaChange,
  densidade,
  onDensidadeChange,
  observacoes,
  onObservacoesChange,
  heranca,
  rotulos,
  ocultarUnidadeFiscal = false,
}: Props) {
  const limparUnidades = rotulos?.limparUnidades ?? 'Limpar (herdar da família no produto)';
  const vis = visibilidadePorTipoFisico(tipoFisicoEfetivo, usaConversao);
  const showFatores = (tipoFisicoEfetivo || 'PECA') !== 'PECA' || usaConversao;
  const avisosPrev = mensagensFatoresFaltando({
    tipoFisico: tipoFisicoEfetivo,
    usaConversao,
    comprimentoBarra,
    pesoMetro,
    pesoChapa,
    pesoPeca,
  });
  const { linhas: previewLinhas, avisos: avisosLinhas } = previewLinhasConversao({
    tipoFisico: tipoFisicoEfetivo,
    usaConversao,
    comprimentoBarra,
    pesoMetro,
    pesoPeca,
    pesoChapa,
  });
  const todosAvisos = [...new Set([...avisosPrev, ...avisosLinhas])];

  const selUnidade = (value: string, onChange: (v: string) => void) => (
    <select className="erp-select mt-1 w-full" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())}>
      <option value="">—</option>
      {UNIDADES_CATALOGO.map((u) => (
        <option key={u} value={u}>
          {u}
        </option>
      ))}
    </select>
  );

  const num = (v: number | null, onChange: (n: number | null) => void, step: string) => (
    <input
      type="number"
      step={step}
      className="erp-input mt-1 w-full"
      value={v ?? ''}
      onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === '' ? null : Number(raw));
      }}
    />
  );

  return (
    <div className="mt-4 rounded-md border border-border bg-muted/10 p-4 space-y-5">
      <h3 className="text-sm font-semibold text-foreground border-b border-border pb-2">Conversão de Medidas</h3>

      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">1. Ativação</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={usaConversao} onChange={(e) => onUsaConversaoChange(e.target.checked)} />
          Usa conversão dimensional?
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <LinhaHeranca campo="tipo_fisico" heranca={heranca}>
            <label className="erp-label">Tipo físico</label>
            <select
              className="erp-select mt-1 w-full"
              value={tipoFisicoProduto || ''}
              onChange={(e) => onTipoFisicoProdutoChange(e.target.value)}
            >
              <option value="">(herdar da família)</option>
              {TIPO_FISICO_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-muted-foreground mt-0.5">Efetivo na tela: {tipoFisicoEfetivo || 'PECA'}</p>
          </LinhaHeranca>
          <LinhaHeranca campo="tipo_controle_unidade" heranca={heranca}>
            <label className="erp-label">Tipo de controle de unidade</label>
            <select
              className="erp-select mt-1 w-full"
              value={tipoControleProduto || ''}
              onChange={(e) => onTipoControleProdutoChange(e.target.value)}
            >
              <option value="">(herdar da família)</option>
              {TIPO_CONTROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </LinhaHeranca>
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">2. Unidades</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <LinhaHeranca campo="unidade_estoque" heranca={heranca}>
            <label className="erp-label">Unidade de estoque</label>
            {selUnidade(unidadeEstoque, onUnidadeEstoqueChange)}
          </LinhaHeranca>
          <LinhaHeranca campo="unidade_venda" heranca={heranca}>
            <label className="erp-label">Unidade de venda padrão</label>
            {selUnidade(unidadeVenda, onUnidadeVendaChange)}
          </LinhaHeranca>
          <LinhaHeranca campo="unidade_compra" heranca={heranca}>
            <label className="erp-label">Unidade de compra padrão</label>
            {selUnidade(unidadeCompra, onUnidadeCompraChange)}
          </LinhaHeranca>
          {!ocultarUnidadeFiscal ? (
            <LinhaHeranca campo="unidade_fiscal" heranca={heranca}>
              <label className="erp-label">Unidade fiscal</label>
              {selUnidade(unidadeFiscal, onUnidadeFiscalChange)}
            </LinhaHeranca>
          ) : null}
        </div>
        <LinhaHeranca campo="unidades_venda" heranca={heranca}>
          <GrupoCheckboxesUnidades
            titulo="Unidades permitidas para venda"
            selecionados={unidadesVenda}
            familiaBase={familiaUnidadesVenda}
            onChange={onUnidadesVendaChange}
            sugestao={vis.showSugestaoUnidadesChapa ? unidadesSugeridasChapa() : unidadesSugeridasLinear()}
            limparLabel={limparUnidades}
          />
        </LinhaHeranca>
        <LinhaHeranca campo="unidades_compra" heranca={heranca}>
          <GrupoCheckboxesUnidades
            titulo="Unidades permitidas para compra"
            selecionados={unidadesCompra}
            familiaBase={familiaUnidadesCompra}
            onChange={onUnidadesCompraChange}
            sugestao={vis.showSugestaoUnidadesChapa ? unidadesSugeridasChapa() : unidadesSugeridasLinear()}
            limparLabel={limparUnidades}
          />
        </LinhaHeranca>
      </section>

      {showFatores && (
        <section className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">3. Fatores</p>
          {(tipoFisicoEfetivo || 'PECA') === 'PECA' && !usaConversao ? (
            <p className="text-xs text-muted-foreground">Peça sem conversão dimensional: use o campo Unidade geral do cadastro (ex.: PC).</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {vis.showBarraMetro && (
                <LinhaHeranca campo="comprimento" heranca={heranca}>
                  <label className="erp-label">Comprimento padrão da barra (m)</label>
                  {num(comprimentoBarra, onComprimentoBarraChange, '0.001')}
                </LinhaHeranca>
              )}
              {vis.showPesoMetro && (
                <LinhaHeranca campo="peso_metro" heranca={heranca}>
                  <label className="erp-label">Peso por metro (kg/m)</label>
                  {num(pesoMetro, onPesoMetroChange, '0.0001')}
                </LinhaHeranca>
              )}
              {vis.showPesoPeca && (
                <LinhaHeranca campo="peso_peca" heranca={heranca}>
                  <label className="erp-label">Peso por peça (kg)</label>
                  {num(pesoPeca, onPesoPecaChange, '0.0001')}
                </LinhaHeranca>
              )}
              {vis.showPesoChapa && (
                <LinhaHeranca campo="peso_chapa" heranca={heranca}>
                  <label className="erp-label">Peso por chapa (kg)</label>
                  {num(pesoChapa, onPesoChapaChange, '0.0001')}
                </LinhaHeranca>
              )}
              {vis.showDensidadeOpcional && (
                <LinhaHeranca campo="densidade" heranca={heranca}>
                  <label className="erp-label">Densidade (opcional)</label>
                  {num(densidade, onDensidadeChange, '0.0001')}
                </LinhaHeranca>
              )}
              {vis.showSugestaoUnidadesChapa && (
                <div className="md:col-span-2 rounded-md border border-dashed border-border bg-background/80 p-2 text-[11px] text-muted-foreground">
                  Em evolução: dimensões da chapa (largura, comprimento, espessura) para cálculo automático futuro.
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">4. Prévia</p>
        <div className="rounded-md border border-border bg-background p-3 space-y-1.5">
          {previewLinhas.map((ln, i) => (
            <p key={i} className="text-sm font-mono">
              {ln}
            </p>
          ))}
          {todosAvisos.length ? (
            <ul className="mt-2 space-y-1 text-xs text-amber-800 dark:text-amber-200 list-disc pl-4">
              {todosAvisos.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">5. Observações</p>
        <LinhaHeranca campo="observacoes" heranca={heranca}>
          <textarea
            className="erp-input mt-1 w-full min-h-[72px] text-sm"
            value={observacoes}
            onChange={(e) => onObservacoesChange(e.target.value)}
            placeholder="Notas internas sobre conversão, tolerâncias, fornecedor, etc."
          />
        </LinhaHeranca>
      </section>
    </div>
  );
}
