import api from './config';

export interface TokenPair {
  access: string;
  refresh: string;
}

export async function login(username: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/token/', { username, password });
  return data;
}

export function persistTokens(tokens: TokenPair): void {
  localStorage.setItem('access_token', tokens.access);
  localStorage.setItem('refresh_token', tokens.refresh);
}

export function clearTokens(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}
