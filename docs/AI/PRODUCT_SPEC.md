> Fonte principal de intenção do produto: especificação fornecida pelo operador em 22/09/2026, preservada integralmente abaixo. Requisitos futuros não são funcionalidades já implementadas nem autorização para implementá-las nesta tarefa.
>
> Estado desta entrega: auditoria/documentação somente. Implementação observada em CODEX_REPORT.md; proposta de fases em TASK.md; decisões e propostas em DECISIONS.md. Os casos João Pichau e Juninho Manella são requisitos informados pelo operador, ainda sem verificação de regulamento externo. Não foram cadastradas campanhas nem presumidos defaults Viewx.
>
> A ordem da seção 35 é uma hipótese: a auditoria propõe antecipar a fundação do Gold Set. As duas referências BRKK são exemplos editoriais, não regras de scoring. A meta de aprovação de 80% é futura e não foi demonstrada pelo baseline de software.

# TUTUCO CLIP MINER V2 — PRODUCT SPEC + AUDITORIA INICIAL

Você está trabalhando no projeto existente:

D:\Projetos\TUTUCO-CLIP-MINER

Este é um projeto REAL, já funcional e com banco, pipeline, interface, testes e dados existentes.

IMPORTANTE:
- NÃO recrie o projeto do zero.
- NÃO substitua a arquitetura existente sem necessidade.
- NÃO implemente todas as funcionalidades descritas abaixo nesta tarefa.
- NÃO altere o pipeline principal nesta primeira etapa.
- NÃO apague dados existentes.
- NÃO altere comportamento funcional apenas para "melhorar arquitetura".
- Primeiro entenda profundamente o que já existe.
- Preserve compatibilidade com campanhas, VODs, candidatos, aprovações e exports existentes.

============================================================
1. MISSÃO DO PRODUTO
============================================================

O TUTUCO CLIP MINER V2 será uma ferramenta para transformar vídeos, VODs e lives longas em uma shortlist de CORTES EDITORIALMENTE COMPLETOS E PUBLICÁVEIS.

A experiência desejada é semelhante à etapa de descoberta e avaliação de cortes de ferramentas como OpusClip, porém o objetivo NÃO é editar automaticamente o vídeo.

O operador humano fará a edição final.

O software deve fazer principalmente o trabalho intelectual e operacional anterior à edição:

FONTE
→ AQUISIÇÃO
→ TRANSCRIÇÃO
→ DESCOBERTA DE MOMENTOS
→ FILTRAGEM
→ COMPREENSÃO SEMÂNTICA
→ DEFINIÇÃO INTELIGENTE DE INÍCIO/FIM
→ DEDUPLICAÇÃO
→ RANKING
→ TÍTULO/HOOK
→ TRANSCRIÇÃO/LEGENDA
→ COMPLIANCE
→ REVISÃO HUMANA
→ RAW + SRT + METADADOS

O objetivo final NÃO é encontrar a maior quantidade possível de momentos.

O objetivo é:

"Coloquei uma live/vídeo de várias horas e os primeiros cortes apresentados realmente parecem vídeos completos que eu publicaria."

============================================================
2. O QUE O PRODUTO NÃO DEVE FAZER
============================================================

A edição final continuará humana.

Portanto, NÃO priorizar:

- autozoom;
- B-roll automático;
- emojis;
- efeitos;
- transições;
- edição automática completa;
- reenquadramento artístico;
- publicação automática neste estágio;
- templates automáticos de vídeo final.

O investimento principal de engenharia deve ser:

ENCONTRAR CORTES EXCELENTES.

O operador fará a edição posteriormente em software externo.

============================================================
3. RESULTADO IDEAL DE UM CORTE
============================================================

Cada corte recomendado deve possuir, quando aplicável:

- ID;
- campanha;
- criador;
- fonte/VOD;
- timestamp inicial recomendado;
- timestamp final recomendado;
- duração;
- preview;
- transcrição;
- arquivo SRT;
- RAW limpo;
- título/hook principal;
- 2 títulos/hooks alternativos;
- descrição curta explicando por que o trecho funciona;
- tipo editorial;
- score editorial;
- nível de confiança;
- breakdown do score;
- compliance da campanha;
- Aprovar;
- Descartar.

Exemplo conceitual:

