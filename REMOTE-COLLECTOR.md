# Remote VOD Collector / Campaign Miner

Camada incremental sobre a V1: campanha/canal/período → descoberta → pendências → trechos temporários → candidatos → revisão → RAWs aprovados. Não é Live Mode. Não modifica os regulamentos em `config/campaigns`.

## Uso com BRKK

1. Abra `http://127.0.0.1:8765/` e clique em **Campanhas / Remote**.
2. Selecione **Nova campanha operacional**, criador **BRKK**, provider **Kick**, canal **brkk**. Informe início e fim do período desejado e clique **Salvar campanha/período**. A configuração oficial existente permite lives a partir de **15/09/2026** e não define data final. O exemplo 01/09–01/10 é um filtro operacional, não uma alteração do regulamento. Twitch não é uma fonte habilitada para BRKK na configuração atual.
3. Clique **Sincronizar VODs**. Acompanhe a tarefa e abra **VODs descobertas e pendências**. Caso a descoberta falhe, expanda **Incluir URLs manualmente**, cole uma URL pública por linha e clique **Adicionar URLs**. Cada campanha operacional usa um único provider.
4. Escolha o modo, normalmente **Equilibrado**, e clique **Garimpar pendentes / Continuar**. Usa CPU e Base por padrão. VODs concluídas são ignoradas. VODs bloqueadas pelas regras aparecem na lista, mas não são mineradas; BRKK mantém a exclusão de fontes concretamente identificadas como Cinefy; palavras promocionais no título/descrição não bloqueiam a VOD.
5. Revise o ranking da campanha. Filtre VOD, data, status, score ou tipo. Clique **Preview**, confira contexto e origem, depois **Aprovar** ou **Descartar**. **Pacote editorial** aceita tarja, título, hook, limites absolutos, layout e observação; pode ficar vazio. VISUAL/TALKING é somente uma sugestão baseada no sinal de atividade, não reconhecimento do conteúdo.
6. Marque vários candidatos e use **Aprovar seleção**, ou aprove individualmente. Depois clique **Selecionar aprovados visíveis**. A seleção segue os filtros atuais.
7. Ajuste as margens (padrão 5 s antes/depois) e clique **Baixar aprovados**. A fila executa um download por vez. Por padrão exige 1080p60 medido. Se não houver, o erro oferece **Tentar melhor qualidade disponível**; também há uma opção explícita antes de enfileirar. Não há upscale nem conversão artificial para 60 fps.
8. RAWs ficam em `TUTUCO-TV/04_RAW/BRKK/`, com nome seguro, ID do candidato e JSON de origem/range/qualidade. O link **RAW** aparece no candidato. Para PREP, use **Abrir VOD**, obtenha um frame, configure a composição e use o PREP existente após obter o RAW.
9. **Cancelar com segurança** interrompe a campanha/fila. **Garimpar pendentes / Continuar** retoma a mineração; tarefas de download com erro/cancelamento/interrupção oferecem **Tentar novamente**. A sincronização seguinte atualiza metadados e acrescenta novas VODs, sem reminerar concluídas.

## Fonte e download

Kick/Twitch usam o JSON público da CLI instalada do any-dl para listagem/metadados/resolução da fonte. O yt-dlp do `.venv` executa os ranges via `python -m yt_dlp --download-sections`, com FFmpeg e `--force-keyframes-at-cuts`. Isso mantém a origem temporal por seek, evitando assumir como exato o corte por keyframe do any-dl. YouTube usa yt-dlp e inclusão manual de URLs. Sem bypass, cookies extraídos, autenticação própria ou downloader próprio.

Listagem limitada às 100 gravações retornadas pela ferramenta; períodos anteriores podem exigir URLs manuais. VODs sem data não entram automaticamente pelo filtro: o resumo informa a limitação. Datas usam o dia fornecido pela fonte, sem presumir fuso oficial. Falhas de metadata/fonte preservam o registro para retry; vinculação de arquivo local continua na tela da VOD.

O app usa o Python do `.venv`, diretório raiz do projeto, ambiente/PATH herdados e `shell=False`. Não muda proxy, firewall ou rede. Processo de download cancelado encerra somente sua própria árvore de processos.

## Processamento, cache e timestamps

Reutiliza `long_vod.run` com um adaptador de fonte: Fast Scan em ranges de até 600 s, energia por segundo, pares visuais 160×90 a cada 20 s, sondagem de fala e aprofundamento seletivo em núcleos de 300 s com contexto. A seleção editorial, clustering e ranking existentes continuam globais, sem quota. Talking continua elegível. O modo Remote usa CPU; não altera CUDA da V1.

O cache persistente inclui identidade da VOD/duração, versão e parâmetros de amostragem. Features/transcrições/checkpoints ficam em `data/campaigns/<criador>/transcripts/<vod>/remote/`. Modo editorial reaproveita medições e transcrição; mudança de modelo reutiliza medições, mas refaz a fala daquele modelo. Transcrição local do chunk permanece como cache do Whisper; `absolute.json` registra os segmentos somados ao início absoluto da região. Candidatos e exports usam segundos absolutos.

