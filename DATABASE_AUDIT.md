# TUTUCO CLIP MINER — Auditoria Completa do Banco de Dados
**Arquivo Auditado:** `data/history.sqlite3`  
**Data da Auditoria:** 25/09/2026  
**Status de Integridade:** `PRAGMA integrity_check: ok`  
**Volume Total:** 1.1 MB (8 tabelas relacionais / documento)

---

## 1. Visão Geral das Tabelas e Volume de Registros

| Tabela | Registros | Chave Primária | Papel no Sistema | Classificação de Ciclo de Vida |
|---|---|---|---|---|
| `candidates` | **436** | `id` (TEXT) | Cortes/momentos minerados pelo pipeline | **PRODUCT STATE** |
| `vods` | **20** | `id` (TEXT) | Transmissões/VODs catalogadas | **PRODUCT STATE** |
| `remote_campaigns` | **7** | `id` (TEXT) | Configurações operacionais de campanha | **PRODUCT STATE** |
| `remote_vods` | **25** | `(run_id, vod_id)` | Associação VODs × Campanhas ativas | **PRODUCT STATE** |
| `editorial_feedback`| **11** | `id` (INTEGER AUTO) | Histórico de aprovação/descarte e notas | **PRODUCT STATE** |
| `exports` | **29** | `id` (INTEGER AUTO) | Referências a arquivos gerados (preview/raw) | **HYBRID (LOCAL / CLOUD)** |
| `remote_jobs` | **24** | `id` (TEXT) | Fila de tarefas de processamento assíncrono | **LOCAL PROCESSING STATE** |
| `jobs` | **21** | `id` (TEXT) | Tarefas locais legadas de extração | **LOCAL PROCESSING STATE** |

---

## 2. Dicionário de Dados, Esquemas e Índices

### 2.1 Tabela `candidates` (Cortes Minerados)
Armazena todos os momentos identificados pelo motor Fast Scan, classificados heuristicamente e transcritos via Faster Whisper.

- **Colunas:**
  - `id` (`TEXT`, PK): Identificador único do corte (ex: `c_01a0ca213cb873d8_006000`).
  - `vod_id` (`TEXT`, NOT NULL): Chave estrangeira lógica referenciando `vods.id`.
  - `start` (`REAL`, NOT NULL): Início em segundos absolutos da live.
  - `end` (`REAL`, NOT NULL): Fim em segundos absolutos da live.
  - `score` (`INTEGER`, NOT NULL): Pontuação heurística combinada (0–100).
  - `status` (`TEXT`, NOT NULL, default `'NOVO'`): Status editorial (`NOVO`, `APROVADO`, `DESCARTADO`).
  - `data` (`TEXT`, NOT NULL, JSON): Metadados profundos de inteligência editorial.
- **Índices:**
  - `candidate_vod` em `vod_id` (não exclusivo) para buscas rápidas por live.
  - `sqlite_autoindex_candidates_1` em `id` (exclusivo).
- **Estrutura do JSON `data`:**
  - `editorial_review`: `{ classification: "RECOMENDADO"|"BOM"|"TALVEZ"|"FRACO", editorial_score: int, hook: str, suggested_start: float, suggested_end: float, reason: str, content_type: str }`
  - `visual_activity_level`: `"HIGH" | "MEDIUM" | "LOW"`
  - `visual_activity_score`: float de movimentação detectada via OpenCV/FFmpeg
  - `visual_boost`: bônus aplicado à pontuação
  - `summary`: resumo textual do trecho
  - `text`: transcrição Whisper completa do momento
  - `mode`: modo de mineração (ex: `"fast_scan"`)
  - `detector_version`: versão do algoritmo
  - `archived`: booleano indicando se foi arquivado
- **Módulos que Escrevem:** `miner/collector.py`, `miner/service.py`, `app.py` (reviews).
- **Módulos que Leem:** `miner/presentation.py`, `miner/caption.py`, `miner/collector.py`, `app.py`.

---

### 2.2 Tabela `vods` (Transmissões & Metadados de Origem)
Catálogo central de transmissões monitoradas de Kick, YouTube e Twitch.