🔥 92 — CORTE #07

TÍTULO NA TELA:
"O JOÃO NÃO ESPERAVA ESSA RESPOSTA..."

TRECHO:
01:27:14 → 01:28:03

DURAÇÃO:
49 segundos

TIPO:
REACTION / OPINION

POR QUE FUNCIONA:
Começa com uma afirmação forte, fornece contexto suficiente,
desenvolve o assunto e termina em uma reação/payoff natural.

SCORES:
Hook: 94
Standalone: 97
Coerência: 96
Payoff: 91
Retenção: 88
Visual: 79

CONFIDENCE:
ALTA

COMPLIANCE:
✓ criador presente
✓ conteúdo permitido
✓ período permitido
✓ hashtag identificada
⚠ comentário obrigatório na publicação

AÇÕES:
[PREVIEW]
[APROVAR]
[DESCARTAR]
[RAW]
[SRT]
[COPIAR TÍTULO]

============================================================
4. VISUAL DO TÍTULO
============================================================

Na interface, o título/hook recomendado deve possuir uma PRÉVIA VISUAL.

Direção visual desejada:

- texto branco;
- forte/bold;
- fundo/faixa vermelha;
- alta legibilidade;
- aparência de título que posteriormente poderá ser colocado sobre o corte.

IMPORTANTE:

ESSA ARTE NÃO DEVE SER RENDERIZADA AUTOMATICAMENTE NO RAW.

É apenas uma prévia/sugestão visual para o operador.

O RAW deve permanecer limpo.

============================================================
5. PRINCÍPIO EDITORIAL
============================================================

O sistema NÃO deve procurar simplesmente "picos de energia".

Ele deve procurar MINI-HISTÓRIAS.

Um corte de conversa/story pode possuir:

HOOK
→ CONTEXTO
→ DESENVOLVIMENTO
→ PAYOFF

Gameplay pode possuir:

SITUAÇÃO
→ TENSÃO
→ AÇÃO
→ REAÇÃO

Opinião pode possuir:

TESE
→ ARGUMENTO
→ EXEMPLO
→ CONCLUSÃO

Reação pode possuir:

ESTÍMULO
→ REAÇÃO
→ COMENTÁRIO/PAYOFF

Um momento com energia alta, grito ou palavra forte mas sem história,
contexto ou interesse suficiente NÃO deve automaticamente virar corte.

============================================================
6. PIPELINE DE QUALIDADE DESEJADO
============================================================

Preservar e aproveitar o pipeline existente sempre que possível.

Arquitetura conceitual desejada:

WHISPER / SINAIS BARATOS
        ↓
CANDIDATE FINDER
        ↓
HEURISTIC FILTER
        ↓
SEMANTIC REVIEWER
        ↓
STORY BOUNDARY FINDER
        ↓
DEDUPLICAÇÃO
        ↓
EDITORIAL / VIRAL RANKER
        ↓
TITLE GENERATOR
        ↓
HUMAN REVIEW

Não executar processamento caro sobre horas inteiras de vídeo se não for necessário.

O pipeline local/barato deve reduzir o universo antes das etapas semanticamente mais caras.

Exemplo:

4 horas de VOD
→ 150 sinais
→ 35 candidatos
→ 15 candidatos semanticamente interessantes
→ 8 cortes realmente publicáveis

Os números são apenas exemplos.

NÃO force uma quantidade fixa.

============================================================
7. SEMANTIC REVIEWER
============================================================

Precisamos futuramente de uma camada capaz de entender o significado do conteúdo, e não apenas palavras-chave.

Para cada candidato finalista, deve ser possível analisar contexto suficiente ANTES e DEPOIS do momento.

Avaliar pelo menos:

1. Hook
2. Standalone / independência de contexto
3. Coerência
4. Progressão
5. Payoff
6. Retenção
7. Emoção
8. Interesse
9. Originalidade
10. Qualidade do começo
11. Qualidade do final
12. Potencial como vídeo independente

Além do score, responder:

"EU PUBLICARIA ESTE TRECHO COMO UM VÍDEO INDEPENDENTE?"

Valores:

SIM
TALVEZ
NÃO

O revisor semântico deve poder REJEITAR um candidato mesmo que heurísticas anteriores tenham dado score alto.

