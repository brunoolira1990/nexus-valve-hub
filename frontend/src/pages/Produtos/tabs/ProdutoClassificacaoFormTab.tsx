import { Label, Select, Input } from '@/components/ui';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import type { ProdutoFormState } from '../types';
import { PolegadaAutocomplete } from '@/components/produtos/PolegadaAutocomplete';
import { ConversaoMedidasBlock } from '@/components/produtos/ConversaoMedidasBlock';
import { MATERIAIS } from '../ProdutoList';
import { schedulesEspessuraService } from '@/services/api/produtos';
import type { ScheduleEspessura } from '@/types';

interface ProdutoClassificacaoFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview?: { codigo?: string; descricao?: string; ncm?: string };
}

export function ProdutoClassificacaoFormTab({
  form,
  setForm,
  preview,
}: ProdutoClassificacaoFormTabProps) {
  const handleInputChange = <K extends keyof ProdutoFormState>(
    key: K,
    value: ProdutoFormState[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleNumberChange = (key: keyof ProdutoFormState, value: string) => {
    const num = value === '' ? 0 : Number(value);
    handleInputChange(key, Number.isFinite(num) ? num : 0);
  };

  return (
    <div className="space-y-4">
      {/* Identidade técnica */}
      <section className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
        <p className="text-sm font-semibold text-foreground">Identidade técnica</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <Label>Material base</Label>
            <Select
              value={form.material}
              onValueChange={(v) => handleInputChange('material', v)}
              className="erp-select mt-1 w-full"
            >
              <option value="">Selecione...</option>
              {form.material && !MATERIAIS.includes(form.material) ? (
                <option value={form.material}>{form.material}</option>
              ) : null}
              {MATERIAIS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Norma técnica</Label>
            <Input
              className="erp-input mt-1"
              value={form.norma}
              onChange={(e) => handleInputChange('norma', e.target.value)}
              placeholder="Ex.: ASME B16.34, DIN 3352"
            />
          </div>
          <div>
            <Label>Pressão nominal</Label>
            <Input
              className="erp-input mt-1"
              value={form.pressao_nominal}
              onChange={(e) => handleInputChange('pressao_nominal', e.target.value)}
              placeholder="Ex.: PN 16, Class 150"
            />
          </div>
          <div>
            <Label>Tipo de peça</Label>
            <Input
              className="erp-input mt-1"
              value={form.tipo_peca}
              onChange={(e) => handleInputChange('tipo_peca', e.target.value)}
              placeholder="Ex.: Válvula, Conexão, Flange"
            />
          </div>
          <div className="md:col-span-2 lg:col-span-3">
            <Label>Conexão (texto livre)</Label>
            <Input
              className="erp-input mt-1"
              value={form.conexao}
              onChange={(e) => handleInputChange('conexao', e.target.value)}
              placeholder="Descrição livre da conexão"
            />
          </div>
        </div>
      </section>

      {/* Dimensões e referências */}
      <section className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
        <p className="text-sm font-semibold text-foreground">Dimensões e referências</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Polegada principal */}
          <div>
            <Label>Polegada principal (autocomplete)</Label>
            <PolegadaAutocomplete
              value={form.polegada_principal_ref_id ?? null}
              onChange={(id) => handleInputChange('polegada_principal_ref_id', id)}
              tipoMedida="OD"
              allowCreate
              placeholder="Busque por código, polegada, decimal ou mm"
            />
          </div>

          {/* Polegada secundária */}
          <div>
            <Label>Polegada secundária (autocomplete)</Label>
            <PolegadaAutocomplete
              value={form.polegada_secundaria_ref_id ?? null}
              onChange={(id) => handleInputChange('polegada_secundaria_ref_id', id)}
              tipoMedida="OD"
              allowCreate
              placeholder="Busque por código, polegada, decimal ou mm"
            />
          </div>

          {/* Schedule / Espessura */}
          <div>
            <Label>Schedule / Espessura (autocomplete)</Label>
            <AsyncAutocomplete<ScheduleEspessura>
              value={form.schedule_ref_id ?? null}
              selectedOption={null}
              placeholder="Digite código, descrição ou aplicação (ex.: 10S, SCH 20, INOX)"
              search={async (term, limit) => schedulesEspessuraService.search(term, limit ?? 20)}
              getOptionValue={(opt) => opt.id}
              getOptionLabel={(opt) =>
                `${opt.codigo || opt.codigo_schedule} — ${opt.descricao || opt.codigo_schedule}`
              }
              onChange={(val, opt) => {
                const id = typeof val === 'number' ? val : null;
                handleInputChange('schedule_ref_id', id);
              }}
            />
          </div>

          {/* Medidas em mm */}
          <div>
            <Label>OD (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 10 | 10,0 | 1,5"
              value={form.od_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('od_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>

          <div>
            <Label>Espessura (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 2 | 2,0 | 1,5"
              value={form.espessura_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('espessura_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>

          <div>
            <Label>Comprimento (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 6000"
              value={form.comprimento_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('comprimento_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>
        </div>
      </section>

      {/* Dimensões especiais (JSON) */}
      <section className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
        <p className="text-sm font-semibold text-foreground">Dimensões especiais</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <Label>Espessura (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 3,2"
              value={form.dim_espessura_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('dim_espessura_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>
          <div>
            <Label>Largura (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 1000"
              value={form.dim_largura_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('dim_largura_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>
          <div>
            <Label>Comprimento (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 2000"
              value={form.dim_comprimento_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('dim_comprimento_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>
          <div>
            <Label>Altura (mm)</Label>
            <Input
              type="text"
              inputMode="decimal"
              className="erp-input mt-1"
              placeholder="Ex.: 50"
              value={form.dim_altura_mm?.toString().replace('.', ',') || ''}
              onChange={(e) => {
                const v = e.target.value.replace(',', '.');
                const n = v === '' ? null : Number(v);
                handleInputChange('dim_altura_mm', Number.isFinite(n) ? n : null);
              }}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Estas dimensões são armazenadas no campo JSON <code className="font-mono">dimensoes_json</code> do produto.
        </p>
      </section>

      {/* Conversão de Medidas */}
      <ConversaoMedidasBlock
        usaConversao={!!form.usa_conversao_dimensional}
        onUsaConversaoChange={(v) => handleInputChange('usa_conversao_dimensional', v)}
        controlaComposicaoFisica={!!form.controla_composicao_fisica}
        onControlaComposicaoFisicaChange={(v) => handleInputChange('controla_composicao_fisica', v)}
        tipoComposicaoFisica={form.tipo_composicao_fisica || 'BARRA_M'}
        onTipoComposicaoFisicaChange={(v) => handleInputChange('tipo_composicao_fisica', v)}
        tipoFisicoEfetivo={form.tipo_fisico_efetivo || form.tipo_fisico || ''}
        tipoFisicoProduto={form.tipo_fisico || ''}
        onTipoFisicoProdutoChange={(v) => handleInputChange('tipo_fisico', v)}
        tipoControleProduto={form.tipo_controle_unidade || ''}
        onTipoControleProdutoChange={(v) => handleInputChange('tipo_controle_unidade', v)}
        unidadeEstoque={form.unidade_estoque || ''}
        onUnidadeEstoqueChange={(v) => handleInputChange('unidade_estoque', v)}
        unidadeVenda={form.unidade_venda_padrao || ''}
        onUnidadeVendaChange={(v) => handleInputChange('unidade_venda_padrao', v)}
        unidadeCompra={form.unidade_compra_padrao || ''}
        onUnidadeCompraChange={(v) => handleInputChange('unidade_compra_padrao', v)}
        unidadeFiscal={form.unidade_fiscal || ''}
        onUnidadeFiscalChange={(v) => handleInputChange('unidade_fiscal', v)}
        unidadesVenda={form.unidades_venda_permitidas || []}
        onUnidadesVendaChange={(list) => handleInputChange('unidades_venda_permitidas', list)}
        unidadesCompra={form.unidades_compra_permitidas || []}
        onUnidadesCompraChange={(list) => handleInputChange('unidades_compra_permitidas', list)}
        comprimentoBarra={form.comprimento_padrao_barra_m ?? null}
        onComprimentoBarraChange={(v) => handleInputChange('comprimento_padrao_barra_m', v)}
        pesoMetro={form.peso_por_metro_kg ?? null}
        onPesoMetroChange={(v) => handleInputChange('peso_por_metro_kg', v)}
        pesoPeca={form.peso_por_peca_kg ?? null}
        onPesoPecaChange={(v) => handleInputChange('peso_por_peca_kg', v)}
        pesoChapa={form.peso_por_chapa_kg ?? null}
        onPesoChapaChange={(v) => handleInputChange('peso_por_chapa_kg', v)}
        densidade={form.densidade ?? null}
        onDensidadeChange={(v) => handleInputChange('densidade', v)}
        observacoes={form.observacoes_conversao || ''}
        onObservacoesChange={(v) => handleInputChange('observacoes_conversao', v)}
        ocultarUnidadeFiscal
      />
    </div>
  );
}