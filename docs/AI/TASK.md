# Tarefa atual — GabePeixe Kick / Campeonato Atual (concluída pelo Antigravity)

Data: 23/09/2026. Responsável pela implementação: **Antigravity**.
Prioridade operacional imediata: GabePeixe → Kick → Campeonato Atual → Produzir cortes hoje.

- **Fonte Operacional Exclusiva:** GabePeixe configurado estritamente para `allowed_sources: ["Kick"]` (YouTube não é fonte primária desta campanha).
- **Regulamento Novo Registrado em `config/campaigns/gabepeixe.json`:**
  - Conteúdo elegível: lives a partir de 01/09/2026 (`min_date: "2026-09-01"`).
  - Janela de contagem/publicação do campeonato: 22/09/2026 às 14:00 até 22/10/2026 às 23:59 (`max_date: "2026-10-22"`).
  - Ranking final: 24/10/2026 às 12:00.
  - Hashtag obrigatória: `#gabepeixe`.
  - Menção obrigatória: Marcar o perfil oficial do GabePeixe na postagem.
  - Elemento visual obrigatório: LOWER oficial do GabePeixe posicionado abaixo do rosto no corte final (`required_visuals: ["LOWER (gabepeixe) abaixo do rosto"]`).
  - Compliance e proibições: compra de engajamento, collabs entre participantes, repost de outros participantes, spam de volume para visualizações vazias e automação 100% IA sem curadoria humana.
- **Alertas ao Operador na Interface:**
  - Banner permanente em destaque na visualização da VOD (`#vod-obligations`) e nas regras da campanha:
    `⚠ LOWER OBRIGATÓRIO (abaixo do rosto do Gabe) · ⚠ #gabepeixe · ⚠ MARCAR PERFIL OFICIAL`
  - Apresentação em destaque dentro do formulário de Pacote Editorial (`#editorial-dialog` / `#editorial-obligations`).
- **Auditoria Técnica do Pipeline Kick:**
  - `any-dl` + `yt-dlp`: `any-dl` consulta metadados e obtém a URL direta da playlist HLS master (`sourceUrl`).
  - `yt-dlp` realiza o download de intervalos/ranges delimitados (`--download-sections *start-end --force-keyframes-at-cuts`) diretamente da stream HLS, sem necessidade de baixar a VOD completa.
  - VODs longas utilizam Fast Scan em fatias leves de 600s para decupagem preliminar de áudio e visual.
  - Fallback preservado: caso ocorra erro 404 em `[kick:vod]`, o sistema orienta e permite a importação de arquivo local sem perda do registro ou dados.
- **Validação e Testes:**
  - Baseline antes: 263 Python / 22 JavaScript.
  - Testes Python novos em `tests/test_gabepeixe_kick.py` (+3 testes) e teste JS em `tests/test_gabepeixe_ui.cjs` (+1 teste).
  - Suíte final: **266 testes Python aprovados (17,12s)** e **23 testes JavaScript aprovados (170ms)**.
  - Ruff, compileall e node --check aprovados com zero erros e zero warnings.
  - Banco de produção mantido 100% intacto (2 VODs, 129 candidatos).
  - Nenhuma chamada externa ou download real de horas de VOD foi executado.

---

# Tarefa atual — A2 Source Scanner YouTube (concluída pelo Antigravity)

Data: 23/09/2026. Responsável pela implementação: **Antigravity**.
Autorização: pedido do operador "Continue A2 no Antigravity" com Opção 2 aprovada.

**A2 desacopla formalmente SOURCE DISCOVERY de MEDIA IMPORT.**
- Baseline antes da refatoração de A2: 253 Python (testes prévios de utilitários) e 21 JavaScript.
- Backup pré-edição em `backups/a2-refactor-20260923/`.
- Utilitários mantidos: `youtube_source`, `youtube_row`, `discovery_args` e parsing leve com `--flat-playlist --skip-download --dump-single-json`.
- Correção arquitetural implementada:
  1. Criação do módulo puro `miner/discovery.py` com `discover_source`, normalização estrita de contrato e classificação de status (`NEW`, `KNOWN`, `OUT_OF_PERIOD`, `NEEDS_REVIEW`, `UPCOMING`, `LIVE_NOW`).
  2. Descoberta é 100% efêmera: zero gravações no banco SQLite (`vods`, `jobs`, etc.), zero downloads de mídia.
  3. `Collector.sync` desacoplado de auto-registro para YouTube.
  4. Adicionado método `Service.discover` e endpoint `POST /api/discover`.
  5. UI enriquecida na aba de importação com [🔍 Descobrir no YouTube], formulário de busca com limite configurável (1 a 100, default 50), renderização de catálogo com badges e botão explícito `[↓ Importar VOD]`.
  6. Importação explícita reutiliza o pipeline existente (`service.import_url`) sem duplicar downloader.
  7. Cobertura estrita comprovando todos os 12 requisitos mandatórios em `tests/test_source_scanner.py` e teste de renderização em `tests/test_discovery_ui.cjs`.