============================================================
8. REVISÃO EM MÚLTIPLOS ESTÁGIOS
============================================================

Avaliar futuramente uma arquitetura com mais de um julgamento.

Exemplo:

REVISOR 1:
estrutura/narrativa/coerência

REVISOR 2:
editor crítico que tenta encontrar motivos para NÃO publicar

Pergunta crítica:

"Se alguém visse este vídeo no TikTok/Reels/Shorts sem conhecer
a live anterior, teria motivo para continuar assistindo?"

Uma divergência grande entre revisores deve reduzir a confiança.

NÃO implementar isso agora sem antes avaliar arquitetura, custo e benefício.

============================================================
9. DEPENDÊNCIA DE CONTEXTO
============================================================

Precisamos detectar cortes que dependem excessivamente de contexto anterior.

Exemplos:

"isso"
"aquilo"
"ele"
"ela"
"como eu falei"
"igual aconteceu antes"
"aquele negócio"
"como vocês viram"
"o que aconteceu ontem"

Essas expressões NÃO significam automaticamente que o corte é ruim.

O sistema deve tentar expandir o contexto para trás.

Se conseguir tornar o corte independente, ajustar o início.

Se mesmo assim uma pessoa externa não conseguir compreender,
reduzir fortemente o ranking ou rejeitar.

============================================================
10. SMART BOUNDARIES
============================================================

O início/fim do candidato bruto NÃO deve automaticamente ser o início/fim do corte.

Precisamos futuramente encontrar:

- onde o assunto realmente começa;
- primeiro contexto necessário;
- melhor ponto de entrada;
- hook;
- desenvolvimento;
- payoff;
- reação posterior relevante;
- ponto onde o assunto termina;
- ponto onde começa outro assunto.

Evitar:

- começar no meio de frase;
- começar depois do contexto necessário;
- começar cedo demais;
- terminar antes do payoff;
- cortar uma reação importante;
- carregar silêncio/enrolação depois do payoff;
- incluir o início de outro assunto.

Objetivo:

CANDIDATO BRUTO
→ COMPREENSÃO DA HISTÓRIA
→ START RECOMENDADO
→ END RECOMENDADO

============================================================
11. TIPOS EDITORIAIS
============================================================

A arquitetura deve permitir diferentes tipos de corte.

No mínimo considerar:

STORY
OPINION
REACTION
GAMEPLAY
CLUTCH
FAIL
ARGUMENT
REVEAL
FUNNY
INFORMATION

Cada tipo pode futuramente possuir critérios diferentes.

Exemplo:

STORY:
hook + contexto + desenvolvimento + conclusão

GAMEPLAY:
situação + tensão + ação + reação

OPINION:
tese + justificativa + conclusão

REACTION:
estímulo + reação + comentário

Não avaliar todos os tipos exatamente da mesma maneira.

============================================================
12. CLASSIFICAÇÃO DOS CORTES
============================================================

Não queremos 30 candidatos medianos na tela principal.

Queremos uma shortlist pequena e forte.

Classificação desejada:

A — PUBLICARIA HOJE
Corte forte e de alta confiança.

B — BOM CORTE
Publicável e útil para frequência.

C — RESERVA
Tem potencial, mas requer julgamento humano.

REJEITADO
Não aparece na shortlist principal.

IMPORTANTE:

NÃO force quantidade.

Se uma VOD tiver apenas 2 cortes realmente bons:
retornar 2.

Se tiver 15 excelentes:
retornar 15.

Nunca reduzir o padrão editorial apenas para atingir uma meta numérica.

============================================================
13. OBJETIVO DE VOLUME
============================================================

A estratégia operacional é produzir aproximadamente 3–5 cortes bons por dia quando houver conteúdo suficiente.

Porém:

QUALIDADE > COTA.

O sistema deve maximizar:

"NÚMERO DE CORTES PUBLICÁVEIS POR HORA DE CONTEÚDO"

mantendo alto padrão editorial.

Quantidade deve vir da capacidade de processar mais fontes,
não da redução do padrão de qualidade.

============================================================
14. SCORE EDITORIAL
============================================================

O score deve ser explicável.

Exemplo:

CLIP SCORE: 92

Hook:          94
Standalone:    97
Coerência:     96
Progressão:    90
Payoff:        91
Retenção:      88
Emoção:        86
Originalidade: 83
Visual:        79
Boundary:      94

