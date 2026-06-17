# NF-e Saída — Envio manual DANFE/XML por e-mail

Envio **manual** dos arquivos da NF-e autorizada (DANFE PDF + XML autorizado) para o cliente, usando SMTP próprio do ambiente Nexus.

## O que faz

- Ação **Enviar DANFE/XML** na NF-e Saída autorizada (drawer de detalhes).
- Modal com destinatário editável, cópia opcional, assunto/mensagem sugeridos e confirmação explícita.
- Anexa XML autorizado e DANFE PDF gerado pelos serviços fiscais já existentes.
- Registra log de envio (`NFeSaidaEnvioEmail`) com usuário, data, destinatários e resultado.

## O que não faz

- Não envia automaticamente ao autorizar NF-e.
- Não retransmite NF-e nem consulta SEFAZ.
- Não altera XML, DANFE, protocolo, chave ou status fiscal.
- Não gera financeiro nem movimenta estoque.

## Configuração SMTP (`.env`)

Use apenas placeholders no `.env.example`. Valores reais ficam no `.env` do servidor:

| Variável | Descrição |
|----------|-----------|
| `EMAIL_BACKEND` | Ex.: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Servidor SMTP |
| `EMAIL_PORT` | Porta (ex.: 587) |
| `EMAIL_HOST_USER` | Usuário SMTP |
| `EMAIL_HOST_PASSWORD` | Senha SMTP |
| `EMAIL_USE_TLS` | `true` / `false` |
| `EMAIL_USE_SSL` | `true` / `false` |
| `DEFAULT_FROM_EMAIL` | Remetente padrão |
| `NEXUS_EMAIL_OPERACIONAL` | Remetente operacional (DANFE/XML) |

Em desenvolvimento, `EMAIL_BACKEND=console` envia para o log do backend.

## API

- `GET /api/nf-saidas/{id}/envio-email/dados/` — preview (destinatário sugerido, anexos, último envio).
- `POST /api/nf-saidas/{id}/envio-email/enviar/` — envia e-mail (exige `confirmar_envio: true`).

## Regras

- Somente NF-e **autorizada** (homologação ou produção).
- Bloqueia NF-e **cancelada** ou **inutilizada**.
- Exige **XML autorizado** real e capacidade de gerar **DANFE PDF**.
- Em **homologação**, assunto deve conter indicação de HOMOLOGAÇÃO / sem valor fiscal.

## Deploy

```bash
docker compose exec backend python manage.py migrate
docker compose restart backend frontend
```
