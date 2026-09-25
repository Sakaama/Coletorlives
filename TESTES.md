# Validação local — TUTUCO CLIP MINER V1

## Garimpo VOD contextual

Baseline antes de editar: **51 testes Python + 4 JavaScript**, lint aprovado. Final: **62 testes Python + 4 JavaScript**, lint aprovado. Reanálise real dos mesmos 20 minutos do GabePeixe: **52 anteriores → 3 atuais no Equilibrado**; os 52 anteriores foram preservados no histórico. Comparação offline: Conservador 2, Equilibrado 3, Agressivo 4. Ver `VOD-GARIMPO.md` para alterações, ajustes de testes ao novo comportamento, limitações e passos exatos de reprodução.

## Ambiente de execução do yt-dlp

Após padronização da chamada para o Python do `.venv` com `-m yt_dlp`: **51 testes Python e 4 JavaScript passaram**. Ruff e sintaxe JavaScript passaram. Resultado em `test-results/cli-env-1/`. A suíte preserva as verificações das três campanhas e do fallback 404; seis casos novos em `tests/test_ytdlp_cli.py` verificam ambiente, argumentos e subprocesso. A consulta real pela API do servidor, iniciado no contexto normal de rede, recebeu 404 e acionou o fallback existente. Diagnóstico e comparação de executável, cwd, env, PATH, proxy e flags em `DIAGNOSTICO-YTDLP.md`.

## Correção específica Kick VOD 404

Validação concluída: **45 testes Python passaram**, preservando os 31 anteriores, e **4 testes JavaScript passaram** (`node --test tests/test_kick_ui.cjs`). Ruff e `node --check static/app.js` passaram. Testes Python em `test-results/kick404-1/`.

A apresentação da API detecta conjuntamente `kick:vod` e `HTTP Error 404` em tarefas com erro, inclusive registros anteriores, mantendo o diagnóstico original no banco. Informa incompatibilidade temporária do extrator yt-dlp para VODs da Kick e oferece **Importar arquivo local** junto à mensagem. A ação reutiliza a vinculação existente à mesma VOD; o botão desaparece após vincular o arquivo e fica desabilitado durante trabalho ativo.

Testados erros controlados nas etapas de metadados e download, nas três campanhas; preservação de URL, título, arquivos e aprovação; vinculação local sem duplicar a VOD; e ausência dessa mensagem especial para 403, 500, timeout, YouTube 404 ou Kick live 404. Sem tentativas de contornar proteção, sem downloader novo e sem chamadas à Kick durante a validação.

## Extensão incremental BRABOX

Após o adendo: **31 testes existentes no total, 31 passaram**, incluindo os **11 testes originais sem alterações** e 20 casos novos em `tests/test_brabox.py`. Execução: `pytest -q --basetemp=test-results/brabox-1` (5,32 segundos). Ruff e verificação de sintaxe JavaScript também passaram.

Verificados: carregamento das três campanhas pela API existente; fontes Twitch/Kick; rejeição de URLs de canais/clips Twitch e YouTube para BRABOX; hashtag e texto obrigatório; período exato registrado e divergência exigindo revisão humana em datas ausentes, inválidas, dentro e fora do período; conteúdo excluído e fontes proibidas; metadados desconhecidos não tratados como comprovação de vídeo editado; câmera persistida por VOD; aprovação obrigatória; PREP BRABOX real em 1080×1920; hashes do RAW e original preservados. GabePeixe e BRKK continuam passando nas regras, extrações e presets anteriores.

Não foram fornecidas URLs de VODs reais do Brabox para validar download Twitch/Kick nesta extensão. Importação remota usa o extrator yt-dlp existente, testado aqui com metadados controlados; PREP foi testado com vídeo real de fixture. Não há nova dependência, alteração de esquema SQLite, integração de publicação ou refatoração do pipeline. As datas anteriores divergentes, @ oficial e assets não foram inventados.

O relatório abaixo preserva o histórico da validação inicial da V1.

Execução nesta máquina em 18/09/2026. Projeto: `D:\Projetos\TUTUCO-CLIP-MINER`.

## Ambiente e dependências

- Windows, Python 3.12.10, FFmpeg/ffprobe 9.0.1 e Node 24.19.0 já instalados.
- NVIDIA GeForce GTX 1650, 4 GB, detectada. Transcrição validada em CPU.
- Instalados no ambiente virtual do projeto: Flask 3.1.3, Waitress 3.0.2, yt-dlp 2026.8.19 com extras oficiais (EJS 0.8.0), faster-whisper 1.2.1, NumPy 2.5.3, pytest 9.1.1, Ruff 0.16.8 e dependências transitivas.
- Modelo Whisper Base baixado para `models/`. Nenhuma VOD de várias horas foi baixada.
- Versões completas: `requirements-lock.txt`. `pip check`: sem dependências quebradas.

