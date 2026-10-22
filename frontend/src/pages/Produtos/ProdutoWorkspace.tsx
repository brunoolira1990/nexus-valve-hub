import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ProdutoPainelOperacionalTab } from '@/components/produtos/ProdutoPainelOperacionalTab';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import { formatProdutoMaterial } from '@/lib/produtoMaterial';
import { ROTULO_MODO_CODIGO } from '@/lib/produtoRotulos';
import type { Produto } from '@/types';

type ProdutoWorkspaceProps = {
  produto: Produto;
  mode: 'view';
};

function formatValor(valor: number | null | undefined, decimais = 2): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
}

/** Quantidade de estoque em pt-BR: até 3 casas, sem casas forçadas (26.847 → '26,847', 8 → '8'). */
function formatQuantidade(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

function formatData(value?: string | null): string {
  if (!value) return '—';
  return value.split('-').reverse().join('/');
}

function renderField(
  label: string,
  value: string | number | null | undefined,
  { menor = false }: { menor?: boolean } = {},
): React.ReactElement {
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 items-start">
      <dt className={menor ? 'text-xs text-muted-foreground' : 'text-sm text-muted-foreground'}>{label}</dt>
      <dd className={menor ? 'text-xs text-muted-foreground break-words' : 'text-sm font-medium text-foreground break-words'}>
        {value ?? '—'}
      </dd>
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
  // Cadastro zerado é poluição visual: sem preço preenchido o que vale é o preço praticado na NF-e.
  const temValoresDeCadastro = Boolean(produto.preco_custo) || Boolean(produto.preco_venda);

  return (
    <Tabs defaultValue="configuracao" className="w-full">
      <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
        <TabsTrigger value="configuracao">Configuração do Produto</TabsTrigger>
        <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
        <TabsTrigger value="painel">Painel operacional</TabsTrigger>
        <TabsTrigger value="rastreabilidade">Rastreabilidade</TabsTrigger>
        {produto.id ? <TabsTrigger value="historico">Histórico</TabsTrigger> : null}
      </TabsList>

      {/* Mesma divisão da ficha de edição: Identificação/Preços e Classificação técnica dividem a
          aba 'Configuração do Produto' porque a Família/Figura dita os campos técnicos do item. */}
      {/* ABA 1 - CONFIGURAÇÃO DO PRODUTO (Geral + Classificação industrial) */}
      <TabsContent value="configuracao" className="mt-4 space-y-6">
        <SectionCard
          title="Identificação"
          description="Dados principais do produto."
        >
          {/* Schedule e polegadas não aparecem aqui: o código cru do nome repete exatamente o valor
              que 'Identidade técnica' já mostra resolvido, e a tela é uma aba só. */}
          <dl className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderField('Código completo', produto.codigo_completo)}
              {renderField('Descrição', produto.descricao)}
              {renderField('Modo de código', produto.modo_codigo ? ROTULO_MODO_CODIGO[produto.modo_codigo] : '—')}
              {renderField('Unidade comercial', produto.unidade)}
            </div>
            {produto.modo_codigo === 'INTERNO' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border">
                {renderField('Família', produto.familia_detalhes?.nome ?? '—')}
                {produto.sufixo?.trim() ? renderField('Sufixo', produto.sufixo.trim()) : null}
              </div>
            )}
            {produto.modo_codigo === 'LEGADO' && produto.sufixo?.trim() ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border">
                {renderField('Sufixo', produto.sufixo.trim())}
              </div>
            ) : null}
          </dl>
        </SectionCard>

        <SectionCard
          title="Preços e estoque"
          description="Últimos preços praticados pela empresa nas NF-e deste item."
        >
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderField(
              'Última compra',
              produto.ultimo_preco_compra != null ? formatValor(produto.ultimo_preco_compra) : null,
            )}
            {renderField(
              'Última venda',
              produto.ultimo_preco_venda != null ? formatValor(produto.ultimo_preco_venda) : null,
            )}
          </dl>
          {temValoresDeCadastro && (
            <>
              <p className="text-xs text-muted-foreground mt-4 mb-2">Valores do cadastro</p>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {renderField('Preço de custo', formatValor(produto.preco_custo), { menor: true })}
                {renderField('Preço de venda', formatValor(produto.preco_venda), { menor: true })}
              </dl>
            </>
          )}
          <p className="text-xs text-muted-foreground mt-4 mb-2">Estoque</p>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderField('Estoque atual', formatQuantidade(produto.estoque_atual), { menor: true })}
            {renderField('Estoque mínimo', formatValor(produto.estoque_minimo, 0), { menor: true })}
          </dl>
        </SectionCard>

        {(produto.usa_conversao_dimensional_efetivo || produto.controla_composicao_fisica_efetivo) && (
          <SectionCard
            title="Composição e conversões"
            description="Controle de composição física e conversões dimensionais."
          >
            <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {renderField('Controla composição física', produto.controla_composicao_fisica_efetivo ? 'Sim' : 'Não')}
              {renderField('Tipo de composição', produto.tipo_composicao_fisica_efetivo_display ?? '—')}
              {renderField('Usa conversão dimensional', produto.usa_conversao_dimensional_efetivo ? 'Sim' : 'Não')}
              {renderField('Comprimento padrão barra (m)', formatValor(produto.comprimento_padrao_barra_m_efetivo, 3))}
              {renderField('Peso por metro (kg/m)', formatValor(produto.peso_por_metro_kg_efetivo, 4))}
              {renderField('Peso por peça (kg)', formatValor(produto.peso_por_peca_kg, 4))}
              {renderField('Peso por chapa (kg)', formatValor(produto.peso_por_chapa_kg, 4))}
              {renderField('Densidade', formatValor(produto.densidade, 4))}
              {renderField('Observações de conversão', produto.observacoes_conversao || '—')}
            </dl>
          </SectionCard>
        )}

        {/* Bloco da antiga aba 'Classificação industrial', agora dentro de Configuração do Produto. */}
        <SectionCard
          title="Identidade técnica"
          description="Características técnicas e classificação do produto."
        >
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {renderField('Material', produto.material_nome ?? formatProdutoMaterial(produto))}
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
            {renderField('Rosca/Conexão', produto.rosca_conexao_detalhes?.codigo ?? '—')}
            {renderField(
              'Schedule',
              produto.schedule_ref_detalhes?.codigo_schedule ?? produto.schedule_ref_detalhes?.codigo ?? '—',
            )}
            {renderField('Polegada principal', produto.polegada_principal_ref_detalhes?.descricao ?? '—')}
            {renderField('Polegada secundária', produto.polegada_secundaria_ref_detalhes?.descricao ?? '—')}
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
              {renderField('Aba (polegada ref)', produto.dim_aba_polegada_ref_detalhes?.descricao ?? '—')}
              {renderField('Espessura (polegada ref)', produto.dim_espessura_polegada_ref_detalhes?.descricao ?? '—')}
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
            {renderField('Tipo de controle de unidade', produto.tipo_controle_unidade_display ?? produto.tipo_controle_unidade ?? '—')}
            {renderField('Tipo físico do produto', produto.tipo_fisico_display ?? produto.tipo_fisico ?? '—')}
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

      {/* ABA 2 - FISCAL */}
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
            {renderField('Unidade estoque efetiva', produto.unidade_estoque_efetiva ?? '—')}
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
            {renderField('Tipo controle unidade efetivo', produto.tipo_controle_unidade_efetivo_display ?? produto.tipo_controle_unidade_efetivo ?? '—')}
            {renderField('Tipo físico efetivo', produto.tipo_fisico_efetivo_display ?? produto.tipo_fisico_efetivo ?? '—')}
            {renderField('Controla composição efetivo', produto.controla_composicao_fisica_efetivo ? 'Sim' : 'Não')}
            {renderField('Tipo composição efetivo', produto.tipo_composicao_fisica_efetivo_display ?? produto.tipo_composicao_fisica_efetivo ?? '—')}
            {renderField('Unidade base composição', produto.unidade_base_composicao_fisica || '—')}
            {renderField('Usa conversão dimensional efetivo', produto.usa_conversao_dimensional_efetivo ? 'Sim' : 'Não')}
          </dl>
        </SectionCard>
      </TabsContent>

      {/* ABA 3 - PAINEL OPERACIONAL */}
      <TabsContent value="painel" className="mt-4">
        <ProdutoPainelOperacionalTab produtoId={produto.id} active={true} />
      </TabsContent>

      {/* ABA 4 - RASTREABILIDADE */}
      <TabsContent value="rastreabilidade" className="mt-4">
        <ProdutoRastreabilidadeTab produtoId={produto.id} active={true} />
      </TabsContent>

      {/* ABA 5 - HISTÓRICO */}
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