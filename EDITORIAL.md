# Revisor editorial — validação de 21/09/2026

## Baseline e proteção

126 testes Python (11,91 s), 16 JavaScript, Ruff e sintaxe aprovados antes das alterações. Backup de código e SQLite: `backups/editorial-before-20260921-102213/`. Evidência: `test-results/editorial-baseline.json`.

As duas VODs BRKK somam 21,64 h e já tinham 129 candidatos. Foram reutilizados esses registros e as transcrições. Não houve nova mineração integral. A primeira continua PARCIAL; a segunda CONCLUÍDO. Campos originais, decisões, pacotes manuais e RAW/PREP foram preservados, incluindo comparação de bytes dos arquivos existentes. SQLite: integrity_check=ok.

## Arquivos da atualização

Novos: `miner/editorial.py`, `miner/performance.py`, `miner/preview_cache.py`, `tests/test_editorial.py`, `tests/test_editorial_ui.cjs`, `scripts/benchmark_editorial.py`, este documento.

Alterados: `app.py`, `miner/analysis.py`, `miner/collector.py`, `miner/long_vod.py`, `miner/remote_analysis.py`, `miner/remote_provider.py`, `miner/service.py`, `miner/store.py`, `static/app.js`, `static/remote.js`, `templates/index.html`, `README.md`, `TESTES.md`.

Relatórios: `test-results/editorial-baseline.json`, `editorial-benchmark.json`, `editorial-final.json`, `editorial-whisper/report.json`.

## Arquitetura e método

O pipeline existente recebe uma etapa após salvar candidatos brutos: transcrição/cache → relações editoriais → sugestões persistidas em `data.editorial_review` → shortlist → preview leve → decisão humana → RAW aprovado.

O revisor usa regras relacionais locais: premissa + conquista, responsabilidade + obstáculo, desvantagem + virada, resultado + causa, opinião + argumento, revelação + desenvolvimento, tentativa + resultado, abertura + revelação e vídeo assistido + reação. Exige proximidade temporal e âncora no candidato; não pontua uma lista solta de palavras. Ainda é um conjunto limitado de padrões linguísticos, não compreensão semântica geral nem avaliação por LLM. Não há exceções por ID, canal ou timestamp no algoritmo; os IDs dos exemplos aparecem apenas no script de benchmark.

Registra score, classe, tipo, hook/story/visual/context/payoff/editability/standalone, evidências, motivo, títulos, layout, dificuldade e limites originais/refinados. Payoff não é obrigatório. O peso visual é moderado e o score bruto tem pouca influência. Sem núcleo confiável, mantém o intervalo original. Com núcleo, inclui contexto e termina a fala; prefere pelo menos 20 segundos, sem teto rígido de 60 segundos. As sugestões humanas salvas prevalecem.

A tabela aditiva `editorial_feedback` registra candidato, decisão, observação, snapshot e data. Não há treinamento. A revisão reutiliza assinatura de versão/dados e não substitui aprovações ou pacotes manuais.

## Resultado real e duplicação refinada

| Classificação | Registros |
|---|---:|
| RECOMENDADO | 4 |
| BOM | 9 |
| TALVEZ | 115 |
| FRACO | 1 |

Total: 129. Os 13 registros recomendados/bons representam **12 intervalos distintos** na shortlist padrão. Não existe quota.

Dois candidatos vizinhos usaram o mesmo contexto e sugeriram exatamente 07:20:09,780–07:20:43,780. A correção agrupa apenas sugestões da mesma VOD cujo início e fim diferem até 0,5 segundo. O maior score representa o grupo, com referência aos horários dos demais originais. É uma transformação de apresentação: não apaga, funde nem altera registros no banco. Todos e os filtros de classe mantêm cada candidato disponível. Candidatos com decisões humanas, pacote manual ou arquivados não são ocultados por esse agrupamento. A deduplicação bruta existente não foi alterada.

| Exemplo | Score antigo → editorial | Posição entre 129 | Posição do momento na shortlist | Sugestão |
|---|---|---:|---:|---|
| A: pouca experiência/final | 68 → 90, RECOMENDADO | 2 | 1, agrupado com vizinho de score 91 | 07:20:09,780–07:20:43,780 (34 s) |
| B: armador/dificuldade | 67 → 89, RECOMENDADO | 3 | 2 | 12:25:02–12:25:22 (20 s) |

Os limites sugeridos diferem das referências humanas e precisam ser ouvidos. A transcrição de A contém “R2 anos de fio”; B contém “não tinha a causa”, em vez de comunicação/call. Títulos alternativos citados podem reproduzir erros. Nenhuma promessa de que esses 12 momentos sejam todos bons cortes.

## Preview e cache

Previews remotos pedem variantes leves 360p/480p, com fallback para variante inferior conhecida. Se a ferramenta não comprovar variante leve, o app recusa baixar qualidade desconhecida/alta para preview. Não baixa 1080p60 para revisão. Render de revisão em 640×360; RAW continua separado, exige aprovação e tenta 1080p60.

`Preparar previews leves da shortlist` inicia a preparação automática do lote recomendado/bom, omitindo duplicados refinados e descartados. Não inicia sozinho ao abrir a campanha. Preview individual continua disponível para qualquer classe. Limites manuais têm prioridade sobre os sugeridos; margens do RAW não aumentam o preview da shortlist.

Cache em `data/preview_cache`: reaproveitado pela VOD/intervalo inclusive entre candidatos vizinhos. A API devolve o arquivo imediatamente quando já existe, sem criar tarefa. Limpeza após 14 dias sem uso verifica marcador de propriedade, caminho e registros exclusivamente de preview. Não percorre importações/RAW/PREP; mantém registros históricos de exports e regenera previews expirados quando solicitados.

