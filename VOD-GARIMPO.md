# Garimpo contextual — rodada VOD Mode

## 1. Baseline inicial

Executado antes de qualquer alteração: **51 testes Python aprovados (5,74s)**, **4 testes JavaScript aprovados**, Ruff e sintaxe JavaScript sem erros. Registro inicial em `test-results/vod-mining-baseline.md`. A VOD de GabePeixe tinha 1200,004666 segundos, 185 segmentos de transcrição Base e 52 candidatos NOVO.

## 2. Alterações

- `miner/vod_mining.py`: detector heurístico com agrupamento temporal, deduplicação, limites de contexto e duração variável. Agrupa sinais até 18 segundos de distância, respeitando novos hooks após payoff; janelas com sobreposição relevante são fundidas. Fusão limitada a 150 segundos evita encadear uma live inteira. Uma pequena sobreposição de contexto pode permanecer entre eventos diferentes.
- `miner/analysis.py`: mantém transcrição e energia existentes e encaminha a detecção ao módulo de VOD.
- `miner/service.py` e `miner/store.py`: modo escolhido persistido por VOD; a nova seleção substitui atomicamente a anterior, sem excluir candidatos, status ou arquivos do histórico. Repetir o mesmo resultado mantém ID/status e não cria novas cópias.
- `app.py`, `templates/index.html` e `static/app.js`: seletor Conservador/Equilibrado/Agressivo e opção de incluir histórico. Motivos positivos e penalizações nos cartões. Preview → Aprovar/Descartar → Extrair RAW permanece igual.
- Testes novos em `tests/test_vod_mining.py`; testes antigos de cobertura automática/silêncio ajustados ao comportamento solicitado. Fixtures de exportação são inseridas explicitamente nos testes de mídia, para que um tom sintético ou vídeo sem áudio não precise ser falsamente classificado como conteúdo interessante.

Modos: Conservador exige score 74; Equilibrado, 56; Agressivo, 38. Picos sem fala só aparecem no Agressivo, com score 12. Não há quota, amostragem periódica obrigatória ou teto global de oito candidatos. Sinais textuais têm pesos de 12–20 pontos por categoria, sem acumulação por repetição da mesma palavra; pico contextual soma no máximo três pontos. Penalizações incluem ausência de payoff, contexto limitado, silêncio/pouca fala, repetição, marcadores de música/ruído/inaudível e baixa confiança quando esses metadados existem. O Whisper/cache existente não foi alterado; transcrições antigas não possuem métricas de confiança, portanto usam os indicadores textuais disponíveis.

Sem ML novo, dependências novas, templates, publicação, any-dl, mudança de framework ou mudanças em Live Mode. Configurações GabePeixe/BRKK/Brabox, importação, tratamento Kick 404, RAW e PREP preservados.

## 3. Testes finais e amostra real

**62 testes Python aprovados (6,81s)**, **4 testes JavaScript aprovados**. Ruff e sintaxe JavaScript passaram. Resultados em `test-results/vod-mining-2/`.

Cobertura: janelas sobrepostas/duplicadas, segmentos duplicados sem inflar score, eventos próximos com ou sem conclusão, durações de 18 e 65 segundos, três modos, seis eventos em 20 minutos, ausência de quota (zero/um/onze eventos), picos isolados, música/ruído sugeridos, silêncio e payoff ausente. Reanálise nas três campanhas preserva decisões/arquivos e não acumula candidatos ativos.

Comparação offline com exatamente o áudio/transcrição existentes da VOD:

| Modo | Candidatos |
|---|---:|
| Detector anterior | 52 |
| Conservador | 2 |
| Equilibrado | 3 |
| Agressivo | 4 |

Depois, uma reanálise real via API do aplicativo em Equilibrado concluiu com 3 candidatos atuais; 52 antigos continuam no histórico, totalizando 55 registros, sem exclusão. Não houve novo download ou transcrição. A interface foi aberta e conferida com os três modos, três candidatos e histórico desmarcado.

Intervalos atuais, relativos ao arquivo de 20 minutos: 08:31,82–10:25,58; 10:17,24–12:46,76; 17:41,60–20:00,00. Durações aproximadas: 114, 150 e 138 segundos, antes das margens de exportação.