## Resultado

**11 testes automatizados passaram (3,82 segundos na execução final).**

| Verificação | Resultado |
|---|---|
| URLs aceitas, normalização e rejeição de domínios/links inválidos | Passou |
| Datas-limite das duas campanhas, fonte, identidade desconhecida e exclusão Cinefy | Passou |
| Picos de energia sem fala e cobertura exploratória de 5 horas sintéticas | Passou |
| Validação de números, margens e região fora do quadro | Passou |
| Importação de vídeo real de fixture, ffprobe e diretórios por campanha | Passou |
| Extração real de áudio e análise de energia | Passou |
| Preview e RAW de 3 segundos; resolução e duração conferidas | Passou |
| PREP BRKK e GabePeixe (placeholder) em 1080×1920 | Passou |
| Hashes do original e RAW intactos após exportação | Passou |
| SQLite, decisões preservadas, fonte conhecida e possível duplicata | Passou |
| API, bloqueio de requisições sem token/origem indevida | Passou |
| Retomada de checkpoint de transcrição concluída | Passou |
| Falha controlada do extrator preservando VOD e registrando erro | Passou |
| Metadados controlados priorizam data da live sobre upload | Passou |
| Recuperação de tarefa interrompida e bloqueio de segunda instância | Passou |
| Ruff, compilação Python, sintaxe JavaScript | Passou |

Os resultados de fixtures estão em `test-results/run4/`. A tabela detalha verificações agrupadas dentro dos 11 testes, não testes adicionais.

## Testes reais adicionais

1. **Whisper Base em CPU:** inferência real em áudio sintético curto produzido localmente pelo FFmpeg. Foram gerados segmentos com timestamps em JSON e TXT. A fala sintética é em inglês, mas a configuração da V1 espera português; houve transcrição em português com erros. Isso valida execução do modelo e persistência, **não qualidade em lives brasileiras**. O sintetizador do Windows não tinha vozes disponíveis; foi usado o sintetizador Flite do FFmpeg.
2. **YouTube:** consulta de metadados e download de `Me at the zoo`, vídeo público de 19 segundos. O primeiro teste exigia uma faixa combinada que não estava disponível; o teste foi ajustado para combinar faixas separadas. O caminho de produção do aplicativo (`Service.metadata` e `Service.download`) também passou, em banco separado em `test-results/network-pipeline/`. Resultado conferido: 320×240, áudio presente, aproximadamente 19 segundos.
3. **Aplicativo iniciado de verdade:** servidor Waitress em `http://127.0.0.1:8765`, página e API acessíveis pelo navegador local.
4. **Fluxo pelo navegador:** importar fixture → analisar com transcrição → abrir preview no player → selecionar/aprovar → extrair RAW → gerar frame → salvar câmera → gerar PREP. Todas as tarefas concluídas. Links RAW e PREP visíveis.
5. **Reinício:** aplicativo reiniciado, VOD e aprovação recuperadas na biblioteca. Nova tentativa de inicialização detectou a instância existente sem reiniciar tarefas.
6. **Inspeção visual:** tela inicial e frame do PREP conferidos. Câmera em cima, texto `kick.com/brkk` dentro do vídeo, conteúdo embaixo, proporção preservada. Console do navegador sem erros/avisos na checagem final.

A demonstração inicial foi removida da biblioteca no reset de fechamento V1. Sua fixture automatizada foi preservada.

## Correções encontradas durante a validação

- Fonte explícita do Windows para o texto do PREP: FFmpeg não encontrou configuração Fontconfig padrão na primeira tentativa.
- Componentes oficiais EJS e Node habilitados para extração atual do YouTube.
- Corrida de atualização do preview quando o processamento termina muito rápido.
- Biblioteca acessível também na janela estreita do navegador.
- Trava de instância para impedir que uma segunda abertura marque tarefas da primeira como interrompidas.

## Ainda não validado

- Download de uma VOD real da Kick: não foi fornecida uma URL de gravação para esse teste.
- Mineração de uma live real em português de GabePeixe/BRKK, com comparação humana dos momentos encontrados.
- Processamento completo de VOD com várias horas: a cobertura de 5 horas foi testada com dados sintéticos; consumo/tempo de uma VOD extensa ainda precisam de medição.
- Aceleração CUDA/cuDNN; modelos Tiny e Small; qualidade de transcrição em áudio ruidoso ou múltiplos interlocutores.
- Asset gráfico oficial GabePeixe, não fornecido; validado apenas o placeholder textual.
- Seleção do arquivo pelo diálogo nativo e arraste visual da câmera: a importação por caminho e o salvamento de coordenadas foram exercitados. A seleção visual está implementada.
- Casos especiais HDR, anamórfico, rotação ou mudança de resolução durante a gravação.

