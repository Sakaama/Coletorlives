# Relatório — GabePeixe Kick / Campeonato Atual (Antigravity)

Data: 23/09/2026. Agente responsável: **Antigravity**.
Prioridade operacional imediata: GabePeixe → Kick → Campeonato Atual → Produzir cortes hoje.

## 1. Escopo e Realizações
- Campanha `config/campaigns/gabepeixe.json` atualizada com o novo regulamento:
  - Fonte restrita à Kick (`allowed_sources: ["Kick"]`).
  - Lives a partir de 01/09/2026 até encerramento do campeonato em 22/10/2026.
  - Obrigatórios: hashtag `#gabepeixe`, marcação do perfil oficial e LOWER abaixo do rosto.
  - Proibições e política de IA devidamente registradas para compliance do operador.
- Alertas visuais adicionados à interface sem quebrar o layout existente:
  - Banner permanente em `index.html` (`#vod-obligations`).
  - Avisos no modal de Pacote Editorial (`#editorial-obligations`).
  - Renderização das obrigações no painel de regras (`rules(c)`).
- Auditoria técnica profunda do pipeline Kick:
  - Identificada e documentada a coexistência de `any-dl` (resolução HLS) e `yt-dlp` (recorte preciso de intervalos).
  - Confirmado suporte a range downloads e Fast Scan para VODs longas.
  - Fallback de importação local mantido operacional para cenários de erro 404 na Kick.
- Testes automatizados adicionados:
  - `tests/test_gabepeixe_kick.py` (contrato, datas e restrição Kick no Collector).
  - `tests/test_gabepeixe_ui.cjs` (renderização dos alertas na interface).
- Validação completa:
  - Baseline antes: 263 Python / 22 JavaScript.
  - Suíte final: **266 Python aprovados (17,12s)** / **23 JavaScript aprovados (170ms)**.
  - Linter Ruff: zero erros.
  - Compileall e node --check: 100% aprovados.
  - Banco de dados de produção preservado (`vods: 2`, `candidates: 129`).

---

# Relatório A2 — Source Scanner YouTube (Refatoração Antigravity)

Data: 23/09/2026. Agente responsável: **Antigravity**.
Autorização: escolha da Opção 2 pelo operador ("Preserve os utilitários já implementados... Corrija A2 para obedecer à arquitetura definida: SOURCE DISCOVERY ≠ MEDIA IMPORT").

## 1. Entrega e Correção Arquitetural
- O módulo `miner/discovery.py` foi criado como serviço de descoberta pura e efêmera.
- O catálogo de vídeos descobertos NÃO é persistido no banco operacional SQLite (`vods`, `jobs`, etc.).
- A consulta a vídeos já existentes (`KNOWN`) é realizada por leitura estrita (`SELECT`) sem mutações de estado.
- Desacoplamento de `Collector.sync`: descoberta de YouTube não registra automaticamente VODs no banco.
- Contrato normalizado preservado: `source_id`, `platform`, `source_type`, `video_id`, `url`, `title`, `channel_id`, `channel_name`, `channel_url`, `upload_date`, `timestamp`, `duration`, `duration_formatted`, `live_status`, `playlist_id`, `playlist_title`, `playlist_position`, `status`, `status_reason`.
- Classificação por estados: `NEW`, `KNOWN`, `OUT_OF_PERIOD`, `NEEDS_REVIEW`, `UPCOMING`, `LIVE_NOW`.
- Interface: adicionada a aba [🔍 Descobrir no YouTube] na tela principal de importação, permitindo consultar canais/playlists com limite configurável (1 a 100, padrão 50) e selecionar os vídeos desejados com o botão explícito `[↓ Importar VOD]`.
- Importação: reutiliza diretamente o pipeline existente (`service.import_url` / `POST /api/import/url`), sem criar novos downloaders ou duplicar código.

## 2. Validação e Testes
- Baseline pré-refatoração: 253 testes Python / 21 JavaScript.
- Testes novos dedicados em `tests/test_source_scanner.py` comprovando:
  1. Discovery não cria VOD;
  2. Discovery não altera banco;
  3. KNOWN é identificado sem persistência;
  4. NEW continua sem persistência;
  5. OUT_OF_PERIOD;
  6. NEEDS_REVIEW;
  7. UPCOMING / LIVE_NOW;
  8. Importar exige ação explícita;
  9. Importar reutiliza pipeline existente;
  10. Discovery nunca baixa mídia;
  11. Contrato da API e catálogo funcionam;
  12. Campanhas existentes inalteradas.
- Teste de interface em `tests/test_discovery_ui.cjs`.
- Suíte final: **263 Python aprovados em 16,30s / 22 JavaScript aprovados**; Ruff, compileall e node --check aprovados com zero erros.
- Banco de dados de produção preservado (2 VODs, 129 candidatos intactos).

---

# A2 — Source Scanner mínimo YouTube

Data: 22/09/2026. Implementação autorizada pelo pedido "Continue A2".

A2 implementada e validada offline. A1 e B1 preservadas. A3, SRT e Semantic Reviewer não iniciados.

## Entrega

- Provider.discover aceita YouTube com listagem flat limitada a 100 entradas, sem baixar mídia.
- Campo de canal aceita nome, @handle, URL /channel/, /c/, /user/, /videos, /streams, /shorts e playlist HTTPS.
- Canal sem aba explícita usa /videos. Para lives arquivadas, informar /streams. Nenhuma identidade oficial foi inventada.
- Validação de catálogo separada de validate_url: importação/download de vídeo individual continua rejeitando canais e playlists.
- Quando a listagem não contém data, consulta metadados individuais, ainda sem mídia. Sem data confirmável, não inclui automaticamente e informa a quantidade.
- Período inclusivo aplicado pelo Collector; upload não é tratado como data comprovada da live. was_live ausente permanece desconhecido.
- Duplicatas são removidas por ID; catálogo vincula registros existentes sem substituir dados, anexos locais, decisões humanas ou estado concluído.
- Vídeos ao vivo/agendados e entradas privadas identificadas não entram no catálogo operacional.
- Configurações externas do yt-dlp são ignoradas somente nos novos comandos de listagem e na consulta de metadados do Provider, garantindo modo sem download. Caminho do Python, ambiente herdado e execução sem shell preservados.

## Uso

Em Campanhas / Remote: selecionar criador e YouTube; informar URL do canal com /streams (lives) ou /videos (uploads), ou URL da playlist; definir período; salvar; sincronizar. Mineração continua sendo uma ação separada.

## Validação

Baseline: 229 testes Python em 17.45s e 21 JavaScript. Final: 253 Python em 15.82s e 21 JavaScript aprovados; ruff, compileall e pip check aprovados. 24 testes novos cobrem validação, contrato de vídeo individual, comandos sem download, deduplicação, limites, datas, indisponibilidade, cancelamento e preservação integral de VOD concluída/aprovação. Testes usam armazenamento temporário e providers simulados.

Backup pré-edição: backups/a2-before-20260922/. Evidência: test-results/a2/pytest.xml e baseline.txt. Teste legado de fonte não suportada passou de YouTube para Local porque YouTube agora é suportado.

## Limitações e aceite operacional