## 4. Limitações

A redução da contagem não certifica que os três cortes são bons. Nenhum foi aprovado automaticamente. A transcrição da amostra contém erros e trechos aparentemente musicais. Os três selecionados não possuem payoff textual explícito; isso foi penalizado e está visível. O último termina no limite do arquivo: sua conclusão pode estar na parte seguinte da VOD. É necessário assistir aos previews.

Agrupamento e contexto são aproximações por tempo e vocabulário, sem compreensão semântica nem classificação real de música. Podem juntar assuntos próximos ou perder momentos sem fala. Pergunta/resposta é apenas possível sequência de falas, não identificação de interlocutores. Dois eventos desta amostra compartilham cerca de oito segundos de contexto; as margens de preview podem ampliar essa sobreposição. Episódios longos podem chegar a 150 segundos. O histórico pode conter sobreposições antigas por ser preservado intencionalmente.

## 5. Repetir exatamente o teste

1. Inicie `iniciar.bat`, se necessário, e abra `http://127.0.0.1:8765`. Atualize a página para carregar os controles novos.
2. Na biblioteca, abra **Aguardando metadados — GabePeixe · 00:20:00**. Confira o ID **GABEPEIXE_2026-09-18_9f13f93df8**. Esse é o registro existente com o arquivo local já vinculado; não use Atualizar metadados nem importe outra cópia.
3. O arquivo vinculado é `data/imports/gabepeixe - 2026-09-17 - A VOLTA DO MINECRAFT ZERANDO PERDEMOS TUDO.mp4`, dentro do projeto, com 20 minutos.
4. Selecione **Áudio + transcrição**, **Base · equilibrado**, **CPU · compatível**, **Equilibrado · recomendado**.
5. Clique **Analisar VOD** e aguarde **CONCLUÍDO**. A transcrição/energia prontas serão reutilizadas.
6. Deixe **Incluir histórico de análises anteriores** desmarcado e o filtro em **Todos os status**. A referência observada é **3 candidatos atuais**; o aviso antigo de 52 no histórico de tarefas não representa a seleção atual.
7. Mantenha pré-roll e pós-roll em 5 segundos. Abra **Preview**, confira contexto e fim, e **Aprove** ou **Descarte** cada candidato.
8. Selecione somente os aprovados e clique **Extrair RAW**. As margens são aplicadas pelo fluxo existente. Nenhum PREP substitui RAW.
9. Para comparar modos, troque somente **Modo de garimpo** e repita **Analisar VOD**. Com a mesma transcrição, a comparação atual produziu Conservador 2, Equilibrado 3 e Agressivo 4. A seleção anterior vai para o histórico; intervalos idênticos preservam suas decisões.


# Fechamento V1 — pipeline VOD Longa (19/09/2026)

## Arquitetura incremental

Vídeo local/proxy → scan de chunks de 600 s → regiões promissoras → transcrição seletiva com contexto → segmentos absolutos → deduplicação/agrupamento global → ranking global → revisão humana → RAW.

Acima de 1800 s é automático. Vídeos curtos preservam a seleção anterior; a API aceita `pipeline: "long"` para benchmark. Não há quota por hora, Top 10 forçado ou redução de limiar para preencher candidatos. O detector contextual e os três modos existentes permanecem.

`miner/long_vod.py` contém parâmetros nomeados em `CONFIG`: células de 60 s, contexto de 45 s, núcleos profundos de até 300 s. Scan extrai PCM mono 16 kHz por chunk e mede RMS por segundo. A camada visual existente amostra pares 160×90 separados por 1 s a cada 20 s; FFmpeg busca diretamente os pontos, sem decodificar uniformemente a VOD toda. Movimento uniforme não basta: a célula deve ter mudança de atividade (máximo ≥60 e amplitude ≥20) e áudio audível, ou variação sustentada de áudio (três segundos acima de 2,5× a mediana e piso 0,015). Essas regras propõem regiões, não candidatos.

Fala estática tem uma via adicional: sondagem de até 30 s por bloco de 5 min audível que ainda não esteja inteiramente coberto. Usa o mesmo Whisper já instalado; se o detector encontra sinais no modo exploratório, expande contexto para análise profunda. Pode perder falas excepcionais entre as sondagens; não existe garantia de cobertura editorial total. Regiões de silêncio podem ter zero transcrições profundas e zero candidatos.