O número final sozinho NÃO é suficiente.

A interface deve explicar resumidamente por que aquele corte recebeu essa avaliação.

Evitar falsa precisão se o sistema não possuir evidência para determinado subscore.

============================================================
15. TÍTULO / HOOK
============================================================

Para cortes classificados A/B, gerar futuramente:

- título principal;
- alternativa 1;
- alternativa 2.

Os títulos devem funcionar como texto na tela durante a edição humana.

Exemplo:

PRINCIPAL:
"O JOÃO NÃO ESPERAVA ESSA RESPOSTA..."

ALTERNATIVA:
"FOI AÍ QUE TUDO DEU ERRADO"

ALTERNATIVA:
"O JOÃO PERCEBEU TARDE DEMAIS"

O título deve representar a promessa REAL do corte.

Precisamos futuramente de validação:

"O conteúdo realmente entrega o que o título promete?"

Se não:
rejeitar ou regenerar o título.

Evitar clickbait sem payoff.

============================================================
16. LEGENDA / CLIP PACKAGE
============================================================

O Whisper já faz parte do projeto.

Um corte aprovado deve futuramente permitir gerar algo equivalente a:

clip_raw.mp4
captions.srt
transcript.txt
metadata.json

Opcionalmente avaliar suporte a ASS se fizer sentido.

metadata.json deve preservar informações como:

- candidate_id;
- vod_id;
- campaign_id;
- creator;
- source;
- original timestamps;
- suggested timestamps;
- final timestamps;
- scores;
- classificação;
- confiança;
- título;
- alternativas;
- tipo editorial;
- motivo da recomendação;
- compliance;
- revisão humana.

============================================================
17. ANÁLISE VISUAL / MULTIMODAL
============================================================

O sistema atual não deve depender exclusivamente da transcrição no futuro.

Alguns bons cortes podem ser:

- reação visual;
- clutch;
- fail;
- vitória;
- morte;
- placar;
- expressão facial;
- situação absurda;
- acontecimento visual com pouca fala.

Porém:

NÃO analisar horas inteiras frame a frame.

Estratégia desejada:

texto/áudio/local
→ candidatos
→ shortlist intermediária
→ somente então análise visual/multimodal dos finalistas

Pode-se considerar amostragem de frames ou pequenos trechos.

Avaliar arquitetura e custo antes de implementar.

============================================================
18. FEEDBACK HUMANO
============================================================

O operador é a autoridade editorial final.

Registrar futuramente:

- aprovado;
- descartado;
- início ajustado;
- fim ajustado;
- título escolhido;
- título editado;
- campanha;
- criador;
- scores no momento da decisão.

Ao descartar, oferecer opcionalmente motivos rápidos:

- Sem graça
- Sem contexto
- Sem payoff
- Começa mal
- Termina mal
- Momento fraco
- Duplicado
- Outro

Não obrigar o usuário a preencher formulário para cada descarte.

============================================================
19. PERFIL EDITORIAL
============================================================

O histórico de feedback deve futuramente permitir aprender preferências por:

- criador;
- campanha;
- tipo de conteúdo.

Exemplo conceitual:

JOÃO PICHAU

STORY: alta aprovação
REACTION: alta aprovação
OPINION: média/alta
conversa operacional: baixa
momentos dependentes de contexto: baixa

IMPORTANTE:

NÃO implementar aprendizado automático agressivo com poucas amostras.

Primeiro coletar feedback suficiente.

Preferir aprendizado interpretável inicialmente.

============================================================
20. BENCHMARK EDITORIAL / GOLD SET
============================================================

Este é um requisito importante.

Testes unitários NÃO medem qualidade editorial.

Precisamos futuramente criar um GOLD SET:

O operador assiste a vídeos reais e marca manualmente:

"EU CORTARIA ISSO."

Esses cortes humanos se tornam referência.

Após alterações no algoritmo, medir:

- Recall Editorial
- Precision
- Approval Rate
- Boundary Accuracy
- False Positives

Exemplo:

Cortes humanos:                40
Encontrados pelo Miner:        35/40
Precision shortlist:           88%
Começo correto:                86%
Final correto:                 91%
Approval Rate prioridade A:    84%

