# Relatório Oficial de Unificação de Projetos — TUTUCO CLIP MINER & Coletorlives

**Data:** 25 de Setembro de 2026  
**Base Canônica:** `D:\Projetos\TUTUCO-CLIP-MINER`  
**Repositório Auxiliar Incorporado:** `D:\Projetos\Coletorlives-main\Coletorlives-main`  
**Status Final:** Unificação Concluída com Sucesso · 100% dos Testes Aprovados · Zero Regressões  

---

## 1. Sumário Executivo

O **TUTUCO CLIP MINER** foi estabelecido como a base canônica inegociável do projeto. Ele contém o motor de mineração heurística Fast Scan, transcrição Faster Whisper, Backlog Runner de alta confiabilidade, Creator Workspace, gerador determinístico de legendas, e 436 candidatos minerados reais do streamer GabePeixe.

O projeto paralelo **Coletorlives** introduziu funcionalidades operacionais complementares de nuvem (Google Cloud Storage, Google Cloud Firestore, upload de vídeos editados por editores humanos, disparos automáticos para Telegram e webhook para radares externos).

A unificação integrou **todas as capacidades úteis do Coletorlives** dentro da arquitetura canônica e robusta do **TUTUCO CLIP MINER**, corrigindo simultaneamente três graves vulnerabilidades de segurança encontradas no Coletorlives original.

---

## 2. Matriz de Comparação e Unificação

| Módulo / Funcionalidade | TUTUCO CLIP MINER (Original) | Coletorlives (Auxiliar) | Solução Unificada Oficial |
|---|---|---|---|
| **Base Canônica** | Sim (Canônico) | Não | **TUTUCO CLIP MINER mantido como base** |
| **Banco de Dados** | SQLite local (`data/history.sqlite3`) | Google Cloud Firestore | **Arquitetura Híbrida:** SQLite preservado como autoridade local/processamento; Firestore atua como sincronizador de Product State quando configurado |
| **Armazenamento de Mídia** | Filesystem local (`data/`) | Google Cloud Storage | **Storage Abstraction (`miner/storage.py`):** `LocalStorageService` e `GCSStorageService` intercambiáveis |
| **Segurança GCS** | N/A (Local) | `blob.make_public()` (Inseguro) | **URLs Assinadas Privadas V4:** `make_public()` estritamente proibido; acesso privado com expiração |
| **Autenticação** | Token local CSRF (`X-Miner-Token`) | Senha fixa em código (Comprometida) | **RBAC (`miner/auth.py`):** PBKDF2/scrypt hashing, 3 perfis (Admin, Editor, Viewer), fail-closed sem senhas default |
| **Webhook de Radar** | N/A | `/api/webhook/radar` (Sem autenticação) | **`/api/webhook/radar` autenticado:** Validação com timing-safe digest de `RADAR_WEBHOOK_SECRET` |
| **Fluxo de Edição Humana** | Mapeamento e exportação de RAW | Upload de vídeo finalizado | **Workflow Integrado:** Corte → Aprovado → Em edição → Vídeo editado enviado → Pronto para postar |
| **Integração Telegram** | N/A | Script direto no `app.py` | **`TelegramService` (`miner/telegram.py`):** Envio de vídeo final + Pacote de Publicação com formatação rica e fallback gracioso |
| **Interface / UI** | Dark-first profissional (Product Pass 2) | Bootstrap 5 básico | **Interface Product Pass 2 Preservada e Enriquecida:** Workflow visual de 5 etapas, player de vídeo editado, badge de nuvem e usuário |
| **Deploy / Container** | Desktop Local (Waitress) | Dockerfile simples | **Docker Híbrido:** `Dockerfile` multi-stage com FFmpeg, Gunicorn e `docker-compose.yml` para nuvem ou local |

---

## 3. Vulnerabilidades Críticas de Segurança Eliminadas

1. **Remoção de Credencial Fixa em Código:**
   - Uma credencial hardcoded histórica foi removida e deve ser considerada comprometida.
   - Qualquer valor prévio foi totalmente expurgado de códigos, documentações e testes.
   - O módulo `miner/auth.py` não contém credenciais padrão embutidas e adota fail-closed.
   - Documentado no `SECURITY.md` com recomendação de rotação emergencial.

2. **Eliminação de Buckets Públicos:**
   - O Coletorlives executava `blob.make_public()`.
   - O `GCSStorageService` foi implementado para operar **exclusivamente com buckets privados**, gerando Signed URLs com validade temporária (V4) ou atuando via proxy local seguro.

3. **Proteção contra Injeção / Spam no Webhook Radar:**
   - O endpoint `/api/webhook/radar` no Coletorlives recebia qualquer requisição POST sem validação.
   - Na versão unificada, o endpoint exige autenticação por `X-Radar-Secret` ou token Bearer validado com `secrets.compare_digest`.

---

## 4. Arquitetura de Dados Unificada

Conforme detalhado no `DATABASE_AUDIT.md`:

```
┌─────────────────────────────────────────────────────────────┐
│                 TUTUCO CLIP MINER ENGINE                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 ┌──────────────────────┐             ┌──────────────────────┐
 │    PRODUCT STATE     │             │ LOCAL PROCESSING     │
 │  (Dados do Produto)  │             │      STATE           │
 ├──────────────────────┤             ├──────────────────────┤
 │ • candidates         │             │ • remote_jobs        │
 │ • vods               │             │ • jobs               │
 │ • remote_campaigns   │             │ • temp audio / chunks│
 │ • editorial_feedback │             │ • fast scan cache    │
 └──────────┬───────────┘             └──────────┬───────────┘
            │                                    │
    ┌───────┴───────┐                            ▼
    ▼               ▼                     [ SQLite Local ]
[ SQLite ]   [ Firestore ]
(Canônico)    (Sync Cloud)
```

- **Sem Nuvens / Modo Offline:** O aplicativo funciona 100% autônomo com SQLite e armazenamento local de arquivos em `data/edited/`.
- **Com Nuvem Ativa:** Quando variáveis GCP estão presentes, o `FirestoreSyncService` espelha os candidatos aprovados e vídeos editados para o Firestore e armazena os MP4s no Cloud Storage privado.

---

## 5. Verificação e Testes

A suíte completa de testes foi executada após a unificação:

- **Testes Python (`pytest`):**
  - Baseline anterior: 287 aprovados.
  - Novos testes adicionados:
    - `tests/test_storage.py` (2 testes)
    - `tests/test_telegram.py` (3 testes)
    - `tests/test_auth.py` (4 testes)
    - `tests/test_unification.py` (5 testes)
  - **Total Python:** **301 testes aprovados** (0 falhas).

- **Testes JavaScript / Node (`node --test tests/*.cjs`):**
  - **Total Node:** **33 testes aprovados** (0 falhas).

- **Verificação Estática e Linting:**
  - `node --check static/product.js`: Sem erros de sintaxe.
  - `python -m compileall app.py miner/`: 100% compilado com sucesso.
  - `PRAGMA integrity_check;`: `ok`.
