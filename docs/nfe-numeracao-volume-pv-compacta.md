# Numeração compacta do Pedido de Venda nos volumes da NF-e (ERP 4.0.14.x)

## Convenção operacional aprovada

| Origem | Resultado |
|--------|-----------|
| `PedidoVenda.numero` no formato `PV-AAAAMMDD-NNNN` | `AAMMDD-NNNN` |
| Exemplo `PV-20260714-0042` | `260714-0042` |

- Aceita **somente** o formato exato completo.
- Valida que ano/mês/dia formam uma data civil válida.
- Pedidos legados ou incompletos **não** geram valor inventado.
- Faturamentos parciais do mesmo PV podem repetir a mesma referência (sem remessa).

## Onde aplica

1. Na **criação** do rascunho NF-e via `gerar_nfe_saida_from_faturamento()`.
2. Campo persistido: `NFeSaida.numeracao_volumes`.
3. XML: `transp` → `vol` → **`nVol`** (truncate defensivo em 60 caracteres).
4. DANFE BrazilFiscalReport: lê o valor do XML (sem alteração no BFR).

## Regras de preenchimento

- Preenche **uma única vez** se o campo estiver vazio e o PV for válido.
- Não sobrescreve valor manual nem rascunho reaberto.
- Retry/idempotência (`ja_existia`) não recalcula.
- Com `modFrete=9`, o grupo `vol` continua omitido do XML; o valor pode permanecer no rascunho.

## Helper

- Backend: `apps.fiscal.nfe_numeracao_volume_pv.compactar_numero_pedido_venda`
- Frontend (ajuda de UI): `src/lib/nfeNumeracaoVolumePv.ts`
