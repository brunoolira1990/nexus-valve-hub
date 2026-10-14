import { Input, Label, RadioGroup, RadioGroupItem, Textarea } from '@/components/ui';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import type { FamiliaProduto } from '@/types';
import type { ProdutoFormState, ModoCodigoProduto } from '../types';
import { familiasProdutoService } from '@/services/api/produtos';

interface ProdutoGeralFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview: { codigo?: string; descricao?: string; ncm?: string };
  familiaSelecionada: FamiliaProduto | null;
  erro?: string | null;
  duplicateCodigo?: string | null;
  setModoCodigo: (modo: ModoCodigoProduto) => void;
}

export function ProdutoGeralFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada,
  erro,
  duplicateCodigo,
  setModoCodigo,
}: ProdutoGeralFormTabProps) {
  const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;

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
      {/* Erro global */}
      {erro && <div className="text-sm text-destructive">{erro}</div>}

      {/* Tipo de cadastro */}
      <div className="space-y-2">
        <Label>Tipo de cadastro</Label>
        <RadioGroup value={modo} onValueChange={setModoCodigo} className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <RadioGroupItem value="INTERNO" id="modo-interno" />
            <Label htmlFor="modo-interno" className="cursor-pointer">
              Código interno por regra (família / figura)
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="MANUAL" id="modo-manual" />
            <Label htmlFor="modo-manual" className="cursor-pointer">
              Código manual / fabricante
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="LEGADO" id="modo-legado" />
            <Label htmlFor="modo-legado" className="cursor-pointer">
              Legado (campos texto livres)
            </Label>
          </div>
        </RadioGroup>
      </div>

      {/* Código - varia conforme modo */}
      {modo === 'MANUAL' && (
        <div className="space-y-1">
          <Label>Código manual / fabricante</Label>
          <Input
            className="font-mono"
            value={form.codigo_completo}
            onChange={(e) => handleInputChange('codigo_completo', e.target.value)}
            placeholder="Ex.: AV4000-F04-4DZ"
          />
          <p className="text-xs text-muted-foreground">Preencha a descrição manualmente.</p>
          {duplicateCodigo && (
            <p className="text-xs text-destructive mt-1">
              Já existe um produto cadastrado com o código "{duplicateCodigo}".
            </p>
          )}
        </div>
      )}

      {modo === 'INTERNO' && (
        <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
          <Label>Código</Label>
          <p className="font-mono font-semibold text-lg">{preview.codigo || '—'}</p>
          {duplicateCodigo && (
            <p className="text-xs text-destructive">Já existe produto com este código.</p>
          )}
        </div>
      )}

      {modo === 'LEGADO' && (
        <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
          <Label>Código (prévia legado)</Label>
          <p className="font-mono font-semibold text-lg">{preview.codigo || '—'}</p>
        </div>
      )}

      {/* Descrição */}
      <div className="space-y-1">
        <Label>Descrição</Label>
        <Input
          value={form.descricao}
          onChange={(e) => handleInputChange('descricao', e.target.value)}
          placeholder="Descrição do produto"
        />
        {preview.descricao && preview.descricao !== form.descricao && (
          <button
            type="button"
            className="text-sm text-primary hover:underline mt-1 inline-block"
            onClick={() => handleInputChange('descricao', preview.descricao!)}
          >
            Usar descrição sugerida: {preview.descricao}
          </button>
        )}
      </div>

      {/* Família (apenas modo INTERNO) */}
      {modo === 'INTERNO' && (
        <div className="space-y-1">
          <Label>Família / figura</Label>
          <AsyncAutocomplete<FamiliaProduto>
            value={form.familia_id ?? null}
            selectedOption={familiaSelecionada}
            placeholder="Digite código ou descrição da família..."
            search={(term, limit) => familiasProdutoService.search(term, limit ?? 20)}
            getOptionValue={(opt) => opt.id}
            getOptionLabel={(opt) => `${opt.codigo_figura} — ${opt.descricao_base}`}
            onChange={(val, opt) => {
              const id = typeof val === 'number' ? val : null;
              handleInputChange('familia_id', id);
            }}
          />
          {familiaSelecionada && (
            <p className="text-xs text-muted-foreground">
              Categoria: {familiaSelecionada.categoria_produto === 'MATERIAL_DIMENSIONAL'
                ? 'Material dimensional'
                : familiaSelecionada.categoria_produto === 'MANUAL_FABRICANTE'
                ? 'Produto manual/fabricante'
                : 'Produto técnico'}
              {' · '}
              Tipo: {familiaSelecionada.tipo_dimensional}
            </p>
          )}
        </div>
      )}

      {/* Grid com campos adicionais */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Unidade comercial */}
        <div className="space-y-1">
          <Label>Unidade comercial</Label>
          <Input
            value={form.unidade || ''}
            onChange={(e) => handleInputChange('unidade', e.target.value)}
            placeholder="Ex.: PC, KG, M"
          />
          <p className="text-xs text-muted-foreground">
            Unidade padrão de negociação. Detalhes fiscais na aba Fiscal.
          </p>
        </div>

        {/* Preço Custo */}
        <div className="space-y-1">
          <Label>Preço Custo</Label>
          <Input
            type="number"
            step="0.01"
            value={form.preco_custo}
            onChange={(e) => handleNumberChange('preco_custo', e.target.value)}
            placeholder="0.00"
          />
        </div>

        {/* Preço Venda */}
        <div className="space-y-1">
          <Label>Preço Venda</Label>
          <Input
            type="number"
            step="0.01"
            value={form.preco_venda}
            onChange={(e) => handleNumberChange('preco_venda', e.target.value)}
            placeholder="0.00"
          />
        </div>

        {/* Estoque Mínimo */}
        <div className="space-y-1">
          <Label>Estoque Mínimo</Label>
          <Input
            type="number"
            step="1"
            value={form.estoque_minimo}
            onChange={(e) => handleNumberChange('estoque_minimo', e.target.value)}
            placeholder="0"
          />
        </div>

        {/* NCM (preview) */}
        {preview.ncm && (
          <div className="space-y-1">
            <Label>NCM sugerido</Label>
            <Input
              className="font-mono bg-muted/40"
              value={preview.ncm}
              readOnly
            />
            <p className="text-xs text-muted-foreground">Vem da família ou do preview.</p>
          </div>
        )}

        {/* Observações */}
        <div className="md:col-span-2 lg:col-span-3 space-y-1">
          <Label>Observações</Label>
          <Textarea
            value={form.observacoes_conversao || ''}
            onChange={(e) => handleInputChange('observacoes_conversao', e.target.value)}
            placeholder="Observações gerais do produto"
            rows={3}
          />
        </div>
      </div>
    </div>
  );
}