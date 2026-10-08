# C0 — Fachada neutra de certificado digital A1

## Objetivo

Expor acesso somente leitura ao A1 da Empresa para futuras integrações
(ex.: CENPROT), **sem** acoplar a emissão NF-e, XML, DANFE, BFR ou SEFAZ.

## O que esta fachada faz

- Valida disponibilidade por finalidade (`FISCAL_SEFAZ`, `CONSULTA_CENPROT`)
- Retorna metadados seguros (sem path, senha, subject, serial, PEM)
- Carrega material criptográfico **apenas em memória**, com liberação explícita

## O que esta fachada não faz

- Não chama HTTP / CENPROT / SEFAZ
- Não assina XML
- Não altera `Empresa` nem a senha
- Não persiste PEM ou PFX
- Não migra consumidores fiscais

## Delegação

Metadados e validação usam `carregar_certificado_empresa` do adaptador fiscal
existente (`fiscal/nfe_integracao/adapters/certificado_a1.py`), com erros remapeados
e sanitizados. O carregador fiscal **não foi movido**.

## Dívida de segurança (fora do C0)

`Empresa.senha_certificado` permanece em texto simples no banco. Correção exige
tarefa separada (criptografia em repouso, migration, rotação e rollback).
