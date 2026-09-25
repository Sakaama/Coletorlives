# TUTUCO CLIP MINER — Especificação de Produto, UI & Design System

> **Documento Oficial de Arquitetura de Interface e Experiência do Usuário (UI/UX Pass)**  
> Versão: 2.0  
> Data: 25 de setembro de 2026  
> Projeto: `D:\Projetos\TUTUCO-CLIP-MINER`

---

## 1. Visão Geral e Filosofia de Produto

O **TUTUCO CLIP MINER** evoluiu de uma coleção de utilitários locais para uma plataforma profissional de **Clipping Intelligence**. A interface foi reconstruída com foco na operação diária de editores de vídeo e criadores de conteúdo, priorizando:

1. **Clareza Operacional Imediata:** Respostas visuais instantâneas para perguntas críticas (*O que está rodando? Quais clips precisam da minha atenção? De onde veio este momento?*).
2. **Design System Moderno (Dark-First):** Estética refinada inspirada em ferramentas como *Linear*, *Raycast* e *Vercel*, com densidade equilibrada, tipografia nítida, superfícies neutras escuras e sem elementos espalhafatosos (neon gamer, gradientes excessivos).
3. **Preservação Absoluta do Motor:** Camada de apresentação e roteamento 100% desacoplada do motor de processamento (Fast Scan, Faster Whisper, Heurísticas, Backlog Runner e SQLite).

---

## 2. Estrutura da Aplicação & App Shell

A interface utiliza uma estrutura de página única (SPA) modular e leve em Vanilla JavaScript, sem frameworks pesados, garantindo carregamento instantâneo e zero dependências de build:

```
┌────────────────────────────────────────────────────────────────────────┐
│ App Shell Container                                                    │
│ ┌───────────────┬────────────────────────────────────────────────────┐ │
│ │ Sidebar       │ Topbar (Breadcrumbs · Processing Pill · Quick CTA) │ │
│ │               ├────────────────────────────────────────────────────┤ │
│ │ • Overview    │ Page Views:                                        │ │
│ │   - Dashboard │  ├── #view-dashboard                              │ │
│ │ • Operação    │  ├── #view-campaigns                               │ │
│ │   - Campanhas │  ├── #view-creators                                │ │
│ │   - Criadores │  ├── #view-sources                                 │ │
│ │   - Fontes    │  ├── #view-inbox (Cards / Table Mode)              │ │
│ │   - Inbox     │  ├── #view-dna                                     │ │
│ │ • Inteligênc. │  ├── #view-publisher (Roadmap)                     │ │
│ │   - DNA       │  ├── #view-analytics (Roadmap)                     │ │
│ │ • Roadmap     │  ├── #view-system                                  │ │
│ │   - Publisher │  └── #vod-view (Inspector legado preservado)       │ │
│ │   - Analytics ├────────────────────────────────────────────────────┤ │
│ │ • Sistema     │ Modals: Preview Video Dialog · Clip Detail Modal   │ │
│ └───────────────┴────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Telas e Módulos do Produto

### 3.1. Dashboard (`#view-dashboard`)
- **Painel de Processamento Ativo:** Informa em tempo real qual tarefa ou VOD está sendo minerada, etapa atual, barra de progresso real e botão para pausa segura. Em estado ocioso, exibe o selo "Motor Local Ocioso e Pronto".
- **Grid de Indicadores Chave (KPIs):**
  - *Campanhas Ativas:* Contador de campanhas registradas.
  - *Criadores Monitorados:* Contagem de criadores (GabePeixe, BRKK, BRABOX, etc.).
  - *Horas Analisadas:* Total acumulado de horas de transmissão já processadas pelo Whisper.
  - *VODs Processadas:* Relação entre transmissões concluídas e total em catálogo.
  - *Aguardando Curadoria:* Total de momentos gerados na Inbox que aguardam revisão do editor.
  - *Clips Aprovados:* Total de cortes aceitos prontos para extração RAW ou PREP vertical 9:16.