Meta inicial desejada:

>= 80% de aprovação humana entre candidatos classificados como PRIORIDADE A.

IMPORTANTE:

Uma alteração NÃO deve ser considerada uma melhoria editorial apenas porque:

"todos os testes passaram."

Precisamos separar:

CORREÇÃO DE SOFTWARE

de

QUALIDADE EDITORIAL.

============================================================
21. CAMPANHAS / CAMPEONATOS
============================================================

O produto será usado fortemente em campeonatos de cortes.

Precisamos de Campaign Core genérico orientado por dados.

NUNCA espalhar lógica assim:

if campaign == "juninho":
if campaign == "joao":
if campaign == "gabe":

As regras devem estar nos dados/schema/configuração.

Precisamos representar futuramente:

- nome;
- provider/origem;
- URL oficial;
- criador;
- data inicial;
- data final;
- ranking/premiação;
- plataformas;
- hashtags obrigatórias;
- perfis/@ obrigatórios;
- fontes autorizadas;
- data mínima do conteúdo;
- requisitos;
- proibições;
- regras temporárias;
- assets obrigatórios;
- lower;
- texto/link obrigatório no vídeo;
- comentário fixado;
- observações;
- status;
- evidência/origem da regra;
- confirmação humana.

As regras devem suportar pelo menos níveis como:

BLOCKING
WARNING
AUTOMATIC

============================================================
22. CASOS REAIS PARA VALIDAR A ARQUITETURA
============================================================

CASO 1 — JOÃO PICHAU

Requisitos conhecidos:

- hashtag #joaopichau;
- utilizar conteúdo das lives/vídeos da Pichau ou canais em que João Pichau tenha participação ativa;
- somente conteúdos a partir de 01/09/2026;
- todo corte deve possuir participação ativa do João Pichau;
- comentário fixado obrigatório até 09/10/2026:
  "Evento Pichau Arena, o maior evento gamer do Sul do Brasil, de 10 a 12 de outubro em Joinville - SC"
- Instagram, TikTok e YouTube permitidos;
- participação no grupo oficial de WhatsApp é requisito operacional.

A arquitetura deve conseguir representar tudo isso SEM código específico para João.

CASO 2 — JUNINHO MANELLA

Requisitos conhecidos:

- hashtag #juninhomanella;
- marcar perfil oficial;
- foco do corte no Juninho Manella;
- divulgar kick.com/juninhomanella DENTRO DO PRÓPRIO CORTE;
- não apenas na legenda/título;
- múltiplas fontes de conteúdo autorizadas;
- grupo de WhatsApp obrigatório.

Novamente:
SEM lógica hardcoded para Juninho.

CASO 3 — GABEPEIXE

Já existe campanha no projeto.

A arquitetura deve permitir representar:

- asset/lower obrigatório;
- demais regras específicas;

sem criar condicionais específicas espalhadas pelo código.

CASO 4 — BRKK / BRABOX

Campanhas existentes devem continuar funcionando.

============================================================
23. REGRAS VIEWX
============================================================

Existem padrões compartilhados entre campeonatos da Viewx.

Porém:

NÃO assumir automaticamente que uma regra vale para todas as campanhas apenas porque apareceu em duas.

Precisamos separar:

VIEWX DEFAULTS CONFIRMADOS

de

OVERRIDES / REGRAS ESPECÍFICAS DA CAMPANHA.

Também separar claramente:

REGRA OFICIAL

de

ESTRATÉGIA EDITORIAL INTERNA.

Nunca inventar regra.

============================================================
24. VIEWX PROVIDER
============================================================

Futuramente queremos um provider/importador Viewx.

Fluxo desejado:

URL DO CAMPEONATO
→ OBTER REGULAMENTO/DADOS
→ EXTRAIR REGRAS
→ ESTRUTURAR
→ MOSTRAR AO OPERADOR
→ CONFIRMAÇÃO HUMANA
→ CRIAR/ATUALIZAR CAMPANHA

Queremos futuramente também um Radar Viewx:

- descobrir campanhas;
- identificar novas;
- comparar com campanhas existentes;
- mostrar prêmio;
- prazo;
- fontes;
- requisitos;
- permitir IMPORTAR.

IMPORTANTE:

NÃO implementar crawler/Viewx nesta primeira tarefa.

