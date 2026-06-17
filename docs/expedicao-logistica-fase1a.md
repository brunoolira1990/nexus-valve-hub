# Expedição / Logística — Fase 1A

Módulo operacional manual para acompanhar entregas, retiradas em fornecedor, volumes, motorista/transportadora e ocorrências.

## Escopo Fase 1A

- Cadastro, listagem, filtros, alteração de status e cancelamento de expedições.
- Vínculos **referenciais** com Pedido de Venda, Pedido de Compra, Faturamento, NF-e Saída, Atendimento Operacional, NF-e Entrada e CT-e Entrada (quando informados manualmente).

## O que este módulo **não** faz

- Não movimenta estoque.
- Não reserva nem baixa estoque.
- Não gera Contas a Receber ou Contas a Pagar.
- Não altera NF-e, XML, DANFE ou BFR.
- Não transmite nem consulta SEFAZ.
- Não altera automaticamente status de Pedido de Venda, Pedido de Compra ou Faturamento.

## API

- `GET/POST /api/expedicoes/`
- `GET/PATCH/DELETE /api/expedicoes/{id}/` (DELETE apenas em rascunho)
- `POST /api/expedicoes/{id}/alterar-status/`
- `POST /api/expedicoes/{id}/cancelar/`
- `GET /api/expedicoes/resumo/`

## Deploy

```bash
docker compose exec backend python manage.py migrate
docker compose restart backend frontend
```

## Rollback

1. Backup do banco antes da migration em produção.
2. Reverter commit e remover item de menu se necessário.
3. Restaurar backup se a migration já tiver sido aplicada.