Máximo de 100 entradas por sincronização, sem paginação histórica nesta versão mínima. A contagem é anterior ao filtro temporal e inclui entradas posteriormente descartadas. Não garante cobrir todo o período em canais grandes; incluir URLs antigas manualmente. Consultas adicionais de data podem levar minutos: não há promessa de sincronização em segundos. Cada comando tem timeout de 120s e a tarefa pode ser cancelada; no pior caso são uma listagem e até 100 consultas individuais. Erro de metadados deixa a entrada sem data para revisão manual. Catálogo não atualiza registros previamente importados, mesmo que a fonte altere título/duração.

Nenhuma sincronização real, mineração, download de mídia, reinício operacional ou migration foi executada. Não houve edição de campanhas, benchmark, ranking ou banco operacional. Aceite de integração com um canal oficial e medição de latência permanecem pendentes: URL oficial não consta dos registros. Fonte técnica consultada: https://github.com/yt-dlp/yt-dlp#usage-and-options

# Relatório A1 — João Pichau + Juninho Manella

Data: 22/09/2026. **A1 concluída; B1 preservada.**

**A1 utiliza o Campaign System atual como ponte operacional.
Não representa o Campaign Core V2 definitivo.**

## Baseline e arquivos

Baseline pré-edição: 212 testes Python passaram em 15,48 s; 19 JavaScript passaram.
Backup conferido em backups/a1-before-20260922/; manifesto e baseline em test-results/a1/.

Criados: config/campaigns/joaopichau.json, config/campaigns/juninhomanella.json,
tests/test_campaigns_a1.py e tests/test_campaigns_a1_ui.cjs.
Alterados: miner/rules.py, tests/test_brabox.py e docs/AI/{TASK,CODEX_REPORT,DECISIONS}.md.
O teste legado passou de igualdade do catálogo inteiro para inclusão das três
campanhas anteriores, preservando sua garantia ao permitir campanhas adicionais.
Nenhum JSON antigo foi editado. Nenhuma alteração no benchmark, ranking, detector,
editorial.py, Collector, importador, exportador, SQLite ou frontend.

## Inspeção direta e compatibilidade

load_campaigns lê todos os JSONs e valida formato do ID. Service.campaign valida
seleção; Service/import/metadata/eligibility e Collector.configure consomem fontes
permitidas. Diretórios/RAW derivam do ID; PREP lê vertical. API /api/state retorna
campanhas sem whitelist. static/app.js preenche seletor por Object.values; remote.js
faz o mesmo e usa fontes, aliases e datas como defaults. rules(c) já exibe notes,
hashtags, required_texts/visuals, source_channels, ai_policy e prohibitions.
Por isso não houve alteração na UI, no servidor ou nos exports.

O hardcode constatado em eligibility era uma mensagem de revisão de lives originais
citando Brabox, não uma trava de identidade por nome. Agora deriva de streamer,
com override original_live_review para registrar a participação em canais terceiros
no caso de João. Mensagem Brabox continua exatamente igual. Não há if por campanha.

A data mínima antes era sempre convertida por fromisoformat. Juninho não tem data
mínima informada: usar uma data fictícia seria incorreto. A alteração genérica aceita
null e acrescenta revisão humana; datas inválidas em texto continuam sendo tratadas
pelo mecanismo anterior. O loader não foi transformado em validador de schema: JSON
malformado/ID inválido continuam ValueError e ausência de ID continua KeyError.

Inspeção de Collector.view confirma que ordenação por score seguida de supressão
por overlap >=65% não verifica status. Um NOVO de score maior pode ocultar um
APROVADO sobreposto na visão agregada (registro permanece no banco). Isso não impede
cadastro/seleção das novas campanhas. Conforme escopo, nenhuma correção foi aplicada.

## Campos e classificação de regras

A) Dados necessários ao funcionamento atual:

- IDs joaopichau / juninhomanella; name, streamer, aliases, verified_channel_ids,
  allowed_sources, min_date/max_date, hashtags, required_texts/visuals, vertical.
- João: data mínima 2026-09-01, somente lives com participação ativa; plataformas
  de publicação Instagram/TikTok/YouTube. Participação não é comprovada por metadados.
- Juninho: data mínima null e revisão humana; foco nele, marcação do perfil oficial
  a confirmar; kick.com/juninhomanella no próprio vídeo, não só legenda/título.
  Não aplicar restrição de somente lives às suas fontes conhecidas.
- Preset PREP compatível: texto de João vazio (não há obrigação visual informada),
  de Juninho kick.com/juninhomanella; RAW permanece limpo. PREP não foi executado.

B) Informação aditiva, sem enforcement novo:

- source_channels contém descrições das fontes conhecidas, não URLs inventadas.
- allowed_sources é o recorte técnico: João YouTube/Kick/Twitch; Juninho YouTube/Kick.
  Isso não certifica fontes oficiais. Origem/participação precisam de revisão.
- Fontes Instagram/TikTok de Juninho e Kings League registradas; URLs diretas de
  Instagram/TikTok seguem rejeitadas pelo importador, arquivo local autorizado é
  alternativa já existente. URLs oficiais não foram pesquisadas nem presumidas.
- operational_requirements registra ingresso manual no WhatsApp; notes o torna visível.
- pinned_comment registra texto exato fornecido e required_until=2026-10-09;
  required_texts mostra instrução com data. Sem expiração automática ou fuso inventado.
- Proibições e ai_policy preservam o texto informado sobre IA, collab, repostagem,
  engajamento/views artificiais, volume, apostas e links não autorizados. Nenhum
  bloqueio técnico novo foi derivado de interpretação dessas regras.

C) Ainda dependente do Campaign Core V2/decisão humana:

- Evidência/versionamento e vigência por regra; confirmação de presença ativa/foco;
  verificação efetiva de menção, divulgação dentro do vídeo, comentário fixado e grupo.
- Cadastro confirmado de URLs/IDs/@ oficiais e período de Juninho.
- Proibições não são automaticamente verificadas. Revisão humana não certifica
  compatibilidade do fluxo com a regra sobre plataformas de IA.
- Não foram generalizadas observações como defaults Viewx. Registros informativos
  cabem no JSON; execução/auditoria dessas obrigações não cabe no mecanismo atual.

## Testes e resultado

17 casos novos Python: carregamento/contrato das cinco campanhas, data inclusiva de
João, participação ativa na orientação, bloqueio de não-live para João, Juninho
sem período inventado/nem restrição indevida a não-live, campos obrigatórios e
informativos, mensagem genérica para criador arbitrário, preservação da mensagem
Brabox, configuração inválida, campos opcionais, API e cadastro operacional isolado
sem jobs/VODs, fontes técnicas inalteradas e contratos antigos.
2 testes JS novos executam funções existentes de renderização de regras/defaults
remotos para ambas as campanhas, incluindo WhatsApp/IA/comentário/limites visuais.
Integração Flask feita com banco temporário; não usou dados operacionais.

Teste específico: 17 Python aprovados em 0,63 s e 2 JS aprovados. Uma primeira
execução sem basetemp terminou com WinError 5 na limpeza de temporários globais do
pytest; repetida com temporários isolados no projeto e saída zero. Não foi preciso
alterar permissões ou apagar arquivos do usuário.

Suíte final: **229 Python aprovados em 16,25 s; 21 JavaScript aprovados**.
Ruff global, compileall e sintaxe de app.js/remote.js aprovados.
Comparação adicional com rules.py do backup: **180 casos das três campanhas antigas
com resultados de eligibility idênticos**, variando fonte, data e was_live.
Evidências: test-results/a1/python-final.xml, legacy-equivalence.json e verification.json.