============================================================
25. SOURCE SCANNER
============================================================

Futuramente queremos aceitar:

- vídeo individual;
- VOD;
- playlist;
- canal YouTube;
- Twitch;
- Kick;
- outras fontes.

Para canais/playlists:

NÃO baixar tudo cegamente.

Primeiro coletar catálogo/metadados.

Classificar:

NOVO
JÁ ANALISADO
FORA DO PERÍODO
ELEGÍVEL
POSSIVELMENTE IRRELEVANTE

Depois selecionar o que será processado.

YouTube é particularmente importante para campanhas como João Pichau.

NÃO implementar Source Scanner nesta primeira tarefa.

============================================================
26. CENTRAL DE OPERAÇÃO
============================================================

Visão futura:

CENTRAL DE CORTES

João Pichau
- novos vídeos
- aguardando mineração
- cortes aguardando revisão

Juninho Manella
- novas fontes
- cortes aguardando revisão

GabePeixe
- novos VODs
- candidatos

Depois:

MELHORES OPORTUNIDADES GLOBAIS

92 João
90 Juninho
88 Gabe
...

A ideia é evitar que o operador precise decidir manualmente:

"qual VOD eu vou abrir agora?"

A ferramenta deve ajudar a priorizar trabalho.

NÃO construir esse dashboard completo agora.

============================================================
27. CONTROLE DE PRODUÇÃO
============================================================

Futuramente cada corte deve poder acompanhar:

ENCONTRADO
APROVADO
RAW GERADO
EDITADO
PUBLICADO TIKTOK
PUBLICADO SHORTS
PUBLICADO REELS

O objetivo é evitar duplicação e perda de controle ao operar muitos cortes/campeonatos.

Não implementar postagem automática nesta fase.

============================================================
28. DEDUPLICAÇÃO
============================================================

Já existe trabalho recente em group_refined.

Preserve esse comportamento e seus testes.

A deduplicação deve continuar evoluindo para impedir que diferentes candidatos representando o MESMO momento poluam a shortlist.

Mas não deve juntar momentos narrativamente diferentes apenas porque estão próximos no tempo.

Não altere isso nesta tarefa sem necessidade.

============================================================
29. COMPATIBILIDADE
============================================================

O projeto atual já possui componentes importantes que devem ser avaliados e reaproveitados, incluindo, entre outros:

- Flask;
- Waitress;
- SQLite;
- yt-dlp;
- FFmpeg;
- faster-whisper;
- campanhas existentes;
- pipeline local;
- pipeline remoto;
- VOD longa;
- checkpoints;
- previews;
- RAW;
- PREP;
- revisão editorial;
- deduplicação;
- feedback;
- testes existentes.

NÃO presuma que precisamos substituir algo antes de estudar sua implementação atual.

============================================================
30. CODEX + ANTIGRAVITY
============================================================

O desenvolvimento será realizado com colaboração entre Codex e Antigravity.

Função principal esperada nesta organização:

CODEX:
- implementação;
- refatoração;
- testes;
- migrations;
- integração.

ANTIGRAVITY:
- auditoria;
- revisão arquitetural;
- segunda opinião;
- busca de regressões;
- avaliação de edge cases;
- revisão editorial;
- proposta de testes adicionais.

NÃO queremos dois agentes alterando os mesmos arquivos simultaneamente.

A comunicação inicial será feita por arquivos dentro do repositório.

Criar:

docs/AI/PRODUCT_SPEC.md
docs/AI/TASK.md
docs/AI/CODEX_REPORT.md
docs/AI/ANTIGRAVITY_REVIEW.md
docs/AI/DECISIONS.md

============================================================
31. SIGNIFICADO DOS ARQUIVOS
============================================================

PRODUCT_SPEC.md

Deve conter a especificação consolidada do produto descrita neste prompt.

Ela será a fonte principal de verdade sobre o objetivo do produto.

------------------------------------------------------------

TASK.md

Deve conter:

- tarefa atual;
- escopo autorizado;
- fora de escopo;
- plano;
- critérios de aceite;
- status.

------------------------------------------------------------

CODEX_REPORT.md

Codex deve registrar:

- diagnóstico;
- arquivos analisados;
- alterações realizadas quando houver;
- decisões;
- testes;
- resultados;
- riscos;
- dúvidas;
- recomendações para próxima fase.

