import { type ReactNode } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Info, Package, DollarSign, FileText } from 'lucide-react';
import type { FamiliaProduto } from '@/types';
import type { ProdutoFormState, ModoCodigoProduto } from '../types';
import { familiasProdutoService } from '@/services/api/produtos';
import { labelsCamposObrigatoriosProduto } from '@/lib/familiaRegra';

/** Asterisco de campo obrigatório (design system C: span text-destructive). */
function Obrigatorio() {
  return (
    <span className="text-destructive" aria-hidden>
      {' '}
      *
    </span>
  );
}

/** Rótulo de campo padronizado (text-sm font-medium mb-1.5). */
function CampoLabel({ children }: { children: ReactNode }) {
  return <Label className="text-sm font-medium mb-1.5 block">{children}</Label>;
}

interface ProdutoGeralFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview: { codigo?: string; descricao?: string; ncm?: string; mensagem?: string };
  familiaSelecionada: FamiliaProduto | null;
  erro?: string | null;
  duplicateCodigo?: string | null;
  setModoCodigo: (modo: ModoCodigoProduto) => void;
  /** Abre o fluxo de criação rápida de família (orquestrado na página container). */
  onNovaFamilia?: () => void;
  /** Código efetivo do produto em edição — fallback read-only quando o preview está vazio. */
  editingCodigo?: string | null;
}

