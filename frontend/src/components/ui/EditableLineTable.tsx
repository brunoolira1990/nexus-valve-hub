import { useEffect, useRef, type ReactNode } from 'react';
import {
  useFieldArray,
  useWatch,
  type ArrayPath,
  type Control,
  type FieldArray,
  type FieldArrayPath,
  type FieldValues,
  type Path,
  type UseFieldArrayReturn,
  type UseFormReturn,
} from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

/**
 * Contrato de coluna da planilha editável (Sprint 3.17). `T` é o tipo da LINHA, não o do
 * formulário: `key` endereça uma propriedade do item.
 */
export type ColumnDef<T> = {
  key: keyof T | string;
  header: string;
  /** Classe de largura aplicada ao cabeçalho da coluna (ex.: "w-32"). */
  width?: string;
  render: (
    field: UseFieldArrayReturn<any>['fields'][number],
    index: number,
    methods: UseFormReturn<any>,
  ) => ReactNode;
  /** Retorna a mensagem de erro da célula; `undefined` significa valor aceito. */
  validate?: (value: any) => string | undefined;
};

export type EditableLineTableProps<Form extends FieldValues = FieldValues, Row = FieldValues> = {
  control: Control<Form>;
  /** Nome do array no formulário (ex.: "itens"). */
  name: FieldArrayPath<Form>;
  columns: ColumnDef<Row>[];
  /**
   * O `useForm` da página. `control` não basta: o 3º argumento de `render` é o objeto de
   * métodos, e derivá-lo dentro da tabela (`useForm({ formControl })`) sobrescreve
   * `control._options` — jogaria fora o `resolver`/`defaultValues` do formulário pai.
   */
  methods: UseFormReturn<Form>;
  /** Valores da linha criada pelo "Adicionar item" (padrão: `{}`). */
  defaultValues?: Row;
  /** Texto da linha vazia quando o array não tem itens. */
  emptyMessage?: string;
  className?: string;
};

/**
 * Planilha de linhas no estilo Odoo: uma linha por item do `useFieldArray`, cada célula
 * entregue pela coluna. A tabela não conhece o domínio — só desenha e valida.
 */
export function EditableLineTable<Form extends FieldValues = FieldValues, Row = FieldValues>({
  control,
  name,
  columns,
  methods,
  defaultValues,
  emptyMessage = 'Nenhuma linha cadastrada.',
  className,
}: EditableLineTableProps<Form, Row>) {
  const { fields, append, remove } = useFieldArray<Form>({ control, name });
  // O `fields` do useFieldArray só acompanha a estrutura do array; para o `validate` ver a
  // tecla digitada é preciso assinar os valores. `useWatch` aceita `Path`, e todo
  // FieldArrayPath é um Path do mesmo formulário — por isso o cast.
  const linhas = useWatch({ control, name: name as Path<Form> }) as readonly Row[] | undefined;

  const corpoRef = useRef<HTMLTableSectionElement | null>(null);
  // Índice da linha que espera pelo foco; -1 quando não há nada pendente.
  const focoPendente = useRef(-1);

  const linhaDoCorpo = (index: number) =>
    corpoRef.current?.querySelector(`tr[data-line-index="${index}"]`);

  const focarLinha = (index: number) => {
    linhaDoCorpo(index)
      ?.querySelector<HTMLElement>(
        'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])',
      )
      ?.focus();
  };

  // Odoo: a linha nova já nasce editável. O `requestAnimationFrame` espera o DOM da linha
  // existir — o RHF resolve o `append` em microtask — e o efeito abaixo dá uma única nova
  // tentativa quando são os valores que ainda não chegaram. Se a linha chegar sem input
  // algum (coluna de botão, por exemplo), nada é focado: o foco fica onde o operador estava.
  const adicionarLinha = (semente: FieldArray<Form, ArrayPath<Form>>) => {
    const index = fields.length;
    focoPendente.current = index;
    requestAnimationFrame(() => {
      if (focoPendente.current !== index || !linhaDoCorpo(index)) return;
      focarLinha(index);
      focoPendente.current = -1;
    });
    append(semente);
  };

  useEffect(() => {
    if (focoPendente.current < 0) return;
    const index = focoPendente.current;
    if (!linhaDoCorpo(index)) return;
    focarLinha(index);
    focoPendente.current = -1;
  }, [fields.length]);

  return (
    <>
      <Table data-testid="editable-line-table" className={className}>
        <TableHeader>
          <TableRow>
            {columns.map((column, columnIndex) => (
              <TableHead
                key={`${columnIndex}-${String(column.key)}`}
                className={cn(column.width)}
                data-testid="editable-line-th"
              >
                {column.header}
              </TableHead>
            ))}
            <TableHead className="w-16" data-testid="editable-line-th-remover" aria-label="Remover" />
          </TableRow>
        </TableHeader>
        <TableBody ref={corpoRef}>
          {fields.length === 0 ? (
            <TableRow data-testid="editable-line-empty">
              <TableCell colSpan={Math.max(columns.length, 1) + 1}>{emptyMessage}</TableCell>
            </TableRow>
          ) : (
            fields.map((field, index) => (
              <TableRow key={field.id} data-line-index={index} data-testid={`editable-line-row-${index}`}>
                {columns.map((column) => {
                  const linha = (linhas?.[index] ?? field) as Row;
                  const erro = column.validate?.(
                    (linha as Record<string, any>)[column.key as string],
                  );
                  return (
                    <TableCell key={`${index}-${String(column.key)}`} data-testid="editable-line-td">
                      {column.render(field, index, methods)}
                      {erro ? (
                        <div
                          data-testid="editable-line-cell-error"
                          className="mt-1 text-xs text-destructive"
                        >
                          {erro}
                        </div>
                      ) : null}
                    </TableCell>
                  );
                })}
                <TableCell className="w-16 text-center">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    aria-label={`Remover linha ${index + 1}`}
                    data-testid={`editable-line-remover-${index}`}
                    onClick={() => remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <div className="mt-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          data-testid="editable-line-adicionar"
          onClick={() =>
            // O parâmetro do `append` é o elemento do array apontado por `name`; para um
            // `Form` genérico esse tipo só se resolve em tempo de execução — daí o cast do
            // fallback `{}` que a spec pede.
            adicionarLinha((defaultValues ?? {}) as FieldArray<Form, ArrayPath<Form>>)
          }
        >
          <Plus className="mr-1 h-4 w-4" />
          Adicionar item
        </Button>
      </div>
    </>
  );
}
