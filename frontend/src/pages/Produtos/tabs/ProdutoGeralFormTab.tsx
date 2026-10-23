import { type ReactNode } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
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
import { Info, Package, DollarSign } from 'lucide-react';
import type { FamiliaProduto, Produto } from '@/types';
import type { ProdutoFormState, ModoCodigoProduto } from '../types';
import { familiasProdutoService } from '@/services/api/produtos';
import { labelsCamposObrigatoriosProduto } from '@/lib/familiaRegra';
import { campoId, classeErroCampo, type CampoFormProdutoInvalido } from '../lib/erroCampo';

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

/** Rótulos do bloco 'Tipo de cadastro' — os mesmos textos servem ao RadioGroup e à ficha read-only. */
const ROTULO_TIPO_CADASTRO: Record<ModoCodigoProduto, string> = {
  INTERNO: 'Código interno por regra (família / figura)',
  MANUAL: 'Código manual / fabricante',
  LEGADO: 'Legado (campos texto livres)',
};

/** Campo só da Visualização: mesmo rótulo e mesma célula de grid do controle editável que ele imita. */
function CampoLeitura({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <CampoLabel>{label}</CampoLabel>
      <Input className="h-10 bg-muted/40" value={value} disabled readOnly />
    </div>
  );
}

/** Preço praticado em pt-BR com duas casas; estoque em até 3 casas sem zeros forçados. */
function formatMoeda(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatQuantidade(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

interface ProdutoGeralFormTabProps {
  form: ProdutoFormState;
  setForm: (updater: (prev: ProdutoFormState) => ProdutoFormState) => void;
  preview: { codigo?: string; descricao?: string; ncm?: string; mensagem?: string };
  familiaSelecionada: FamiliaProduto | null;
  duplicateCodigo?: string | null;
  /** Só a Edição usa: em leitura o RadioGroup não é montado. */
  setModoCodigo?: (modo: ModoCodigoProduto) => void;
  /** Abre o fluxo de criação rápida de família (orquestrado na página container). */
  onNovaFamilia?: () => void;
  /** Código efetivo do produto em edição — fallback read-only quando o preview está vazio. */
  editingCodigo?: string | null;
  /** Campo apontado pela validação do salvar(): recebe o anel e a âncora de rolagem. */
  campoErro?: CampoFormProdutoInvalido | null;
  /** Ficha de Visualização: preços praticados e estoque atual vêm do payload, não do formulário. */
  produto?: Produto | null;
  /** Ficha de Visualização: cards e grid idênticos aos da Edição, com tudo desabilitado e sem ações. */
  somenteLeitura?: boolean;
}

export function ProdutoGeralFormTab({
  form,
  setForm,
  preview,
  familiaSelecionada,
  duplicateCodigo,
  setModoCodigo,
  onNovaFamilia,
  editingCodigo,
  campoErro = null,
  produto = null,
  somenteLeitura = false,
}: ProdutoGeralFormTabProps) {
  const modo = (form.modo_codigo || 'LEGADO') as ModoCodigoProduto;
  // Sem preço de cadastro nem estoque mínimo, o que vale é o praticado na NF-e.
  const mostrarCadastro =
    !somenteLeitura ||
    Number(form.preco_custo) > 0 ||
    Number(form.preco_venda) > 0 ||
    Number(form.estoque_minimo) > 0;
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
            {somenteLeitura ? (
              <p className="text-sm font-medium mt-1">{ROTULO_TIPO_CADASTRO[modo]}</p>
            ) : (
              <RadioGroup value={modo} onValueChange={setModoCodigo} className="flex flex-wrap gap-4 mt-1">
                {(['INTERNO', 'MANUAL', 'LEGADO'] as ModoCodigoProduto[]).map((opcao) => (
                  <div key={opcao} className="flex items-center gap-2">
                    <RadioGroupItem value={opcao} id={`modo-${opcao.toLowerCase()}`} />
                    <Label htmlFor={`modo-${opcao.toLowerCase()}`} className="cursor-pointer font-normal">
                      {ROTULO_TIPO_CADASTRO[opcao]}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            )}
          </div>

          {/* Família (apenas modo INTERNO — vem antes do código para que o código
              derivado da família seja gerado após selecioná-la) */}
          {modo === 'INTERNO' && (
            <div id={campoId('familia_id')} className={classeErroCampo(campoErro, 'familia_id')}>
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <Label className="text-sm font-medium">
                  Família / figura
                  <Obrigatorio />
                </Label>
                {!somenteLeitura && onNovaFamilia && (
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
                disabled={somenteLeitura}
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
                disabled={somenteLeitura}
                onChange={(e) => handleInputChange('codigo_completo', e.target.value)}
                placeholder="Ex.: AV4000-F04-4DZ"
              />
              {!somenteLeitura && (
                <p className="text-xs text-muted-foreground mt-1">Preencha a descrição manualmente.</p>
              )}
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
              {!somenteLeitura && (
                <p className="text-xs text-muted-foreground">
                  Cadastro legado: apenas segmentos preenchidos entram no código (sem reticências).
                </p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <div>
                  <CampoLabel>Figura</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.figura || ''}
                    disabled={somenteLeitura}
                    onChange={(e) => handleInputChange('figura', e.target.value)}
                    placeholder="Ex.: 6119"
                  />
                </div>
                <div>
                  <CampoLabel>Sufixo (texto livre)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.sufixo || ''}
                    disabled={somenteLeitura}
                    onChange={(e) => handleInputChange('sufixo', e.target.value)}
                    placeholder="Ex.: F04"
                  />
                </div>
                <div>
                  <CampoLabel>Schedule (texto livre)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.schedule || ''}
                    disabled={somenteLeitura}
                    onChange={(e) => handleInputChange('schedule', e.target.value)}
                    placeholder="Ex.: 40"
                  />
                </div>
                <div>
                  <CampoLabel>Polegada principal (texto)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.polegada_principal || ''}
                    disabled={somenteLeitura}
                    onChange={(e) => handleInputChange('polegada_principal', e.target.value)}
                    placeholder='Ex.: 1 1/2"'
                  />
                </div>
                <div>
                  <CampoLabel>Polegada secundária (texto)</CampoLabel>
                  <Input
                    className="h-10"
                    value={form.polegada_secundaria || ''}
                    disabled={somenteLeitura}
                    onChange={(e) => handleInputChange('polegada_secundaria', e.target.value)}
                    placeholder='Ex.: 3/4"'
                  />
                </div>
              </div>
            </div>
          )}

          {/* Descrição */}
          <div id={campoId('descricao')} className={classeErroCampo(campoErro, 'descricao')}>
            <CampoLabel>
              Descrição
              <Obrigatorio />
            </CampoLabel>
            <Input
              className="h-10"
              value={form.descricao}
              disabled={somenteLeitura}
              onChange={(e) => handleInputChange('descricao', e.target.value)}
              placeholder="Descrição do produto"
            />
            {!somenteLeitura && preview.descricao && preview.descricao !== form.descricao && (
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
          {mostrarCadastro && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {/* Unidade comercial */}
              <div>
                <CampoLabel>Unidade comercial</CampoLabel>
                <Input
                  className="h-10"
                  value={form.unidade || ''}
                  disabled={somenteLeitura}
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
                  disabled={somenteLeitura}
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
                  disabled={somenteLeitura}
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
                  disabled={somenteLeitura}
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
          )}

          {/* Só a Visualização: o que a empresa realmente pagou e cobrou (NF-e) e o saldo em
              estoque. Nenhum desses campos existe no formulário de Edição. */}
          {somenteLeitura && produto ? (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">Últimos Preços e Estoque</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <CampoLeitura label="Última compra" value={formatMoeda(produto.ultimo_preco_compra)} />
                <CampoLeitura label="Última venda" value={formatMoeda(produto.ultimo_preco_venda)} />
                <CampoLeitura label="Estoque atual" value={formatQuantidade(produto.estoque_atual)} />
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
