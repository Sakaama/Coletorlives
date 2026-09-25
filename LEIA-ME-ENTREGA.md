# TUTUCO CLIP MINER — MANUAL DE TRANSIÇÃO E ENTREGA TÉCNICA

> **Documento de Handoff para o Novo Desenvolvedor**  
> Data: 24 de setembro de 2026  
> Repositório: `D:\Projetos\TUTUCO-CLIP-MINER`  
> Pacote de Entrega: `TUTUCO_CLIP_MINER_HANDOFF.zip`

---

## 1. Visão Geral do Projeto e Estrutura de Pastas

### O que é o TUTUCO Clip Miner
O **TUTUCO Clip Miner** é uma plataforma local de inteligência e mineração editorial para criadores de conteúdo e editores de vídeo. Sua finalidade principal é analisar transmissões ao vivo de longa duração (VODs de 6h a 16h do Kick e YouTube) e extrair automaticamente candidatos a cortes verticais (Shorts, Reels, TikTok) de alto engajamento.

### Pipeline Técnico Operacional
```
Kick / YouTube VOD
      │
      ▼
any-dl / yt-dlp  ──►  Extração de Metadados & Manifest HLS (sem baixar a VOD completa em 1080p)
      │
      ▼
  Fast Scan      ──►  Download de áudio em fatias remotas (300s) + Amostragem Visual
      │
      ▼
Faster Whisper   ──►  Transcrição contínua + Energia sonora + Deteção de picos de atividade
      │
      ▼
  Editorial AI   ──►  Heurísticas de gancho (Hook), clímax (Payoff) e limites editoriais recomendados
      │
      ▼
 group_refined   ──►  Deduplicação de janelas sobrepostas e ranqueamento (Recomendado, Bom, Talvez, Fraco)
      │
      ▼
Shortlist & UI   ──►  Disponibilização imediata no painel web + Geração de Preview leve sob demanda
      │
      ▼
  Export RAW     ──►  Download em altíssima qualidade (1080p60) apenas dos trechos aprovados
```

### Estrutura de Diretórios
```
TUTUCO-CLIP-MINER/
├── app.py                      # Servidor HTTP local (Waitress/Flask), API REST e rotas
├── iniciar.bat                 # Script de bootstrap automatizado (Windows)
├── pyproject.toml              # Metadados do projeto e configurações
├── requirements.txt            # Dependências essenciais em tempo de execução
├── requirements-dev.txt        # Dependências para suíte de testes e linting
├── requirements-lock.txt       # Lockfile exato de todas as bibliotecas
├── .env.example                # Exemplo ilustrativo de variáveis de ambiente
├── LEIA-ME-ENTREGA.md          # Este documento oficial de transição
│
├── miner/                      # Núcleo do processador em Python
│   ├── backlog.py              # Backlog Runner: fila cronológica, isolamento e checkpoints
│   ├── collector.py            # Orquestrador de campanhas, downloads e pipelines
│   ├── editorial.py            # Motor editorial de scoring e agrupamento (group_refined)
│   ├── remote_provider.py      # Integração com any-dl / yt-dlp e HLS ranges
│   ├── store.py                # Camada de persistência SQLite
│   ├── remote_analysis.py      # Fast Scan: fatiamento remoto, extração de áudio e Whisper
│   ├── analysis.py             # Análise de áudio local, energia e transcrição com Faster Whisper
│   ├── visual_activity.py      # Amostragem e cálculo de atividade visual
│   ├── rules.py                # Regras de elegibilidade de campanhas e streamers
│   └── ...
│
├── config/
│   └── campaigns/              # Configurações JSON das campanhas (datas, streamer, regras)
│       ├── gabepeixe.json      # Campanha oficial GabePeixe
│       ├── brkk.json           # Campanha BRKK
│       └── ...
│
├── data/
│   ├── history.sqlite3         # Banco de dados persistente SQLite (VODs, candidatos, jobs)
│   ├── campaigns/              # Dados analíticos e checkpoints por campanha
│   │   ├── gabepeixe/          # Transcrições Whisper (JSON/TXT) e checkpoints de blocos
│   │   └── brkk/               # Metadados e candidatos BRKK
│   ├── preview_cache/          # Cache efêmero de previews gerados (não versionado)
│   └── remote_tmp/             # Arquivos temporários de download e áudio
│
├── static/                     # Assets estáticos do frontend (CSS e JavaScript)
│   ├── app.js / app.css        # Frontend da visualização de VOD única
│   └── remote.js / remote.css  # Frontend do Painel de Campanhas e Backlog Runner
│
├── templates/                  # Templates HTML das interfaces
│   ├── index.html              # Interface do explorador de VOD e candidatos
│   └── remote.html             # Painel de campanhas e shortlist
│
├── scripts/                    # Scripts utilitários de diagnóstico, discovery e teste
├── tests/                      # Suíte de testes automatizados com pytest
│
└── TUTUCO-TV/                  # Estrutura operacional do canal
    ├── 08_TEMPLATES/           # Templates editoriais em Markdown
    ├── 02_VODS/                # [Local] VODs completas armazenadas localmente
    └── 04_RAW/                 # [Local] Arquivos brutos gerados após aprovação
```

