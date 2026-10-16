import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ProdutoPainelOperacionalTab } from '@/components/produtos/ProdutoPainelOperacionalTab';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import type { Produto } from '@/types';

type ProdutoWorkspaceProps = {
  produto: Produto;
  mode: 'view';
};

function formatValor(valor: number | null | undefined, decimais = 2): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
}

function formatData(value?: string | null): string {
  if (!value) return '—';
  return value.split('-').reverse().join('/');
}

function renderField(label: string, value: string | number | null | undefined): React.ReactElement {
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 items-start">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground break-words">{value ?? '—'}</dd>
    </div>
  );
}

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </CardHeader>
      <CardContent className="pt-0">{children}</CardContent>
    </Card>
  );
}

export function ProdutoWorkspace({ produto, mode }: ProdutoWorkspaceProps) {
  if (mode !== 'view') {
    return <div className="p-4 text-sm text-muted-foreground">Modo não suportado.</div>;
  }

  const ncmEfetivo = produto.ncm_efetivo?.codigo || produto.ncm || produto.ncm_especifico || 'Não definido';
  const ncmOrigem = produto.ncm_origem === 'produto' ? 'Override no produto' : produto.ncm_origem === 'familia' ? 'Família/figura' : 'Não definido';

  return (
    <Tabs defaultValue="geral" className="w-full">
      <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
        <TabsTrigger value="geral">Geral</TabsTrigger>
        <TabsTrigger value="classificacao">Classificação industrial</TabsTrigger>
        <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
        <TabsTrigger value="painel">Painel operacional</TabsTrigger>
        <TabsTrigger value="rastreabilidade">Rastreabilidade</TabsTrigger>
        {produto.id ? <TabsTrigger value="historico">Histórico</TabsTrigger> : null}
      </TabsList>

      {/* ABA 1 - GERAL */}
      <TabsContent value="geral" className="mt-4 space-y-6">
        <SectionCard
          title="Identificação"
          description="Dados principais do produto."
        >
          <dl className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderField('Código completo', produto.codigo_completo)}
              {renderField('Descrição', produto.descricao)}
              {renderField('Modo de código', produto.modo_codigo)}
              {renderField('Unidade comercial', produto.unidade)}
            </div>
            {produto.modo_codigo === 'INTERNO' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border">
                {renderField('Família', produto.familia_id ? `#${produto.familia_id}` : '—')}
                {renderField('Figura', produto.figura || '—')}
                {renderField('Sufixo', produto.sufixo || '—')}
                {renderField('Schedule', produto.schedule || '—')}
                {renderField('Polegada principal', produto.polegada_principal || '—')}
                {renderField('Polegada secundária', produto.polegada_secundaria || '—')}
              </div>
            )}
            {produto.modo_codigo === 'MANUAL' && (
              <div className="pt-2 border-t border-border">
                {renderField('Código manual/fabricante', produto.codigo_completo)}
              </div>
            )}
            {produto.modo_codigo === 'LEGADO' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border">
                {renderField('Figura', produto.figura || '—')}
                {renderField('Sufixo', produto.sufixo || '—')}
                {renderField('Schedule', produto.schedule || '—')}
                {renderField('Polegada principal', produto.polegada_principal || '—')}
                {renderField('Polegada secundária', produto.polegada_secundaria || '—')}
              </div>
            )}
          </dl>
        </SectionCard>

        <SectionCard
          title="Preços e estoque"
          description="Valores financeiros e controle de estoque."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('Preço de custo', formatValor(produto.preco_custo))}
            {renderField('Preço de venda', formatValor(produto.preco_venda))}
            {renderField('Estoque mínimo', formatValor(produto.estoque_minimo, 0))}
          </dl>
        </SectionCard>

        <SectionCard
          title="Composição e conversões"
          description="Controle de composição física e conversões dimensionais."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('Controla composição física', produto.controla_composicao_fisica ? 'Sim' : 'Não')}
            {renderField('Tipo de composição', produto.tipo_composicao_fisica || '—')}
            {renderField('Usa conversão dimensional', produto.usa_conversao_dimensional ? 'Sim' : 'Não')}
            {renderField('Comprimento padrão barra (m)', formatValor(produto.comprimento_padrao_barra_m, 3))}
            {renderField('Peso por metro (kg/m)', formatValor(produto.peso_por_metro_kg, 4))}
            {renderField('Peso por peça (kg)', formatValor(produto.peso_por_peca_kg, 4))}
            {renderField('Peso por chapa (kg)', formatValor(produto.peso_por_chapa_kg, 4))}
            {renderField('Densidade', formatValor(produto.densidade, 4))}
            {renderField('Observações de conversão', produto.observacoes_conversao || '—')}
          </dl>
        </SectionCard>
      </TabsContent>

      {/* ABA 2 - CLASSIFICAÇÃO INDUSTRIAL */}
      <TabsContent value="classificacao" className="mt-4 space-y-6">
        <SectionCard
          title="Identidade técnica"
          description="Características técnicas e classificação do produto."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField(
              'Material',
              produto.material_ref_detalhes?.nome ?? produto.material ?? '—',
            )}
            {renderField(
              'Norma ASTM',
              produto.material_ref_detalhes?.norma_astm || '—',
            )}
            {renderField(
              'NCM sugerido',
              produto.material_ref_detalhes?.ncm_sugerido || '—',
            )}
            {renderField('Norma', produto.norma || '—')}
            {renderField('Tipo de peça', produto.tipo_peca || '—')}
            {renderField('Pressão nominal', produto.pressao_nominal || '—')}
            {renderField('Conexão', produto.conexao || '—')}
            {renderField('Rosca/Conexão ID', produto.rosca_conexao_id ? `#${produto.rosca_conexao_id}` : '—')}
            {renderField('Schedule ID', produto.schedule_ref_id ? `#${produto.schedule_ref_id}` : '—')}
            {renderField('Polegada principal ID', produto.polegada_principal_ref_id ? `#${produto.polegada_principal_ref_id}` : '—')}
            {renderField('Polegada secundária ID', produto.polegada_secundaria_ref_id ? `#${produto.polegada_secundaria_ref_id}` : '—')}
          </dl>
        </SectionCard>

        {(produto.od_mm || produto.espessura_mm || produto.comprimento_mm) && (
          <SectionCard
            title="Dimensões tubulares"
            description="Medidas principais para produtos tubulares."
          >
            <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {renderField('OD (mm)', formatValor(produto.od_mm, 3))}
              {renderField('Espessura (mm)', formatValor(produto.espessura_mm, 3))}
              {renderField('Comprimento (mm)', formatValor(produto.comprimento_mm, 0))}
            </dl>
          </SectionCard>
        )}

        {(produto.dim_espessura_mm || produto.dim_largura_mm || produto.dim_comprimento_mm || produto.dim_altura_mm || produto.dim_furo_mm || produto.dim_aba_mm) && (
          <SectionCard
            title="Dimensões de material dimensional"
            description="Medidas para chapas, perfis, barras e cantoneiras."
          >
            <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {renderField('Espessura (mm)', formatValor(produto.dim_espessura_mm, 3))}
              {renderField('Largura (mm)', formatValor(produto.dim_largura_mm, 3))}
              {renderField('Comprimento (mm)', formatValor(produto.dim_comprimento_mm, 0))}
              {renderField('Altura (mm)', formatValor(produto.dim_altura_mm, 3))}
              {renderField('Furo (mm)', formatValor(produto.dim_furo_mm, 3))}
              {renderField('Aba (mm)', formatValor(produto.dim_aba_mm, 3))}
              {renderField('Aba (polegada ref)', produto.dim_aba_polegada_ref ? `#${produto.dim_aba_polegada_ref}` : '—')}
              {renderField('Espessura (polegada ref)', produto.dim_espessura_polegada_ref ? `#${produto.dim_espessura_polegada_ref}` : '—')}
            </dl>
          </SectionCard>
        )}

        {(produto.dimensao_codigo || produto.dimensao_descricao) && (
          <SectionCard
            title="Dimensional livre controlado"
            description="Código e descrição personalizados para dimensões livres."
          >
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderField('Dimensão código', produto.dimensao_codigo || '—')}
              {renderField('Dimensão descrição', produto.dimensao_descricao || '—')}
            </dl>
          </SectionCard>
        )}

        <SectionCard
          title="Unidades e controle físico"
          description="Configuração de unidades de medida e tipo físico."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('Tipo de controle de unidade', produto.tipo_controle_unidade || '—')}
            {renderField('Tipo físico do produto', produto.tipo_fisico || '—')}
            {renderField('Unidade de estoque', produto.unidade_estoque || '—')}
            {renderField('Unidade de venda padrão', produto.unidade_venda_padrao || '—')}
            {renderField('Unidade de compra padrão', produto.unidade_compra_padrao || '—')}
            {renderField('Unidade fiscal', produto.unidade_fiscal || '—')}
            {renderField('Unidades de venda permitidas', produto.unidades_venda_permitidas?.join(', ') || '—')}
            {renderField('Unidades de compra permitidas', produto.unidades_compra_permitidas?.join(', ') || '—')}
          </dl>
        </SectionCard>

        {produto.alertas && produto.alertas.length > 0 && (
          <SectionCard
            title="Alertas"
            description="Alertas gerados pelo sistema para este produto."
          >
            <div className="flex flex-wrap gap-2">
              {produto.alertas.map((alerta, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {alerta}
                </Badge>
              ))}
            </div>
          </SectionCard>
        )}
      </TabsContent>

      {/* ABA 3 - FISCAL */}
      <TabsContent value="fiscal" className="mt-4 space-y-6">
        <SectionCard
          title="NCM efetivo para tributação"
          description="Código NCM utilizado em NF-e e regras fiscais."
        >
          <dl className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderField('NCM efetivo', ncmEfetivo)}
              {renderField('Origem do NCM', ncmOrigem)}
            </div>
            {produto.ncm_efetivo?.descricao && (
              <div className="pt-2 border-t border-border">
                {renderField('Descrição do NCM', produto.ncm_efetivo.descricao)}
              </div>
            )}
            {produto.ncm && (
              <div className="pt-2 border-t border-border">
                <p className="text-xs text-muted-foreground">
                  Override no produto: <span className="font-mono font-medium">{produto.ncm}</span>
                </p>
              </div>
            )}
          </dl>
        </SectionCard>

        <SectionCard
          title="Unidades fiscais e específicas"
          description="Configurações de unidade para fins fiscais e legados."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('NCM específico (legado)', produto.ncm_especifico || '—')}
            {renderField('Unidade específica (override)', produto.unidade_especifica || '—')}
            {renderField('Unidade fiscal', produto.unidade_fiscal || '—')}
            {renderField('Unidade estoque efetiva', produto.unidade_estoque_efetiva || produto.unidade_estoque || produto.unidade || '—')}
            {renderField('Unidade venda efetiva', produto.unidade_venda_efetiva || '—')}
            {renderField('Unidade compra efetiva', produto.unidade_compra_efetiva || '—')}
            {renderField('Unidade fiscal efetiva', produto.unidade_fiscal_efetiva || '—')}
            {renderField('Peso por metro efetivo (kg/m)', formatValor(produto.peso_por_metro_kg_efetivo, 4))}
            {renderField('Comprimento barra efetivo (m)', formatValor(produto.comprimento_padrao_barra_m_efetivo, 3))}
            {renderField('Unidades venda efetivas', produto.unidades_venda_permitidas_efetivas?.join(', ') || '—')}
            {renderField('Unidades compra efetivas', produto.unidades_compra_permitidas_efetivas?.join(', ') || '—')}
          </dl>
        </SectionCard>

        <SectionCard
          title="Controle efetivo (herdado + override)"
          description="Valores efetivos após herança da família e overrides do produto."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('Tipo controle unidade efetivo', produto.tipo_controle_unidade_efetivo || '—')}
            {renderField('Tipo físico efetivo', produto.tipo_fisico_efetivo || '—')}
            {renderField('Controla composição efetivo', produto.controla_composicao_fisica_efetivo ? 'Sim' : 'Não')}
            {renderField('Tipo composição efetivo', produto.tipo_composicao_fisica_efetivo || '—')}
            {renderField('Unidade base composição', produto.unidade_base_composicao_fisica || '—')}
            {renderField('Usa conversão dimensional efetivo', produto.usa_conversao_dimensional_efetivo ? 'Sim' : 'Não')}
          </dl>
        </SectionCard>
      </TabsContent>

      {/* ABA 4 - PAINEL OPERACIONAL */}
      <TabsContent value="painel" className="mt-4">
        <ProdutoPainelOperacionalTab produtoId={produto.id} active={true} />
      </TabsContent>

      {/* ABA 5 - RASTREABILIDADE */}
      <TabsContent value="rastreabilidade" className="mt-4">
        <ProdutoRastreabilidadeTab produtoId={produto.id} active={true} />
      </TabsContent>

      {/* ABA 6 - HISTÓRICO */}
      {produto.id && (
        <TabsContent value="historico" className="mt-4">
          <HistoricoAlteracoesPanel
            appLabel="produtos"
            modelName="produto"
            objectId={produto.id}
            active={true}
            enabled={true}
          />
        </TabsContent>
      )}
    </Tabs>
  );
}