## Como usar, riscos e recomendação A2

Reiniciar normalmente o aplicativo e recarregar a página para ler os dois novos
JSONs. Selecionar João Pichau ou Juninho Manella no seletor existente. No Remote,
confirmar canal real, provider e período antes de salvar. Default de canal não
comprova identidade; João não recebeu alias oficial inventado. Período de Juninho
precisa ser preenchido pelo operador. O cabeçalho legado de regras não tem rótulo
específico para data mínima null; notes exibe explicitamente período não informado.
Nenhum servidor de produção foi reiniciado nesta tarefa.

Disponibilidade foi validada por API isolada e renderização JS dos controles,
sem iniciar importação/mineração/download. Não houve chamadas externas nem alteração
de dados, RAWs ou checkpoints de produção. Limitações de loaders, identidade e
revisão manual estão explicitadas acima; não há promessa de compliance automático.

A2 recomendada: Source Scanner mínimo de YouTube, após confirmar canais/URLs oficiais,
com descoberta somente de metadados, deduplicação incremental e testes com fixtures.
Não confundir upload com data da live ou inferir participação ativa apenas pelo canal.
**A2 não iniciada. Parar após A1.**

---

# Relatório B1 — Gold Set + benchmark editorial offline

Data: 22/09/2026. **B1 concluída.** O relatório histórico da auditoria permanece
integral abaixo. A revisão Antigravity foi aceita parcialmente pelo operador;
vale o roadmap dual-track descrito em TASK.md, com autorização exclusiva de B1.

## Baseline e preservação

Antes de editar qualquer fonte/documento: **148 Python passaram em 19,53 s;
19 JavaScript passaram**. Sem divergência do baseline solicitado.
Backup byte a byte dos documentos a editar em `backups/b1-before-20260922/`.
Baseline e manifesto SHA-256 em `test-results/b1/baseline.json` e
`source-before.json`. Nenhum arquivo funcional existente foi editado.

Criados:

- `miner/benchmark.py`: engine puro + CLI, somente biblioteca padrão.
- `tests/test_benchmark.py`: 64 casos de teste.
- `benchmarks/gold/schema.json`: contrato JSON versionado.
- `benchmarks/gold/README.md`: contrato, métricas oficiais, execução e limitações.
- `benchmarks/gold/samples/gold.json` e `predictions.json`: exemplo sintético de aceite.

Alterados: somente `docs/AI/TASK.md`, `CODEX_REPORT.md`, `DECISIONS.md`, preservando
o histórico. Registros auxiliares de teste em `test-results/b1/` e backup local
não integram o produto. PRODUCT_SPEC e ANTIGRAVITY_REVIEW foram preservados.

## Gold Set e estratégia

Gold Set e editorial_feedback são fontes distintas. O contrato independente
do SQLite exige schema_version=1 e gold_cuts; cada entrada tem gold_id, vod_id,
campaign_id, creator, expected_start, expected_end e would_clip=true. Content_type,
priority, notes e metadata são opcionais. IDs únicos, tempos finitos não negativos
em segundos absolutos e fim > início são validados. Predictions têm prediction_id,
vod_id, campaign_id, start/end e metadata opcional. Não houve anotação automática
nem promoção de decisões existentes a gold. Nenhuma mídia ou credencial foi adicionada.

O motor cria um grafo bipartido por identidade exata de campanha/VOD e threshold
inclusivo de IoU (padrão 0,50). Fluxo máximo de custo mínimo com Bellman-Ford na
rede residual permite desfazer matches anteriores. A ordem dos objetivos é:
máximo número de pares válidos; máxima soma de IoU; mínima soma de boundary MAE;
menor conjunto lexicográfico de pares de IDs. Frações exatas preservam comparação
de limiares e custos; bits por aresta resolvem o desempate final. Greedy foi
descartado porque pode perder um match em grafos ambíguos. A entrada não é modificada.

## Definição oficial das métricas

I=max(0,min(ge,pe)−max(gs,ps)); U=(ge−gs)+(pe−ps)−I; IoU=I/U.
Erros de início/fim são abs(gs−ps) e abs(ge−pe), em segundos; MAE do par é a
média desses erros. Com G golds, P predictions e M matches:

- gold_count=G; prediction_count=P; matched_count=M.
- recall=M/G; precision=M/P; false_positive_count=P−M; false_negative_count=G−M.
- mean_temporal_iou, mean_start_error, mean_end_error, boundary_mae: médias nos M matches.
- boundary_start/end/both_within_tolerance_rate: fração dos M matches com erro(s)
  <= tolerância, padrão 3 s. Essa tolerância não afeta a detecção do match.
- precision_at_k (3, 5, 10): número de matches ótimos no prefixo recebido / min(K,P).
  Cada prefixo é rematcheado independentemente, sem alterar o ranking recebido.
  Predictions tardias não retiram acertos da primeira página.
- Divisões por zero e médias/taxas sem matches retornam null; não NaN ou 100% artificial.

Relatório inclui configuração, pares, interseção/união/erros individuais, IDs
não pareados, ordem recebida e denominadores Top-K para auditoria. Metadata pode
ser filtrada por igualdade (AND), preservando ordem, sem inferir prioridade A.
Gold permanece completo após filtro, e input_prediction_count informa o total
anterior. Publicable/approval rate exige julgamento humano e não é calculado
como se fosse precisão temporal. Detalhes normativos em `benchmarks/gold/README.md`.

## Testes e resultado de aceite

64 testes novos cobrem match perfeito/ausente; threshold exato/abaixo; erros de
início/fim; duplicatas de intervalo e IDs; competição em ambos os lados;
cardinalidade ótima em caso ambíguo; desempates por IoU/MAE/ID; permutações;
precision/recall/FP/FN/boundaries; Top-3/5/10 e prefixos menores; conjuntos vazios;
timestamps/contratos/configurações inválidos; campanha/VOD distintas; filtros;
ausência de mutação; exemplo de aceite e CLI offline/read-only. Um oráculo
independente enumera todas as associações possíveis de 35 casos pequenos
reproduzíveis e confere os quatro objetivos do matching. CLI também executada
sem site-packages em diretório isolado, sem a infraestrutura do produto.

Exemplo solicitado: humano 01:10–01:55; prediction 01:12–01:53:

| Resultado | Valor |
|---|---|
| Encontrado / matches | Sim / 1 |
| Interseção / união | 41 s / 45 s |
| IoU | 0,9111111111 |
| Erro início / fim / MAE | 2 s / 2 s / 2 s |
| Recall / precision | 1 / 1 |
| Boundaries dentro de 3 s | Ambos |
| Precision@3 / @5 / @10 | 1 / 1 / 1; denominador 1 |

Resultado CLI em `test-results/b1/acceptance.json`. Medição pontual, incluindo
início do processo: 0,0851 s para esse único par sintético; não é previsão de
escala nem melhoria comprovada do Miner. Não houve mineração ou teste de VOD real.

Validação final: **212 Python passaram em 15,35 s (148 existentes + 64 novos);
19 JavaScript passaram**. Ruff global, compileall, sintaxe de static/app.js e
pip check aprovados. Relatório JUnit: `test-results/b1/python-final.xml`.

