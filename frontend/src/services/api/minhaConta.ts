import api from './config';

export const minhaContaService = {
  alterarSenha: async (payload: {
    senha_atual: string;
    nova_senha: string;
    confirmar_senha: string;
  }) => (await api.post<{ mensagem: string }>('minha-conta/alterar-senha/', payload)).data,
};