Regiões se unem antes da transcrição. Cada núcleo profundo tem contexto dos dois lados. O áudio da região é recortado dos WAVs de scan já prontos, sem nova decodificação de vídeo, inclusive ao atravessar fronteiras; fallback de extração direta existe quando um chunk de áudio não está disponível. Segmentos mantêm offset absoluto e pertencem ao núcleo pelo ponto médio. Falas muito semelhantes/sobrepostas são deduplicadas e o detector é executado UMA vez sobre toda a VOD, preservando clustering e motivos existentes.

Ranking: limiares e pesos textuais em `miner/vod_mining.py`; peso visual explícito `MAX_BOOST = 8` em `miner/visual_activity.py`, aplicado APÓS a seleção. Média das amostras do candidato, 0–100; HIGH ≥60, MEDIUM ≥25, LOW abaixo disso. Sem amostra = não medido. Tela estática não elimina candidatos. Áudio exploratório isolado não ganha bônus visual. Não se reconhecem jogos, cartas, vídeos ou payoff visual: são aproximações por texto e movimento.

## Checkpoint, retomada e invalidação

Pasta: `data/campaigns/<campanha>/transcripts/<VOD>/long/<assinatura>/`.

| Resultado | Retomada / invalidação |
|---|---|
| Namespace de aquisição | Caminho absoluto, tamanho, mtime_ns, duração, versão do pipeline, tamanho do chunk e versão/resolução/intervalo visual |
| `scan_N/audio.wav`, `energy.json`, `visual.json`, `complete.json` | Chunk concluído reutilizado; erro não publica `complete.json`; reanálise tenta novamente |
| `plan_<hash>.json` | Configuração de Fast Scan, modelo e opção de transcrição; alterar modo editorial não invalida |
| `speech_<início>_<fim>/audio.wav` | Mesmo intervalo/fonte reutiliza PCM; recortado dos chunks prontos |
| Transcrição por modelo | Arquivos já existentes do Whisper, checkpoint a cada 300 s; modelo diferente ganha pasta distinta. CPU/GPU reutilizam resultado válido |
| Ranking | Recalculado barato a cada análise; modo e peso visual não obrigam nova inferência |
| `checkpoint.json` / `result.json` | Etapa, erros recuperáveis com intervalos, parâmetros, regiões, resultados e tempos |

Cada escrita JSON é publicada atomicamente. Uma interrupção preserva chunks anteriores e checkpoints Whisper. Ao reiniciar, a tarefa aparece como interrompida; clique **Analisar VOD** novamente. Falhas regionais são registradas e outras regiões continuam. Uma análise parcial sem candidatos preserva a seleção anterior. Com resultados parciais, a interface informa incompletude e mantém o histórico anterior. Parciais FFmpeg podem repetir apenas sua etapa incompleta. Não há ETA inventada; progresso mostra etapa, chunk/região e tempo decorrido.

Não altere um arquivo local durante a análise. Os caches legados de vídeos curtos continuam usando o comportamento anterior e pressupõem original imutável. Fonte substituída deve ser importada como novo registro. Nenhum cache depende de GPU para ser lido.

## Timestamp, proxy e RAW

Todos os offsets internos são somados ao tempo do ARQUIVO ORIGINAL analisado. Exemplo: 06:00:00 + 00:17:42 = 06:17:42. Preview/RAW recebem esse intervalo absoluto, com pré/pós-roll limitado à duração. Proxy completo pode ser 720p60; análise visual é reduzida em memória e não cria proxy de vídeo adicional. Não é necessário 1080p60 para minerar.

RAW remoto é opt-in por extração: URL válida de VOD e confirmação de que o proxy começa no zero da mesma VOD, sem cortes. Proxies que são apenas uma hora de uma transmissão maior devem usar RAW local; não inferimos offset pelo nome. Kick/Twitch: CLI pública `any-dl 4.1.0`, opções `--quality 1080p60 --from ... --to ... --output ... --yes --progress none`. YouTube: yt-dlp do `.venv`, `--download-sections`, qualidade estrita e `--force-keyframes-at-cuts`. Nenhum downloader ou acesso à plataforma foi reimplementado. Sem modificações de proxy, PATH ou proteção de rede.