## Riscos conhecidos e encerramento

Gold incompleto pode contabilizar bons cortes não anotados como FP. É preciso
mesmo escopo e anotação humana adequada para interpretar qualidade editorial.
Este benchmark mede localização temporal, não narrativa, direitos ou publicabilidade.
Somente fixtures sintéticas foram entregues; não existe nova avaliação humana real.
Matching foi projetado para golds pequenos: O(M×V×E), mais O(G×P) para construir
arestas; frações e desempate por bits têm custo adicional. Top-K repete o cálculo
nos prefixos. Não foi validado para milhões de candidatos.

Não houve APIs, LLM, FFmpeg, SQLite, Flask ou mudanças na produção pelo módulo.
Não foram alterados ranking, detector, group_refined, UI, campanhas, export ou
pipeline. **Parar em B1. Trilha A e B2 não iniciadas.**

---

# Histórico — Auditoria inicial — TUTUCO CLIP MINER V2

Data: 22/09/2026. Projeto: `D:\Projetos\TUTUCO-CLIP-MINER`. Autor: Codex. Escopo: leitura, baseline, diagnóstico e planejamento. **Nenhum código funcional, campanha, ranking, migration ou pipeline foi alterado.**

## 1. Conclusão executiva

A base existente deve ser reaproveitada. Flask/Waitress, SQLite, executor serial, importação local, ferramentas públicas de aquisição, chunks, checkpoints, previews e RAW já atendem grande parte da infraestrutura. A V2 exige principalmente contratos de avaliação/proveniência, aferição humana da qualidade, revisão semântica e limites narrativos, pacote de corte e regras de campanha mais estruturadas. Não há evidência que justifique trocar framework, banco ou reconstruir o pipeline.

O revisor em `miner/editorial.py` é uma heurística de relações por regex e proximidade temporal. Não equivale ao Semantic Reviewer da especificação. Os subscores têm constantes derivadas de padrões, não calibração estatística; score 90 não significa 90% de probabilidade de publicação. Não existe hoje evidência de atingir >=80% de aprovação na prioridade A.

Recomendação de ordem: **fundação do Gold Set antes de alterar julgamento editorial**, Campaign Core compatível, contratos/eventos, reviewer textual seletivo, limites narrativos com reavaliação, Clip Package, ampliação de fontes e só depois multimodal/Viewx/personalização/central. O roadmap completo e a primeira tarefa proposta estão em `TASK.md`. Nada dele foi implementado nesta auditoria.

## 2. Baseline executado nesta tarefa

| Verificação | Resultado |
|---|---|
| Python, suíte completa | **148 aprovados em 14,18 s** |
| JavaScript, todos os `tests/*.cjs` | **19 aprovados** |
| Ruff (`ruff check .`) | Aprovado |
| Compileall (`app.py miner scripts`) | Aprovado |
| Sintaxe `static/app.js` e `static/remote.js` | Aprovada |
| `pip check` no .venv | Sem dependências quebradas |
| SQLite `PRAGMA integrity_check`, conexão somente leitura | `ok` |

