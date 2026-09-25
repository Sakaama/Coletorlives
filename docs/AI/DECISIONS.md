# Decisões GabePeixe Kick / Campeonato Atual (Antigravity) — 23/09/2026

- GP-D01: **GabePeixe é exclusivamente Kick neste campeonato.** Configurado `allowed_sources: ["Kick"]`. Tentativas de configurar YouTube para GabePeixe são bloqueadas no Collector e no validador de elegibilidade. O Source Scanner YouTube A2 continua ativo para outras campanhas (ex: João Pichau).
- GP-D02: **Atualização in-place de `gabepeixe.json`.** Preservado o ID estável `gabepeixe`, evitando forks desnecessários (`gabepeixe_v2`).
- GP-D03: **Vigência temporal do campeonato.** Conteúdo de lives elegível a partir de 01/09/2026 (`min_date: "2026-09-01"`). Janela de publicação até 22/10/2026 23:59 (`max_date: "2026-10-22"`). Ranking final em 24/10/2026 12:00.
- GP-D04: **Obrigações mandatórias visíveis ao operador.** Implementados banners de alerta de alta visibilidade no fluxo da VOD (`#vod-obligations`) e no formulário de Pacote Editorial (`#editorial-obligations`): `⚠ LOWER OBRIGATÓRIO (abaixo do rosto do Gabe)`, `⚠ #gabepeixe`, `⚠ MARCAR PERFIL OFICIAL`. Sem editor gráfico complexo desnecessário; a aplicação criativa do lower é responsabilidade do editor no software de edição.
- GP-D05: **Arquitetura Kick validada.** O provider Kick utiliza `any-dl` para resolução da stream master HLS (`sourceUrl`) e `yt-dlp` com `--download-sections` para obtenção precisa de ranges com re-encode em keyframes. Não há download da VOD inteira. Fallback 404 preserva o registro permitindo vincular arquivo local.

---

# Decisões A2 (Antigravity) — 23/09/2026

- A2-D01: **Source Discovery é separado de Media Import.** O ato de descobrir o catálogo de um canal, playlist ou vídeo do YouTube é uma operação de consulta e metadados, completamente desacoplada da criação de VODs ou aquisição de arquivos de mídia.
- A2-D02: **Discovery não cria VOD automaticamente.** Nenhuma linha é inserida na tabela `vods` ou `jobs` durante a descoberta.
- A2-D03: **Catálogo de descoberta é efêmero.** O resultado da descoberta vive na resposta da API e no estado do cliente na interface; a persistência no banco operacional ocorre estritamente por ação explícita do operador ao clicar em `[↓ Importar VOD]`.
- A2-D04: **Identificação de itens KNOWN sem mutação.** O estado de vídeos já importados na campanha é detectado via consulta de leitura (`SELECT`), colapsando duplicatas por `video_id`.
- A2-D05: **Reutilização integral do pipeline de importação.** Ao importar um item descoberto, o sistema chama o método `service.import_url` existente, garantindo consistência com jobs e metadados legados sem duplicar downloaders.

---

# Decisões A2 — 22/09/2026

A2 autorizada por "Continue A2". Validador de catálogo separado do validador de vídeo, evitando ampliar os caminhos de download. /videos como padrão explícito; /streams para lives. Flat não garante datas: complementar metadados e excluir entradas sem data do filtro automático. Preservar integralmente registros já conhecidos no catálogo, inclusive concluídos e revisões. Limite de 100 entradas visível na sincronização; sem promessa de cobertura histórica completa ou de latência em segundos. Sem migration, mineração ou download; A3/B2 fora desta entrega.

---

# Decisões A1 — 22/09/2026

**A1 utiliza o Campaign System atual como ponte operacional.
Não representa o Campaign Core V2 definitivo.**

- A1-D01: IDs estáveis joaopichau e juninhomanella; três campanhas legadas intactas.
  Não há ramificação de código por criador/campanha.
- A1-D02: Reutilizar JSON e consumidores atuais. allowed_sources representa suporte
  operacional de entrada, sem atestar autorização/autoria de um canal. João admite
  plataformas técnicas YouTube/Kick/Twitch para lives com participação ativa;
  Juninho usa YouTube/Kick no importador existente. Instagram/TikTok permanecem
  registrados como fontes conhecidas; entrada direta por URL ainda não suportada.