- **Colunas:**
  - `id` (`TEXT`, PK): ID gerado ou hash do link/arquivo (ex: `01a0ca21-3cb8-73d8-8b68-a47c5c51987a`).
  - `campaign` (`TEXT`, NOT NULL): Slug da campanha associada (ex: `gabepeixe`, `brkk`).
  - `source_key` (`TEXT`, NOT NULL): Data da live ou identificador da fonte (ex: `2026-09-22`).
  - `created` (`TEXT`, default `CURRENT_TIMESTAMP`).
  - `data` (`TEXT`, NOT NULL, JSON): Metadados operacionais e técnicos da VOD.
- **Índices:**
  - `vod_source` em `campaign`, `source_key` (não exclusivo).
  - `sqlite_autoindex_vods_1` em `id` (exclusivo).
- **Estrutura do JSON `data`:**
  - `title`: Título original da transmissão.
  - `url`: URL canônica da transmissão (ex: Kick / YouTube).
  - `channel` / `streamer`: Nome do criador.
  - `duration`: Duração em segundos (ex: 44400s = 12h 20m).
  - `platform`: Provedor (`Kick`, `YouTube`, `Twitch`, `Local`).
  - `remote_state`: Estado operacional (`CONCLUÍDO`, `EXECUTANDO`, `ERRO`, `BLOQUEADO`).
  - `remote_completed`: Timestamp ISO da conclusão.
  - `analyzed`: Booleano indicando se a análise heurística foi concluída.
  - `eligibility`: `{ status: "PERMITIDA"|"NÃO PERMITIDA", reason: str }`
  - `analysis_metrics`: Estatísticas do Fast Scan (blocos processados, tempo de áudio, Whisper timings).
- **Módulos que Escrevem:** `miner/collector.py`, `miner/discovery.py`, `miner/service.py`.
- **Módulos que Leem:** `miner/presentation.py`, `miner/backlog.py`, `miner/collector.py`, `app.py`.

---

### 2.3 Tabela `remote_campaigns` (Configurações de Campanha)
Armazena as campanhas configuradas no runner remoto/backlog.

- **Colunas:**
  - `id` (`TEXT`, PK): Identificador da campanha (ex: `2137c0d0e8d54b67` ou `gabepeixe`).
  - `data` (`TEXT`, NOT NULL, JSON): Configurações e estado de sincronização.
- **Estrutura do JSON `data`:**
  - `id`, `name`, `creator`, `provider`, `channel`, `start`, `end`, `last_sync`, `sync_message`.
- **Módulos que Escrevem:** `miner/collector.py`.
- **Módulos que Leem:** `miner/collector.py`, `miner/presentation.py`, `app.py`.

---

### 2.4 Tabela `remote_vods` (Junção Campanha × VODs)
Tabela associativa que controla a fila de VODs a processar em cada campanha.

- **Colunas:**
  - `run_id` (`TEXT`, NOT NULL, PK parte 1): ID da campanha/run.
  - `vod_id` (`TEXT`, NOT NULL, PK parte 2): ID da VOD.
- **Índices:**
  - `sqlite_autoindex_remote_vods_1` em `(run_id, vod_id)`.
- **Módulos que Escrevem:** `miner/collector.py`, `miner/discovery.py`.
- **Módulos que Leem:** `miner/collector.py`, `miner/backlog.py`.

---

### 2.5 Tabela `editorial_feedback` (Histórico de Curadoria Humana)
Registro imutável de todas as decisões tomadas pelo operador humano (Aprovado / Descartado).

- **Colunas:**
  - `id` (`INTEGER`, PK AUTOINCREMENT).
  - `candidate_id` (`TEXT`, NOT NULL): ID do corte revisado.
  - `status` (`TEXT`, NOT NULL): Status atribuído (`APROVADO`, `DESCARTADO`, `NOVO`).
  - `note` (`TEXT`, default `''`): Anotação do editor.
  - `snapshot` (`TEXT`, NOT NULL, JSON): Fotografia completa do corte no momento da revisão.
  - `created` (`TEXT`, default `CURRENT_TIMESTAMP`).
- **Módulos que Escrevem:** `app.py` (`/api/vods/<vid>/review` e `/api/remote/<rid>/action`).
- **Módulos que Leem:** `miner/presentation.py` (feed de atividade recente e analytics).

---

### 2.6 Tabela `exports` (Arquivos Gerados & Mídias)
Rastreia clipes extraídos pelo FFmpeg (vídeos de preview, arquivos RAW em alta qualidade e PREP com tarja).