- Suíte final: **263 Python aprovados (16,30s) / 22 JavaScript aprovados**; Ruff, compileall e node --check verdes.
- Zero migrações de banco, zero downloads reais, zero chamadas à internet durante os testes.

**A2 concluída. Não iniciar A3 nem B2.**

---

# Tarefa atual — A2 implementada; validação offline concluída

22/09/2026. Pedido "Continue A2" autoriza esta fase e substitui a parada de A1 abaixo. Descoberta YouTube de canais/playlists integrada ao Remote, somente metadados, 100 entradas por sincronização, filtro temporal e preservação dos registros existentes. Final: 253 Python / 21 JS aprovados. Detalhes e limitações em CODEX_REPORT.md. Aceite real com URL oficial ainda pendente; não houve mineração ou download. A3/B2 não iniciados.

---

# Tarefa atual — A1 campanhas operacionais (concluída)

Data: 22/09/2026. B1 aceita pelo operador. Somente A1 autorizada e implementada.

**A1 utiliza o Campaign System atual como ponte operacional.
Não representa o Campaign Core V2 definitivo.**

- Baseline antes das edições: 212 Python (15,48 s), 19 JavaScript.
- Backup de rules.py, teste BRABOX e três documentos em backups/a1-before-20260922/.
- Criadas campanhas joaopichau e juninhomanella, com regras fornecidas pelo operador.
- Generalizada mensagem de revisão de lives; data mínima null exige revisão humana.
- UI existente deriva as opções das configurações; nenhuma alteração visual.
- Validado Collector.view por inspeção: dedup >=65% pode ocultar aprovado de menor
  score; não impede cadastro, não foi alterado nesta tarefa.
- 17 testes Python e 2 JS novos; final: 229 Python / 21 JS aprovados, lint e sintaxe aprovados.
- 180 casos de elegibilidade das campanhas antigas equivalentes ao código anterior.
- Sem mineração, download, chamada externa, migration, mudança no benchmark ou ranking.

IDs oficiais de canais e perfis não foram inventados. Período de Juninho não foi
informado; selecionar período operacional manualmente. Reiniciar normalmente o
aplicativo para carregar os novos JSONs e recarregar a página. Nenhum processo
operacional foi reiniciado automaticamente nesta tarefa.

**A1 encerrada. Não iniciar A2, SRT ou Semantic Reviewer.**

---

# Tarefa atual — B1 Gold Set + benchmark offline (concluída)

Data: 22/09/2026. A autorização do operador após a revisão parcial do Antigravity
substitui a ordem proposta na auditoria abaixo. **Somente B1 foi implementada.**

Roadmap autorizado em duas trilhas:

- A1: João Pichau + Juninho Manella nas campanhas existentes; A2: Source Scanner
  mínimo YouTube; A3: Clip Package RAW + SRT + transcript + metadata.
- B1: Gold Set + benchmark offline; B2: Semantic Reviewer + Smart Boundaries
  juntos; B3: ranking explicável A/B/C/REJEITADO; B4: multimodal seletivo.

Trilha A e B2 em diante não iniciadas. Recomendações adicionais do Antigravity
não foram tratadas como autorização de implementação.

## Execução B1

1. Ler os cinco documentos de auditoria e a especificação B1.
2. Antes de editar: Python 148 aprovados (19,53 s); JavaScript 19 aprovados.
3. Registrar baseline e manifesto em `test-results/b1/`; copiar e conferir os
   três documentos existentes em `backups/b1-before-20260922/`.