- **Feed de Atividade Recente:** Linha do tempo cronológica com revisões editoriais, conclusões de tarefas e novos discoveries com badges coloridos (`success`, `danger`, `accent`).

### 3.2. Campanhas (`#view-campaigns`)
- **Cartões Operacionais de Campanhas:**
  - Identificação clara entre campanha oficial (`GabePeixe · Campeonato Kick 2026`) e rascunhos de teste.
  - Período de vigência, plataforma/provider e contadores de VODs e candidatos.
  - Botão de acesso direto à operação da campanha.
- **Backlog Runner Integrado:**
  - Painel de controle completo (`Iniciar`, `Pausar`, `Retomar`, `Atualizar`).
  - Grid de status com contagem de concluídas, em fila, falhas e shortlists prontas.
  - Fila persistente ordenada da live mais recente para a mais antiga.

### 3.3. Criadores (`#view-creators`)
- **Cards de Criadores:**
  - Avatar expressivo, nome e arroba (@streamer).
  - Tags de plataformas ativas (Kick, YouTube, Twitch).
  - Contadores rápidos: VODs analisadas, horas de transmissão e clips extraídos.
  - Snippet do Creator DNA e botão para perfil aprofundado.

### 3.4. Creator DNA & Inteligência de Estilo (`#view-dna`)
- **Mapeamento Editorial do Streamer:**
  - *Tom & Personalidade:* Comportamento emocional em live (energético, espontâneo, tático, reativo).
  - *Formatos de Alta Retenção:* Tags de categorias com melhor tração (Rage/Fail, Vitória Épica, React, Diálogo de Squad).
  - *Tópicos Recorrentes:* Games e temas centrais minerados.
  - *Duração Típica Recomendada:* Faixa ideal em segundos calculada pelo histórico.
  - *Calibração Automática de IA:* Indicação do estado de maturidade do aprendizado com base nos cortes já revisados.

### 3.5. Fontes & VODs (`#view-sources`)
- **Identificação Humana das Transmissões:**
  - Substituição de UUIDs técnicos por Título da Live, Criador, Data legível (`AAAA-MM-DD`) e Duração formatada (`Xh Ym`).
  - Badges semânticos de status operacional:
    - `Processed` (Verde): Análise concluída com candidatos gerados.
    - `Queued` (Neutro): Em fila para o Backlog Runner.
    - `Processing` (Índigo/Pulsante): Em mineração ativa no momento.
    - `Failed` (Vermelho): Falha isolada com exibição humana do motivo (ex.: live em andamento sem duração final).
- **Filtros e Busca em Tempo Real:**
  - Busca por palavra-chave no título da live ou ID.
  - Filtro por Criador, Status operacional e Plataforma.
- **Ações:**
  - Acesso direto ao Inspector individual de VOD com player e recorte de câmera.
  - Filtro instantâneo no Clip Inbox para exibir somente cortes daquela VOD.

### 3.6. Clip Inbox (`#view-inbox`) — Centro de Curadoria Humana
- **Modos de Visualização Alternáveis:**
  - **Modo Cards:** Ideal para revisão visual e leitura da transcrição de cada momento.
  - **Modo Tabela Compacta:** Ideal para revisão rápida em alto volume com densidade máxima.
- **Filtros Ágeis:**
  - *Classificação Editorial:* `🔥 Shortlist (Recomendados + Bons)`, `RECOMENDADO (Score ≥ 82)`, `BOM (Score ≥ 68)`, `TALVEZ`, `FRACO`, `TODOS`.
  - *Status da Revisão:* `NOVO (Aguardando)`, `APROVADO`, `DESCARTADO`, `TODOS`.
  - *Busca:* Busca instantânea por termos falados na transcrição, título ou gancho.
