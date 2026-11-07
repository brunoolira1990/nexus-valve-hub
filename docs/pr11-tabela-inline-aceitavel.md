HEAD 6630cff; painel 1615 l.
- PR11-A (editor por item, celula td L1305-1386): 82 linhas liquidas MAS 0 hooks limpos; acoplamento via dados.itens + updateItem por linha em celula td compartilhada (AsyncAutocomplete / AlocarEntradaParaVendaBlock / status / ignorado) => nao fatiavel.
- PR11-B (botao Informar + handler L1269-1299): ~31 linhas com updateItem no handler => nao limpa.
- Parte pura (helpers criarEquivalenciasIniciais / fatoresEquivalenciaDoProduto / totalMetrosComposicao / mapItemPayloadEquivalencia) JA saiu no EquivalenciaEntradaEditor.tsx L1-770.
- Call-sites de acoes.updateItem/upsertProdutoCache: L1191, L1193, L1244, L1251, L1260-1264, L1278-1290, L1327, L1333, L1395, L1412 + vincularItemPedido L174/L183/L186.
- Criterio que derruba: trocar acoplamento por acoplamento sem ganho = NAO extrair. A barra de ~15 linhas OU ~2-3 hooks limpos NAO e o ponto aqui; a trava de acoplamento manda.