4. Criar `miner/benchmark.py`, `tests/test_benchmark.py`, schema, README e dois
   exemplos sintéticos em `benchmarks/gold/`.
5. Implementar matching ótimo 1:1, métricas temporais/boundaries, Top-K e filtro
   opcional de metadata, sem importar ou modificar a infraestrutura operacional.
6. Validar exemplo de aceite pela CLI offline e novos testes (64 aprovados).
7. Suíte final: **212 Python / 19 JavaScript**, lint, compilação, sintaxe JS e
   consistência de dependências aprovados. Atualizar somente estes três documentos.

Gold Set e editorial_feedback são fontes distintas. Não houve promoção de feedback,
mineração real, API externa, mudança de banco, campanhas, ranking ou export.
Definições oficiais de métricas e contrato: `benchmarks/gold/README.md` e
relatório B1 em `CODEX_REPORT.md`. Os exemplos não constituem gold humano real.

**Gate B1 cumprido. Parar; aguardar nova tarefa.**

---

# Histórico — auditoria inicial da V2

Data: 22/09/2026. Responsável pela execução: Codex. Revisão externa: pendente.

## Escopo autorizado

Inspecionar o projeto existente, banco em leitura, pipeline, campanhas, feedback, deduplicação, caches e testes; executar a suíte completa; consolidar a especificação; produzir gap analysis, riscos e roadmap. Criar os cinco documentos em `docs/AI/`. Não alterar código funcional.

## Fora de escopo

Implementação de Campaign Core, Semantic Reviewer, novos limites, LLM, multimodal, Source Scanner, Viewx, dashboard, aprendizado, migrations, ranking, Live Mode ou publicação. Não executar mineração, benchmark com escrita na produção, downloads ou inferência longa. Não modificar dados, decisões humanas, configurações ou mídias. Não executar reset. Não atribuir ao Antigravity uma revisão que ele ainda não realizou.

## Plano executado

1. Ler a especificação integral e inventariar código/configuração/testes/scripts/documentação.
2. Registrar SHA-256 de 66 arquivos existentes e snapshot lógico das oito tabelas via SQLite `mode=ro`.
3. Executar Python, JavaScript, lint, compilação, sintaxe e consistência das dependências; fixtures isoladas.
4. Rastrear importação até export, incluindo pipeline curto, longo e remoto; separar regras, recomendação editorial e decisão humana.
5. Produzir os documentos, mantendo o Product Spec integral e diferenciando estado atual de propostas.
6. Conferir integridade dos documentos e comparar arquivos existentes e banco com o início. Parar para revisão externa.

## Critérios de aceite e resultado

| Critério | Resultado |
|---|---|
| Baseline completo e registrado | 148 Python / 19 JS; lint, sintaxe, compileall e pip check aprovados |
| Mapeamento de banco, pipeline, campanhas, feedback e group_refined | CODEX_REPORT.md |
| Gap analysis específica por arquivo/função e ação | CODEX_REPORT.md |
| Custos, riscos, dependências e ordem justificada | CODEX_REPORT.md e roadmap abaixo |
| Cinco documentos de colaboração | Criados |
| Conteúdo Antigravity não inventado | Template sem parecer |
| Código/configurações/testes existentes preservados | Conferência por hashes registrada no relatório |
| Banco operacional preservado | Snapshot lógico antes/depois; nenhuma migration |
| Nenhuma mineração ou download real | Não executados nesta auditoria |

Status: **auditoria concluída; aguardando revisão externa. Nenhuma fase de implementação autorizada.**

## Roadmap proposto, sujeito à revisão

As fases não implicam autorização de execução. Cada incremento deve manter testes legados, comparar baseline e parar ao concluir seu próprio escopo.

