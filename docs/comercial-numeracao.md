# Numeração comercial (Comercial 2.2.1)

## Pedido de Compra (referência)

- **Formato:** `PC-AAAAMMDD-NNNN`
- **Sequência:** por dia, com base na `data` do pedido
- **Padding:** 4 dígitos no sufixo
- **Implementação:** `pedido_compra_numero.alocar_numero_pedido_compra`, modelo `SequenciaPedidoCompra`

## Proposta

- **Formato:** `PROP-AAAAMMDD-NNNN` (mesmo estilo visual/lógico do PC)
- **Sequência:** por dia, com base na `data` da proposta
- **Geração:** backend quando `numero` vazio; número informado é preservado

## Pedido de Venda

- **Formato:** `PV-AAAAMMDD-NNNN`
- **Sequência:** por dia, com base na `data` do pedido
- **Conversão proposta → pedido:** sempre gera número **próprio** de PV; vínculo com a proposta fica em `proposta_id` / badge / link na UI — **não** embute `PROP-…` no número do pedido (descartado padrão `PV-{numero_proposta}`).

## Registros legados (compatibilidade)

Continuam válidos e exibidos sem migração agressiva:

| Exemplo | Origem |
|---------|--------|
| `PROP-000099`, `PV-000088` | Comercial 2.2 (hífen + sequência global) |
| `PROP42`, `PV7` | Comercial 2.2.1 intermediário (estilo CQ) |
| `LEGADO-XYZ` | Cadastro manual |

Novos registros sem número passam a usar apenas o padrão diário `PREFIXO-AAAAMMDD-NNNN`.

## Certificado de Qualidade (fase futura — não alterado nesta entrega)

Padrão **distinto** da numeração comercial de proposta/pedido:

- **Sigla:** `CQ`
- **Série** (quando aplicável)
- **Referência ao Pedido de Venda** (`PV-AAAAMMDD-NNNN`)
- **Sufixo/sequência** quando houver mais de um CQ para o mesmo pedido

Exemplo conceitual: `CQ-A-PV20260521-0003-01`

Requisitos:

- Evitar duplicidade para o mesmo pedido + série + sufixo
- Não confundir com numeração fiscal de NF-e
- Implementação atual de CQ permanece (`CQ{n}` / normalização em `qualidade` serializers)