## Próximo teste real

Usar uma gravação ou trecho de **10–20 minutos em português** de uma das campanhas, com origem/data conhecidas e câmera visível. Analisar em Base/CPU, revisar os candidatos, conferir um momento que você já sabe onde acontece, aprovar e extrair 2–3 RAWs. Em seguida ajustar a câmera e gerar um PREP. Isso mede a utilidade real da seleção antes de processar uma VOD de várias horas.


## Fechamento V1 — 19/09/2026

Baseline: **75 Python (9,31 s), 8 JavaScript, Ruff aprovado**. Final: **94 Python (8,52 s), 11 JavaScript, Ruff, compileall e sintaxe JS aprovados**. Relatório consolidado: `test-results/v1-report.json`.

Novos cenários: chunks e cauda fracionária; 06:00:00 + 00:17:42; evento atravessando chunks; deduplicação entre chunks; ranking global; reinício após interrupção com reaproveitamento do primeiro chunk; retry independente de região; cache hit; mudança de fonte/config/modelo; 12 h simuladas sem transcrição profunda em silêncio; Fast Scan não cria candidatos; talking excepcional e bônus visual preservados; PCM de proxy atravessando chunks sem mudar duração; argumentos absolutos de download por intervalo; 1080p30/720p60 não identificados como 1080p60; fallback local mantendo aprovação e limites; falhas de carga/inferência CUDA caem para CPU; reset recusa arquivos/banco alterados e preserva campanhas/configuração/originais externos; UI mostra tempos e RAW remoto só por opção explícita.

### Benchmark comparável em CPU Base/int8

Trecho real inicial de **600,005 segundos** da VOD local GabePeixe, remux sem recodificação. Comparação fria e cache na mesma máquina, sem alteração da biblioteca. Dados brutos arquivados em `backups/v1-diagnostics/v1-benchmark-release/report.json`.

| Etapa | Anterior frio | VOD Longa frio |
|---|---:|---:|
| Áudio | 0,579 s | 0,603 s |
| Energia / Fast Scan | 0,026 s | 0,027 s |
| Visual | 8,016 s | 8,008 s |
| Transcrição | 40,484 s | 57,094 s |
| Análise contextual | 0,032 s | 0,022 s |
| Deduplicação de segmentos | — | 0,0015 s |
| Ranking | <0,001 s | <0,001 s |
| Total | **49,137 s** | **65,765 s** |
| Total com cache | **0,019 s** | **0,030 s** |

VOD Longa: 1 região promissora, 2 unidades profundas, 345,005 s de núcleo selecionado (57,5% da amostra), além de contexto e sondagem curta. 1 candidato; anterior 0. Mudança de contexto/chunk pode mudar a transcrição e a seleção; **não é demonstração de melhor qualidade editorial**. A primeira execução seletiva ficou mais lenta neste caso; não há alegação de aceleração universal. O cache reutilizou scan/visual e as duas transcrições profundas.

GTX 1650/4 GB: CPU carregou Base em 1,13 s e inferiu o áudio sintético em 1,41 s (2 segmentos). CUDA falhou após 0,87 s por DLL cuBLAS ausente; não foi instalada pilha CUDA. Resultado em `test-results/v1-gpu.json` e relatório consolidado. Testes de 12 h usam sinais simulados; ainda não foi feita inferência real de uma VOD inteira de 12 h.

### Integração remota real

any-dl 4.1.0 instalado, VOD Kick já usada nos testes: solicitado **00:17:40–00:18:10**. Apenas intervalo baixado: aproximadamente 34,7 MB, **1920×1080, ~60 fps, 30,050 s**, seguido de RAW H.264/AAC. Resultado/sidecar/log em `backups/v1-diagnostics/v1-range/`. Precisão limitada a keyframes foi informada. Não foi implementado acesso próprio à plataforma. Testes existentes de Preview, RAW, PREP nas campanhas e preservação do original continuam passando.

### Reset final

Backups: `backups/v1-before-20260919/` e `backups/v1-final-20260919/`, com SQLite íntegro e SHA-256 conferidos. Removidos 4 registros de VOD de teste e suas pastas operacionais, candidatos, jobs, previews, RAW/PREP, transcrições/cache associados e o import conhecido de 20 minutos. Banco final: **0 VODs, 0 candidatos, 0 exports, 0 jobs**. Manifesto exato em `backups/v1-final-20260919/reset.json`.