------------------------------------------------------------

ANTIGRAVITY_REVIEW.md

Será preenchido posteriormente pelo Antigravity.

NÃO inventar conteúdo em nome do Antigravity.

Pode criar o arquivo com template vazio.

------------------------------------------------------------

DECISIONS.md

Registrar decisões arquiteturais importantes para impedir que agentes futuros repitam discussões ou revertam decisões sem motivo.

============================================================
32. PROTOCOLO DE DESENVOLVIMENTO
============================================================

Antes de qualquer alteração funcional relevante:

1. entender a tarefa;
2. inspecionar implementação atual;
3. executar baseline;
4. registrar baseline;
5. identificar arquivos envolvidos;
6. criar backup quando aplicável;
7. implementar somente o escopo autorizado;
8. adicionar testes;
9. executar testes específicos;
10. executar suíte completa;
11. executar benchmark editorial quando aplicável;
12. comparar antes/depois;
13. atualizar documentação;
14. parar.

NÃO implementar "só mais uma feature" sem autorização.

============================================================
33. SEGURANÇA / DADOS
============================================================

Não:

- apagar banco;
- recriar banco sem migration;
- perder decisões humanas;
- apagar candidatos aprovados;
- quebrar campanhas existentes;
- invalidar caminhos existentes;
- destruir exports;
- modificar arquivos de mídia originais;
- fazer migrations destrutivas sem necessidade.

Mudanças de schema devem possuir estratégia explícita de migração/compatibilidade.

============================================================
34. O QUE VOCÊ DEVE FAZER AGORA
============================================================

ESTA É UMA TAREFA DE AUDITORIA E PLANEJAMENTO.

NÃO IMPLEMENTE O CLIP MINER V2 AGORA.

Primeiro:

1. Leia completamente a estrutura atual do TUTUCO-CLIP-MINER.

2. Inspecione os componentes relevantes do pipeline.

3. Entenda o banco/schema atual.

4. Entenda o pipeline:
   importação
   → transcrição
   → análise
   → candidatos
   → editorial
   → shortlist
   → preview
   → aprovação
   → export.

5. Entenda como campanhas atuais funcionam.

6. Entenda editorial_feedback.

7. Entenda group_refined e a deduplicação recente.

8. Entenda processamento de VOD longa.

9. Entenda testes existentes.

10. Execute a suíte atual COMPLETA para estabelecer baseline.

Se o comando Python global falhar mas existir .venv, utilize o Python da .venv.

11. NÃO altere código funcional.

12. Crie:

docs/AI/PRODUCT_SPEC.md
docs/AI/TASK.md
docs/AI/CODEX_REPORT.md
docs/AI/ANTIGRAVITY_REVIEW.md
docs/AI/DECISIONS.md

13. Coloque esta especificação consolidada em PRODUCT_SPEC.md.

14. Em CODEX_REPORT.md, faça uma GAP ANALYSIS:

Para cada grande componente do Product Spec:

- EXISTE
- EXISTE PARCIALMENTE
- NÃO EXISTE
- DEVE SER REAPROVEITADO
- DEVE SER ESTENDIDO
- DEVE SER CRIADO

15. Identifique dívida técnica que realmente afeta este roadmap.

Não faça refatoração estética.

16. Proponha roadmap incremental.

============================================================
35. ROADMAP A SER AVALIADO
============================================================

Não aceite cegamente esta ordem.

Analise o código e diga se faz sentido.

Hipótese inicial:

FASE 0
Documentação + baseline + benchmark foundation

FASE 1
Campaign Core

FASE 2
Semantic Reviewer

FASE 3
Smart Boundaries

FASE 4
Clip Package:
RAW + SRT + transcript + metadata + títulos

FASE 5
Gold Set + Benchmark Editorial robusto

FASE 6
Source Scanner / YouTube

FASE 7
Multimodal Reviewer

FASE 8
Viewx Provider / Radar

FASE 9
Personalização baseada em feedback

FASE 10
Central de Operação / Production Tracking

Analise dependências.

Se outra ordem for tecnicamente superior, proponha e JUSTIFIQUE.

============================================================
36. CRITÉRIOS PARA A GAP ANALYSIS
============================================================

