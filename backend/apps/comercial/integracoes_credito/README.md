# Fundação B2/B3 — Consultas externas da Liberação Financeira

## Objetivo

Preparar contratos, registry, model e capability para futuras consultas
cadastrais (B2) e de birô (B3), **sem provider real**, **sem HTTP externo** e
**sem dados simulados em produção**.

## Estado atual

- Provider cadastral ativo: nenhum
- Provider de birô ativo: nenhum
- Capability: `configurado=false`, `permite_consulta=false`
- Decisão financeira: **MANUAL**
- ReceitaWS (`cadastros/consulta_cnpj.py`) **não** é usada pelo dossiê

## Como registrar um adapter futuro

1. Implementar `ConsultaCadastralCNPJProvider` ou `CreditBureauProvider` em módulo dedicado.
2. Registrar via `CreditIntegrationRegistry.register_cadastral(...)` / `register_bureau(...)`
   somente após gate contratual e configuração segura (secrets fora do código).
3. Não registrar `receitaws`, `mock` ou `fake` como provider de produção.
4. Fakes são permitidos **somente** nos testes, via injeção no registry.

## Campos proibidos no resultado persistido

`raw`, `payload`, `response`, `request`, `headers`, `token`, `api_key`, `secret`,
`authorization`, `qsa`, `socios`, `pdf`, `xml`, `stack`, `traceback`.

## Gate contratual

Antes de chamada real: provider, produto, campos, autenticação, custo, sandbox,
retenção, usuários autorizados e termos de API.

## Permissões

- `solicitar_consulta_cadastral_analise`
- `ver_resultado_cadastral_analise`
- `solicitar_consulta_buro_analise`
- `ver_resultado_buro_analise`

Nenhuma é concedida automaticamente nesta fundação.

## Comportamento desativado

- Abrir dossiê / capability: não cria registro e não chama rede
- POST de consulta: retorna erro de negócio (`PROVIDER_NAO_CONFIGURADO` / `BURO_NAO_CONTRATADO`)
- UI: botões desabilitados; sem score/dívidas/capital fictícios

## Escritas nesta fundação

- Nenhum endpoint público cria `ConsultaExternaAnaliseFinanceira`.
- O model existe apenas como fundação para adapters futuros.
- Somente testes internos podem criar registros para validar serializer/leitura.
- Capability e POSTs desabilitados são read-only do ponto de vista do banco
  (POST falha com 409 **antes** de qualquer `save()`/`create()`).
- Nenhuma tentativa gera evento append-only da análise.
- Futuras escritas dependerão de novo gate contratual e nova revisão.

## Testes com fake

Use `register_*` no registry **apenas** em testes; chame `reset_default_registry_for_tests()`
no `tearDown`.