Os dois originais locais de 1 h em `TUTUCO-TV/02_VODS/GABEPEIXE` foram preservados, pois não foi comprovado que suas mídias eram descartáveis. Seus registros operacionais foram arquivados no backup e retirados da biblioteca conforme o reset solicitado. Configurações/campanhas e arquivos das áreas protegidas conferidos por hash; estrutura TUTUCO-TV, modelos e fixtures automatizadas intactos. Artefatos desta rodada foram movidos para `backups/v1-diagnostics`, fora da biblioteca.

## Remote Collector — 20/09/2026

Baseline anterior às mudanças: **94 Python em 9,99 s; 11 JavaScript; Ruff e sintaxe aprovados** (`test-results/remote-baseline.json`). Na retomada, a execução que havia ficado pendente terminou com **117 Python em 12,73 s; 14 JavaScript; Ruff, compileall e sintaxe JS aprovados**.

Os 23 novos casos Python e 3 JavaScript cobrem descoberta/período/deduplicação por URL e ID, incremental 18→19, exclusão de VOD concluída, campanhas preservadas, URL manual/erro de provider, checkpoint antes da limpeza, órfãos, pouco disco, timestamps e transcrição absoluta, cache, interrupção/resume, zero quota, ranking agregado, revisão múltipla, pacote editorial/histórico, fila/cancelamento, margens/nome/destino, 1080p60 real versus 1080p30/720p60, fallback explícito, .venv/cwd/env, encerramento da árvore do processo cancelado, origem local e proteção da API. Integração FFmpeg: Preview/RAW/frame/PREP sem vídeo integral, RAW intacto após PREP, saída vertical 1080×1920.

Teste público controlado aprovado (`test-results/remote-real/report.json`): descoberta/metadata de Kick, análise remota 600–780 s mais contexto (região profunda 495–870 s), 2 candidatos, análise fria 81,10 s, cache 0,063 s. RAW 616,90–771,75 s: 154,85 s medidos, 1920×1080/60 fps/H.264, 63.888.505 bytes. Temporários zerados depois da análise e do RAW. Não foi baixada VOD integral. RAW aprovado de teste preservado em `test-results/remote-real/TUTUCO-TV/04_RAW/GABEPEIXE/`, fora da biblioteca. Relatório de descoberta BRKK: `test-results/remote-discovery-real.json`; as três amostras possuem Cinefy e as regras continuam bloqueando esse material.

Banco operacional e backup anterior: `PRAGMA integrity_check = ok`. Nenhum registro anterior foi removido. As tabelas Remote são aditivas. Campanhas/configuração e originais locais preservados. UI conferida em banco isolado; pacote editorial salvo, filtros e candidato/RAW acessíveis. Detalhes e limitações em `REMOTE-COLLECTOR.md`.

Fechamento da retomada: **117 Python em 11,83 s, 14 JavaScript**, Ruff/compileall/sintaxe aprovados novamente após cobrir também o descarte de WAV recriável em erro com checkpoint. Resumo consolidado em `test-results/remote-final-report.json`.


## Correção de elegibilidade por trecho — 20/09/2026

Baseline antes desta correção: 117 Python aprovados (12,03 s). Final: **126 Python (12,21 s), 16 JavaScript**, Ruff/compileall/sintaxe aprovados. Regressões: título “A VOLTA ... !CINEFY !APP” não bloqueia; período/origem concretamente excluída continuam protegidos; sincronização remove bloqueio antigo sem reabrir VOD concluída; VOD válida continua processável enquanto candidato com indício textual recebe REVISÃO DE ELEGIBILIDADE; react, gameplay, atividade visual e promoção não inferem filme/série; aviso aparece nas duas listas preservando Preview/Aprovar/Descartar. As expectativas antigas de bloqueio por título foram atualizadas para a regra solicitada.

Sincronização real da campanha BRKK existente: 0 novas, 2 atualizadas; 2 VODs/21,6439 h; 0 bloqueadas, 2 pendentes, nenhuma processada. Somente tarefa sync criada. Banco anterior protegido por backup validado (caminho registrado em `test-results/eligibility-resync.json`). Nenhum RAW, original ou histórico apagado.

## Revisor editorial e shortlist — 21/09/2026

Baseline: 126 Python / 16 JavaScript. Final: **143 Python / 19 JavaScript**, lint e sintaxe aprovados. Os 129 candidatos BRKK foram revisados pelo cache: 4 recomendados, 9 bons, 115 talvez e 1 fraco; **12 momentos distintos na shortlist**, agrupando dois intervalos refinados iguais sem apagar originais. As 21,6 h não foram mineradas novamente. Relatório, arquivos, limitações, tempos e passos de teste em [EDITORIAL.md](EDITORIAL.md).