Quero respostas específicas.

Evite frases genéricas como:

"precisamos melhorar a IA."

Quero algo como:

"miner/editorial.py já implementa X, mas não Y."

"store.py possui feedback persistido, porém nenhum consumidor usa esses dados para ranking."

"vod_mining.py pode ser reaproveitado como Candidate Finder."

"esta função já possui suggested_start/end e deve ser estendida em vez de duplicada."

Sempre que possível:

- arquivo;
- função/classe;
- responsabilidade atual;
- limitação;
- recomendação.

============================================================
37. CUSTO E PERFORMANCE
============================================================

Avalie explicitamente:

- processamento local;
- uso de CPU;
- uso de GPU;
- memória;
- disco;
- duração de VOD;
- chamadas externas;
- LLM;
- multimodal;
- cache;
- reprocessamento;
- checkpoints.

Queremos evitar arquitetura que mande uma VOD inteira para um modelo caro quando uma peneira local resolveria.

Preferir:

BARATO
→ BARATO
→ BARATO
→ CARO APENAS NOS FINALISTAS

============================================================
38. MÉTRICA PRINCIPAL DO PRODUTO
============================================================

A métrica norteadora é:

PUBLICABLE CUT RATE

ou seja:

"Quantos dos cortes que o sistema coloca no topo da shortlist
o operador realmente aprovaria/publicaria?"

Meta inicial para PRIORIDADE A:

>= 80% de aprovação humana.

Também acompanhar:

- recall editorial;
- precision;
- boundary accuracy;
- false positives;
- candidatos por hora de VOD;
- tempo de processamento;
- tempo humano economizado.

============================================================
39. RESTRIÇÃO IMPORTANTE SOBRE IA
============================================================

Alguns campeonatos proíbem o uso de plataformas de IA para GERAR automaticamente cortes.

Nosso produto mantém:

- revisão humana;
- aprovação humana;
- edição humana.

A ferramenta auxilia:

- descoberta;
- análise;
- organização;
- transcrição;
- sugestão;
- compliance.

Portanto, mantenha rastreabilidade de decisões e não desenhe arquitetura que elimine obrigatoriamente a participação humana.

============================================================
40. RESULTADO ESPERADO DESTA PRIMEIRA TAREFA
============================================================

Ao terminar, NÃO quero uma grande implementação.

Quero:

A) baseline completo dos testes;

B) PRODUCT_SPEC.md criado;

C) TASK.md com roadmap proposto;

D) CODEX_REPORT.md contendo:
   - arquitetura atual;
   - gap analysis;
   - componentes reaproveitáveis;
   - componentes novos necessários;
   - dívida técnica relevante;
   - riscos;
   - dependências;
   - ordem recomendada de implementação;

E) ANTIGRAVITY_REVIEW.md criado como template vazio;

F) DECISIONS.md criado;

G) confirmação explícita de que nenhum código funcional foi alterado;

H) lista dos arquivos criados/alterados;

I) recomendação da PRIMEIRA tarefa pequena e implementável.

============================================================
41. NÃO FAÇA AINDA
============================================================

NÃO implementar ainda:

- Semantic Reviewer;
- Smart Boundaries novo;
- integração com LLM;
- multimodal;
- crawler Viewx;
- Source Scanner;
- Campaign Core novo;
- dashboard novo;
- aprendizado;
- postagem;
- edição automática;
- alterações no ranking;
- migrations;
- refatorações grandes.

Primeiro planejar.

============================================================
42. HANDOFF
============================================================

Quando terminar:

PARE.

Não continue para implementação.

O relatório será revisado externamente e depois por outro agente (Antigravity).

A próxima tarefa será fornecida somente após essa revisão.

============================================================
43. PRINCÍPIO FINAL
============================================================

Não estamos construindo um detector de picos.

Não estamos construindo um editor automático.

Estamos construindo:

UM SISTEMA QUE ENCONTRA CORTES QUE UM EDITOR HUMANO REALMENTE QUER PUBLICAR.

O sucesso não é:

"geramos 50 candidatos."

O sucesso é:

"abri a primeira página e quase tudo ali era corte de verdade."

Comece pela leitura completa do projeto, execute o baseline e produza a documentação/auditoria solicitada.

NÃO implemente funcionalidades ainda.