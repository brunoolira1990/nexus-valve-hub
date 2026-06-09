# Motor central de relatórios PDF (Nexus)

**O motor de relatórios PDF é independente do motor fiscal/DANFE.**

- PDFs gerenciais/operacionais: `apps.relatorios` + adaptadores por módulo (ex.: `apps.financeiro.relatorios_pdf`).
- DANFE e documentos fiscais: `apps.fiscal` (BrazilFiscalReport) — não importar daqui.

## Extensão futura

1. Montar `ReportDefinition` (título, filtros, colunas, linhas, métricas).
2. Chamar `ReportExportService().export_pdf(defn)`.
3. Expor rota `GET .../pdf/` com os mesmos filtros da tela JSON.
4. Registrar módulo em documentação (`fiscal`, `comercial`, `estoque`, etc.).

Módulos previstos: Fiscal, Compras, Comercial, Estoque, Produtos, Qualidade, Cadastros, Financeiro avançado, Contábil.
