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

Use apenas placeholders no `.env.example`. Valores reais ficam no `.env` do servidor (nunca commitar senha ou host de produção).

O Django lê as variáveis em `backend/nexus_erp/settings.py` na inicialização do backend. Após alterar o `.env`, recrie ou reinicie o container:

```bash
docker compose up -d --force-recreate backend
# ou
docker compose restart backend
```

| Variável | Descrição |
|----------|-----------|
| `EMAIL_BACKEND` | Ex.: `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Servidor SMTP (ex.: `mail.example.com`) |
| `EMAIL_PORT` | Porta (ex.: `25` sem TLS, `587` com STARTTLS) |
| `EMAIL_HOST_USER` | Usuário SMTP |
| `EMAIL_HOST_PASSWORD` | Senha SMTP |
| `EMAIL_USE_TLS` | `true` / `false` (STARTTLS) |
| `EMAIL_USE_SSL` | `true` / `false` (SSL implícito) |
| `DEFAULT_FROM_EMAIL` | Remetente padrão (fallback: `EMAIL_HOST_USER`) |
| `NEXUS_EMAIL_OPERACIONAL` | Remetente do envio DANFE/XML (fallback: `DEFAULT_FROM_EMAIL`) |

Verificar carga das variáveis:

```bash
docker compose exec backend python manage.py shell -c "
from django.conf import settings
print('EMAIL_HOST=', settings.EMAIL_HOST)
print('EMAIL_PORT=', settings.EMAIL_PORT)
print('PASSWORD_SET=', bool(settings.EMAIL_HOST_PASSWORD))
"
```

Em desenvolvimento local, pode usar `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` para logar no stdout do backend em vez de enviar SMTP real.

## API

- `GET /api/nf-saidas/{id}/envio-email/dados/` — preview (destinatário sugerido, anexos, último envio).
- `POST /api/nf-saidas/{id}/envio-email/enviar/` — envia e-mail (exige `confirmar_envio: true`).

### Pré-preenchimento do destinatário

O campo **Para** do modal é preenchido automaticamente com a sugestão retornada pelo endpoint de dados. A sugestão é **somente leitura do cadastro** — o usuário pode apagar, editar ou substituir antes de enviar.

Prioridade da sugestão (campos do cadastro `Cliente`):

1. `email_nf` — e-mail fiscal / NF-e
2. `email` — e-mail principal do cliente
3. vazio — com aviso discreto: *"Cliente sem e-mail cadastrado. Informe o destinatário manualmente."*

O último envio registrado (`ultimo_envio`) permanece apenas como histórico; não substitui a sugestão do cadastro ao abrir o modal.

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