| Fase | Entrega pequena / dependência | Gate de aceite proposto |
|---|---|---|
| 0 — esta entrega | Documentação, baseline e auditoria | Zero mudança funcional; cinco documentos revisáveis |
| 0B — fundação do Gold Set | Contrato de anotação humana versionado e avaliador offline; consumir cópias, sem alterar produção | Métricas com denominadores explícitos, pareamento 1:1, duplicatas sem inflar recall, casos não avaliados separados |
| 1A — Campaign Core compatível | Schema versionado e adaptador dos três JSON legados, sem mudar decisões | Contratos para regras/origem/validade/evidência; testes de equivalência com campanhas atuais |
| 1B — regras e feedback rastreáveis | Validador genérico, confirmação humana e eventos de ajuste; migration apenas aditiva quando autorizada | João/Juninho como fixtures de requisitos informados; preservar decisões/export e não transformar texto promocional em bloqueio |
| 2 — revisão semântica textual | Interface de reviewer e contrato de avaliação versionados; primeiro execução comparativa isolada, sobre finalistas | Publicaria SIM/TALVEZ/NÃO, evidências, abstenção, custo/cache/limites; comparação com Gold Set antes de afetar ranking |
| 3 — limites narrativos | Estender suggested_start/end, sem substituir originais; contexto progressivo e verificação após ajuste | Não truncar frases/payoff; timestamp absoluto e lacunas explícitas; revisão e limite avaliados juntos |
| 4 — Clip Package | RAW aprovado existente + SRT relativo ao corte final + TXT + JSON + título e duas alternativas | Idempotência; RAW intacto; cues dentro da duração; origem e confiança; pacote manual tem prioridade |
| 5 — Source Scanner YouTube | Catálogo de canal/playlist por metadados, sobre contratos de fonte/período e identidade | Incremental; não baixar tudo; sem reprocessar concluídos; não confundir upload com live |
| 6 — multimodal seletivo | Só finalistas em que texto/sinais são insuficientes, após benchmark textual | Limite de frames/bytes/custo; melhoria medida por tipo; não inferir direitos pela imagem |
| 7 — Viewx Provider/Radar | Importar proposta de regras para schema confirmado; confirmação antes de ativar | Evidências e diff de regulamento; defaults só confirmados; não sobrescrever overrides |
| 8 — perfil editorial | Consumir feedback suficiente, por criador/campanha/tipo | Amostra mínima definida, comparação fora da amostra, explicabilidade e possibilidade de desligar |
| 9 — central e produção | Visão global + estados editado/publicado manualmente; nenhuma postagem automática | Não duplicar tarefas/cortes; manter identidade, campanhas e trilha de export |

O Gold Set robusto da hipótese original deixa de ser uma fase tardia: começa em 0B e cresce em todas as fases. Sem referência humana anterior, não há como demonstrar que o novo revisor ou os novos limites melhoraram. Campaign Core mantém prioridade antes da escala multi-campanha, mas não exige migrar todo o banco de uma vez. Reviewer e limites são incrementos separados com validação conjunta: mudar limites pode invalidar o julgamento do trecho. O Clip Package aproveita o RAW/Whisper existentes; não requer um novo downloader nem uma solução multimodal.

O julgamento crítico por um segundo revisor é uma experiência posterior da fase 2, condicionada a ganho medido que compense custo/latência. Não é requisito de infraestrutura prévio. Campos mínimos de rastreabilidade de produção podem nascer no pacote; o dashboard completo continua no fim.

## Primeira tarefa pequena recomendada — ainda não executada

**Fundação de benchmark editorial offline, sem alterar o ranking.**

Criar, após autorização, um contrato JSON versionado de anotação humana e um avaliador puro que compare anotações e sugestões exportadas. Os exemplos A/B entram como referências fornecidas pelo operador; não inventar rótulos para os demais 127. Registrar fonte/intervalo de avaliação completo, anotador, decisão, limites aceitos e motivo opcional. Separar exemplos usados para calibrar de vídeos reservados para avaliar.

Aceite: fixtures sintéticas para coincidência, perda, duplicata, limites divergentes e ausência de rótulos; medição de precision/recall somente quando os denominadores existem; arquivo de relatório fora de `data`; nenhuma chamada a Whisper/rede, nenhuma gravação SQLite, nenhuma alteração em `detect`, `review`, `group_refined` ou na interface operacional. Não considerar os 11 eventos de feedback atuais como amostra representativa automaticamente.

Essa entrega é pequena, testável e oferece uma base objetiva para a primeira alteração editorial da V2.

## Handoff

Antigravity deverá revisar o diagnóstico, as dependências e os riscos em seu arquivo próprio. Codex não implementará o roadmap até receber a próxima tarefa. Evitar edição simultânea: revisão externa inicialmente documental; mudanças de código exigem escopo acordado e novo baseline.