- **Colunas:**
  - `id` (`INTEGER`, PK AUTOINCREMENT).
  - `candidate_id` (`TEXT`, NOT NULL): ID do corte associado.
  - `vod_id` (`TEXT`, NOT NULL): ID da live correspondente.
  - `kind` (`TEXT`, NOT NULL): Tipo do arquivo (`preview`, `raw`, `prep`).
  - `path` (`TEXT`, NOT NULL): Caminho no disco local (ex: `data/preview_cache/preview_...mp4`).
  - `start` (`REAL`, NOT NULL), `end` (`REAL`, NOT NULL): Delimitação temporal do arquivo.
  - `created` (`TEXT`, default `CURRENT_TIMESTAMP`).
- **Módulos que Escrevem:** `miner/service.py`, `miner/collector.py`.
- **Módulos que Leem:** `app.py` (`/media/export/<eid>`), `miner/presentation.py`.

---

### 2.7 Tabelas `remote_jobs` e `jobs` (Fila de Tarefas Operacionais)
Gerenciam a execução de tarefas assíncronas (downloads parciais, extração de áudio, transcrição, geração de preview).

- **Colunas `remote_jobs`:**
  - `id` (`TEXT`, PK): ID da tarefa (UUID).
  - `run_id` (`TEXT`, NOT NULL): Campanha associada.
  - `kind` (`TEXT`, NOT NULL): Tipo da tarefa (`analyze`, `preview`, `download`, `metadata`).
  - `state` (`TEXT`, NOT NULL): `PENDENTE`, `EXECUTANDO`, `CONCLUÍDO`, `ERRO`, `CANCELADO`, `INTERROMPIDO`.
  - `payload` (`TEXT`, JSON): Parâmetros da execução.
  - `progress` (`REAL`, default 0): Progresso 0 a 100.
  - `message` (`TEXT`): Mensagem de log/status para o operador.
  - `cancel_requested` / `pause_requested` (`INTEGER`).
  - `created` (`TEXT`, NOT NULL).
- **Módulos que Escrevem:** `miner/collector.py`, `miner/backlog.py`, `miner/service.py`.
- **Módulos que Leem:** `miner/collector.py`, `miner/presentation.py`, `app.py`.

---

## 3. Classificação de Dados: Product State × Local Processing State

| Categoria | Tabelas / Dados | Destino Recomendado | Justificativa Técnica |
|---|---|---|---|
| **PRODUCT STATE** (Compartilhado) | `candidates`, `vods`, `remote_campaigns`, `remote_vods`, `editorial_feedback` | **Firestore (Cloud)** + Cache SQLite Local | São os ativos de negócio fundamentais: lives descobertas, cortes encontrados, decisões editoriais, notas e metadados. Múltiplos editores e máquinas precisam enxergar a mesma lista e os mesmos status. |
| **SHARED MEDIA ASSETS** | Vídeos editados finais, exports RAW aprovados, thumbnails | **Google Cloud Storage (GCS)** | Arquivos binários pesados de vídeo não devem ficar em bancos de dados. Devem ser salvos no GCS com URLs seguras e assinadas temporárias. |
| **LOCAL PROCESSING STATE** (Efêmero) | `jobs`, `remote_jobs`, `data/remote_tmp/`, checkpoints de áudio | **SQLite Local / Filesystem Local** | Estados transitórios de processamento de máquina (transcrição Whisper, blocos temporários de 90s, download parcial HLS). Não têm valor na nuvem e sobrecarregariam o Firestore com escritas a cada segundo. |
| **HYBRID METADATA** | `exports` (tabela de mapeamento) | **Firestore + SQLite** | O registro de que um corte possui vídeo editado/exportado sobe para a nuvem; o arquivo bruto temporário de preview permanece em cache local. |

---

## 4. Estratégia de Coexistência e Migração Segura

1. **Zero Destruição do SQLite:** O banco `history.sqlite3` permanece intacto e funcional no ambiente local.
2. **Modo Híbrido Resiliente:**
   - Se credenciais do Google Cloud estiverem presentes e ativas: o sistema sincroniza o **Product State** com o Firestore e faz upload de vídeos editados para o Cloud Storage.
   - Se as credenciais não estiverem configuradas: o sistema opera 100% no SQLite local, exibindo indicadores informativos na interface sem quebrar nenhuma funcionalidade.