- A1-D03: min_date=null significa data não informada, exige revisão humana e não
  inventa início de vigência. Nenhum valor foi alterado nas campanhas anteriores.
- A1-D04: Mensagem de original_lives_only usa streamer e aceita override informativo
  original_live_review. João exige live e participação ativa; Juninho não recebe
  indevidamente a regra de somente lives. Regras de presença/foco são revisão humana.
- A1-D05: WhatsApp, proibições e política de IA são informação, sem automação ou
  interpretação jurídica. Comentário de João tem texto exato e required_until
  2026-10-09; vigência conferida manualmente, sem assumir fuso ou expiração automática.
- A1-D06: Campos extras informativos operational_requirements e pinned_comment
  são aditivos; regras também constam em notes/required_texts para exibição atual.
  Nenhum default Viewx foi introduzido.
- A1-D07: Não corrigir Collector.view aqui. Supressão por overlap ignora status;
  débito confirmado por inspeção, sem relação necessária com cadastro das campanhas.
- A1-D08: Core V2 deverá tratar evidências, URLs/IDs oficiais confirmados, vigência
  por regra, confirmação por trecho e compliance por plataforma. Não implementado.

---

# Decisões B1 — 22/09/2026

Esta seção registra a autorização posterior à auditoria; o histórico abaixo
permanece para rastreabilidade. D01/D17 descrevem a fase anterior, já encerrada.

| ID | Status | Decisão / consequência |
|---|---|---|
| B1-D01 | Confirmada pelo operador | Revisão Antigravity aceita parcialmente; roadmap dual-track. A1 campanhas existentes João/Juninho → A2 scanner YouTube → A3 Clip Package; B1 benchmark → B2 Semantic Reviewer + Smart Boundaries juntos → B3 ranking explicável → B4 multimodal. Só B1 autorizada nesta tarefa. |
| B1-D02 | Implementada | Gold Set e editorial_feedback são fontes distintas. Sem conversão automática, consulta ao banco ou integração com feedback de produção. |
| B1-D03 | Implementada | Contrato JSON v1 com declaração explícita would_clip=true, IDs e segundos absolutos. Mídia não pertence ao Gold Set; exemplos entregues são sintéticos. |
| B1-D04 | Implementada | Matching bipartido ótimo: máxima cardinalidade, máxima soma de IoU, mínima soma de MAE, menor conjunto lexicográfico de pares de IDs. Fluxo de custo mínimo, sem dependências externas ou greedy. |
| B1-D05 | Implementada | Match exige mesma campanha/VOD e IoU >= 0,50 por padrão. Tolerância de boundaries <= 3 s independente de detecção. Ambos configuráveis; cálculo exato antes da saída em float. |
| B1-D06 | Implementada | Precision@3/5/10 rematcheia cada prefixo na ordem recebida e usa min(K,P) como denominador. Sem denominador, null; sem matches, médias/taxas de boundaries null. |
| B1-D07 | Implementada | Metadata/filtro opcional prepara recortes futuros por prioridade A, sem criar classes ou confundir precisão temporal com publicabilidade. |
| B1-D08 | Preservada | Somente módulo/testes/fixtures de benchmark e três documentos. Nenhuma alteração funcional em detector, ranking, group_refined, UI, banco, campanha, export ou pipeline. B1 concluída; não iniciar outras tarefas. |

Definição oficial: M = matches 1:1; G = golds; P = predictions após filtro.
Recall=M/G; precision=M/P; FP=P−M; FN=G−M. IoU=interseção/união dos intervalos.
Erros absolutos de início/fim em segundos; boundary MAE é a média dos dois erros,
agregada somente sobre matches. Taxas de início/fim/ambos dentro da tolerância
também usam M. Precision@K usa matches ótimos do prefixo / min(K,P).
Divisão por zero é null. Fórmulas completas, escopo, formatos e limitações em
`benchmarks/gold/README.md`. Essas métricas são relativas ao gold fornecido;
gold incompleto não sustenta estimativa confiável de falsos positivos editoriais.

---

# Histórico — Decisões e propostas — TUTUCO CLIP MINER

Data de abertura: 22/09/2026. Separar restrições já autorizadas, fatos da implementação e propostas ainda sujeitas à revisão.