---

## 2. Instalação e Execução Local

### Pré-requisitos
1. **Windows 10 / 11 x64** (ou Linux/macOS adaptando os scripts shell).
2. **Python 3.12** instalado no sistema (garanta que `py -3.12` ou `python` esteja no PATH).
3. **FFmpeg e FFprobe** instalados e configurados no `PATH` global do Windows.
   - Para testar, execute no terminal: `where ffmpeg` e `where ffprobe`.

### Inicialização Automática (Windows)
Basta clicar duas vezes ou executar pelo terminal:
```cmd
iniciar.bat
```
O script verifica a presença do `.venv`, instala automaticamente as dependências de `requirements.txt` se necessário, valida a existência do FFmpeg e inicia o servidor Waitress na porta 8765.

### Inicialização Manual
```powershell
# 1. Criar e ativar o ambiente virtual
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Executar o servidor
python app.py
```
Acesse a aplicação no navegador em: **`http://127.0.0.1:8765`**.

### Executando Testes de Validação
```powershell
pip install -r requirements-dev.txt
pytest -v tests/test_backlog.py tests/test_editorial.py tests/test_remote_provider.py
```

---

## 3. Restauração de Dados e Ajuste de Caminhos Absolutos

### Independência de Caminhos no Banco de Dados
A arquitetura do TUTUCO Clip Miner foi projetada para ser portátil:
- As tabelas `vods`, `candidates`, `jobs`, `remote_jobs` e `remote_campaigns` **não utilizam caminhos absolutos** de disco. Elas armazenam URLs da Kick/YouTube e metadados relativos.
- Os checkpoints de transcrição (`data/campaigns/...`) são lidos pelo diretório relativo do projeto.

### Única Tabela com Caminhos Absolutos: `exports`
A tabela `exports` contém 29 registros de testes preliminares com a campanha BRKK que foram gravados com o caminho absoluto da máquina de desenvolvimento original (`D:\Projetos\TUTUCO-CLIP-MINER\...`).

Se você mover o projeto para outra unidade ou pasta (por exemplo, `C:\Dev\TUTUCO-CLIP-MINER`):
1. O minerador e o catálogo de candidatos continuarão funcionando **100% normalmente**.
2. Caso queira que os links dos 29 arquivos antigos de exportação BRKK continuem acessíveis, execute o seguinte comando SQL no SQLite:
```sql
-- Atualização no arquivo data/history.sqlite3:
UPDATE exports 
SET path = REPLACE(path, 'D:\Projetos\TUTUCO-CLIP-MINER', 'SEU_NOVO_CAMINHO_AQUI')
WHERE path LIKE 'D:\Projetos\TUTUCO-CLIP-MINER%';
```

### Arquivos Excluídos do Pacote e Impacto na Continuidade
Para garantir que o pacote de entrega permaneça leve e rápido de baixar, foram excluídos arquivos derivados ou caches descartáveis. Veja a política de recomposição:
- **`models/` (Modelo Faster-Whisper, ~141 MB):**
  - *Impacto:* Nenhum. Na primeira vez que uma nova VOD for analisada, a biblioteca `faster-whisper` faz o download automático e silencioso do modelo para o diretório de cache.
- **`data/preview_cache/` (Arquivos `.mp4` de preview):**
  - *Impacto:* Nenhum dado analítico é perdido. Os previews de 30s a 60s são gerados dinamicamente sob demanda quando o editor clica no botão "▶ Preview" de um candidato na interface web.
- **`data/remote_tmp/` (Fatias temporárias de áudio/vídeo):**
  - *Impacto:* Nenhum. Tratam-se de arquivos efêmeros de processamento que são automaticamente criados e limpos durante o ciclo do Fast Scan.
- **`TUTUCO-TV/02_VODS/*.mp4` (VODs completas, ~2.9 GB):**
  - *Impacto:* O pipeline atual utiliza HLS remoto (Fast Scan). Ele nunca precisa baixar a VOD inteira de 12 horas para minerar os candidatos. O download em alta fidelidade ocorre apenas via export RAW.

