# Importação TIPI/NCM

## Prévia a partir de Downloads

```bash
./scripts/importar_tipi_downloads.sh
```

## Prévia com arquivo específico

```bash
./scripts/importar_tipi_downloads.sh ~/Downloads/TIPI.pdf
```

## Importar após validar prévia

```bash
./scripts/importar_tipi_downloads.sh ~/Downloads/TIPI.pdf --importar
```

## Importar com desativação de ausentes

```bash
./scripts/importar_tipi_downloads.sh ~/Downloads/TIPI.xlsx --importar --desativar-ausentes
```

## Preferência

Use XLSX oficial quando disponível.  
PDF é aceito, mas recomenda-se sempre validar com dry-run primeiro.
