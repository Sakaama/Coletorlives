# TUTUCO CLIP MINER

<div align="center">

**Plataforma de Inteligência Editorial, Mineração de VODs e Curadoria de Cortes para Streamers**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 301 Python + 33 Node](https://img.shields.io/badge/Tests-301%20Python%20%7C%2033%20Node%20Passing-success.svg)](#testes-e-validação)
[![Docker Support](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](#execução-com-docker)

</div>

---

## 📌 Visão Geral

O **TUTUCO CLIP MINER** é uma aplicação completa de inteligência editorial desenvolvida para equipes de corte, editores e streamers. A plataforma monitora transmissões de longa duração (Kick, YouTube, Twitch), realiza varredura acústica e semântica com **Fast Scan** e **Faster Whisper**, classifica momentos candidatos por pontuação editorial e entrega um fluxo completo de curadoria: da VOD bruta ao vídeo editado pronto para postar nas redes sociais.

> [!NOTE]
> **Curadoria Humana Obrigatória:** O Tutuco Clip Miner não é um "bot gerador de memes aleatórios". O motor seleciona os melhores momentos candidatos e gera pacotes de publicação determinísticos, garantindo que o olhar e a criatividade do editor humano definam o corte final em conformidade com as regras dos campeonatos.

---

## 🏛️ Os 4 Pilares da Arquitetura

O sistema é estruturado em quatro pilares modulares de inteligência:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      TUTUCO CLIP MINER ARCHITECTURE                     │
├─────────────────┬─────────────────┬──────────────────┬──────────────────┤
│    PILAR 1      │     PILAR 2     │     PILAR 3      │     PILAR 4      │
│  RADAR & FONTE  │  MINING ENGINE  │  CREATOR DNA &   │  DISTRIBUIÇÃO &  │
│                 │  & EDITORIAL AI │    WORKSPACE     │    PUBLISHER     │
├─────────────────┼─────────────────┼──────────────────┼──────────────────┤
│ • Kick & YT VODs│ • Fast Scan     │ • Workspace      │ • Upload Vídeo   │
│ • Webhook Radar │ • Faster Whisper│ • Template 9:16  │ • GCS Privado    │
│ • Discovery     │ • Heurística    │ • Regras Campanha│ • Telegram Bot   │
│ • Deduplicação  │ • Visual Score  │ • Legendas       │ • SQLite/Cloud   │
└─────────────────┴─────────────────┴──────────────────┴──────────────────┘
```

1. **Pilar 1 — Radar & Ingestão de Fontes:**
   Monitoramento de canais, descoberta de VODs recentes por provedores (Kick/YouTube/Twitch) e recepção de alertas em tempo real via Webhook autenticado (`/api/webhook/radar`).
2. **Pilar 2 — Motor de Mineração & Inteligência Editorial:**
   Pipeline Fast Scan em chunks de 10 minutos, transcrição seletiva de áudio a 16 kHz com Faster Whisper, cálculo de atividade visual e pontuação editorial heurística (0–100).
3. **Pilar 3 — Creator DNA & Workspace do Criador:**
   Espaço operacional individual para cada criador (GabePeixe, BRKK, Brabox, etc.), perfil de cortes, templates visuais 9:16 (CapCut/Premiere), verificação estrita de conformidade (LOWER, menções e hashtags obrigatórias) e gerador determinístico de legendas.
4. **Pilar 4 — Distribuição & Publicação Unificada:**
   Fluxo completo de edição humana (`Corte → Aprovado → Em edição → Vídeo editado enviado → Pronto para postar`), reprodutor integrado para o arquivo final, armazenamento híbrido (Local ou Google Cloud Storage privado com Signed URLs) e publicação em 1 clique para Telegram.

---

## ⚡ Início Rápido

### Pré-requisitos
- Python 3.11 ou 3.12
- Node.js 20+ (para testes de interface)
- FFmpeg e FFprobe instalados e disponíveis no `PATH` do sistema

### Execução no Windows (Local)
Dê dois cliques no arquivo **`iniciar.bat`** ou execute no terminal:

```powershell
# Criação do ambiente virtual
py -3.12 -m venv .venv
.\.venv\Scripts\activate

# Instalação das dependências
pip install -r requirements.txt

# Inicialização do servidor
python app.py
```

A aplicação abrirá automaticamente no navegador em:  
👉 **`http://127.0.0.1:8765`**

---

## 🐳 Execução com Docker

O projeto possui suporte a contêineres Docker multi-stage com FFmpeg e Gunicorn:

```bash
# Copie o arquivo de exemplo de ambiente
cp .env.example .env

# Suba a aplicação com Docker Compose
docker-compose up --build
```

Acesse em `http://localhost:8765`. Os dados de histórico SQLite e uploads são persistidos na pasta `./data`.

---

## 💾 Arquitetura Híbrida de Dados: Local vs Nuvem

O TUTUCO CLIP MINER divide os dados em duas categorias:

- **Product State (Estado de Produto):**
  Candidatos minerados, histórico de aprovação/descarte, metadados de transmissões e configurações de campanha. É gravado canonicamente no **SQLite Local** (`data/history.sqlite3`) e sincronizado para o **Google Cloud Firestore** quando credenciais de nuvem são configuradas.
- **Local Processing State (Estado de Processamento):**
  Fila de downloads em andamento, chunks temporários de áudio e tarefas assíncronas do Backlog Runner permanecem estritamente no armazenamento local da máquina.
- **Armazenamento de Mídia (`StorageService`):**
  - **Modo Local:** Grava cortes editados em `data/edited/` com URLs de streaming seguras.
  - **Modo Nuvem (GCS):** Grava no bucket do Google Cloud Storage com buckets privados e **Signed URLs V4 temporárias**. Proibido o uso de `make_public()`.

---

## 🔐 Controle de Acesso e Segurança (RBAC)

O sistema conta com autenticação por perfis de acesso baseada em PBKDF2/scrypt (`werkzeug.security`):

- **Admin (Nível 30):** Operação total de mineração, runner, configurações e deleção.
- **Editor (Nível 20):** Aprovação/descarte no Clip Inbox, upload de vídeos editados e envio ao Telegram.
- **Viewer (Nível 10):** Visualização somente-leitura de candidatos e métricas.

> [!IMPORTANT]
> **Modo Local vs Cloud:** Quando `AUTH_REQUIRED=false` (padrão local), a aplicação oferece acesso imediato para desenvolvedores sem login. Quando `AUTH_REQUIRED=true`, a proteção por sessão e tokens passa a ser obrigatória. Veja detalhes em [`SECURITY.md`](SECURITY.md).

---

## 📡 Endpoints Principais da API

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/api/health` | Diagnóstico de binários, hardware, integridade do SQLite e status da nuvem |
| `GET` | `/api/product/dashboard` | Métricas operacionais em tempo real e tarefas ativas |
| `GET` | `/api/product/inbox` | Listagem paginada de cortes com filtros por criador, classificação e status |
| `POST` | `/api/product/caption/generate` | Geração de legenda e pacote de publicação determinístico |
| `POST` | `/api/product/clip/<id>/upload-edited` | Upload multipart do vídeo final editado (.mp4) com persistência e status |
| `POST` | `/api/product/clip/<id>/send-telegram` | Disparo do vídeo editado + pacote de legenda para o Telegram |
| `POST` | `/api/webhook/radar` | Recepção autenticada de alertas e eventos de radar externo |
| `POST` | `/api/auth/login` / `/logout` | Autenticação e encerramento de sessão RBAC |

---

## 🧪 Testes e Validação

A qualidade da aplicação é garantida por testes de unidade e integração:

```bash
# Executar todos os testes Python (301 testes)
pytest

# Executar testes específicos da unificação
pytest tests/test_unification.py tests/test_auth.py tests/test_storage.py tests/test_telegram.py

# Executar testes headless de interface Node.js (33 testes)
node --test tests/*.cjs

# Verificação estática de sintaxe e linting
node --check static/product.js
ruff check .
```

---

## 📄 Licença

Distribuído sob licença MIT. Consulte [`LICENSE`](LICENSE) para mais informações.