O RAW usa os limites editoriais (ou os recomendados no pacote) mais margens configuradas, limitadas à VOD. Os limites da região analisada são guardados separadamente. A duração obtida é medida; o início absoluto efetivo não é medido independentemente e permanece nulo no JSON, com explicação. A ferramenta recodifica no corte; resolução e FPS são conferidos, não se promete cópia sem perdas.

## Temporários, disco e retomada

Cada pasta em `data/remote_tmp/<id>` tem manifesto próprio: VOD, range, etapa, qualidade e estado. Vídeo/áudio temporários só são descartados após um checkpoint persistente e checksum válido. Em falha recuperável, uma evidência persistente de retry antecede a remoção do range recriável. Cancelamento preserva o range necessário até retomada. Na inicialização, órfãos comprovadamente descartáveis são limpos; os demais ficam para retry.

A limpeza recusa caminhos fora dessa área e links/junctions. Não percorre pastas de importação nem RAWs. O uso temporário aparece no resumo. Antes de ranges, limpa descartáveis e confere uma reserva conservadora: 512 MiB + 1 MB/s para análise ou 4 MB/s para qualidade de corte. Confere também espaço do destino RAW. É uma estimativa, não previsão exata de bitrate; mudanças externas no disco ainda podem causar erro.

Não guarda VOD inteira em Remote. Isso **não significa pouco tráfego total**: o Fast Scan visita todos os chunks e regiões profundas podem ser transferidas outra vez após descarte. Disco temporário é limitado pela etapa, enquanto transcrições/features e exports permanecem. Os vídeos integrais importados pela V1 não são removidos.

SQLite recebe somente três tabelas adicionais (`remote_campaigns`, `remote_vods`, `remote_jobs`), com criação idempotente. A fila reutiliza o executor serial existente. Status e checkpoints sobrevivem a reinício; tarefas em execução são marcadas interrompidas. A retomada requer ação do operador, sem scheduler. Whisper e geração de Preview podem levar até o próximo ponto seguro para aplicar cancelamento.

## Validação de 20/09/2026

Baseline: 94 Python, 11 JavaScript. Final: 117 Python, 14 JavaScript; Ruff, compileall e sintaxe JS aprovados. Ver `TESTES.md`.

Teste público isolado: VOD conhecida de GabePeixe, Fast Scan somente 600–780 s, aprofundamento com contexto 495–870 s. CPU/Base produziu 2 candidatos (scores 95/88), sem alterar detector nem forçar quantidade. Análise fria 81,10 s; cache 0,063 s. RAW solicitado 616,90–771,75 s; duração medida 154,85 s, H.264, 1920×1080, 60 fps, 63.888.505 bytes. Temporários: zero após análise e após RAW. Tempo total com descoberta/metadata/RAW: 195,09 s. Relatório: `test-results/remote-real/report.json`.

Descoberta pública BRKK validou três gravações; as três tinham `Cinefy` no título e continuam sujeitas ao bloqueio existente. O teste de mídia usou GabePeixe, cuja configuração não tem essa exclusão. Incremental 18 concluídas → 19 disponíveis → 1 pendente foi validado com fixture, sem baixar dezenas de VODs.

UI revisada no navegador usando banco separado: ranking, campos, regras de BRKK, pacote editorial salvo e link do RAW. Integração FFmpeg local verificou Preview → RAW → frame → PREP 1080×1920 sem VOD integral e preservando os bytes do RAW. O RAW aprovado do teste permanece fora da biblioteca operacional, conforme a orientação de preservação; não é temporário. Nenhum arquivo do usuário foi apagado.

Limites: não houve benchmark completo de 8–12 h, teste público de Twitch/YouTube nem certificação de qualidade editorial. Descoberta depende do provider; datas/autoria e falhas de transcrição ainda exigem revisão humana. Não há paginação além da listagem limitada, concorrência ajustável pela UI, reconhecimento visual, publicação ou Live Mode.


## Correção pontual de elegibilidade — 20/09/2026

A observação histórica acima sobre bloqueio por Cinefy no título foi corrigida: título/descrição, !CINEFY, !APP e chamadas promocionais não comprovam origem nem inelegibilidade. Plataforma, período e identificação exata de fonte excluída mantêm suas regras. Indícios textuais na transcrição de um candidato (como “assistindo um filme” ou “transmissão protegida”) geram REVISÃO DE ELEGIBILIDADE somente no trecho, sem mudar score/status de aprovação nem bloquear a VOD. Não há classificação de filme por atividade visual, react, gameplay ou menção isolada. Essa heurística é um aviso para revisão, não reconhecimento de conteúdo ou prova de infração.

Após a correção, a campanha BRKK de 15/09 a 20/09 foi sincronizada: mesmas 2 VODs, 21,6439 h, 2 pendentes, 0 bloqueadas. Revisão humana da identidade do canal permanece. Nenhuma mineração foi iniciada. Evidência: `test-results/eligibility-resync.json`.