---

## 4. Estado Real do Backlog e Checkpoints Auditados

### Resumo Operacional da Campanha GabePeixe
- **Total de VODs Encontradas no Catálogo:** **18 VODs** (período de 01/09/2026 a 23/09/2026).
- **VODs Totalmente Concluídas:** **7 VODs**.
- **Total de Candidatos Reais Salvos no Banco:** **307 candidatos**.
  - **5 RECOMENDADO** (Score editorial >= 82)
  - **68 BOM** (Score editorial >= 68)
  - **198 TALVEZ** (Score editorial >= 48)
  - **36 FRACO** (Score editorial < 48)
  - **Shortlist Pronta para Uso:** **73 cortes de alta prioridade** (Recomendados + Bons).
- **VOD Interrompida com Checkpoint Preservado:** **1 VOD** (`2026-09-12`, 59.7% processada).
- **VODs Pendentes na Fila:** **9 VODs**.
- **VOD com Erro Isolado:** **1 VOD** (`2026-09-23`, live em andamento no discovery).

### Tabela Detalhada das 18 VODs do Backlog
| # | Data | VOD ID | Duração | Candidatos | Status Operacional | Detalhes / Observação |
|---|---|---|---|---|---|---|
| 1 | 2026-09-23 | `...5b25ac325e` | 0.00h | 0 | **ERRO** | Live ativa na Kick no momento do discovery; duração nula. |
| 2 | 2026-09-22 | `...f63dcd9eb1` | 12.36h | 5 | **CONCLUÍDA** | VOD do teste técnico inicial de validação. |
| 3 | 2026-09-20 | `...e8cd09d9a8` | 10.26h | 44 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 4 | 2026-09-19 | `...41a7e2c751` | 5.93h | 35 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 5 | 2026-09-18 | `...c946376eea` | 10.58h | 61 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 6 | 2026-09-17 | `...e1de9ceec8` | 12.76h | 62 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 7 | 2026-09-15 | `...d92df58ca4` | 10.53h | 68 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 8 | 2026-09-13 | `...9d91aece2b` | 5.47h | 32 | **CONCLUÍDA** | Shortlist completa gravada no SQLite. |
| 9 | 2026-09-12 | `...56025e66df` | 11.16h | 0 | **CANCELADA / CHECKPOINT OK** | **Interrompida aos 59.7%**. 79 blocos transcritos salvos em disco. |
| 10 | 2026-09-11 | `...0ba69695f0` | 11.85h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 11 | 2026-09-10 | `...7a24052e79` | 11.56h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 12 | 2026-09-09 | `...fc88702f98` | 6.49h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 13 | 2026-09-06 | `...f8bd83d1b0` | 9.49h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 14 | 2026-09-05 | `...52af73f9ed` | 9.03h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 15 | 2026-09-04 | `...acca9f6b73` | 9.39h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 16 | 2026-09-03 | `...936d5b4f1d` | 6.59h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 17 | 2026-09-02 | `...c0dc115d2c` | 14.64h | 0 | **PENDENTE** | Na fila, pronta para mineração. |
| 18 | 2026-09-01 | `...cc1bcdfbb8` | 15.17h | 0 | **PENDENTE** | Na fila, pronta para mineração. |

---

## 5. Campanha Oficial vs Rascunho de Teste

> [!IMPORTANT]
> **Use sempre a Campanha Oficial:**
> - **Nome:** `GabePeixe · Campeonato Kick 2026`
> - **ID:** `2137c0d0e8d54b67`
>
> **Aviso de Desambiguação:**  
> Existe no banco outro registro com ID `dddb669fff0c4321` intitulado `GabePeixe · 2026-09-01 a 2026-10-22`. Trata-se de um rascunho descartável criado em um teste anterior. **Ignore completamente o ID `dddb669fff0c4321`**.

---

## 6. Como Retomar o Backlog Explicitamente Sem Reprocessar VODs Concluídas

### Garantia de Não Reprocessamento
O módulo `miner/backlog.py` implementa a função `BacklogQueue.load_queue()`, que consulta o status real de cada VOD no banco de dados. Uma VOD é considerada definitivamente `CONCLUÍDO` se:
1. `remote_state == 'CONCLUÍDO'`, OU
2. `analyzed == True` E possui candidatos vinculados no SQLite.

Como as 7 VODs concluídas atendem a ambos os critérios, elas **não serão reprocessadas**.

