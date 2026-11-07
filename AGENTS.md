# Regras universais - nexus-valve-hub (Fase 2 e alem)

PROTOCOLO (NAO viole):
1. DISCO > DECLARACAO. Antes de assumir qualquer linha, localize no disco atual. Se divergir do
   enunciado/relatorio, priorize o disco e DECLARE. NUNCA confie em numero de linha de msg antiga.
2. NAO corrija erros TypeScript baseline de carona. O repo tem ~770 erros TS pre-existentes
   (dezenas em RegrasFiscaisEntradaTab.tsx por intersecao de tipo colapsada em never via
   icms_st_aplicavel, + os do painel, + modal de devolucao :144, etc.). Meta de tsc: NAO adicionar
   erro, manter <= 770.
3. FRONTEND (tsc + vitest): rode no HOST, NAO no container (container subconta tsc em 4 = artefato
   de typings; 766 container = 770 host). Medicao de tsc SEMPRE:
   cd frontend; npx tsc --noEmit -p tsconfig.app.json 2>&1 | Out-File ..\tsc.log -Encoding utf8;
   cd ..; (Select-String tsc.log -Pattern "error TS\d+:").Count
   (o redirect > do PS5.1 corrompe stderr; use Out-File -Encoding utf8).
4. BACKEND (manage.py): container apenas para makemigrations/testes Python.
5. Prompt = texto. Leia os arquivos do disco. NAO use log/print colado como fonte de verdade.
6. NAO faca deploy. NAO commite nem faca push sem o PO mandar explicitamente. Producao fica fora.
7. Leia arquivos GRANDES em FAIXAS (grep primeiro, depois linhas especificas). NAO carregue o
   painel inteiro de uma vez (contexto do modelo local e limitado).
8. WARNINGS BENIGNOS - ignore, NAO bloqueie por eles: no vitest aparecem "React Router Future Flag
   Warning" (v7_startTransition, v7_relativeSplatPath), "act(...)", e CORS do jsdom. Sao ruido, nao
   falha. Motivo literal das docs oficiais: v7_startTransition so exige mudanca se houver React.lazy
   DENTRO de componente (mover pro module scope; "You don't need to update anything unless you are
   using React.lazy inside of a component"); v7_relativeSplatPath so se houver rota splat
   multi-segmento tipo dashboard/* com Link relativo (dividir Route + ".."); act() e utilitario de
   teste ("To prepare a component for assertions, wrap the code rendering it and performing updates
   inside an act() call"; o warning nao e erro). Nenhum dos casos se aplica a este repo hoje. O
   veredito que importa e a linha "Tests N passed" + o numero do tsc no host, NAO a ausencia de stderr.
9. ANTI-AUTODECLARACAO: nunca diga "verde" sem colar SAIDA BRUTA do comando. O PO valida no host;
   sua palavra so nao basta (modelo local pode errar a conferencia - ja queimou 3x na Fase 2).

CONTEXTO VOLATIL (reconfirme no disco; NAO grave numero na memoria):
- Painel alvo: frontend/src/components/fiscal/NFeEntradaConferenciaPanel.tsx (1615 l. no HEAD 6630cff).
- Store (NAO altere): frontend/src/hooks/useConferenciaStore.ts.
- Doc de mapeamento: docs/mapeamento-estado-interno-conferencia.md.
- Wrappers extraidos e INTOCAVEIS: ReaberturaEntradaBloco, DevolucaoEntradaBloco,
  FinanceiroEntradaBloco, EstoqueEntradaBloco, EquivalenciaEntradaBloco.
- Rede de testes: reconfirme rodando a suite (hoje ~50: formShell 15 + reaberturaAcoes 2 + cada
  wrapper + store 5 + equivalencia 7). NAO assuma contagem fixa.
- Rail UnifiedEntradaFeed, Chatter, FormShell, StatusPipeline: NAO tocar.

FLUXO DA FASE 2 (referencia): PO da alvo -> Tech Lead FASE 0 (leitura/medicao) -> PO aprova ->
Dev Frontend FASE 1 (escrita+gates) -> Tech Lead REVISAR -> PO valida gates no HOST -> PO manda
COMMIT -> Dev Frontend faz git. TRAVAS: (1) nunca pule aprovacao do PO entre FASE 0 e FASE 1;
(2) FASE 1 de bloco que TOCA tabela/updateItem so depois do PO confirmar browser do estoque
(aplicar ok + forcar erro no aplicar -> rodape descongela); (3) nunca COMMIT sem o PO colar as
saidas brutas dos gates no host; (4) nunca deploy, nunca git --force.