Comandos usados na raiz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=test-results/v2-audit-20260922/pytest
node --test tests/*.cjs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q app.py miner scripts
node --check static/app.js
node --check static/remote.js
.\.venv\Scripts\python.exe -m pip check
```

Os 143 Python da entrega anterior não são o baseline atual: há cinco testes posteriores para `group_refined`, e sua tolerância padrão agora é **3,0 segundos**, configurável. O modo estrito de 0,5 segundo também é testado. Essas alterações preexistiam e foram preservadas. `EDITORIAL.md` descreve a versão histórica de 0,5 s; não foi reescrito nesta tarefa. Para estado observado, prevalece esta auditoria; para intenção futura, `PRODUCT_SPEC.md`.

As integrações automatizadas executam mídia sintética curta/FFmpeg e usam providers/modelos simulados quando apropriado. Nenhuma VOD real foi baixada, transcrita ou minerada aqui. Scripts opcionais `smoke_remote`, `smoke_youtube`, `smoke_transcription`, `benchmark_gpu`, `benchmark_long_vod` e `benchmark_editorial` não foram executados. O último pode escrever avaliações no banco operacional, portanto não é uma auditoria somente leitura.

Evidências em `test-results/v2-audit-20260922/`: `baseline.json`, `source-before.json`, `data-before.json`, `verification.json` e fixtures em `pytest/`. O manifesto registra SHA-256 de 66 arquivos preexistentes de código/configuração/testes/scripts/documentos da raiz. O snapshot lógico registra as oito tabelas, não é um backup completo de mídias. Como não houve alteração funcional nem escrita de banco, não foi necessário criar outro backup de todas as VODs. Antes da próxima implementação, aplicar o protocolo de backup adequado à alteração.

## 3. Inventário e arquitetura atual

Não há diretório `.git` nesta raiz; a conferência usa manifesto de arquivos, não um diff Git. Não foram encontrados AGENTS.md na raiz ou nos diretórios pais consultados.

| Área / arquivos analisados | Responsabilidade e pontos de integração |
|---|---|
| `app.py`, `iniciar.bat`, `pick_file.py`, `miner/instance.py` | API Flask, Waitress loopback, token/origem local, seletor nativo, .venv e trava de instância |
| `miner/service.py` | `Service`: campanhas, importação, fila serial, transcrição local, persistência/reanálise, preview/RAW/PREP |
| `miner/store.py` | `Store`: conexões SQLite/WAL/FKs, registros JSON, lookup e histórico de candidatos/exports |
| `miner/collector.py` | `Collector`: campanha operacional, descoberta incremental, fila remota, aprovação, pacote manual, corte remoto e ranking agregado |
| `miner/rules.py`, `config/campaigns/{gabepeixe,brkk,brabox}.json` | Regras/presets legados, URL, elegibilidade de VOD e indícios por trecho |
| `miner/analysis.py`, `miner/performance.py` | Energia RMS, Whisper com chunks de 300 s, cache por modelo, fallback CPU, reuso do modelo durante a operação e timers |
| `miner/vod_mining.py` | Candidate Finder e filtro heurístico: tags, contexto, penalizações, agrupamento, modos e score bruto |
| `miner/visual_activity.py` | Pares de frames de baixa resolução a cada 20 s, bônus visual limitado; sem reconhecimento semântico |
| `miner/long_vod.py` | Fast Scan por 600 s, regiões por células de 60 s, sondagem, aprofundamento seletivo, offsets absolutos, dedup global e checkpoint |
| `miner/remote_analysis.py`, `miner/remote_temp.py` | Adaptador `RemoteSource`, ranges/chunks, leases, checkpoint antes de limpeza e reserva de espaço |
| `miner/remote_provider.py`, `miner/range_download.py`, `miner/ytdlp_cli.py` | Ferramentas públicas any-dl/yt-dlp; caminhos remoto e legado; Python do .venv, cwd definido e ambiente herdado |
| `miner/editorial.py` | `relations`, `review`, `cached_segments`, `review_vod`, `group_refined`: sugestões e agrupamento visual sem apagar registros |
| `miner/media.py`, `miner/preview_cache.py` | FFmpeg/ffprobe, arquivos parciais, cache leve e RAW/PREP separados |
| `miner/errors.py` | Apresentação específica de `kick:vod` + `HTTP Error 404` com importação local, sem reescrever diagnóstico persistido |
| `miner/maintenance.py`, `scripts/reset_operations.py` | Backup/reset de desenvolvimento; legado a revisar antes de uso com o schema atual; não executado |
| `templates/index.html`, `static/app.js`, `static/remote.js`, `static/style.css` | Biblioteca/VOD/Remote, filtros, shortlist, player, seleção múltipla, pacote e regras; JS sem framework adicional |
| `tests/`, `pyproject.toml`, requirements | Suite Python parametrizada, integrações FFmpeg e testes JS; dependências fixadas e lint |
| `scripts/benchmark_*`, `scripts/smoke_*` | Benchmarks/transportes opcionais; separados da suíte rotineira |
| README, TESTES, EDITORIAL, VOD-GARIMPO, REMOTE-COLLECTOR, DIAGNOSTICO-YTDLP | Histórico, resultados medidos e limitações; não presumir que todo resultado histórico descreve o código atual |

### Fluxo local

`import_local` referencia o original sem copiá-lo; `import_url` obtém metadados e o download integral é uma ação explícita da V1. `analyze` usa o caminho curto até 1800 s ou `long_vod.run` acima disso/por opção. `analysis.detect` é o detector de `vod_mining`; atividade visual reordena candidatos existentes. `save_analysis` arquiva gerações antigas, reutiliza ID/status em limites coincidentes e preserva pacote manual; em seguida chama `editorial.review_vod`.

API de detalhe chama `group_refined` na lista retornada. A interface filtra recomendados/bons, mantendo classes restantes consultáveis. Aprovação/descarte grava status e snapshot. Export local usa pacote manual → sugestão → original, exige aprovação para RAW/PREP e mantém os resultados separados do original. PREP lê o RAW já produzido e aplica o preset legado; a V2 não precisa removê-lo nem estendê-lo para edição automática.

### Fluxo remoto

`configure` cadastra uma execução/campanha operacional: criador existente, um provider/canal e período. `sync/register` consulta metadados, canonicaliza identidade, associa VOD e mantém estado concluído. Kick/Twitch têm descoberta via any-dl limitada a 100; YouTube entra por URL individual. `mine` ignora CONCLUÍDO/BLOQUEADO, utiliza o mesmo executor da V1 e adapta `long_vod.run` com `RemoteSource`.

O Fast Scan remoto percorre chunks em qualidade baixa; não mantém VOD integral permanentemente. Sondagem/aprofundamento podem baixar de novo ranges sobrepostos, pois o vídeo do scan é descartado após checkpoint. JSON/transcrições ficam persistidos; timestamps locais recebem offset absoluto. `save_analysis` integra o mesmo revisor. Preview pede variante leve, RAW aprovado tenta 1080p60; a opção de melhor qualidade é explícita. RAW remoto vai a `TUTUCO-TV/04_RAW/<CRIADOR>/`; RAW local legado fica sob `data/campaigns/<campanha>/raw/<vod>/`. Preservar ambos os caminhos.

## 4. Banco e dados observados — leitura, sem migrations

| Tabela | Estrutura relevante | Registros no início |
|---|---|---:|
| vods | id, campaign, source_key, created, data JSON | 2 |
| candidates | id, vod_id FK, start/end absolutos, score bruto, status, data JSON | 129 |
| jobs | VOD, kind/state/progress/message | 17 |
| exports | candidate_id/VOD FKs, kind/path/start/end/created | 24 |
| editorial_feedback | candidato FK, status, note, snapshot JSON, created | 11 |
| remote_campaigns | id e data JSON operacional | 5 |
| remote_vods | relação execução/VOD, PK composta | 6 |
| remote_jobs | execução, payload JSON, status/progresso/cancelamento | 19 |

Estado dos candidatos: 10 APROVADO, 119 NOVO. Eventos de feedback: 10 APROVADO e 1 DESCARTADO. Exports: 19 previews e 5 RAWs. Não há tarefa FILA/EXECUTANDO no snapshot. Esses são estados/eventos diferentes: não deduzir uma taxa de aprovação de 10/11, nem inferir que houve publicação ou que todos os 129 foram avaliados.

As tabelas base nascem em `Store.__init__`; as três remotas em `Collector.__init__`. Há `CREATE TABLE IF NOT EXISTS`, mas não há migration runner/versionamento incremental: `PRAGMA user_version=0`. Dados extensíveis estão em JSON, incluindo análises, `editorial_review`, `editorial_package`, métricas, origem e estado remoto. `source_key` tem índice, não restrição UNIQUE. A fila serial reduz concorrência pesada, mas rotas HTTP podem escrever simultaneamente.

`editorial_feedback` guarda um snapshot **anterior** à atualização de status; a coluna `status` representa a nova decisão. O snapshot contém scores e VOD ID; campanha/criador requerem vínculo à VOD e não constituem snapshot independente do regulamento. `Collector.package` sobrescreve o pacote atual sem emitir evento específico de alteração de início/fim/título. Nenhum consumidor usa feedback para modificar ranking.

## 5. Gap analysis por componente da especificação

Legenda: estado descreve o que existe; ação é recomendação futura, não alteração feita.

| Componente V2 | Estado | Evidência atual e lacuna concreta | Ação |
|---|---|---|---|
| Aplicativo local / infraestrutura | EXISTE | `app.create_app`, `Service`, `Store`, executor único, interface e ferramentas instaladas | DEVE SER REAPROVEITADO |
| Aquisição local/VOD/ranges | EXISTE | `import_local`, `Provider.download`, `RemoteSource.acquire`; sem downloader próprio | DEVE SER REAPROVEITADO; não unificar caminhos por estética |
| Fonte/catalogação incremental ampla | EXISTE PARCIALMENTE | `Collector.sync` Kick/Twitch; YouTube só URL; `validate_url` rejeita canal/playlist | DEVE SER ESTENDIDO com catálogo separado da aquisição |
| Candidate Finder e filtro barato | EXISTE | `vod_mining.detect/group_windows`, `long_vod.promising`; três modos e sem quota | DEVE SER REAPROVEITADO; aferir recall antes de aumentar filtros |
| Revisor editorial determinístico | EXISTE | `editorial.relations/review/review_vod`; padrões e evidências locais | DEVE SER REAPROVEITADO como baseline/fallback identificado, não como prova semântica |
| Semantic Reviewer | NÃO EXISTE | Não há modelo/provider semântico, publicaria SIM/TALVEZ/NÃO, coerência/progressão/originalidade ou confiança calibrada | DEVE SER CRIADO como etapa/contrato opcional sobre finalistas |
| Segundo julgamento crítico | NÃO EXISTE | Uma avaliação heurística; nenhum mecanismo de divergência | Avaliar experimento futuro, não criar infraestrutura agora |
| Independência de contexto | EXISTE PARCIALMENTE | `detect` penaliza alguns pronomes; `review` lê -40/+15 s; não resolve referentes/assuntos | DEVE SER ESTENDIDO com contexto progressivo limitado e abstenção |
| Smart Boundaries | EXISTE PARCIALMENTE | `review` já guarda original/suggested; padding de 2/4 s e extensão de segmento não identificam fronteira de assunto | DEVE SER ESTENDIDO na mesma estrutura; não criar um segundo início/fim concorrente |
| Tipos editoriais | EXISTE PARCIALMENTE | Tipos heurísticos PT, como COMPETITIVO/BASTIDOR/TALKING; visual layout também usa `type` | DEVE SER ESTENDIDO com taxonomia versionada; separar tipo de layout; preservar leitura legada |
| Classificação A/B/C/REJEITADO | EXISTE PARCIALMENTE | RECOMENDADO/BOM/TALVEZ/FRACO e filtros existem; não são equivalentes calibrados a A/B/C | DEVE SER ESTENDIDO sem migrar nomes cegamente |
| Ranking explicável | EXISTE PARCIALMENTE | Score bruto, visual e `editorial_review.editorial_score`; motivos/evidências, vários subscores constantes | DEVE SER ESTENDIDO com proveniência, confiança separada e ausência explícita de evidência |
| Deduplicação | EXISTE | `group_windows`, `dedup_segments`, `Collector.view` por overlap e `group_refined` por limites | DEVE SER REAPROVEITADO e protegido; sem dedup semântica geral |
| Shortlist sem quota | EXISTE | `remoteFiltered` e `renderCandidates`, classes e consulta dos registros | DEVE SER REAPROVEITADO; não impor top-N como quota editorial |
| Preview leve/cacheado | EXISTE | `PreviewCache`, API imediata por VOD/range, lote seletivo, expiração segura | DEVE SER REAPROVEITADO; avaliar paridade do player local/remoto |
| RAW limpo e aprovação | EXISTE | `Service.export` / `Collector.export`, FFmpeg; RAW sem título renderizado | DEVE SER REAPROVEITADO |
| Título/alternativas validados | EXISTE PARCIALMENTE | Título genérico por regra + uma citação; pacote manual editável | DEVE SER ESTENDIDO para 2 alternativas e validação promessa/conteúdo |
| Tarja vermelha de prévia do título | NÃO EXISTE como componente V2 | Cards têm texto forte; não há preview de arte branco/bold sobre faixa vermelha | DEVE SER CRIADO somente na UI, sem alterar RAW |
| Transcrição / SRT / pacote exportável | EXISTE PARCIALMENTE | JSON/TXT de transcrição por modelo/região; RAW remoto tem sidecar limitado; nenhum SRT/ASS por corte | DEVE SER ESTENDIDO; SRT e manifest de pacote novos, reutilizando transcrição e exports |
| Atividade visual | EXISTE | `visual_activity.sample/rank`, 160×90 gray, pares a cada 20 s | DEVE SER REAPROVEITADO como sinal barato, sem inferir objetos/direitos |
| Compreensão multimodal | NÃO EXISTE | Nenhum reconhecimento de clutch/placar/face ou reviewer de frames | DEVE SER CRIADO futuramente, seletivo e medido |
| Decisão/feedback humano | EXISTE PARCIALMENTE | `editorial_feedback`, rotas de revisão, note opcional; sem motivos rápidos/eventos de cada edição | DEVE SER ESTENDIDO preservando eventos legados |
| Perfil editorial/aprendizado | NÃO EXISTE | Histórico persistido sem consumidor estatístico ou modelo | DEVE SER CRIADO só após amostra adequada; não inferir de 11 eventos |
| Gold Set / qualidade editorial | NÃO EXISTE como avaliação robusta | Benchmark BRKK relata 129 scores e 2 exemplos; sem anotações completas, holdout ou métricas de publicação | DEVE SER CRIADO antes de alterar reviewer; script legado é evidência histórica |
| Campanhas orientadas a dados | EXISTE PARCIALMENTE | Três JSONs, presets, datas/fontes, required_texts/visuals; validador mínimo | DEVE SER ESTENDIDO por adaptador/schema, preservando IDs |
| Compliance genérico/evidência | EXISTE PARCIALMENTE | `eligibility` VOD e `candidate_eligibility`; regras extensas exibidas como texto | DEVE SER ESTENDIDO com escopo, evidência, severidade, validade e confirmação |
| Viewx defaults e importador/Radar | NÃO EXISTE | Sem provider de regulamentos, evidência/versões ou descoberta Viewx | DEVE SER CRIADO após Campaign Core; defaults nunca presumidos |
| Central multi-campanha | EXISTE PARCIALMENTE | Biblioteca e ranking por campanha operacional; nenhuma fila global editorial | DEVE SER ESTENDIDO depois dos contratos e catálogo |
| Controle de produção | EXISTE PARCIALMENTE | NOVO/APROVADO/DESCARTADO, jobs e exports; sem EDITADO/publicação por plataforma | DEVE SER ESTENDIDO com eventos manuais; sem postagem |
| Protocolo entre agentes | CRIADO NESTA AUDITORIA | Cinco arquivos `docs/AI/`; Antigravity vazio | Usar no próximo handoff; não implica colaboração de escrita simultânea |

## 6. Campaign Core: compatibilidade e casos reais

`load_campaigns` valida apenas o formato do ID e lê JSON; não valida um schema completo. `eligibility` cobre plataforma, data/live/upload, canal excluído exato, autoria não verificada e regra de lives originais. `channel_aliases`/URLs de origem ajudam a configuração, mas não comprovam participação ativa. O texto de revisão de `original_lives_only` ainda menciona Brabox diretamente: há um acoplamento a tornar parametrizável numa fase autorizada, não justificativa para refazer o motor inteiro.

Proposta de contrato: identidade da campanha separada de criador e execuções operacionais; coleção de fontes autorizadas; coleção de regras com ID, escopo (fonte/trecho/edição/publicação/operação), condição, vigência, severidade BLOCKING/WARNING, avaliação automática/manual, evidência, confiança e confirmação. AUTOMATIC é mecanismo, não gravidade. Datas de conteúdo, período de campanha e validade temporária de regra devem ser distintos. Armazenar fuso quando conhecido; não inventá-lo.

| Caso informado pelo operador | Dados que o modelo deverá representar | Verificação/pendência |
|---|---|---|
| João Pichau | #joaopichau; fontes Pichau ou participação ativa; conteúdo desde 01/09/2026; Instagram/TikTok/YouTube; grupo obrigatório | Participação ativa é evidência por trecho e revisão humana, não simples comparação do nome do canal |
| João, comentário temporário | Texto exato: “Evento Pichau Arena, o maior evento gamer do Sul do Brasil, de 10 a 12 de outubro em Joinville - SC”; obrigatório até 09/10/2026 | Escopo publicação/comentário fixado, vigência própria; confirmar evidência oficial e fuso antes de ativar |
| Juninho Manella | #juninhomanella; perfil oficial a confirmar; foco no criador; múltiplas fontes; grupo obrigatório | URL `kick.com/juninhomanella` exigida no vídeo, não satisfazê-la só em título/legenda; confirmar lista real de fontes/@ |
| GabePeixe | Regras atuais, lower/asset obrigatório | `vertical.asset` existe, mas atual é null/placeholder; não certificar asset oficial ausente |
| BRKK | Período/fontes atuais e exclusão de origem Cinefy | Palavra Cinefy em promoção não bloqueia VOD; indício protegido só pede revisão de trecho |
| BRABOX | Lives originais, fontes, proibições, restrição informada sobre IA e período divergente | Preservar revisão humana para divergência; não pressupor que decisão humana por si certifica conformidade |

Esses casos são requisitos do Product Spec, não validação externa de regras atuais. Não houve consulta a regulamentos, cadastro de João/Juninho nem criação de defaults Viewx. Regras oficiais e preferência interna por cortes visuais ficarão em namespaces distintos. A UI futura deve distinguir regra conhecida, evidência observada, pendência humana e ação de publicação ainda não realizada.

## 7. Dívida técnica relevante e riscos priorizados

Achados de inspeção são explicitados como tal. Não foram corrigidos, pois a tarefa proíbe alteração funcional.

| Prioridade | Local / evidência | Impacto no roadmap e encaminhamento |
|---|---|---|
| Alta | `editorial.review`: subscore constante por presença de padrão, ligação temporal não causal | Falsa precisão, falsos positivos e títulos apoiados em ASR ruim; Gold Set e abstenção antes de introduzir prioridade A |
| Alta | `analysis.transcribe` persiste só start/end/text; `detect` procura avg_logprob/no_speech_prob que o produtor não guarda | Penalização de baixa confiança raramente tem evidência real; estender contrato de transcrição/qualidade sem invalidar cache antigo silenciosamente |
| Alta | `cached_segments` escolhe `result.json` de maior mtime, não chave explícita da geração ativa | Mudança de janela/fonte pode vincular contexto de análise diferente; testar e persistir identidade da análise/transcrição antes de reviewer V2 |
| Alta | Cache curto de energia/transcrição aceita arquivo existente; não carrega fingerprint da mídia/configuração completa | Substituir arquivo no mesmo caminho ou anexar fonte diferente pode reutilizar texto antigo; criar testes de proveniência antes de expandir reprocessamento |
| Alta | `Store`/`Collector` criam schema no construtor e `user_version=0` | Necessário plano de migration aditiva e rollback antes de alterar schema; não simplesmente recriar banco |
| Alta | `maintenance.reset` conhece quatro tabelas antigas e só checa jobs locais; não remove relações remote_vods/editorial_feedback | Com FKs atuais, pode falhar ao apagar candidatos/VOD. Transação tende a reverter antes de apagar arquivos; não afirmar perda observada. Reproduzir só em fixture e corrigir em tarefa própria antes de usar reset |
| Média/alta | `Collector.view` remove candidatos por overlap original >=65% antes de group_refined, sem respeitar decisão nesse filtro | Um candidato aprovado pode ficar fora da visão agregada, embora continue no banco/VOD. Cobrir com teste dedicado antes de tornar central global; não confundir com a proteção de decisões em group_refined |
| Média/alta | `Collector.package` não gera evento de edição; feedback tem snapshot anterior ao novo status | Não permite reconstruir todas as escolhas de título/limites nem treinamento confiável; eventos versionados, sem sobrescrever história |
| Média | `save_analysis`: arquiva/regrava seleção e depois faz revisão em outra etapa/transação | Falha do reviewer pode deixar candidatos brutos válidos e job em erro; definir estado independente/retry da avaliação; não apagar candidatos por falha externa |
| Média | `group_refined` compara limites com tolerância 3 s, sem semântica; ignora aprovados/pacotes | Protege decisão humana, mas pode manter redundância intencional ou juntar sugestões de narrativas distintas; preservar atual e avaliar com pares negativos, não ampliar tolerância sem benchmark |
| Média | Duas rotas de export/preview (`Service` e `Collector`) com diretórios, margens, cache e retorno distintos | Futuro SRT/metadata precisa contrato compartilhado do corte final, não supor mesma semântica em todos os caminhos |
| Média | Preview compartilhado pode pertencer a outro candidate_id; a API Remote retorna diretamente, player do fluxo VOD procura exports do próprio ID | Risco de tarefa concluída sem abrir player naquele caminho quando arquivo foi reutilizado do vizinho; reproduzir em fixture/browser isolado antes de corrigir |
| Média | Namespaces de score: `score`, `editorial_score` visual anterior e `editorial_review.editorial_score` | UI/subscores podem exibir valores com sentidos diferentes; tipar/versionar avaliação, não renomear dados antigos em massa |
| Média | `Store.candidates` consulta exports por candidato; frontend Remote faz polling a cada 3 s | Escala multi-campanha aumenta consultas/render; medir antes de propor consulta em lote/paginação, não trocar SQLite |
| Média | `Service.__init__`/`Collector.__init__` marcam jobs interrompidos e fazem limpeza | Scripts de inspeção não devem instanciar serviços na produção. Esta auditoria usou sqlite3 somente leitura |
| Média | `benchmark_editorial` grava avaliações na produção, lê RAW inteiro para hash e usa dois IDs de referência | Não é Gold Set genérico nem isolado; criar avaliador offline novo, reutilizar relatório histórico e evitar carregar RAW grande na RAM |
| Média | Metadados de regras sem versão/evidência, autorizações específicas e confirmação por regra | Score/compliance não auditáveis historicamente; introduzir snapshots de regras aplicadas por candidato/pacote |
| Baixa operacional | Documentos históricos divergentes, sem repositório Git nesta pasta | Manifestos protegem esta auditoria; sugerir versionamento/backup em tarefa aprovada, sem executar agora |

## 8. Performance, custo e recuperação

**Local/CPU:** executor de uma tarefa pesada por vez; Whisper Base/int8 em CPU por padrão, threads limitadas a 8 na construção principal. O host informa 12 CPUs lógicas. `performance.model` mantém até duas instâncias por sessão (incluindo fallback), sem cache global indefinido. O remoto força CPU. Não houve nova medição de throughput/inferência nesta auditoria.

**GPU:** o caminho local oferece CUDA/int8_float16 com fallback; o histórico registra GTX 1650/4 GB e falha de DLL. Não foi retestado CUDA nesta tarefa, portanto não há promessa de aceleração atual. Não recomendar GPU/modelo maior antes de medir qualidade e pico de memória.

**Memória:** vídeo não é carregado integralmente; WAV é lido por blocos e frames são pequenos. Ainda há listas globais de energia/segmentos e leitura de transcrições; `cached_segments` reconstrói contexto por VOD. Pico de RSS/VRAM não foi medido. Para LLM local, orçamento de RAM/VRAM/modelo é uma decisão futura, não requisito para a fundação do benchmark.

**Disco:** `data` observado ~0,088 GiB/3111 arquivos e `models` ~0,138 GiB/9 arquivos; não incluem RAW externo em TUTUCO-TV, backups ou fixtures. PCM mono 16 kHz/16 bit custa ~115,2 MB/h por cópia, ~1,38 GB para 12 h; caminho local pode manter chunks/provas adicionais. Remoto usa leases e descarta mídia própria após checkpoint; preview expira após 14 dias sem uso, sem teto global de bytes. RAW nunca deve participar dessa limpeza.

**VOD longa:** 12 h representam 72 scans de 10 min, até 144 sondagens de 30 s por passo de 5 min antes de considerar cobertura, e aproximadamente 4320 extrações de frames (pares a cada 20 s). São estimativas derivadas da configuração, não tempos medidos. Spawn/seek de FFmpeg em cada frame pode dominar parte do custo visual. O scan remoto é baixo custo relativo, mas ainda precisa transferir chunks ao longo da VOD; não é descoberta de eventos apenas por metadados.

**Seletividade/recall:** há gate de áudio em `promising`, variação visual/energética e filtro remoto de fração audível. A sondagem cobre trechos curtos e espaçados; pode perder uma história calma entre sondagens ou gameplay silencioso. Um Semantic Reviewer posterior não recupera o que nunca virou candidato. Medir recall num intervalo humano completamente anotado antes de tornar o gate mais restritivo.

**Rede:** descoberta e mídia dependem das ferramentas instaladas/plataformas. Ranges até 900 s, ferramenta com timeout, tentativas e cancelamento da árvore própria. Ranges de aprofundamento/contexto podem repetir downloads já descartados; transcrição concluída evita repetição. Não há chamada LLM atual, nem custo por token. A auditoria não realizou chamadas a plataformas.

**Cache/checkpoint:** manter camadas separadas: identidade de mídia → scan → plano → transcrição → avaliação → preview/export. Pipeline longo já possui fingerprint/chave, planos por configuração/modelo, checkpoints por região e offsets absolutos. Futuros cache keys semânticos devem incluir hash do texto/contexto, versão de prompt/contrato/modelo/configuração e regras relevantes. Não invalidar download/transcrição porque mudou título ou ranking.

**Futuro LLM:** calcular custo = finalistas × tokens médios × tarifas de entrada/saída × passagens, com contagem de cache misses. Nenhuma tarifa/modelo foi escolhida; sem orçamento numérico inventado. Limitar contexto, concorrência, tentativas e gasto por execução; persistir resultado válido por candidato. Conteúdo de VOD/transcrição é dado não confiável, não instrução para ferramentas. Exigir JSON validado, evidências, abstenção, metadados de custo e consentimento/configuração antes de envio externo.

**Multimodal futuro:** selecionar frames só de finalistas com incerteza visual, limitar bytes/frames/resolução e medir ganho por tipo. Movimento atual não identifica partida, rosto, placar nem conteúdo protegido. Não enviar vídeo de horas a um modelo por padrão.

**Tempos históricos, não reexecutados:** BRKK teve ~13,02 h acumuladas no registro, das quais ~10,14 h de transcrição; revisão dos 129 levou ~7,51 s e cache ~0,77 s; previews A/B ~11,99/~9,69 s, cache ~0,07 s. Métricas são inclusivas em várias etapas: não somar timers aninhados nem atribuir todo custo da transcrição a load do modelo. A nova arquitetura precisa medir tempo de parede, CPU/RSS, bytes baixados, cache hits e tempo humano de revisão, além dos timers existentes.

## 9. Qualidade editorial: como avaliar sem falsa conclusão

Classes atuais persistidas continuam 4 RECOMENDADO, 9 BOM, 115 TALVEZ, 1 FRACO. O benchmark anterior destacou exemplos A/B com scores 90/89. Isso demonstra comportamento do algoritmo, não qualidade generalizável. Os dados humanos atuais não são um Gold Set completo nem amostra aleatória.

Proposta de métricas:

- Publicable Cut Rate A: decisões humanas de “publicaria” entre os A efetivamente avaliados, com tamanho da amostra e intervalo de incerteza. Não contar pendentes como aprovação/rejeição. Registrar se foi aprovado como proposto ou só após edição substantiva.
- Precision da shortlist: momentos distintos considerados publicáveis entre todos os momentos avaliados na amostra; deduplicação não pode inflar resultado.
- Recall editorial: cortes humanos encontrados / cortes humanos anotados em intervalos completos, usando pareamento temporal 1:1 e tolerância definida antes do teste. Duas referências positivas não permitem estimar recall da VOD inteira.
- Boundary accuracy: erro de início e fim separadamente, percentual dentro da tolerância humana e necessidade de acrescentar contexto. Duração correta não comprova início absoluto correto; `Provider.download` declara obtained_start/end desconhecidos.
- Falsos positivos por motivo/tipo/criador; candidatos por hora; tempo de processamento; bytes/custo por aprovado; tempo humano de revisão por corte utilizável.

Separar conjuntos de calibração e avaliação por fonte/VOD, evitando que vizinhos da mesma história apareçam nos dois. Não usar exemplos A/B como exceções. Conservar casos negativos: grito sem contexto, música com ASR alucinada, opinião incompleta, narrativa boa sem payoff, visual silencioso, falas com pronomes, mudança de assunto e duplicatas quase iguais. A meta >=80% para prioridade A é gate futuro com amostra suficiente, não número já atingido.

## 10. Cobertura existente e testes futuros necessários

`test_miner`, `test_brabox`, `test_ytdlp_cli`, `test_kick_errors` cobrem fundação, campanhas, mídia, API, preservação, ambiente e fallback. `test_vod_mining` cobre dinâmica, cluster, três modos, penalizações e histórico. `test_visual_activity` cobre sinal/cache/FFmpeg. `test_long_vod` cobre 12 h simuladas, chunk/cauda, offsets, resumo global, retry/cache e CPU fallback. `test_remote` cobre descoberta incremental, elegibilidade por trecho, temporários, cancelamento, ranking, revisão, pacote, RAW/PREP e API. `test_editorial` cobre relações heurísticas, limites, cache, decisões/feedback e agrupamento 3 s/0,5 s. JS cobre filtros, shortlist sem quota, controles, avisos e agrupamento.

Esses testes são regressões valiosas. Não medem retenção, viralidade, conhecimento de contexto ou promessa do título. Testes recomendados para próximas tarefas: contrato/proveniência de cache; troca de fonte/modelo/janela sem reuso indevido; revisor externo inválido/timeout; rejeição de candidato heurístico forte; título sustentado por evidência; SRT no tempo final; ajustes humanos registrados; aprovado não ocultado pela dedup agregada; reset com FKs novas em fixture; campanhas com regra temporária; sugestão maliciosa na transcrição; eventos visualmente bons sem fala. Não foram adicionados nesta tarefa.

## 11. Alterações, preservação e handoff

Criados apenas como entregáveis principais:

1. `docs/AI/PRODUCT_SPEC.md` — prompt integral com nota de escopo e distinção entre intenção futura/estado observado.
2. `docs/AI/TASK.md` — plano, aceite, status, roadmap proposto e primeira tarefa pequena.
3. `docs/AI/CODEX_REPORT.md` — este diagnóstico.
4. `docs/AI/ANTIGRAVITY_REVIEW.md` — template vazio, sem parecer inventado.
5. `docs/AI/DECISIONS.md` — restrições confirmadas, fatos preservados e propostas não aprovadas.

Artefatos auxiliares: `test-results/v2-audit-20260922/` com manifests/snapshot/baseline/verificação e fixtures de testes; caches usuais de Python/pytest/Ruff podem ter sido atualizados. Nenhum arquivo funcional ou configuração existente foi editado. Nenhum serviço operacional foi instanciado para auditar o banco; nenhuma fila, aprovação, export, regra ou mídia de produção foi modificada pela auditoria. A conferência final está em `verification.json`.

A primeira tarefa recomendada é a fundação do benchmark offline definida em TASK, não implementar automaticamente a próxima fase. Antigravity ainda precisa revisar riscos, contratos e ordem. Questões abertas: conjunto humano/holdout, critérios de publicação com ou sem ajuste, orçamento/privacidade de eventual API semântica, tolerância de limites, evidência oficial dos regulamentos e ativos/@ pendentes.

**Encerramento: aguardando revisão externa e nova tarefa. Sem implementação V2, nova mineração longa ou Live Mode.**