### Retomada Inteligente da VOD 2026-09-12
A VOD `2026-09-12` (`GABEPEIXE_2026-09-23_56025e66df`) foi pausada aos **59.7%**. Os checkpoints de todos os 79 blocos de 300 segundos concluídos estão preservados em:
`data/campaigns/gabepeixe/transcripts/GABEPEIXE_2026-09-23_56025e66df/remote/5baada4bbc941dbfcff5/`
Ao acionar o runner, o motor carrega esses blocos do disco sem fazer nova requisição à Kick ou re-transcrever, partindo diretamente para os 40.3% restantes.

### Instruções para Iniciar / Retomar o Runner
1. Inicie a aplicação via `iniciar.bat` ou `python app.py`.
2. Acesse `http://127.0.0.1:8765` e abra o **Painel de Campanhas**.
3. Selecione a campanha `GabePeixe · Campeonato Kick 2026` (`2137c0d0e8d54b67`).
4. Verifique os contadores na barra superior (7 concluídas, 1 em fila/pendente, etc.).
5. Clique em **"Iniciar / Retomar Backlog"**.
   - O runner processará estritamente **1 VOD pesada por vez**.
   - Ao finalizar cada VOD, a shortlist fica imediatamente disponível para revisão e exportação na interface, avançando de forma resiliente para a próxima VOD mais recente.

---

## 7. Problemas Conhecidos e Limitações Técnicas

### Fatos Comprovados
- **Duração Nula em Lives em Andamento:** Se uma live estiver ativa no momento do discovery via API da Kick, a duração retornará `None`, impedindo o cálculo de blocos do Fast Scan. O runner registra erro isolado na VOD sem derrubar a fila. Quando a live for encerrada, uma nova sincronização obtém a duração correta.
- **Serialização Estrita de Tarefas Pesadas:** Para preservar a integridade do SQLite e o consumo de CPU/RAM em máquinas locais, o runner proíbe o processamento simultâneo de duas VODs de 12 horas.
- **Velocidade de Processamento em CPU:** O modelo Faster-Whisper `base` consome aproximadamente 4 a 6 minutos de CPU por hora de transmissão. Uma VOD de 12 horas requer entre 50 e 70 minutos para mineração editorial completa.

### Hipóteses e Riscos Não Confirmados
- **Expiração de CDN em VODs Antigas:** Transmissões com mais de 60 a 90 dias podem sofrer rotação de chaves no HLS da Kick. Nas VODs analisadas de setembro/2026, todos os manifests permaneceram 100% acessíveis.
- **Impacto de Ruído no Microfone:** Em trechos onde o streamer joga com microfone saturado ou volume musical extremamente elevado, a confiança das palavras no Whisper cai proporcionalmente, embora a detecção de pico de energia ainda capture o momento.

---

## 8. Plano Futuro e Roadmap de Inteligência (Apenas Planejados)

As seguintes propostas foram desenhadas conceitualmente como próximos passos para a evolução da plataforma, **mas NÃO estão implementadas no código atual**:

1. **DNA do Criador vs. DNA Editorial:**
   - *Conceito:* Separar a modelagem de comportamento do criador (gírias específicas do GabePeixe, reações a jogos de terror vs Minecraft, momentos de vitória) das preferências da linha editorial do canal de cortes (tempo ideal de retenção, hooks de pergunta, regras de censura de palavrões).
2. **Clip Intelligence Multimodal:**
   - *Conceito:* Integrar modelos de visão computacional leve (OCR na killfeed e placar de jogos, detecção de expressão facial na webcam) somados ao áudio para aumentar o score de momentos sem fala expressiva.
3. **Clip Inbox Colaborativo:**
   - *Conceito:* Interface simplificada estilo fila de triagem (Tinder/Kanban) para que editores assistentes aprovem, ajustem marcações de início/fim e exportem direto para pastas compartilhadas.
4. **Chat como Sinal Auxiliar de Engajamento:**
   - *Conceito:* Ingerir o histórico de mensagens do chat da Kick/Twitch em tempo real para correlacionar tempestades de emojis (ex.: "OMEGALUL", "KKKKKK") com os picos identificados pelo áudio.

---

## 9. Observação sobre Nuvem e Infraestrutura

> [!NOTE]
> **A migração para Google Cloud Platform (GCP) NÃO foi executada.**  
> O TUTUCO Clip Miner opera **100% localmente no Windows**. Não existem instâncias de Cloud Run, buckets GCS, segredos em Secret Manager ou dependências de serviços gerenciados na nuvem. Toda a persistência é feita no SQLite local (`data/history.sqlite3`) e no sistema de arquivos local.