- **Ações de Revisão em 1 Clique:**
  - `✓ Aprovar`: Marca o candidato como aprovado, atualiza o contador do card imediatamente e grava feedback no banco.
  - `✕ Descartar`: Desativa o corte da lista ativa com feedback visual esmaecido.
  - `▶ Preview`: Dispara a geração/leitura do preview de 30s-60s com reprodução no modal de vídeo.
  - `⋯ Detalhes`: Abre o modal de inspeção minuciosa com transcrição completa, heurísticas e opções de download.

### 3.7. Clip Detail Modal (`#clip-detail-modal`)
- Reúne em janela modal limpa e operacional:
  - **Fluxo Visual de 5 Estágios:** Indicador interativo do progresso: `Corte Mapeado → Aprovado → Em edição → Vídeo editado enviado → Pronto para postar`.
  - Cabeçalho com pontuação editorial e classificação (`RECOMENDADO`, `BOM`, `TALVEZ`, `FRACO`).
  - Informações de origem (Criador, título da live, timestamps precisos `01:23:45 → 01:24:35`, duração e atividade visual).
  - Caixa de transcrição integral transcrita pelo Whisper com as falas do trecho.
  - **Player de Vídeo Final Editado:** Quando o vídeo final é enviado, exibe reprodutor HTML5 integrado com suporte a download direto do arquivo final.
  - **Área de Upload de Vídeo Editado:** Permite ao editor anexar o arquivo `.mp4` finalizado com anotações e opção de disparo automático para o Telegram.
  - **Pacote de Publicação & Gerador de Legendas:** Seletor de redes sociais (TikTok, Shorts, Reels, Kwai), legenda personalizável, menções e hashtags obrigatórias do streamer, e checklist de conformidade visual (LOWER obrigatório, ausência de IA 100% não curada, datas).
  - **Ações de Publicação:** Botão `Copiar Legenda`, `Copiar Pacote Completo` e `✈️ Enviar para Telegram`.

### 3.8. Diagnóstico & Sistema (`#view-system`)
- Painel para verificação do ambiente local e nuvem:
  - Binários locais: caminho e disponibilidade de FFmpeg e FFprobe.
  - Aceleração de hardware: detecção de GPU NVIDIA CUDA vs CPU multithread.
  - Banco de dados: caminho do arquivo SQLite e integridade (`PRAGMA integrity_check: ok`).
  - **Nuvem & Publicação Unificada:** Detecção do modo de armazenamento (`LOCAL` vs `GCS`), conexão com Google Firestore, configuração do Bot Telegram e status do controle de acesso por perfis (RBAC).

---

## 4. Design System & Tokens Visuais

