/**
 * ERP 4.0.15.0.6 — Política de sync automático vs manifestação manual.
 *
 * DF-e automático (permitido em background ao abrir Central DF-e):
 * - GET central-dfe/ — listagem local
 * - POST dfe-recebidos/capturar/ — captura XML/recebidos
 * - POST fiscal/manifestacao-destinatario/consultar/ — apenas resumos destinados (dist NSU)
 * - GET fiscal/manifestacao-destinatario/ — leitura de status (sem evento fiscal)
 *
 * Manifestação manual (somente clique explícito do usuário):
 * - POST fiscal/manifestacao-destinatario/iniciar-por-chave/ — prepara registro (sem evento fiscal)
 * - POST fiscal/manifestacao-destinatario/{id}/manifestar/
 * - POST fiscal/manifestacao-destinatario/{id}/baixar-xml/
 * - POST central-dfe/{id}/armazenar-xml-nfe/ — armazena NF-e na base importada
 * - POST central-dfe/{id}/armazenar-xml-cte/ — confirma CT-e na base importada
 */

export const DFE_SYNC_ENDPOINTS_AUTOMATICOS = [
  'dfe-recebidos/capturar/',
  'fiscal/manifestacao-destinatario/consultar/',
] as const;

export const MANIFESTACAO_ENDPOINTS_SOMENTE_MANUAL = [
  'fiscal/manifestacao-destinatario/iniciar-por-chave/',
  'fiscal/manifestacao-destinatario/{id}/manifestar/',
  'fiscal/manifestacao-destinatario/{id}/baixar-xml/',
  'central-dfe/{id}/armazenar-xml-nfe/',
  'central-dfe/{id}/armazenar-xml-cte/',
] as const;