O RAW remoto é validado por resolução, fps e duração e recodificado em H.264 CRF16/AAC. Ausência de 1080p60 ou falha produz aviso explícito e fallback local; não inventa detalhes nem interpola quadros. O any-dl não garante precisão de frame: keyframes podem deslocar alguns segundos. Os limites solicitados e mídia obtida ficam no JSON ao lado do RAW. O operador deve conferir o resultado. O PREP converte coordenadas do proxy para a resolução efetiva do RAW.

## Backup e reset operacional

Feche o app. `scripts/reset_operations.py --backup <pasta-nova>` faz backup SQLite consistente, `integrity_check`, cópia dos dados e hashes SHA-256 verificados. Não exclui nada por padrão. Para resetar, acrescente `--apply --ids <ID1> <ID2> ...`; cada ID deve ser previamente identificado como teste. Opcional `--test-source <caminho>` só aceita arquivos conhecidos de teste dentro de `data/imports`. O script exige biblioteca inativa e verifica que o banco/arquivos ainda correspondem ao backup antes de apagar.

Remove apenas registros dos IDs selecionados e suas pastas operacionais conhecidas. Código, config, modelos, testes, Git (se existir) e TUTUCO-TV não são alvos. Arquivos originais externos ficam preservados. Links/junctions, caminhos fora do escopo, backup alterado ou dados novos fazem o reset recusar a exclusão. Mantenha o backup: para restaurar, feche o app e restaure banco e pastas correspondentes, respeitando caminhos dos originais.

## Benchmark reproduzível e limitações

Execute com o app ocioso e uma pasta de saída NOVA:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_long_vod.py "D:\Lives\vod.mp4" --seconds 600 --output test-results/benchmark-novo
.\.venv\Scripts\python.exe scripts/benchmark_gpu.py
```

O script extrai um trecho inicial por remux (sem recodificar), executa anterior e VOD Longa, cada um frio e com cache, e salva tempos por etapa, duração, regiões, candidatos e CPU. Não escreve na biblioteca operacional. Áudio/visão baratos continuam percorrendo toda a duração por chunks/amostras; transcrição completa é seletiva. Em material uniformemente movimentado/ruidoso ou rico, regiões podem se unir e boa parte da VOD ser analisada; não há teto artificial para esconder isso. Mais contexto e recarregamentos de Whisper podem tornar a primeira execução mais lenta em amostras curtas. Não afirmar ganho de velocidade antes de medir a VOD real.

GTX 1650, 4096 MiB, driver 596.49; CTranslate2 4.8.2 detecta CUDA, mas inferência falhou por `cublas64_12.dll` ausente. CPU Base/int8: carga 1,13 s + inferência 1,41 s no áudio sintético curto (2 segmentos). GPU: erro após 0,87 s. Testado em subprocessos isolados; não foi instalada pilha CUDA. CPU permanece padrão, com fallback CUDA → CPU testado para falha de carga/inferência.

A suite inclui execução orquestrada de 12 horas com sinais simulados, não inferência real de 12 horas. A qualidade editorial dos candidatos exige revisão humana. Não há reconhecimento visual semântico, tradução, diarização nem garantias de recall. O fechamento não adiciona Live, cloud, templates, publicação ou quotas.


## Resultado final desta rodada

94 testes Python, 11 JavaScript, lint e sintaxe aprovados. Benchmark final: anterior frio 49,14 s; VOD Longa frio 65,77 s; cache longo 0,030 s. Núcleo profundo 345 s de 600 s, 1 região/2 unidades, 1 candidato contra 0 no anterior. Não demonstra superioridade editorial nem aceleração em VODs reais de 12 h. Tabela completa e reset em `TESTES.md`; dados consolidados em `test-results/v1-report.json`.

O procedimento de repetição de 20 minutos descrito no histórico acima refere-se à rodada anterior: essa VOD de teste já saiu da biblioteca. Ela está preservada no backup final para diagnóstico; a operação atual começa vazia.