| ID | Status | Decisão / fundamento | Consequência |
|---|---|---|---|
| D01 | Confirmada pelo operador | Esta fase é auditoria/documentação, sem código funcional | Não iniciar implementação ao concluir documentos |
| D02 | Confirmada pelo operador | Evoluir o projeto atual; preservar Flask/Waitress/SQLite e ferramentas existentes quando adequadas | Não criar V2 paralela nem trocar framework/banco sem evidência |
| D03 | Confirmada pelo operador | Operador é autoridade editorial; RAW limpo e edição final humana | Aprovação continua necessária; título visual não é aplicado ao RAW |
| D04 | Confirmada pelo operador | Qualidade supera quota; objetivo de 3–5 por dia é estratégia operacional | Não diminuir limiar para preencher quantidade |
| D05 | Confirmada pelo operador | Preservar originais, decisões, timestamps, exports e checkpoints | Mudanças futuras aditivas/versionadas, com backup e teste de compatibilidade |
| D06 | Estado observado, preservado | group_refined usa tolerância padrão 3 s, somente NOVO bom/recomendado sem pacote manual/arquivo histórico | Não restaurar 0,5 s por causa de documento antigo; manter teste explícito do modo estrito |
| D07 | Confirmada pelo operador | Campanhas orientadas a dados; regra oficial separada de estratégia editorial | Não criar if por criador; nenhuma regra Viewx global sem evidência/confirmacão |
| D08 | Confirmada pelo operador | Conteúdo promocional em título não prova inelegibilidade | Preservar origem/período/plataforma e revisão humana por trecho; não reintroduzir falso bloqueio Cinefy |
| D09 | Confirmada pelo operador | Etapas caras apenas após a peneira barata | Não enviar VOD integral a LLM/visão nem processar frames completos |
| D10 | Proposta | Antecipar fundação Gold Set para antes de Semantic Reviewer/Smart Boundaries | Evitar declarar melhoria editorial só com testes unitários |
| D11 | Proposta | Compatibilizar campanhas por adaptador de leitura antes de migration | Manter IDs/caminhos e resultados legados; só normalizar persistência com necessidade demonstrada |
| D12 | Proposta | Separar importância editorial, confiança, compliance e decisão humana | Score alto não certifica direitos, precisão de transcrição ou aprovação humana |
| D13 | Proposta | Novo reviewer com avaliação versionada, evidências e resposta de abstenção | Falhas/timeout não apagam resultado nem reduzem silenciosamente proteção; comparação isolada antes de ativar |
| D14 | Proposta | Reavaliar o trecho após mudar seus limites | Uma narrativa julgada em 90 s pode ficar incompleta em 25 s |
| D15 | Proposta | Segundo revisor só se ensaio demonstrar benefício | Não duplicar chamadas e custo por padrão |
| D16 | Proposta | Feedback como eventos, incluindo edição de título/limites e versão julgada | Não treinar com poucas aprovações nem tratar ausência de feedback como rejeição |
| D17 | Confirmada pelo operador | Antigravity revisará depois, sem escrita simultânea nos mesmos fontes | Template vazio; nenhuma aprovação externa presumida |

## Contratos de compatibilidade propostos

Não renomear os três identificadores legados (`gabepeixe`, `brkk`, `brabox`), caminhos de mídia ou status de decisão. `RECOMENDADO/BOM/TALVEZ/FRACO` não deve ser retroativamente substituído por A/B/C/REJEITADO: avaliações V2 devem portar versão e manter a leitura do legado. Confiança ausente permanece desconhecida, não vira zero ou alta por inferência.

Timestamp absoluto é tempo na fonte; SRT futuro deve usar o tempo relativo ao RAW final, incluindo margens/ajuste humano. Guardar ambos explicitamente. Campos original/sugerido/final não são intercambiáveis.

Regras terão escopo (fonte, trecho, edição ou publicação), severidade, mecanismo de verificação, validade, evidência e confirmação. AUTOMATIC descreve mecanismo de avaliação; BLOCKING/WARNING descrevem consequência. São dimensões distintas a validar no schema proposto, preservando os três conceitos exigidos pelo Product Spec.

## Questões não decididas

Fornecedor/modelo semântico, processamento externo permitido, orçamento por VOD/candidato, armazenamento de chaves, conjunto de avaliação cega, tolerância humana de limites e interpretação oficial dos regulamentos ainda dependem de revisão/decisão futura. Nenhum fornecedor foi escolhido, nenhuma credencial foi solicitada e nenhuma regra externa foi consultada como oficial nesta auditoria.