| Teste real | Primeira geração | Reutilização | Arquivo |
|---|---:|---:|---|
| A, 34 s | 11,989 s | 0,066 s | 640×360, 30 fps, 2.528.624 bytes |
| B, 20 s | 9,691 s | 0,069 s | 640×360, ~29,90 fps, 1.538.555 bytes |

Somente 54 segundos de preview foram gerados no teste real; não houve novo RAW nem VOD integral. No navegador, o grupo A reutilizou o export 13 criado para seu vizinho.

## Performance medida

Revisão dos 129 candidatos: 4,418 + 3,093 = **7,511 s**. Segunda passagem com cache: 0,494 + 0,278 = **0,772 s**.

Nos previews, ferramenta remota: A 10,283 s/B 8,528 s; codificação leve: A 1,619 s/B 1,074 s. Consulta/reprodução via API cacheada validada sem fila/download.

Whisper Base/CPU real: duas inferências do mesmo áudio curto em diretórios distintos, numa sessão, total **3,104 s**, carregamento **0,859 s**, sem segundo carregamento. Reuso limitado à operação/modelo/dispositivo; sessão termina e libera as referências. Fallback CPU separado preservado.

Métricas antigas persistidas somam 13,02 h de processamento e 10,14 h de transcrição (~78% do total). O baseline humano era aproximadamente 12 h; usamos os valores gravados quando disponíveis. O carregamento antigo não era medido separadamente. O antigo visual=0 não prova custo zero: faltava instrumentação remota.

Agora são registrados descoberta, ferramenta remota, scan, áudio, energia, visual, sondagem, Whisper load, transcrição, análise profunda, deduplicação/ranking, revisor e preview. Tempos de etapas aninhadas são inclusivos; não devem ser somados como se fossem exclusivos.

Novos planos evitam análise profunda em regiões com fala/áudio sustentado insuficiente. Sondagem aceita relações editoriais mesmo sem payoff. Planos/checkpoints existentes continuam reaproveitados. **Não foi medido ganho de ponta a ponta nas 21,6 h**, nem garantida retenção de todo momento bom em áudio baixo. Esse teste longo exige autorização futura.

## Validação final

**143 Python em 14,59 s; 19 JavaScript; Ruff, compileall e sintaxe dos dois scripts aprovados.** Os testes anteriores continuam passando, incluindo GabePeixe, BRKK, BRABOX, importação local, elegibilidade, checkpoints, RAW/PREP e fallback Kick.

Novos testes cobrem relações, ausência de payoff, negação, palavras isoladas, contexto distante, ausência de quota, limites refinados, decisões/pacotes/feedback preservados, cache de revisão, cancelamento, preview real via FFmpeg, limpeza e proteção de RAW, variante leve, reuso Whisper, lote seletivo, API cacheada sem fila, agrupamento refinado sem perda de registros e isolamento entre VODs/ajustes humanos. Browser: filtros, pacote sugerido e player cacheado.

Comandos executados (na raiz):

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=test-results/editorial-final-3
node --test tests/*.cjs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q app.py miner scripts
node --check static/app.js
node --check static/remote.js
```

## Limitações e próximo passo

Regras relacionais podem ligar falas próximas sem ligação real, falhar com ironia e deixar bons trechos em TALVEZ. Movimento não comprova gameplay, qualidade, direitos ou composição de câmera. Não existe reconhecimento visual. O agrupamento corrige intervalos praticamente iguais, não identifica toda paráfrase/evento semelhante. O feedback guarda dados para uso futuro, sem aprendizagem automática.

Layout é uma recomendação para edição manual; o renderer PREP legado não foi redesenhado. Nenhum render vertical final, legendas finais, publicação ou Live Mode foi acrescentado. Dependências pesadas não foram instaladas.

Próximo passo recomendado: avaliar manualmente os 12 momentos, registrar motivos e corrigir limites/títulos antes de considerar outro processamento longo. Medir precisão editorial e retenção com essa avaliação; não foi implementada outra etapa.

## Como testar sem mineração

1. Abra `http://127.0.0.1:8765/`, atualize a página e entre em **Campanhas / Remote**.
2. Selecione BRKK, 15/09/2026–20/09/2026. Existem entradas com o mesmo nome; a usada neste benchmark é a última das três, ID `993ac85955514c4d`, identificada por **2 VODs / 21,6 h / 129 candidatos**.
3. A shortlist padrão mostra 12 cards; o resumo por classe conta os 129 registros. Se quiser testar o revisor novamente, use **Revisar candidatos existentes (cache)**. Isso reaproveita texto; não use **Garimpar pendentes / Continuar** nesta validação.
4. Confira o grupo do exemplo A em primeiro e B em segundo. No grupo A aparece o original 07:20:37–07:21:15. **Todos — incluindo fracos** mostra os 129, inclusive o original de A com score 90 e o aviso de agrupamento.
5. Clique **Preview** nos exemplos. Os arquivos já estão cacheados; feche e abra de novo. Para os demais, **Preparar previews leves da shortlist** gera só o lote útil e reutiliza os existentes.
6. Abra **Pacote editorial**. Ouça e corrija título, hook e início/fim se necessário. Horários aceitam segundos ou HH:MM:SS; o ajuste humano salvo prevalece sobre a sugestão.
7. Informe feedback opcional e use **Aprovar/Descartar**, individualmente ou na seleção. Nenhuma decisão foi tomada pelo agente nos candidatos reais.
8. Após sua revisão, selecione aprovados, ajuste margens e use **Baixar aprovados**. Deixe desmarcada a opção de melhor qualidade para exigir 1080p60; se indisponível, o app informa e oferece o fallback explícito. Destino: `TUTUCO-TV/04_RAW/BRKK/`.
