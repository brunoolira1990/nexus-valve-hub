/**
 * Piloto isolado do EditableLineTable (Sprint 3.17 FASE 1).
 * Nenhum form de negócio participa daqui: um `useForm` de demonstração fornece `control` e
 * `methods` e a tabela desenha as linhas. O que se prova é a arquitetura do componente.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useRef } from 'react';
import { useForm, type UseFormReturn } from 'react-hook-form';
import { EditableLineTable, type ColumnDef } from '@/components/ui/EditableLineTable';

type ItemDemo = { produto: string; quantidade: number; preco?: number; referencia?: string };
type FormDemo = { itens: ItemDemo[]; extras: ItemDemo[] };

const ITENS: ItemDemo[] = [
  { produto: 'VAL-ESF-INOX-1', quantidade: 2 },
  { produto: 'VAL-GLO-LAT-2', quantidade: 5 },
];

/** Duas linhas com um campo no meio: é a ordem que o Tab do navegador percorre. */
const ITENS_COM_POST: ItemDemo[] = [
  { produto: 'VAL-ESF-INOX-1', quantidade: 2, referencia: 'NCM-8481' },
  { produto: 'VAL-GLO-LAT-2', quantidade: 5, referencia: 'NCM-8482' },
];

/**
 * Coluna de quantidade com `validate`: o valor aceito é 1 ou mais. Serve tanto ao teste do
 * erro quanto ao do empty state, então vive fora dos testes.
 */
function colunasPara(prefixo: 'itens' | 'extras'): ColumnDef<ItemDemo>[] {
  return [
    {
      key: 'produto',
      header: 'Produto',
      width: 'w-1/2',
      render: (_field, index, methods) => (
        <input {...methods.register(`${prefixo}.${index}.produto`)} data-testid={`produto-${index}`} />
      ),
    },
    {
      key: 'quantidade',
      header: 'Quantidade',
      width: 'w-32',
      render: (_field, index, methods) => (
        <input
          type="number"
          {...methods.register(`${prefixo}.${index}.quantidade`, { valueAsNumber: true })}
          data-testid={`quantidade-${index}`}
        />
      ),
      validate: (value: unknown) =>
        typeof value === 'number' && value >= 1 ? undefined : 'Quantidade mínima: 1',
    },
  ];
}

/**
 * Colunas do cálculo reativo (TAREFA 5): `total` não é um campo do formulário, é qtd × preço
 * lido do estado vivo a cada renderização da tabela.
 */
function colunasComTotal(): ColumnDef<ItemDemo>[] {
  const numericas = colunasPara('itens');
  return [
    numericas[0],
    numericas[1],
    {
      key: 'preco',
      header: 'Preço',
      width: 'w-32',
      render: (_field, index, methods) => (
        <input
          type="number"
          {...methods.register(`itens.${index}.preco`, { valueAsNumber: true })}
          data-testid={`preco-${index}`}
        />
      ),
    },
    {
      key: 'total',
      header: 'Total',
      width: 'w-32',
      render: (_field, index, methods) => {
        const linha = methods.getValues(`itens.${index}`) as ItemDemo | undefined;
        return (
          <span data-testid={`total-${index}`}>
            {(linha?.quantidade ?? 0) * (linha?.preco ?? 0)}
          </span>
        );
      },
    },
  ];
}

type RefMetodos = { current: UseFormReturn<FormDemo> | null };

function MontaPoC({
  defaultValues,
  columns,
  name = 'itens',
  emptyMessage,
  novaLinha,
  refMetodos,
}: {
  defaultValues: FormDemo;
  columns: ColumnDef<ItemDemo>[];
  name?: 'itens' | 'extras';
  emptyMessage?: string;
  novaLinha?: ItemDemo;
  refMetodos?: RefMetodos;
}) {
  const methods = useForm<FormDemo>({ defaultValues });
  const captureRef = useRef(refMetodos);
  if (captureRef.current) captureRef.current.current = methods;

  return (
    <EditableLineTable<FormDemo, ItemDemo>
      control={methods.control}
      name={name}
      columns={columns}
      methods={methods}
      defaultValues={novaLinha}
      emptyMessage={emptyMessage}
    />
  );
}