O design system segue uma estrutura estrita de tokens CSS em [static/product.css](file:///D:/Projetos/TUTUCO-CLIP-MINER/static/product.css):

### Cores e Superfícies
| Token | Valor Hex | Finalidade |
|---|---|---|
| `--bg-app` | `#080A0E` | Fundo principal da aplicação |
| `--bg-sidebar` | `#0D1017` | Barra de navegação lateral fixa |
| `--bg-surface` | `#121620` | Superfície padrão de cards e tabelas |
| `--bg-elevated` | `#181E2B` | Superfícies elevadas, tooltips e botões |
| `--bg-card` | `#141923` | Cards do Clip Inbox |
| `--border-subtle` | `rgba(255,255,255,0.08)` | Linhas divisórias e bordas sutis |
| `--border-medium` | `rgba(255,255,255,0.14)` | Bordas de foco e elementos interativos |

### Cores Semânticas
| Semântica | Cor Hex / Token | Aplicação |
|---|---|---|
| **Accent / Primária** | `#6366F1` (Índigo) | Botões principais, links ativos, seleção |
| **Sucesso** | `#10B981` (Esmeralda) | Status Aprovado, VOD Processed, KPIs positivos |
| **Alerta** | `#F59E0B` (Âmbar) | Itens na fila, avisos de regras de campeonato |
| **Perigo** | `#EF4444` (Rosa/Vermelho) | Descartar clip, VOD com falha isolada |
| **Neutro** | `#64748B` (Slate) | Labels secundárias, metadados de tempo |

---

## 5. Endpoints de Apresentação (Camada Segura de API)

Criados em [miner/presentation.py](file:///D:/Projetos/TUTUCO-CLIP-MINER/miner/presentation.py) e registrados em [app.py](file:///D:/Projetos/TUTUCO-CLIP-MINER/app.py):

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/product/dashboard` | Retorna métricas consolidadas, processamento ativo e feed de atividade recente. |
| `GET` | `/api/product/creators` | Retorna lista de criadores com horas analisadas, lives, cortes e status factual. |
| `GET` | `/api/product/creator/<key>/workspace` | Retorna workspace individualizado do criador (regras de campeonato, template visual, lives, cortes e Perfil de Cortes). |
| `POST` | `/api/product/caption/generate` | Gera pacote de publicação determinístico (regras, hashtags, menções, checklist) com legenda criativa por plataforma. |
| `GET` | `/api/product/inbox` | Retorna lista de cortes enriquecida com filtros de classificação, status, criador e busca. |
| `GET` | `/api/product/vods` | Retorna catálogo unificado de lives/VODs com status operacional em português (`Analisado`, `Processando`, `Na Fila`, `Erro`). |

---

## 6. Pass 2: Creator Workspace & Pacote de Publicação

### 6.1 Creator Workspace
- Página individual dedicada para cada streamer: GabePeixe, BRKK, BRABOX, João Pichau e Juninho Manella.
- Navegação em abas: **Visão Geral | Campeonato | Lives | Cortes | Perfil de Cortes**.
- Cards inteiros clicáveis em `/creators`.
- Perfil honesto sem adjetivos comportamentais inventados: templates visuais reais (1080x1920 9:16, layouts visual/talking) e status factual em construção.

### 6.2 Pacote de Publicação & Gerador de Legendas
- Serviço desacoplado em `miner/caption.py` (`CaptionGenerator`).
- **Regra inquebrável**: Regras do campeonato (hashtags, menções oficiais, lower obrigatório, janela de elegibilidade) são **100% determinísticas** e extraídas diretamente de `config/campaigns/<id>.json`.
- Variações criativas de gancho e legenda adaptadas por plataforma: **TikTok, YouTube Shorts, Instagram Reels e Kwai**.
- Ações no modal de detalhe:
  - **Copiar Legenda** (área de transferência em 1 clique)
  - **Copiar Pacote Completo** (legenda + marcações + checklist de conformidade)
  - **Gerar Outra Legenda** (regenera variações com base contextual no hook/transcrição)
  - **Checklist de Conformidade do Campeonato** com validação visual de obrigações (LOWER, menção, tags, política anti-IA 100%, engajamento orgânico).

---

## 7. Funcionalidades Preparadas mas Não Implementadas (Roadmap)

As seguintes páginas e conceitos foram preparados visualmente para dar clareza de futuro, sem adicionar código de máquina prematuro:

1. **Publisher Automático:** Módulo de distribuição para agendamento e envio automático de arquivos aos canais oficiais (Shorts, TikTok, Reels).
2. **Analytics & Funil de Retenção:** Visualização gráfica de taxa de clique do hook, retenção nos primeiros 3 segundos e correlação de formatos.
3. **Calibração de Modelos de IA:** Ajuste fino supervisionado de modelos com base nos cortes aprovados pelo operador humano.

---

## 7. Dívidas Técnicas Identificadas para Próximas Etapas

1. **Caminhos Absolutos na Tabela `exports`:** 29 registros antigos de testes com a campanha BRKK retêm o caminho `D:\Projetos\TUTUCO-CLIP-MINER\...`. Se o projeto for movido de máquina, esses caminhos devem ser atualizados via script SQL documentado no `LEIA-ME-ENTREGA.md`.
2. **Normalização de Metadados de VOD:** Alguns campos operacionais (duração, títulos, URLs) encontram-se dentro de uma coluna JSON (`vods.data`). Uma futura migração não-destrutiva poderá extrair esses campos para colunas indexadas no SQLite caso o volume supere 1.000 VODs.
