import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProdutoPainelOperacionalTab } from '@/components/produtos/ProdutoPainelOperacionalTab';
import { ProdutoRastreabilidadeTab } from '@/components/produtos/ProdutoRastreabilidadeTab';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import { ProdutoGeralFormTab } from './tabs/ProdutoGeralFormTab';
import { ProdutoClassificacaoFormTab } from './tabs/ProdutoClassificacaoFormTab';
import { ProdutoFiscalFormTab } from './tabs/ProdutoFiscalFormTab';
import { produtoParaFormState } from './lib/produtoParaForm';
import { getFamReq } from './lib/familiaDerivations';
import { familiaDaFicha } from '@/types';
import type { Produto } from '@/types';
import type { ProdutoFormState } from './types';

type ProdutoWorkspaceProps = {
  produto: Produto;
  mode: 'view';
};

export function ProdutoWorkspace({ produto, mode }: ProdutoWorkspaceProps) {
  // Estado local só para dar aos componentes da Edição o par form/setForm que eles exigem.
  // Em leitura nada escreve aqui, e a página container monta a ficha depois de receber o payload.
  const [form, setForm] = useState<ProdutoFormState>(() => produtoParaFormState(produto));
  const familiaFicha = familiaDaFicha(produto.familia_detalhes);
  const famReq = getFamReq(familiaFicha);

  if (mode !== 'view') {
    return <div className="p-4 text-sm text-muted-foreground">Modo não suportado.</div>;
  }

  return (
    <Tabs defaultValue="configuracao" className="w-full">
      <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4">
        <TabsTrigger value="configuracao">Configuração do Produto</TabsTrigger>
        <TabsTrigger value="fiscal">Fiscal</TabsTrigger>
        <TabsTrigger value="painel">Painel operacional</TabsTrigger>
        <TabsTrigger value="rastreabilidade">Rastreabilidade</TabsTrigger>
        {produto.id ? <TabsTrigger value="historico">Histórico</TabsTrigger> : null}
      </TabsList>

      {/* Mesmos componentes da ficha de Edição, com somenteLeitura: se a Edição ganhar um card,
          a Visualização ganha junto — é por isso que esta aba não monta cards próprios. */}
      <TabsContent value="configuracao" className="mt-4 space-y-6">
        <ProdutoGeralFormTab
          form={form}
          setForm={setForm}
          preview={{}}
          familiaSelecionada={familiaFicha}
          editingCodigo={produto.codigo_completo}
          produto={produto}
          somenteLeitura
        />

        <ProdutoClassificacaoFormTab
          form={form}
          setForm={setForm}
          familiaSelecionada={familiaFicha}
          famReq={famReq}
          produto={produto}
          somenteLeitura
        />
      </TabsContent>

      <TabsContent value="fiscal" className="mt-4 space-y-6">
        <ProdutoFiscalFormTab
          form={form}
          setForm={setForm}
          familiaSelecionada={familiaFicha}
          somenteLeitura
        />
      </TabsContent>

      <TabsContent value="painel" className="mt-4">
        <ProdutoPainelOperacionalTab produtoId={produto.id} active={true} />
      </TabsContent>

      <TabsContent value="rastreabilidade" className="mt-4">
        <ProdutoRastreabilidadeTab produtoId={produto.id} active={true} />
      </TabsContent>

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
