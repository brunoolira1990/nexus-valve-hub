/**
 * Demo navegável do EditableLineTable (Sprint 3.17 FASE 1).
 * Rota `/dev/line-table`, só existe em DEV. Prova visual no localhost de que o apêndice, a
 * remoção, o auto-foco e o estado do react-hook-form fluem pela mesma planilha — o `<pre>` ao
 * lado é o `watch()` do formulário, então ele mexe junto com a digitação.
 */
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EditableLineTable, type ColumnDef } from '@/components/ui/EditableLineTable';

const schema = z.object({
  itens: z.array(
    z.object({
      descricao: z.string(),
      quantidade: z.number(),
      preco: z.number(),
    }),
  ),
});

type LinhaDemo = z.infer<typeof schema>['itens'][number];
type FormDemo = z.infer<typeof schema>;

const colunas: ColumnDef<LinhaDemo>[] = [
  {
    key: 'descricao',
    header: 'Descrição',
    width: 'w-1/2',
    render: (_field, index, methods) => (
      <Input className="h-8" {...methods.register(`itens.${index}.descricao`)} />
    ),
  },
  {
    key: 'quantidade',
    header: 'Quantidade',
    width: 'w-32',
    render: (_field, index, methods) => (
      <Input
        className="h-8"
        type="number"
        {...methods.register(`itens.${index}.quantidade`, { valueAsNumber: true })}
      />
    ),
    validate: (value) =>
      typeof value === 'number' && value >= 1 ? undefined : 'Quantidade mínima: 1',
  },
  {
    key: 'preco',
    header: 'Preço',
    width: 'w-32',
    render: (_field, index, methods) => (
      <Input
        className="h-8"
        type="number"
        step="0.01"
        {...methods.register(`itens.${index}.preco`, { valueAsNumber: true })}
      />
    ),
  },
];

export default function LineTableDemo() {
  const methods = useForm<FormDemo>({
    resolver: zodResolver(schema),
    defaultValues: {
      itens: [{ descricao: 'VÁLVULA DE ESFERA INOX 316 1 POL', quantidade: 2, preco: 149.9 }],
    },
  });
  // Assinatura raiz: é o que faz o `<pre>` acompanhar cada tecla digitada na planilha.
  const estado = methods.watch();

  const enviar = methods.handleSubmit((dados) => {
    console.log('[LineTableDemo] submit', dados);
  });

  return (
    <div className="p-6">
      <h1 className="mb-1 text-xl font-semibold">LineTable Demo - Sprint 3.17</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Rota de desenvolvimento: edição inline de itens sem modal. O JSON abaixo é o estado vivo
        do react-hook-form.
      </p>

      {/*
        `noValidate` é obrigatório: com a validação nativa ativa, um `input type="number"` sem
        `step` aceita só inteiros e o `requestSubmit()` do zod/RHF nem chega a rodar. A
        validação do formulário é do react-hook-form, não do navegador.
      */}
      <form className="max-w-4xl space-y-4" noValidate onSubmit={(e) => void enviar(e)}>
        <EditableLineTable
          control={methods.control}
          name="itens"
          columns={colunas}
          methods={methods}
          defaultValues={{ descricao: '', quantidade: 1, preco: 0 }}
        />

        <div className="flex items-center gap-3">
          <Button type="submit">Submit</Button>
          <span className="text-sm text-muted-foreground">
            {estado.itens.length} linha(s) no formulário
          </span>
        </div>

        <pre className="overflow-auto rounded border bg-muted p-3 font-mono text-xs">
          {JSON.stringify(estado, null, 2)}
        </pre>
      </form>
    </div>
  );
}