export function ProdutoGeralFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada,
  erro,
  duplicateCodigo,
  setModoCodigo,
  onNovaFamilia,
  editingCodigo,
}: ProdutoGeralFormTabProps) {
  const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;
  // Obrigatórios derivados da família (fonte única: @/lib/familiaRegra)
  const obrigatorios = familiaSelecionada
    ? labelsCamposObrigatoriosProduto(familiaSelecionada)
    : [];

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
    <div className="space-y-6">
      {/* Erro global */}
      {erro && <div className="text-sm text-destructive">{erro}</div>}

      {/* ===== Identificação ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Identificação</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Tipo de cadastro, família/figura, código e descrição do produto
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Tipo de cadastro */}
          <div>
            <CampoLabel>Tipo de cadastro</CampoLabel>
            <RadioGroup value={modo} onValueChange={setModoCodigo} className="flex flex-wrap gap-4 mt-1">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="INTERNO" id="modo-interno" />
                <Label htmlFor="modo-interno" className="cursor-pointer font-normal">
                  Código interno por regra (família / figura)
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="MANUAL" id="modo-manual" />
                <Label htmlFor="modo-manual" className="cursor-pointer font-normal">
                  Código manual / fabricante
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="LEGADO" id="modo-legado" />
                <Label htmlFor="modo-legado" className="cursor-pointer font-normal">
                  Legado (campos texto livres)
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Família (apenas modo INTERNO — vem antes do código para que o código
              derivado da família seja gerado após selecioná-la) */}
          {modo === 'INTERNO' && (
            <div>
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <Label className="text-sm font-medium">
                  Família / figura
                  <Obrigatorio />
                </Label>
                {onNovaFamilia && (
                  <button
                    type="button"
                    className="erp-btn-outline erp-btn-sm"
                    onClick={onNovaFamilia}
                  >
                    + Nova família
                  </button>
                )}
              </div>
              <AsyncAutocomplete<FamiliaProduto>
                value={form.familia_id ?? null}
                selectedOption={familiaSelecionada}
                placeholder="Digite código ou descrição da família..."
                search={(term, limit) => familiasProdutoService.search(term, limit ?? 20)}
                getOptionValue={(opt) => opt.id}
                getOptionLabel={(opt) => `${opt.codigo_figura} — ${opt.descricao_base}`}
                onChange={(val) => {
                  const id = typeof val === 'number' ? val : null;
                  handleInputChange('familia_id', id);
                }}
              />
              {familiaSelecionada && (
                <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs space-y-1.5 mt-2">
                  <p className="font-semibold text-foreground">Produto guiado pela Família/Figura</p>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">
                      {familiaSelecionada.categoria_produto === 'MATERIAL_DIMENSIONAL'
                        ? 'Material dimensional'
                        : familiaSelecionada.categoria_produto === 'MANUAL_FABRICANTE'
                        ? 'Produto manual/fabricante'
                        : 'Produto técnico'}
                    </Badge>
                    <Badge variant="secondary">
                      Tipo: {familiaSelecionada.tipo_dimensional || 'SIMPLES'}
                    </Badge>
                  </div>
                  {obrigatorios.length > 0 && (
                    <p className="text-muted-foreground">
                      <span className="font-medium text-foreground">Obrigatórios:</span>{' '}
                      {obrigatorios.join(' · ')}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Código — varia conforme modo */}
          {modo === 'MANUAL' && (
            <div>
              <CampoLabel>Código manual / fabricante</CampoLabel>
              <Input
                className="font-mono h-10"
                value={form.codigo_completo}
                onChange={(e) => handleInputChange('codigo_completo', e.target.value)}
                placeholder="Ex.: AV4000-F04-4DZ"
              />
              <p className="text-xs text-muted-foreground mt-1">Preencha a descrição manualmente.</p>
              {duplicateCodigo && (
                <p className="text-xs text-destructive mt-1">
                  Já existe um produto cadastrado com o código "{duplicateCodigo}".
                </p>
              )}
            </div>
          )}

          {modo === 'INTERNO' && (
            <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
              <Label className="text-sm font-medium">Código</Label>
              <p className="font-mono font-semibold text-lg">{preview.codigo || editingCodigo || '—'}</p>
              {preview.mensagem && (
                <p className="text-xs text-amber-700 dark:text-amber-300">{preview.mensagem}</p>
              )}
              {duplicateCodigo && (
                <p className="text-xs text-destructive">Já existe produto com este código.</p>
              )}
            </div>
          )}

          {modo === 'LEGADO' && (
            <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
              <Label className="text-sm font-medium">Código (prévia legado)</Label>
              <p className="font-mono font-semibold text-lg">{preview.codigo || editingCodigo || '—'}</p>
            </div>
          )}

          {/* Segmentos de texto do código legado — só existem neste modo. */}
          {modo === 'LEGADO' && (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Cadastro legado: apenas segmentos preenchidos entram no código (sem reticências).
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <div>
                  <CampoLabel>Figura</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.figura || ''}
                    onChange={(e) => handleInputChange('figura', e.target.value)}
                    placeholder="Ex.: 6119"
                  />
                </div>
                <div>
                  <CampoLabel>Sufixo (texto livre)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.sufixo || ''}
                    onChange={(e) => handleInputChange('sufixo', e.target.value)}
                    placeholder="Ex.: F04"
                  />
                </div>
                <div>
                  <CampoLabel>Schedule (texto livre)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.schedule || ''}
                    onChange={(e) => handleInputChange('schedule', e.target.value)}
                    placeholder="Ex.: 40"
                  />
                </div>
                <div>
                  <CampoLabel>Polegada principal (texto)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.polegada_principal || ''}
                    onChange={(e) => handleInputChange('polegada_principal', e.target.value)}
                    placeholder='Ex.: 1 1/2"'
                  />
                </div>
                <div>
                  <CampoLabel>Polegada secundária (texto)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.polegada_secundaria || ''}
                    onChange={(e) => handleInputChange('polegada_secundaria', e.target.value)}
                    placeholder='Ex.: 3/4"'
                  />
                </div>
              </div>
            </div>
          )}

          {/* Descrição */}
          <div>
            <CampoLabel>
              Descrição
              <Obrigatorio />
            </CampoLabel>
            <Input
              className="h-10"
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
        </CardContent>
      </Card>

      {/* ===== Preços e estoque ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Preços e estoque</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Unidade comercial, preços de custo e venda, e estoque mínimo
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* Unidade comercial */}
            <div>
              <CampoLabel>Unidade comercial</CampoLabel>
              <Input
                className="h-10"
                value={form.unidade || ''}
                onChange={(e) => handleInputChange('unidade', e.target.value)}
                placeholder="Ex.: PC, KG, M"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Unidade padrão de negociação. Detalhes fiscais na aba Fiscal.
              </p>
            </div>

            {/* Preço Custo */}
            <div>
              <CampoLabel>Preço Custo</CampoLabel>
              <Input
                type="number"
                step="0.01"
                className="h-10"
                value={form.preco_custo}
                onChange={(e) => handleNumberChange('preco_custo', e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Preço Venda */}
            <div>
              <CampoLabel>Preço Venda</CampoLabel>
              <Input
                type="number"
                step="0.01"
                className="h-10"
                value={form.preco_venda}
                onChange={(e) => handleNumberChange('preco_venda', e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Estoque Mínimo */}
            <div>
              <CampoLabel>Estoque Mínimo</CampoLabel>
              <Input
                type="number"
                step="1"
                className="h-10"
                value={form.estoque_minimo}
                onChange={(e) => handleNumberChange('estoque_minimo', e.target.value)}
                placeholder="0"
              />
            </div>

            {/* NCM (preview) */}
            {preview.ncm && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Label className="text-sm font-medium">NCM sugerido</Label>
                  <Badge variant="secondary">somente leitura</Badge>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        Vem da família/figura ou do preview do servidor. Ajuste o NCM na aba Fiscal.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Input
                  className="font-mono h-10 bg-muted/40"
                  value={preview.ncm}
                  readOnly
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
      {/* ===== Observações ===== */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Observações</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Notas internas e informações complementares sobre o produto
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Textarea
            value={form.observacoes_conversao || ''}
            onChange={(e) => handleInputChange('observacoes_conversao', e.target.value)}
            placeholder="Observações gerais do produto"
            rows={4}
          />
        </CardContent>
      </Card>
    </div>
  );
}
