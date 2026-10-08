import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { ClienteContatosAdicionaisEditor, contatosClienteParaApi } from '@/components/clientes/ClienteContatosAdicionaisEditor';
import {
  MSG_AUXILIAR_CONTATOS_FISCAIS,
  MSG_EMAIL_DUPLICADO,
  MSG_EMAIL_FISCAL_OBRIGATORIO,
  contatoVazioCliente,
  contatosClienteTemErro,
  emailContatoValido,
  validarContatosCliente,
} from '@/lib/clienteContatosFiscais';
import type { ContatoCliente } from '@/types';

describe('clienteContatosFiscais helpers', () => {
  it('valida e-mail e exige e-mail para flag fiscal', () => {
    expect(emailContatoValido('a@b.com')).toBe(true);
    expect(emailContatoValido('x')).toBe(false);

    const fiscalSemEmail: ContatoCliente = {
      ...contatoVazioCliente(),
      recebe_documentos_fiscais: true,
      email: '',
    };
    const erros = validarContatosCliente([fiscalSemEmail]);
    expect(erros[0]?.email).toBe(MSG_EMAIL_FISCAL_OBRIGATORIO);
    expect(contatosClienteTemErro(erros)).toBe(true);
  });

  it('detecta duplicidade case-insensitive', () => {
    const erros = validarContatosCliente([
      { ...contatoVazioCliente(), email: 'Fiscal@Test.Local' },
      { ...contatoVazioCliente(), tipo: 'FINANCEIRO', email: ' fiscal@test.local ' },
    ]);
    expect(erros[0]?.email).toBe(MSG_EMAIL_DUPLICADO);
    expect(erros[1]?.email).toBe(MSG_EMAIL_DUPLICADO);
  });

  it('contatosClienteParaApi preserva flags e trim de e-mail', () => {
    const api = contatosClienteParaApi([
      {
        ...contatoVazioCliente(),
        email: '  a@test.local ',
        ativo: false,
        recebe_documentos_fiscais: true,
      },
    ]);
    expect(api[0].email).toBe('a@test.local');
    expect(api[0].ativo).toBe(false);
    expect(api[0].recebe_documentos_fiscais).toBe(true);
  });
});

describe('ClienteContatosAdicionaisEditor', () => {
  it('renderiza checkboxes e texto auxiliar', () => {
    const onChange = vi.fn();
    render(
      <ClienteContatosAdicionaisEditor
        value={[
          {
            ...contatoVazioCliente(),
            email: 'um@test.local',
            recebe_documentos_fiscais: true,
          },
        ]}
        onChange={onChange}
      />,
    );
    expect(screen.getByText(MSG_AUXILIAR_CONTATOS_FISCAIS)).toBeTruthy();
    expect(screen.getByTestId('contato-ativo-0')).toBeTruthy();
    expect(screen.getByTestId('contato-recebe-fiscais-0')).toBeTruthy();
    expect(screen.getByDisplayValue('um@test.local')).toBeTruthy();
  });

  it('impede marcar fiscal sem e-mail válido', () => {
    const onChange = vi.fn();
    render(
      <ClienteContatosAdicionaisEditor value={[contatoVazioCliente()]} onChange={onChange} />,
    );
    const fiscal = screen.getByTestId('contato-recebe-fiscais-0') as HTMLInputElement;
    expect(fiscal.disabled).toBe(true);
    fireEvent.click(fiscal);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('adiciona dois contatos e permite marcar fiscais com e-mail', () => {
    let value: ContatoCliente[] = [];
    const onChange = vi.fn((next: ContatoCliente[]) => {
      value = next;
    });
    const { rerender } = render(
      <ClienteContatosAdicionaisEditor value={value} onChange={onChange} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Adicionar contato' }));
    expect(onChange).toHaveBeenCalled();
    rerender(<ClienteContatosAdicionaisEditor value={value} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Adicionar contato' }));
    rerender(<ClienteContatosAdicionaisEditor value={value} onChange={onChange} />);
    expect(value).toHaveLength(2);

    const email0 = screen.getByTestId('contato-email-0');
    fireEvent.change(email0, { target: { value: 'fiscal1@test.local' } });
    rerender(<ClienteContatosAdicionaisEditor value={value} onChange={onChange} />);

    const fiscal0 = screen.getByTestId('contato-recebe-fiscais-0') as HTMLInputElement;
    expect(fiscal0.disabled).toBe(false);
    fireEvent.click(fiscal0);
    expect(value[0].recebe_documentos_fiscais).toBe(true);
  });

  it('exibe erro de duplicidade no contato', () => {
    render(
      <ClienteContatosAdicionaisEditor
        value={[
          { ...contatoVazioCliente(), email: 'a@test.local' },
          { ...contatoVazioCliente(), tipo: 'FINANCEIRO', email: 'A@test.local' },
        ]}
        onChange={vi.fn()}
        erros={[{ email: MSG_EMAIL_DUPLICADO }, { email: MSG_EMAIL_DUPLICADO }]}
      />,
    );
    expect(screen.getAllByText(MSG_EMAIL_DUPLICADO).length).toBeGreaterThanOrEqual(1);
  });

  it('inativa sem excluir o contato da lista', () => {
    let value: ContatoCliente[] = [
      { ...contatoVazioCliente(), id: 9, email: 'x@test.local', ativo: true },
    ];
    const onChange = vi.fn((next: ContatoCliente[]) => {
      value = next;
    });
    const { rerender } = render(
      <ClienteContatosAdicionaisEditor value={value} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId('contato-ativo-0'));
    rerender(<ClienteContatosAdicionaisEditor value={value} onChange={onChange} />);
    expect(value).toHaveLength(1);
    expect(value[0].ativo).toBe(false);
    expect(value[0].id).toBe(9);
  });

  it('confirma antes de remover contato persistido', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const onChange = vi.fn();
    render(
      <ClienteContatosAdicionaisEditor
        value={[{ ...contatoVazioCliente(), id: 3, email: 'keep@test.local' }]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Remover' }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