describe('EditableLineTable — piloto isolado (FASE 1)', () => {
  it('desenha um cabeçalho por coluna, na ordem de `columns`', () => {
    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);

    const cabecalhos = screen.getAllByTestId('editable-line-th').map((th) => th.textContent);
    expect(cabecalhos).toEqual(['Produto', 'Quantidade']);
  });

  it('cria uma linha por item do useFieldArray, com os valores do formulário', () => {
    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);

    expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(2);
    expect(screen.getByDisplayValue('VAL-ESF-INOX-1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('VAL-GLO-LAT-2')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2')).toBeInTheDocument();
  });

  it('passa (field, index, methods) para `render`, com o mesmo control do formulário pai', () => {
    const chamada = vi.fn();
    const refMetodos: RefMetodos = { current: null };
    const columns: ColumnDef<ItemDemo>[] = [
      {
        key: 'produto',
        header: 'Produto',
        render: (field, index, methods) => {
          chamada({ field, index, methods });
          return null;
        },
      },
    ];

    render(
      <MontaPoC
        defaultValues={{ itens: [ITENS[0]], extras: [] }}
        columns={columns}
        refMetodos={refMetodos}
      />,
    );

    expect(chamada).toHaveBeenCalled();
    const args = chamada.mock.calls[0][0] as {
      field: { id?: string; produto?: string };
      index: number;
      methods: UseFormReturn<FormDemo>;
    };
    // `field` é o item do array com a chave id usada como React key da linha.
    expect(typeof args.field.id).toBe('string');
    expect(args.field.id).not.toBe('');
    expect(args.index).toBe(0);
    // Prova de que a tabela repassa o methods da página, não um derivado por dentro.
    expect(args.methods.control).toBe(refMetodos.current?.control);
    expect(typeof args.methods.setValue).toBe('function');
    expect(typeof args.methods.getValues).toBe('function');
  });

  it('mostra o erro de `validate` sob a célula enquanto o valor for inválido', () => {
    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);

    // Válido nos valores iniciais: nenhuma mensagem.
    expect(screen.queryByTestId('editable-line-cell-error')).toBeNull();

    fireEvent.change(screen.getByTestId('quantidade-0'), { target: { value: '0' } });
    expect(screen.getByTestId('editable-line-cell-error')).toHaveTextContent('Quantidade mínima: 1');

    fireEvent.change(screen.getByTestId('quantidade-0'), { target: { value: '3' } });
    expect(screen.queryByTestId('editable-line-cell-error')).toBeNull();
  });

  it('mostra a linha vazia quando o array do formulário não tem itens', () => {
    render(
      <MontaPoC
        defaultValues={{ itens: [], extras: [] }}
        columns={colunasPara('itens')}
        emptyMessage="Sem itens na lista."
      />,
    );

    expect(screen.getByTestId('editable-line-empty')).toHaveTextContent('Sem itens na lista.');
    expect(screen.queryByTestId(/^editable-line-row-/)).toBeNull();
  });

  it('lê o array apontado por `name`', () => {
    render(
      <MontaPoC
        defaultValues={{ itens: ITENS, extras: [{ produto: 'VAL-ESFERA-EXTRA', quantidade: 1 }] }}
        columns={colunasPara('extras')}
        name="extras"
      />,
    );

    expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(1);
    expect(screen.getByDisplayValue('VAL-ESFERA-EXTRA')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('VAL-ESF-INOX-1')).toBeNull();
  });

  it('adiciona uma linha pelo rodapé e leva o foco para o primeiro input dela', async () => {
    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);
    expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(2);

    // O `append` do useFieldArray resolve em microtask, então a linha aparece logo após o clique.
    fireEvent.click(screen.getByTestId('editable-line-adicionar'));
    await waitFor(() => expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(3));

    // Sem `defaultValues` na prop, a linha nasce vazia: `{}`.
    const primeiroInput = screen.getByTestId('produto-2');
    expect(primeiroInput).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(primeiroInput));
    // E por isso a única célula inválida da tabela é a quantidade da linha nova.
    const erros = screen.getAllByTestId('editable-line-cell-error');
    expect(erros).toHaveLength(1);
    expect(erros[0]).toHaveTextContent('Quantidade mínima: 1');
  });

  it('usa `defaultValues` da prop como semente da linha nova', async () => {
    render(
      <MontaPoC
        defaultValues={{ itens: [ITENS[0]], extras: [] }}
        columns={colunasPara('itens')}
        novaLinha={{ produto: 'VAL-GLO-BRONZE-3', quantidade: 4 }}
      />,
    );

    fireEvent.click(screen.getByTestId('editable-line-adicionar'));

    await waitFor(() => expect(screen.getByDisplayValue('VAL-GLO-BRONZE-3')).toBeInTheDocument());
    expect(screen.getByDisplayValue('4')).toBeInTheDocument();
    expect(screen.queryByTestId('editable-line-cell-error')).toBeNull();
  });

  it('remove a linha pelo ícone de lixeira', async () => {
    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);

    fireEvent.click(screen.getByTestId('editable-line-remover-0'));

    await waitFor(() => expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(1));
    expect(screen.queryByDisplayValue('VAL-ESF-INOX-1')).toBeNull();
    // A linha que sobra reindexa: era a segunda, passa a ser a linha 0.
    expect(screen.getByTestId('produto-0')).toHaveValue('VAL-GLO-LAT-2');
  });

  it('recalcula qtd × preço ao digitar na linha recém-adicionada', async () => {
    render(
      <MontaPoC
        defaultValues={{ itens: [{ produto: 'VAL-ESF-INOX-1', quantidade: 2, preco: 10 }], extras: [] }}
        columns={colunasComTotal()}
        novaLinha={{ produto: 'VAL-GLO-BRONZE-3', quantidade: 3, preco: 7 }}
      />,
    );
    expect(screen.getByTestId('total-0')).toHaveTextContent('20');

    fireEvent.click(screen.getByTestId('editable-line-adicionar'));
    await waitFor(() => expect(screen.getByTestId('total-1')).toHaveTextContent('21'));

    fireEvent.change(screen.getByTestId('quantidade-1'), { target: { value: '4' } });
    expect(screen.getByTestId('total-1')).toHaveTextContent('28');

    fireEvent.change(screen.getByTestId('preco-1'), { target: { value: '5' } });
    expect(screen.getByTestId('total-1')).toHaveTextContent('20');
  });

  it('não furta o foco ao montar a tabela com linhas já cadastradas', () => {
    const antes = document.activeElement;

    render(<MontaPoC defaultValues={{ itens: ITENS, extras: [] }} columns={colunasPara('itens')} />);

    // O auto-foco é consequência do "Adicionar item". Uma tela que abre com linhas não pode
    // jogar o cursor para dentro da planilha.
    expect(document.activeElement).toBe(antes);
  });

  it('mantém os campos em ordem de linha — o caminho que o Tab percorre', () => {
    // Requisito 4: a tabela não implementa navegação própria e não coloca nada no caminho do
    // Tab nativo. Em jsdom a tecla Tab não move o foco, então o que se prova aqui é a ordem
    // do DOM (linha 0 inteira, depois linha 1) e a ausência de `tabindex` nos campos.
    const colunas: ColumnDef<ItemDemo>[] = [
      {
        key: 'produto',
        header: 'Produto',
        render: (_field, index, methods) => (
          <input {...methods.register(`itens.${index}.produto`)} data-testid={`produto-${index}`} />
        ),
      },
      {
        key: 'referencia',
        header: 'Referência',
        render: (_field, index, methods) => (
          <input
            {...methods.register(`itens.${index}.referencia`)}
            data-testid={`referencia-${index}`}
          />
        ),
      },
      {
        key: 'quantidade',
        header: 'Quantidade',
        render: (_field, index, methods) => (
          <input
            type="number"
            {...methods.register(`itens.${index}.quantidade`, { valueAsNumber: true })}
            data-testid={`quantidade-${index}`}
          />
        ),
      },
    ];

    render(<MontaPoC defaultValues={{ itens: ITENS_COM_POST, extras: [] }} columns={colunas} />);

    const campos = Array.from(document.querySelectorAll('tbody input')) as HTMLInputElement[];
    expect(campos.map((campo) => campo.name)).toEqual([
      'itens.0.produto',
      'itens.0.referencia',
      'itens.0.quantidade',
      'itens.1.produto',
      'itens.1.referencia',
      'itens.1.quantidade',
    ]);
    expect(campos.every((campo) => !campo.hasAttribute('tabindex'))).toBe(true);
  });

  it('deixa a digitação chegar ao formulário e ao `validate` sem modal', () => {
    render(
      <MontaPoC defaultValues={{ itens: [ITENS_COM_POST[0]], extras: [] }} columns={colunasPara('itens')} />,
    );

    fireEvent.change(screen.getByTestId('produto-0'), { target: { value: 'VAL-ESF-BRONZE-9' } });
    fireEvent.change(screen.getByTestId('quantidade-0'), { target: { value: '7' } });

    expect(screen.getByTestId('produto-0')).toHaveValue('VAL-ESF-BRONZE-9');
    expect(screen.queryByTestId('editable-line-cell-error')).toBeNull();
    const quantidade = screen.getByTestId('quantidade-0') as HTMLInputElement;
    expect(quantidade.value).toBe('7');
  });

  it('não foca a lixeira quando a linha nova não tem campo editável', async () => {
    // Coluna de ação apenas: o único elemento focável da linha é um botão, e o auto-foco
    // procura input/select/textarea — nunca botão. O alvo com campo editável já é provado no
    // teste do "Adicionar item".
    const colunasDeAcao: ColumnDef<ItemDemo>[] = [
      {
        key: 'acao',
        header: 'Ação',
        render: (_field, index) => (
          <button type="button" data-testid={`abrir-picker-${index}`}>
            Abrir catálogo
          </button>
        ),
      },
    ];

    render(<MontaPoC defaultValues={{ itens: [ITENS[0]], extras: [] }} columns={colunasDeAcao} />);
    const focoAntes = document.activeElement;

    fireEvent.click(screen.getByTestId('editable-line-adicionar'));
    await waitFor(() => expect(screen.getAllByTestId(/^editable-line-row-/)).toHaveLength(2));

    expect(document.activeElement).toBe(focoAntes);
    expect(screen.getAllByTestId('abrir-picker-1')).toHaveLength(1);
  });
});
