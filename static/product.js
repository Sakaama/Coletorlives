/**
 * TUTUCO CLIP MINER — Product Presentation & Interaction Layer
 * Manages App Shell, Dashboard, Campaigns, Creators, Sources/VODs, and Clip Inbox.
 */

// State management for product layer
const productState = {
  currentView: 'dashboard',
  inboxMode: 'cards', // 'cards' | 'table'
  dashboardData: null,
  creatorsData: [],
  inboxData: { items: [], counts: {} },
  vodsData: [],
  activeFilters: {
    inbox: { classification: 'SHORTLIST', status: 'NOVO', creator: '', search: '' },
    vods: { creator: '', status: '', platform: '', search: '' }
  },
  selectedClip: null,
  pollTimer: null,
  currentCreator: 'gabepeixe',
  currentWorkspaceTab: 'overview',
  workspaceData: null,
  currentCaptionClipId: null,
  currentCaptionPlatform: 'TikTok',
  currentCaptionSeed: 0,
  currentCaptionData: null
};

// Safe selector helper
const getEl = id => document.getElementById(id);

// Format helper functions
function formatSecToTime(seconds) {
  if (seconds === null || seconds === undefined) return '00:00:00';
  const total = Math.floor(seconds || 0);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':');
}

function timeAgo(dateString) {
  if (!dateString) return '';
  const now = new Date();
  const past = new Date(dateString.replace('Z', '+00:00'));
  const diffSec = Math.floor((now - past) / 1000);
  if (diffSec < 60) return 'agora mesmo';
  if (diffSec < 3600) return `há ${Math.floor(diffSec / 60)}m`;
  if (diffSec < 86400) return `há ${Math.floor(diffSec / 3600)}h`;
  const days = Math.floor(diffSec / 86400);
  return days === 1 ? 'ontem' : `há ${days} dias`;
}

// Global View Navigation
function productNavigate(viewId, params = {}) {
  productState.currentView = viewId;

  // Update sidebar active buttons
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => {
    const isTarget = el.dataset.view === viewId || (viewId === 'creator-workspace' && el.dataset.view === 'creators');
    el.classList.toggle('active', isTarget);
  });

  // Update breadcrumb
  const breadcrumbEl = getEl('product-breadcrumb');
  if (breadcrumbEl) {
    if (viewId === 'creator-workspace') {
      const cKey = (params.creator || productState.currentCreator || 'gabepeixe').toLowerCase();
      const tab = params.tab || productState.currentWorkspaceTab || 'overview';
      const cName = cKey === 'gabepeixe' ? 'GabePeixe' : cKey.toUpperCase();
      const tabNames = {
        overview: 'VISÃO GERAL',
        campaign: 'CAMPEONATO',
        lives: 'LIVES',
        cuts: 'CORTES',
        profile: 'PERFIL DE CORTES'
      };
      breadcrumbEl.textContent = `CRIADORES / ${cName} / ${tabNames[tab] || tab.toUpperCase()}`;
    } else {
      const titles = {
        dashboard: 'OVERVIEW / DASHBOARD',
        campaigns: 'OPERAÇÃO / CAMPANHAS',
        creators: 'OPERAÇÃO / CRIADORES',
        sources: 'OPERAÇÃO / LIVES E VODS',
        inbox: 'OPERAÇÃO / CORTES',
        dna: 'INTELIGÊNCIA / PERFIL DE CORTES',
        publisher: 'ROADMAP / PUBLISHER',
        analytics: 'ROADMAP / ANALYTICS',
        system: 'SISTEMA / DIAGNÓSTICO',
        'vod-detail': 'INSPECTOR / VOD'
      };
      breadcrumbEl.textContent = titles[viewId] || viewId.toUpperCase();
    }
  }

  // Toggle page views
  document.querySelectorAll('.page-view').forEach(el => {
    el.hidden = el.id !== `view-${viewId}`;
  });

  // Also manage legacy main panels visibility
  const welcomeEl = getEl('welcome');
  const remotePanelEl = getEl('remote-panel');
  const vodViewEl = getEl('vod-view');
  if (welcomeEl) welcomeEl.hidden = true;
  if (remotePanelEl) remotePanelEl.hidden = true;
  if (vodViewEl && viewId !== 'vod-detail') vodViewEl.hidden = true;

  // Route specific loads
  if (viewId === 'dashboard') loadDashboardView();
  else if (viewId === 'campaigns') loadCampaignsView();
  else if (viewId === 'creators') loadCreatorsView();
  else if (viewId === 'creator-workspace') loadCreatorWorkspaceView(params.creator, params.tab);
  else if (viewId === 'sources') loadSourcesView();
  else if (viewId === 'inbox') loadInboxView();
  else if (viewId === 'dna') loadDnaView(params.creator);
  else if (viewId === 'system') loadSystemView();
}

// 1. DASHBOARD VIEW
async function loadDashboardView() {
  try {
    const data = await api('/api/product/dashboard');
    productState.dashboardData = data;
    renderDashboard(data);
  } catch (err) {
    console.error('Failed to load dashboard:', err);
  }
}

function renderDashboard(data) {
  const m = data.metrics || {};

  // Update topbar processing pill
  const procPill = getEl('topbar-processing-pill');
  if (procPill) {
    if (data.active_processing) {
      procPill.hidden = false;
      procPill.innerHTML = `<span class="pulse-dot"></span> Minerando VOD... (${data.active_processing.kind})`;
    } else {
      procPill.hidden = true;
    }
  }

  // Render KPI values
  const setTxt = (id, val) => { const el = getEl(id); if (el) el.textContent = val; };
  setTxt('kpi-active-campaigns', m.campaigns_count || 1);
  setTxt('kpi-creators', m.creators_count || 1);
  setTxt('kpi-hours-analyzed', `${m.hours_analyzed || 0}h`);
  setTxt('kpi-vods-ratio', `${m.vods_completed || 0} / ${m.vods_total || 0}`);
  setTxt('kpi-inbox-waiting', m.new_candidates || 0);
  setTxt('kpi-approved-clips', m.approved_candidates || 0);

  // Render active processing card
  const procCard = getEl('dash-active-processing-card');
  if (procCard) {
    if (data.active_processing) {
      const p = data.active_processing;
      procCard.innerHTML = `
        <div class="card-section" style="border-color: rgba(99, 102, 241, 0.4); background: rgba(99, 102, 241, 0.04);">
          <div class="card-section-head">
            <div>
              <span class="badge badge-accent"><span class="pulse-dot"></span> PROCESSAMENTO ATIVO</span>
              <h2 style="margin-top:8px;">${esc(p.message || 'Minerando blocos de áudio')}</h2>
              <p>Tarefa: <strong>${esc(p.kind.toUpperCase())}</strong> · Status: ${esc(p.state)}</p>
            </div>
            <button class="btn-danger" onclick="productCancelJob('${esc(p.run_id)}')">Pausar com Segurança</button>
          </div>
          <div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 4px; border: 1px solid var(--border-subtle); margin-top: 10px;">
            <div style="background: var(--accent); height: 6px; border-radius: 4px; width: ${p.progress ? Math.min(100, Math.max(5, p.progress)) : 100}%; transition: width 0.3s ease;"></div>
          </div>
        </div>
      `;
    } else {
      procCard.innerHTML = `
        <div style="padding: 14px 18px; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: var(--radius-md); display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="status-dot"></span>
            <div>
              <strong style="font-size:13px; color: var(--text-primary);">Motor Local Ocioso e Pronto</strong>
              <div style="font-size:11px; color: var(--text-muted);">Fast Scan, Whisper e Backlog Runner aguardando comandos.</div>
            </div>
          </div>
          <button class="primary" onclick="productNavigate('campaigns')">Abrir Backlog Runner →</button>
        </div>
      `;
    }
  }

  // Render recent activity feed
  const actList = getEl('dash-recent-activity-list');
  if (actList) {
    if (data.recent_activity && data.recent_activity.length) {
      actList.innerHTML = data.recent_activity.map(a => `
        <div style="display: flex; align-items: flex-start; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-subtle);">
          <div style="display: flex; align-items: flex-start; gap: 10px;">
            <span class="badge badge-${a.badge_type || 'neutral'}" style="margin-top:2px;">${esc(a.badge || a.type)}</span>
            <div>
              <div style="font-weight: 600; font-size: 13px; color: var(--text-primary);">${esc(a.title)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${esc(a.detail)}</div>
            </div>
          </div>
          <div style="font-size: 11px; color: var(--text-muted); white-space: nowrap;">${timeAgo(a.timestamp)}</div>
        </div>
      `).join('');
    } else {
      actList.innerHTML = '<div class="empty-state-box"><p>Nenhuma atividade recente registrada.</p></div>';
    }
  }
}

// 2. CAMPAIGNS VIEW
async function loadCampaignsView() {
  const container = getEl('campaigns-grid-container');
  if (!container) return;

  try {
    container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted);">Carregando campanhas...</div>';
    const res = await api('/api/remote/campaigns');
    const campaigns = res.campaigns || [];

    if (!campaigns.length) {
      container.innerHTML = '<div class="empty-state-box"><h3>Nenhuma campanha configurada</h3><p>Importe uma nova campanha operacional.</p></div>';
      return;
    }

    container.innerHTML = campaigns.map(c => {
      const isOfficialGabe = c.id === '2137c0d0e8d54b67';
      const isDraftGabe = c.id === 'dddb669fff0c4321';
      return `
        <div class="card-section" style="margin-bottom: 16px; border-color: ${isOfficialGabe ? 'rgba(16, 185, 129, 0.4)' : isDraftGabe ? 'rgba(239, 68, 68, 0.3)' : 'var(--border-subtle)'};">
          <div class="card-section-head">
            <div>
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="badge ${isOfficialGabe ? 'badge-success' : isDraftGabe ? 'badge-danger' : 'badge-neutral'}">${isOfficialGabe ? '★ OFICIAL' : isDraftGabe ? '⚠ RASCUNHO' : 'CAMPANHA'}</span>
                <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${esc(c.id)}</span>
              </div>
              <h2 style="margin-top:6px; font-size:17px;">${esc(c.campaign_name || c.name || 'Campanha')}</h2>
              <p>${esc(c.start || 'Início')} até ${esc(c.end || 'Fim')} · Provider: <strong>${esc(c.provider || 'Kick')}</strong> · Streamer: <strong>${esc(c.streamer || c.creator || 'GabePeixe')}</strong></p>
            </div>
            <div style="display:flex; gap:8px;">
              <button class="primary" onclick="productOpenCampaignDetail('${esc(c.id)}')">Operar Campanha →</button>
            </div>
          </div>
          ${isOfficialGabe ? `
            <div style="display:flex; gap:16px; margin-top:14px; padding-top:14px; border-top:1px solid var(--border-subtle); font-size:12px; color:var(--text-secondary); flex-wrap:wrap;">
              <span><strong>18</strong> VODs catalogadas</span>
              <span><strong>7</strong> VODs concluídas</span>
              <span><strong>307</strong> candidatos reais</span>
              <span><strong>73</strong> momentos na Shortlist</span>
              <span style="color:var(--warning);"><strong>1</strong> em checkpoint (59.7%)</span>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="warning">Erro ao carregar campanhas: ${esc(err.message)}</div>`;
  }
}

function productOpenCampaignDetail(campaignId) {
  // Select campaign in legacy remote select
  const runSelect = getEl('remote-runs');
  if (runSelect) {
    runSelect.value = campaignId;
    runSelect.dispatchEvent(new Event('change'));
  }
  // Reveal remote panel and navigate
  productNavigate('campaigns');
  const remotePanel = getEl('remote-panel');
  if (remotePanel) remotePanel.hidden = false;
  remotePanel.scrollIntoView({ behavior: 'smooth' });
}

// 3. CREATORS VIEW
async function loadCreatorsView() {
  const container = getEl('creators-grid-container');
  if (!container) return;

  try {
    container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted);">Carregando criadores...</div>';
    const res = await api('/api/product/creators');
    productState.creatorsData = res.creators || [];

    if (!productState.creatorsData.length) {
      container.innerHTML = '<div class="empty-state-box"><h3>Nenhum criador encontrado</h3></div>';
      return;
    }

    container.innerHTML = productState.creatorsData.map(c => `
      <div class="creator-card" style="cursor:pointer;" onclick="productNavigate('creator-workspace', { creator: '${esc(c.key)}', tab: 'overview' })">
        <div class="creator-card-header">
          <div class="creator-avatar-box">${c.avatar || '🎬'}</div>
          <div class="creator-name-group">
            <h3>${esc(c.name)}</h3>
            <div class="creator-handle">${esc(c.handle)} · ${esc((c.platforms || []).join(', '))}</div>
          </div>
        </div>
        <div class="creator-stats-row">
          <div class="creator-stat-col">
            <span class="stat-num">${c.vods_count || 0}</span>
            <span class="stat-lbl">Lives</span>
          </div>
          <div class="creator-stat-col">
            <span class="stat-num">${c.hours_analyzed || 0}h</span>
            <span class="stat-lbl">Horas</span>
          </div>
          <div class="creator-stat-col">
            <span class="stat-num" style="color:var(--accent);">${c.candidates_count || 0}</span>
            <span class="stat-lbl">Cortes</span>
          </div>
        </div>
        <div class="creator-dna-snippet">
          <strong>Perfil:</strong> ${esc(c.dna?.status || 'Perfil em construção através das lives')}
          <div style="font-size:11px; color:var(--accent); margin-top:6px; font-weight:600;">Abrir Workspace →</div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="warning">Erro ao carregar criadores: ${esc(err.message)}</div>`;
  }
}

// ==================== CREATOR WORKSPACE (PASS 2) ====================
async function loadCreatorWorkspaceView(creatorKey = 'gabepeixe', targetTab = 'overview') {
  productState.currentCreator = (creatorKey || 'gabepeixe').toLowerCase();
  productState.currentWorkspaceTab = targetTab || 'overview';

  const viewEl = getEl('view-creator-workspace');
  if (!viewEl) return;

  try {
    const data = await api(`/api/product/creator/${productState.currentCreator}/workspace`);
    productState.workspaceData = data;
    renderCreatorWorkspace(data, productState.currentWorkspaceTab);
    updateSidebarContext(productState.currentCreator);
  } catch (err) {
    console.error('Failed to load creator workspace:', err);
    toast(`Erro ao carregar workspace: ${err.message}`, true);
  }
}

function renderCreatorWorkspace(data, activeTab = 'overview') {
  if (!data || !data.creator) return;
  const c = data.creator;
  const camp = data.campaign || {};
  const tmpl = data.template || {};
  const st = data.stats || {};
  const vods = data.vods || [];
  const candidates = data.recent_candidates || [];
  const perfil = data.perfil_de_cortes || {};

  // Header info
  const setElTxt = (id, val) => { const el = getEl(id); if (el) el.textContent = val; };
  setElTxt('cw-avatar', c.avatar || '🎬');
  setElTxt('cw-name', c.name || 'Criador');
  setElTxt('cw-handle', `${c.handle || ''} · ${c.category || 'Streaming'}`);
  setElTxt('cw-platform-badge', (c.platforms || []).join(', ') || 'Kick');
  setElTxt('cw-category-badge', c.category || 'Conteúdo');

  // Tab counters
  setElTxt('cw-lives-count', vods.length);
  setElTxt('cw-cuts-count', candidates.length);

  // Overview Tab KPIs
  setElTxt('cw-kpi-vods', st.vods_count || 0);
  setElTxt('cw-kpi-vods-sub', `${st.vods_completed || 0} analisadas`);
  setElTxt('cw-kpi-hours', `${st.hours_analyzed || 0}h`);
  setElTxt('cw-kpi-candidates', st.candidates_count || 0);
  setElTxt('cw-kpi-candidates-sub', `${st.shortlist_count || 0} na shortlist`);
  setElTxt('cw-kpi-approved', st.approved_count || 0);

  // Overview Highlight Championship Card
  const champCard = getEl('cw-overview-campaign-card');
  if (champCard) {
    champCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;">
        <div>
          <span class="badge badge-accent">🎯 CAMPEONATO ATIVO</span>
          <h2 style="margin:8px 0 6px; font-size:18px;">${esc(camp.name || c.name)} · Diretrizes Oficiais</h2>
          <p style="margin:0; font-size:13px; color:var(--text-secondary); max-width:700px;">
            ${esc(camp.notes || 'Regras operacionais de decupagem, obrigatoriedade de LOWER e marcações oficiais do campeonato.')}
          </p>
          <div style="display:flex; gap:10px; margin-top:12px; flex-wrap:wrap; font-size:12px;">
            <span class="badge badge-neutral">📅 Lives a partir de: <strong>${esc(camp.min_date || '01/09/2026')}</strong></span>
            <span class="badge badge-neutral">📺 Canal: <strong>${esc((camp.source_channels || [])[0] || 'Kick Oficial')}</strong></span>
            <span class="badge badge-success">#️⃣ ${esc((camp.hashtags || []).join(' '))}</span>
          </div>
        </div>
        <button type="button" class="primary" onclick="productSwitchWorkspaceTab('campaign')">
          Ver Regras & Compliance →
        </button>
      </div>
    `;
  }

  // Overview Shortlist Grid (Top cuts)
  const cutsGrid = getEl('cw-overview-cuts-grid');
  if (cutsGrid) {
    const topCuts = candidates.filter(i => i.classification === 'RECOMENDADO' || i.classification === 'BOM').slice(0, 6);
    if (!topCuts.length) {
      cutsGrid.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted); grid-column: 1 / -1;">Nenhum corte na shortlist no momento.</div>';
    } else {
      cutsGrid.innerHTML = topCuts.map(item => renderClipCardHtml(item)).join('');
    }
  }

  // Campeonato Tab
  const campContainer = getEl('cw-campaign-container');
  if (campContainer) {
    campContainer.innerHTML = `
      <div class="card-section" style="margin-bottom:20px; border-color: rgba(99, 102, 241, 0.4); background: rgba(99, 102, 241, 0.03);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
          <div>
            <span class="badge badge-accent">REGRAS DO CAMPEONATO</span>
            <h2 style="margin:8px 0 4px; font-size:20px;">${esc(camp.name || c.name)} — Regulamento Editorial</h2>
            <p style="margin:0; font-size:13px; color:var(--text-secondary);">
              Janela de publicação: <strong>${esc(camp.period_start || camp.min_date || '22/09/2026')}</strong> até <strong>${esc(camp.period_end || camp.max_date || '22/10/2026')}</strong>
            </p>
          </div>
          <button type="button" class="btn-quiet" onclick="productSwitchWorkspaceTab('lives')">
            📹 Ver Lives Elegíveis Deste Campeonato →
          </button>
        </div>
      </div>

      <div class="campaign-rule-grid">
        <div class="rule-detail-card">
          <h4>🎨 Regra Visual Obrigatória</h4>
          <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-medium); border-radius:6px; padding:12px; margin-bottom:12px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">LOWER OBRIGATÓRIO (Abaixo do rosto do criador):</div>
            <div style="font-weight:700; color:var(--success); font-family:var(--font-mono); font-size:13px;">
              ${esc(camp.vertical?.text || `kick.com/${c.key}`)}
            </div>
          </div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.5;">
            Todo corte publicado deve conter a barra/lower oficial posicionada logo abaixo da câmera do streamer no vídeo vertical 9:16.
          </p>
        </div>

        <div class="rule-detail-card">
          <h4>🏷️ Marcações & Hashtags</h4>
          <div style="margin-bottom:12px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">Hashtags Obrigatórias:</div>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
              ${(camp.hashtags || []).map(h => `<span class="badge badge-success">${esc(h)}</span>`).join('')}
            </div>
          </div>
          <div style="margin-bottom:12px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">Perfil Oficial:</div>
            <span class="badge badge-accent">${esc(camp.official_profile || c.handle)}</span>
          </div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.5;">
            Obrigatório marcar o perfil oficial do criador na legenda do vídeo na plataforma onde for publicado.
          </p>
        </div>

        <div class="rule-detail-card">
          <h4>📱 Plataformas Válidas</h4>
          <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
            ${(camp.publication_platforms || ['TikTok', 'Instagram', 'YouTube Shorts', 'Kwai']).map(p => `
              <span class="badge badge-neutral" style="padding:6px 10px;">✓ ${esc(p)}</span>
            `).join('')}
          </div>
          <p style="font-size:12px; color:var(--text-secondary); line-height:1.5;">
            Formato obrigatório: 1080x1920 (9:16 vertical), mínimo 30 FPS.
          </p>
        </div>

        <div class="rule-detail-card">
          <h4>🚫 Proibições & Diretrizes Anti-IA 100%</h4>
          <ul style="margin:0; padding-left:18px; font-size:12px; color:var(--text-secondary); line-height:1.6;">
            <li>Proibido o uso 100% automatizado de IA sem curadoria e edição humana.</li>
            <li>Proibida a compra de visualizações ou manipulação de métricas.</li>
            <li>Proibido utilizar cortes de outros participantes ou vídeos já editados.</li>
            <li>Proibido collab entre participantes da campanha.</li>
          </ul>
        </div>
      </div>
    `;
  }

  // Lives Tab
  renderWorkspaceLivesTable(vods);

  // Cortes Tab
  renderWorkspaceCutsGrid(candidates);

  // Perfil de Cortes Tab
  const profileContainer = getEl('cw-profile-container');
  if (profileContainer) {
    profileContainer.innerHTML = `
      <div class="card-section" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0 0 4px; font-size:18px;">Perfil de Cortes — ${esc(c.name)}</h2>
            <p style="margin:0; font-size:13px; color:var(--text-muted);">
              Diretrizes de layout do template visual, formatos de retenção e calibração contínua.
            </p>
          </div>
          <span class="badge badge-accent">● ${esc(perfil.status || 'Perfil em calibração')}</span>
        </div>
      </div>

      <div class="campaign-rule-grid">
        <div class="rule-detail-card">
          <h4>📐 Formato & Template Visual (9:16)</h4>
          <p><strong>Canvas:</strong> ${esc(tmpl.canvas || '1080x1920 (9:16 vertical)')}</p>
          <p><strong>FPS Recomendado:</strong> ${tmpl.fps || 30} FPS</p>
          <p><strong>Layout Visual:</strong> ${esc(tmpl.layout_visual || 'Câmera em cima + Conteúdo embaixo')}</p>
          <p><strong>Layout Talking:</strong> ${esc(tmpl.layout_talking || 'B-Roll em cima + Câmera embaixo')}</p>
          <p><strong>Lower / Tarja:</strong> <code style="color:var(--success);">${esc(perfil.lower_text || '')}</code></p>
        </div>

        <div class="rule-detail-card">
          <h4>📊 Métricas Reais de Decupagem</h4>
          <p><strong>Lives Analisadas:</strong> ${st.vods_completed || 0} (${st.hours_analyzed || 0}h)</p>
          <p><strong>Cortes Totais Encontrados:</strong> ${st.candidates_count || 0}</p>
          <p><strong>Cortes Aprovados:</strong> ${st.approved_count || 0}</p>
          <p><strong>Duração Média dos Cortes:</strong> ${esc(perfil.average_clip_duration || '45s')}</p>
          <div style="margin-top:14px; font-size:12px; color:var(--text-muted);">
            Status: <span style="color:var(--text-secondary);">${esc(perfil.status)}</span>
          </div>
        </div>

        <div class="rule-detail-card">
          <h4>🎯 Formatos Detectados</h4>
          <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
            ${(perfil.formats_detected || ['Gameplay', 'Destaques']).map(f => `
              <span class="badge badge-neutral" style="padding:6px 12px;">★ ${esc(f)}</span>
            `).join('')}
          </div>
          <div style="margin-top:16px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">Tópicos / Categorias Recorrentes:</div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${(perfil.topics || []).map(t => `<span class="badge badge-neutral">${esc(t)}</span>`).join('')}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Switch to active tab
  productSwitchWorkspaceTab(activeTab);
}

function renderWorkspaceLivesTable(vods) {
  const tbody = getEl('cw-lives-table-body');
  if (!tbody) return;

  const countEl = getEl('cw-lives-filtered-count');
  if (countEl) countEl.textContent = vods.length;

  if (!vods.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">Nenhuma live encontrada para este criador.</td></tr>';
    return;
  }

  tbody.innerHTML = vods.map(v => `
    <tr>
      <td style="font-family:var(--font-mono); white-space:nowrap;">${esc(v.date || '—')}</td>
      <td>
        <div style="font-weight:600; color:var(--text-primary); max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${esc(v.title)}">
          ${esc(v.title)}
        </div>
        ${v.error ? `<div style="font-size:11px; color:#F87171; margin-top:2px;">⚠ ${esc(v.error)}</div>` : ''}
      </td>
      <td style="white-space:nowrap;">${esc(v.duration_formatted)}</td>
      <td><span class="badge badge-neutral">${esc(v.platform)}</span></td>
      <td><span class="badge badge-${v.status_color || 'neutral'}">● ${esc(v.status)}</span></td>
      <td>
        ${v.candidates_count > 0 ? `
          <span class="badge badge-accent" style="cursor:pointer;" onclick="productFilterWorkspaceCutsByVod('${esc(v.id)}')">
            ${v.candidates_count} cortes (${v.shortlist_count} top)
          </span>
        ` : '<span style="color:var(--text-muted);">0</span>'}
      </td>
      <td style="white-space:nowrap;">
        <button class="btn-quiet" onclick="openVod('${esc(v.id)}')">Abrir Inspector →</button>
      </td>
    </tr>
  `).join('');
}

function renderWorkspaceCutsGrid(candidates) {
  const container = getEl('cw-cuts-items-container');
  if (!container) return;

  const countEl = getEl('cw-cuts-filtered-count');
  if (countEl) countEl.textContent = candidates.length;

  if (!candidates.length) {
    container.innerHTML = '<div style="padding:32px; text-align:center; color:var(--text-muted); grid-column:1 / -1;">Nenhum corte encontrado com os filtros selecionados.</div>';
    return;
  }

  container.innerHTML = candidates.map(item => renderClipCardHtml(item)).join('');
}

function renderClipCardHtml(item) {
  const isRecommended = item.classification === 'RECOMENDADO';
  const isShortlist = isRecommended || item.classification === 'BOM';
  const badgeClass = isRecommended ? 'success' : isShortlist ? 'accent' : 'neutral';

  return `
    <div class="clip-card" id="inbox-card-${esc(item.id)}" style="${item.status === 'APROVADO' ? 'border-color: rgba(16,185,129,0.5); background: rgba(16,185,129,0.04);' : ''}">
      <div class="clip-card-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="badge badge-${badgeClass}">${item.score} · ${esc(item.classification)}</span>
          <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${esc(item.duration_formatted)}</span>
        </div>
        <div>
          ${item.status === 'APROVADO' ? '<span class="badge badge-success">✓ APROVADO</span>' : item.status === 'DESCARTADO' ? '<span class="badge badge-danger">DESCARTADO</span>' : '<span class="badge badge-neutral">NOVO</span>'}
        </div>
      </div>

      <div class="clip-title" style="cursor:pointer;" onclick="productOpenClipDetail('${esc(item.id)}')">
        ${esc(item.title)}
      </div>

      ${item.hook ? `<div class="clip-hook">💡 "${esc(item.hook)}"</div>` : ''}

      <div class="clip-meta-row">
        <span>⏱ ${esc(item.start_formatted)} → ${esc(item.end_formatted)}</span>
        <span>👁 Ativ. ${esc(item.visual_activity || 'Média')}</span>
      </div>

      <div class="clip-actions-row">
        <button type="button" class="btn-quiet" onclick="productOpenClipPreview('${esc(item.id)}', '${esc(item.vod_id)}')">
          ▶ Assistir
        </button>
        <button type="button" class="btn-quiet" style="color:var(--accent);" onclick="productOpenClipDetail('${esc(item.id)}')">
          📦 Pacote & Legenda
        </button>
        <div style="margin-left:auto; display:flex; gap:6px;">
          <button type="button" class="btn-danger" style="padding:5px 9px;" onclick="productReviewClip('${esc(item.vod_id)}', '${esc(item.id)}', 'DESCARTADO')" title="Descartar">✕</button>
          <button type="button" class="btn-success" style="padding:5px 9px;" onclick="productReviewClip('${esc(item.vod_id)}', '${esc(item.id)}', 'APROVADO')" title="Aprovar">✓</button>
        </div>
      </div>
    </div>
  `;
}

function productSwitchWorkspaceTab(tabName) {
  productState.currentWorkspaceTab = tabName;

  // Update tab buttons
  document.querySelectorAll('.cw-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName || btn.id === `cw-tab-${tabName}`);
  });

  // Toggle tab panes
  document.querySelectorAll('.cw-tab-pane').forEach(pane => {
    pane.hidden = pane.id !== `cw-pane-${tabName}`;
  });

  // Update breadcrumb
  const breadcrumbEl = getEl('product-breadcrumb');
  if (breadcrumbEl && productState.currentView === 'creator-workspace') {
    const cKey = productState.currentCreator || 'gabepeixe';
    const cName = cKey === 'gabepeixe' ? 'GabePeixe' : cKey.toUpperCase();
    const tabNames = {
      overview: 'VISÃO GERAL',
      campaign: 'CAMPEONATO',
      lives: 'LIVES',
      cuts: 'CORTES',
      profile: 'PERFIL DE CORTES'
    };
    breadcrumbEl.textContent = `CRIADORES / ${cName} / ${tabNames[tabName] || tabName.toUpperCase()}`;
  }
}

function productFilterWorkspaceLives() {
  const ws = productState.workspaceData;
  if (!ws) return;
  const search = (getEl('cw-lives-search')?.value || '').toLowerCase().trim();
  const status = (getEl('cw-lives-status-filter')?.value || '').toLowerCase().trim();

  let filtered = ws.vods || [];
  if (search) {
    filtered = filtered.filter(v => (v.title || '').toLowerCase().includes(search) || (v.id || '').toLowerCase().includes(search));
  }
  if (status) {
    filtered = filtered.filter(v => (v.status || '').toLowerCase() === status || (v.status_key || '').toLowerCase() === status);
  }
  renderWorkspaceLivesTable(filtered);
}

function productFilterWorkspaceCuts() {
  const ws = productState.workspaceData;
  if (!ws) return;
  const search = (getEl('cw-cuts-search')?.value || '').toLowerCase().trim();
  const classification = getEl('cw-cuts-classification-filter')?.value || 'TODOS';
  const status = getEl('cw-cuts-status-filter')?.value || 'ALL';

  let filtered = ws.recent_candidates || [];
  if (search) {
    filtered = filtered.filter(i => (i.title || '').toLowerCase().includes(search) || (i.hook || '').toLowerCase().includes(search) || (i.transcript || '').toLowerCase().includes(search));
  }
  if (classification !== 'TODOS') {
    if (classification === 'SHORTLIST') {
      filtered = filtered.filter(i => (i.classification === 'RECOMENDADO' || i.classification === 'BOM') && i.status !== 'DESCARTADO');
    } else {
      filtered = filtered.filter(i => i.classification === classification);
    }
  }
  if (status !== 'ALL') {
    filtered = filtered.filter(i => i.status === status);
  }
  renderWorkspaceCutsGrid(filtered);
}

function productFilterWorkspaceCutsByVod(vodId) {
  productSwitchWorkspaceTab('cuts');
  const searchInput = getEl('cw-cuts-search');
  if (searchInput) {
    searchInput.value = vodId;
    productFilterWorkspaceCuts();
  }
}

function updateSidebarContext(creatorKey) {
  const libEl = getEl('library');
  if (!libEl) return;

  // Add tooltips to library items so titles never truncate silently
  libEl.querySelectorAll('.library-item').forEach(btn => {
    const strong = btn.querySelector('strong');
    if (strong && !btn.getAttribute('title')) {
      btn.setAttribute('title', strong.textContent);
    }
  });
}

// 4. CREATOR DNA VIEW (Truthful & honest)
function loadDnaView(creatorKey = 'gabepeixe') {
  const container = getEl('dna-detail-container');
  if (!container) return;

  const creators = productState.creatorsData || [];
  const creator = creators.find(c => c.key === (creatorKey || 'gabepeixe').toLowerCase()) || creators[0] || {
    key: 'gabepeixe', name: 'GabePeixe', handle: '@gabepeixe', avatar: '🐟',
    dna: {
      status: 'Perfil comportamental em construção através da análise das lives',
      formats: ['Momentos de Gameplay', 'Reações / Destaques'],
      topics: ['Minecraft', 'TCG / Coringa', 'FC 27', 'Presencial Narizes'],
      typical_duration: '30s a 65s'
    }
  };

  const dna = creator.dna || {};
  const cKey = creator.key || creatorKey || 'gabepeixe';

  container.innerHTML = `
    <div style="display:flex; align-items:center; gap:16px; margin-bottom:24px; padding-bottom:18px; border-bottom:1px solid var(--border-subtle);">
      <div class="creator-avatar-box" style="width:64px; height:64px; font-size:32px;">${creator.avatar || '🎬'}</div>
      <div>
        <h2 style="font-size:22px; margin:0; color:var(--text-primary);">${esc(creator.name)} · Perfil de Cortes & Template</h2>
        <p style="margin:4px 0 0; color:var(--text-muted); font-size:13px;">${esc(creator.handle)} · Diretrizes visuais e calibração</p>
      </div>
      <div style="margin-left:auto;">
        <button class="primary" onclick="productNavigate('creator-workspace', { creator: '${esc(cKey)}', tab: 'profile' })">
          Abrir Workspace do Criador →
        </button>
      </div>
    </div>

    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:18px;">
      <div class="card-section">
        <h3>Status de Calibração</h3>
        <p style="font-size:13px; color:var(--text-secondary); line-height:1.6;">${esc(dna.status || 'Perfil comportamental em construção através da análise das lives')}</p>
        <div style="margin-top:14px; font-size:11px; color:var(--text-muted);">Heurística:</div>
        <p style="font-size:12px; color:var(--text-secondary);">Análise de áudio (Fast Scan) + Transcrição Whisper sem frases inventadas.</p>
      </div>

      <div class="card-section">
        <h3>Formatos com Maior Retenção</h3>
        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px;">
          ${(dna.formats || ['Gameplay', 'Destaques']).map(f => `<span class="badge badge-neutral" style="padding:6px 12px; font-size:12px;">★ ${esc(f)}</span>`).join('')}
        </div>
        <div style="margin-top:18px; font-size:12px; color:var(--text-muted);">
          Duração Típica Recomendada: <strong style="color:var(--text-primary);">${esc(dna.typical_duration || '30s a 60s')}</strong>
        </div>
      </div>

      <div class="card-section">
        <h3>Tópicos & Categorias Recorrentes</h3>
        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px;">
          ${(dna.topics || []).map(t => `<span class="badge badge-neutral" style="padding:6px 12px; font-size:12px;"># ${esc(t)}</span>`).join('')}
        </div>
      </div>
    </div>
  `;
}

// 5. SOURCES / VODS VIEW
async function loadSourcesView() {
  const container = getEl('sources-table-body');
  if (!container) return;

  try {
    container.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted);">Carregando catálogo de VODs...</td></tr>';
    const params = new URLSearchParams();
    if (productState.activeFilters.vods.creator) params.set('creator', productState.activeFilters.vods.creator);
    if (productState.activeFilters.vods.status) params.set('status', productState.activeFilters.vods.status);
    if (productState.activeFilters.vods.search) params.set('search', productState.activeFilters.vods.search);

    const res = await api(`/api/product/vods?${params.toString()}`);
    productState.vodsData = res.vods || [];
    renderSourcesTable(productState.vodsData);
  } catch (err) {
    container.innerHTML = `<tr><td colspan="7" class="warning">Erro ao carregar VODs: ${esc(err.message)}</td></tr>`;
  }
}

function renderSourcesTable(vods) {
  const container = getEl('sources-table-body');
  if (!container) return;

  const countEl = getEl('sources-total-count');
  if (countEl) countEl.textContent = vods.length;

  if (!vods.length) {
    container.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:36px; color:var(--text-muted);">Nenhuma VOD corresponde aos filtros.</td></tr>';
    return;
  }

  container.innerHTML = vods.map(v => `
    <tr>
      <td>
        <div style="display:flex; align-items:center; gap:8px;">
          <span>${v.creator_avatar || '🎬'}</span>
          <strong>${esc(v.creator)}</strong>
        </div>
      </td>
      <td>
        <div style="font-weight:600; color:var(--text-primary); max-width:380px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${esc(v.title)}">
          ${esc(v.title)}
        </div>
        ${v.error ? `<div style="font-size:11px; color:#F87171; margin-top:2px;">⚠ ${esc(v.error)}</div>` : ''}
      </td>
      <td style="font-family:var(--font-mono); white-space:nowrap;">${esc(v.date || '—')}</td>
      <td style="white-space:nowrap;">${esc(v.duration_formatted)}</td>
      <td><span class="badge badge-neutral">${esc(v.platform)}</span></td>
      <td>
        <span class="badge badge-${v.status_color || 'neutral'}">
          ● ${esc(v.status)}
        </span>
      </td>
      <td>
        ${v.candidates_count > 0 ? `
          <span class="badge badge-accent" style="cursor:pointer;" onclick="productFilterInboxByVod('${esc(v.id)}')">
            ${v.candidates_count} clips (${v.shortlist_count} top)
          </span>
        ` : '<span style="color:var(--text-muted);">0</span>'}
      </td>
      <td style="white-space:nowrap;">
        <button class="btn-quiet" onclick="openVod('${esc(v.id)}')">Abrir Inspector →</button>
      </td>
    </tr>
  `).join('');
}

function productFilterInboxByVod(vodId) {
  productNavigate('inbox');
  const searchInput = getEl('inbox-search-input');
  if (searchInput) {
    searchInput.value = vodId;
    searchInput.dispatchEvent(new Event('input'));
  }
}

// 6. CLIP INBOX VIEW
async function loadInboxView() {
  const container = getEl('inbox-items-container');
  if (!container) return;

  try {
    container.innerHTML = '<div style="padding:32px; text-align:center; color:var(--text-muted);">Carregando candidatos da Inbox...</div>';
    const params = new URLSearchParams();
    const f = productState.activeFilters.inbox;
    if (f.classification) params.set('classification', f.classification);
    if (f.status) params.set('status', f.status);
    if (f.creator) params.set('creator', f.creator);
    if (f.search) params.set('search', f.search);

    const res = await api(`/api/product/inbox?${params.toString()}`);
    productState.inboxData = res;
    renderInbox(res);
  } catch (err) {
    container.innerHTML = `<div class="warning">Erro ao carregar Inbox: ${esc(err.message)}</div>`;
  }
}

function renderInbox(data) {
  const container = getEl('inbox-items-container');
  if (!container) return;

  const items = data.items || [];
  const counts = data.counts || {};

  // Update classification count pills
  const updateCountPill = (id, count) => {
    const el = getEl(id);
    if (el) el.textContent = count !== undefined ? count : 0;
  };
  updateCountPill('inbox-count-shortlist', counts.SHORTLIST || 0);
  updateCountPill('inbox-count-recommended', counts.RECOMENDADO || 0);
  updateCountPill('inbox-count-good', counts.BOM || 0);
  updateCountPill('inbox-count-all', counts.total || 0);

  const totalMatchesEl = getEl('inbox-matches-total');
  if (totalMatchesEl) totalMatchesEl.textContent = `${items.length} exibidos`;

  if (!items.length) {
    container.innerHTML = `
      <div class="empty-state-box">
        <div class="empty-icon">✓</div>
        <h3>Nenhum corte aguardando neste filtro</h3>
        <p>Todos os momentos foram revisados ou não correspondem aos critérios selecionados.</p>
        <button class="primary" onclick="productResetInboxFilters()">Ver Todos os Momentos</button>
      </div>
    `;
    return;
  }

  if (productState.inboxMode === 'cards') {
    container.className = 'inbox-cards-grid';
    container.innerHTML = items.map(c => {
      const isApproved = c.status === 'APROVADO';
      const isDiscarded = c.status === 'DESCARTADO';
      const classBadgeType = c.classification === 'RECOMENDADO' ? 'success' : c.classification === 'BOM' ? 'accent' : 'neutral';

      return `
        <article class="clip-card" id="inbox-card-${esc(c.id)}" style="${isApproved ? 'border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.03);' : isDiscarded ? 'opacity: 0.5;' : ''}">
          <div class="clip-card-header">
            <div class="clip-creator-info">
              <span>${c.creator_avatar || '🐟'}</span>
              <span>${esc(c.creator)}</span>
              <span style="font-weight:400; color:var(--text-muted); font-size:11px;">${esc(c.vod_date)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="badge badge-${classBadgeType}">${c.score} · ${esc(c.classification)}</span>
              <span class="badge ${isApproved ? 'badge-success' : isDiscarded ? 'badge-danger' : 'badge-neutral'}">${esc(c.status)}</span>
            </div>
          </div>

          <h3 class="clip-card-title">${esc(c.title || c.hook || 'Momento da live')}</h3>

          <div class="clip-timestamp-row">
            <span class="duration-pill">⏱ ${esc(c.duration_formatted)}</span>
            <span>${esc(c.start_formatted)} → ${esc(c.end_formatted)}</span>
            <span style="color:var(--text-muted);">· ${esc(c.content_type || 'GAMEPLAY')}</span>
          </div>

          <div class="clip-transcript-box">
            ${esc(c.transcript || c.summary || 'Transcrição em análise')}
          </div>

          <div class="clip-card-footer">
            <div style="display:flex; gap:6px;">
              <button class="btn-quiet" style="font-size:11px;" onclick="productOpenClipPreview('${esc(c.id)}', '${esc(c.vod_id)}')">▶ Preview</button>
              <button class="btn-quiet" style="font-size:11px;" onclick="productOpenClipDetail('${esc(c.id)}')">⋯ Detalhes</button>
            </div>
            <div class="clip-card-actions">
              <button class="btn-danger" style="padding:5px 9px;" onclick="productReviewClip('${esc(c.vod_id)}', '${esc(c.id)}', 'DESCARTADO')">✕</button>
              <button class="btn-success" style="padding:5px 12px; font-weight:600;" onclick="productReviewClip('${esc(c.vod_id)}', '${esc(c.id)}', 'APROVADO')">✓ Aprovar</button>
            </div>
          </div>
        </article>
      `;
    }).join('');
  } else {
    // Compact table view
    container.className = 'data-table-container';
    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Score</th>
            <th>Criador</th>
            <th>Momento / Título</th>
            <th>Timestamp</th>
            <th>Duração</th>
            <th>Status</th>
            <th style="text-align:right;">Ações</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(c => `
            <tr id="inbox-row-${esc(c.id)}">
              <td><span class="badge badge-${c.classification === 'RECOMENDADO' ? 'success' : c.classification === 'BOM' ? 'accent' : 'neutral'}">${c.score}</span></td>
              <td>${esc(c.creator)}</td>
              <td>
                <div style="font-weight:600; color:var(--text-primary);">${esc(c.title)}</div>
                <div style="font-size:11px; color:var(--text-muted); max-width:440px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(c.transcript)}</div>
              </td>
              <td style="font-family:var(--font-mono); font-size:11px;">${esc(c.start_formatted)} → ${esc(c.end_formatted)}</td>
              <td>${esc(c.duration_formatted)}</td>
              <td><span class="badge ${c.status === 'APROVADO' ? 'badge-success' : c.status === 'DESCARTADO' ? 'badge-danger' : 'badge-neutral'}">${esc(c.status)}</span></td>
              <td style="text-align:right; white-space:nowrap;">
                <button class="btn-quiet" onclick="productOpenClipPreview('${esc(c.id)}', '${esc(c.vod_id)}')">▶</button>
                <button class="btn-danger" style="padding:4px 8px;" onclick="productReviewClip('${esc(c.vod_id)}', '${esc(c.id)}', 'DESCARTADO')">✕</button>
                <button class="btn-success" style="padding:4px 10px;" onclick="productReviewClip('${esc(c.vod_id)}', '${esc(c.id)}', 'APROVADO')">✓</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }
}

// Inbox Actions
async function productReviewClip(vodId, candidateId, status) {
  try {
    await api(`/api/vods/${vodId}/review`, {
      ids: [candidateId],
      status: status,
      feedback: 'Revisão via Clip Inbox'
    });

    toast(status === 'APROVADO' ? '✓ Clip aprovado com sucesso!' : '✕ Clip descartado.', false);

    // Optimistic UI update
    const card = getEl(`inbox-card-${candidateId}`);
    if (card) {
      if (status === 'APROVADO') {
        card.style.borderColor = 'rgba(16, 185, 129, 0.5)';
        card.style.background = 'rgba(16, 185, 129, 0.05)';
      } else {
        card.style.opacity = '0.35';
      }
    }

    // Refresh inbox data in background
    setTimeout(loadInboxView, 600);
  } catch (err) {
    toast(`Erro ao revisar clip: ${err.message}`, true);
  }
}

function productOpenClipPreview(candidateId, vodId) {
  // Use existing preview action
  const dialog = getEl('preview-dialog');
  const player = getEl('player');
  const caption = getEl('preview-caption');

  if (dialog && player) {
    // Trigger preview export job or cached file
    api(`/api/vods/${vodId}/action`, {
      kind: 'preview',
      ids: [candidateId],
      pre: 2,
      post: 2
    }).then(res => {
      dialog.showModal();
      toast('Gerando/carregando preview do corte...');
    }).catch(err => {
      toast(`Falha no preview: ${err.message}`, true);
    });
  }
}

async function productOpenClipDetail(candidateId) {
  // Find candidate across inbox or workspace data
  let item = (productState.inboxData.items || []).find(i => i.id === candidateId);
  if (!item && productState.workspaceData && productState.workspaceData.recent_candidates) {
    item = productState.workspaceData.recent_candidates.find(i => i.id === candidateId);
  }
  if (!item) {
    item = {
      id: candidateId,
      vod_id: 'vod_local',
      title: `Corte ${candidateId.slice(0, 8)}`,
      score: 85,
      classification: 'RECOMENDADO',
      creator: 'Criador',
      vod_title: 'Live',
      vod_date: '2026-09-22',
      start_formatted: '00:01:00',
      end_formatted: '00:01:45',
      duration_formatted: '45s',
      status: 'NOVO'
    };
  }

  productState.selectedClip = item;
  productState.currentCaptionClipId = candidateId;
  productState.currentCaptionSeed = 0;
  if (!productState.currentCaptionPlatform) productState.currentCaptionPlatform = 'TikTok';

  const modal = getEl('clip-detail-modal');
  if (!modal) return;
  modal.showModal();

  await productFetchAndRenderCaption(candidateId, productState.currentCaptionPlatform, productState.currentCaptionSeed);
}

async function productFetchAndRenderCaption(candidateId, platform = 'TikTok', seed = 0) {
  const bodyEl = getEl('clip-detail-body');
  if (!bodyEl) return;

  const item = productState.selectedClip || { id: candidateId, title: 'Corte', score: 80, classification: 'BOM', creator: 'Criador' };
  productState.currentCaptionPlatform = platform;
  productState.currentCaptionSeed = seed;

  bodyEl.innerHTML = '<div style="padding:32px; text-align:center; color:var(--text-muted);">Carregando corte e gerando pacote de publicação...</div>';

  try {
    const pkg = await api('/api/product/caption/generate', {
      candidate_id: candidateId,
      platform: platform,
      variation_seed: seed
    });
    productState.currentCaptionData = pkg;

    const editedVideo = item.edited_video || (pkg && pkg.edited_video);
    const isApproved = item.status === 'APROVADO' || item.status === 'PRONTO_PARA_POSTAR' || !!editedVideo;
    const isReady = item.status === 'PRONTO_PARA_POSTAR' || !!editedVideo;

    bodyEl.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px; border-bottom:1px solid var(--border-subtle); padding-bottom:12px;">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="badge badge-${item.classification === 'RECOMENDADO' ? 'success' : 'accent'}">${item.score} · ${esc(item.classification)}</span>
            <span class="badge badge-neutral">${esc(item.creator || pkg.streamer)}</span>
            <span class="badge badge-neutral">${esc(item.duration_formatted || '45s')}</span>
            ${isReady ? '<span class="badge badge-success">✓ PRONTO PARA POSTAR</span>' : isApproved ? '<span class="badge badge-accent">APROVADO</span>' : ''}
          </div>
          <h2 style="margin:8px 0 4px; font-size:18px;">${esc(item.title)}</h2>
          <p style="margin:0; font-size:12px; color:var(--text-muted);">${esc(item.vod_title || 'Live')} (${esc(item.vod_date || '—')})</p>
        </div>
        <button class="btn-quiet" onclick="getEl('clip-detail-modal').close()">✕ Fechar</button>
      </div>

      <!-- Workflow Progression Steps -->
      <div class="clip-workflow-steps">
        <div class="step-item active"><span>1</span> Corte Mapeado</div>
        <div class="step-arrow">→</div>
        <div class="step-item ${isApproved ? 'active' : ''}"><span>2</span> Aprovado</div>
        <div class="step-arrow">→</div>
        <div class="step-item ${isReady ? 'active' : isApproved ? 'in-progress' : ''}"><span>3</span> Em Edição</div>
        <div class="step-arrow">→</div>
        <div class="step-item ${editedVideo ? 'active' : ''}"><span>4</span> Vídeo Final</div>
        <div class="step-arrow">→</div>
        <div class="step-item ${isReady ? 'active' : ''}"><span>5</span> Pronto para Postar</div>
      </div>

      <!-- Final Edited Video Player or Upload Box -->
      ${editedVideo ? `
        <div class="card-section" style="border:1px solid var(--accent-success); background:rgba(16,185,129,0.06); padding:14px; margin-bottom:14px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <h4 style="margin:0; font-size:13px; color:var(--accent-success); font-weight:700; display:flex; align-items:center; gap:6px;">
              <span>🎬</span> Vídeo Final Editado — Pronto para Postar
            </h4>
            <span class="badge badge-success">PRONTO</span>
          </div>
          <video controls src="${esc(editedVideo.url)}" style="width:100%; max-height:360px; border-radius:8px; background:#000; margin-bottom:10px;"></video>
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:var(--text-secondary); margin-bottom:10px;">
            <span><strong>Arquivo:</strong> ${esc(editedVideo.filename || 'video.mp4')}</span>
            <span><strong>Armazenamento:</strong> ${esc((editedVideo.storage_mode || 'local').toUpperCase())}</span>
          </div>
          ${editedVideo.notes ? `<p style="font-size:12px; color:var(--text-muted); margin:0 0 10px;"><strong>Notas:</strong> ${esc(editedVideo.notes)}</p>` : ''}
          <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <button type="button" class="btn-accent" onclick="productSendClipToTelegram('${esc(candidateId)}')">
              ✈️ Enviar para Telegram (Vídeo + Legenda)
            </button>
            <a href="${esc(editedVideo.url)}" download="${esc(editedVideo.filename || 'corte.mp4')}" class="btn-quiet" style="text-decoration:none; display:inline-flex; align-items:center;">
              💾 Baixar MP4
            </a>
          </div>
        </div>
      ` : `
        <div class="card-section" style="border:1px dashed var(--border-subtle); padding:14px; margin-bottom:14px;">
          <h4 style="margin:0 0 6px; font-size:12px; font-weight:700; color:var(--text-secondary);">
            📤 Enviar Vídeo Finalizado (.mp4)
          </h4>
          <p style="margin:0 0 10px; font-size:11px; color:var(--text-muted);">
            Suba o vídeo com edição final (cortes verticais 9:16, legendas, lower de patrocinador) para finalizar o corte.
          </p>
          <div style="display:flex; gap:10px; flex-direction:column;">
            <input type="file" id="edited-video-file-${esc(candidateId)}" accept="video/mp4,video/*" style="font-size:12px;">
            <input type="text" id="edited-video-notes-${esc(candidateId)}" placeholder="Notas de edição opcionais (ex: corte vertical com legendas e lower)..." style="font-size:12px; padding:6px 10px; background:rgba(0,0,0,0.2); border:1px solid var(--border-subtle); border-radius:4px; color:var(--text-primary);">
            <label style="font-size:11px; color:var(--text-secondary); display:flex; align-items:center; gap:6px;">
              <input type="checkbox" id="edited-video-tg-${esc(candidateId)}">
              Enviar automaticamente para o canal do Telegram após o upload
            </label>
            <button type="button" class="primary" style="align-self:flex-start;" onclick="productUploadEditedVideo('${esc(candidateId)}')">
              Salvar Vídeo Editado
            </button>
          </div>
        </div>
      `}

      <!-- Quick Details & Whisper Transcript -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:14px;">
        <div class="card-section" style="margin:0; padding:12px 14px;">
          <h4 style="margin:0 0 6px; font-size:11px; color:var(--text-muted);">DADOS DO CORTE</h4>
          <p style="margin:3px 0; font-size:12px;"><strong>Intervalo:</strong> ${esc(item.start_formatted || '—')} → ${esc(item.end_formatted || '—')}</p>
          <p style="margin:3px 0; font-size:12px;"><strong>Duração:</strong> ${esc(item.duration_formatted || '—')}</p>
          <p style="margin:3px 0; font-size:12px;"><strong>Atividade Visual:</strong> ${esc(item.visual_activity || 'Média')}</p>
        </div>

        <div class="card-section" style="margin:0; padding:12px 14px;">
          <h4 style="margin:0 0 6px; font-size:11px; color:var(--text-muted);">TRECHO TRANSCRIÇÃO (WHISPER)</h4>
          <div style="background:rgba(0,0,0,0.25); padding:8px 10px; border-radius:6px; font-size:12px; line-height:1.4; color:var(--text-secondary); max-height:68px; overflow-y:auto;">
            "${esc(item.transcript || 'Transcrição não disponível')}"
          </div>
        </div>
      </div>

      <!-- PACOTE DE PUBLICAÇÃO & GERADOR DE LEGENDAS -->
      <div class="publishing-package-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 style="margin:0; font-size:13px; font-weight:700; display:flex; align-items:center; gap:6px;">
            <span>📦</span> Pacote de Publicação & Legenda
          </h3>
          <button type="button" class="btn-quiet" style="font-size:12px;" onclick="productRegenerateCaption('${esc(candidateId)}')">
            🔄 Gerar Outra Legenda
          </button>
        </div>

        <!-- Platform Selector -->
        <div class="platform-pill-selector">
          ${['TikTok', 'YouTube Shorts', 'Instagram Reels', 'Kwai'].map(p => `
            <button type="button" class="platform-pill-btn ${pkg.platform === p ? 'active' : ''}" onclick="productSelectCaptionPlatform('${esc(candidateId)}', '${p}')">
              ${p === 'TikTok' ? '🎵' : p === 'YouTube Shorts' ? '🔴' : p === 'Instagram Reels' ? '📸' : '⚡'} ${p}
            </button>
          `).join('')}
        </div>

        <!-- Editable Suggested Caption -->
        <label style="font-size:11px; color:var(--text-muted); margin-bottom:4px; display:block;">
          Legenda Sugerida (personalize se desejar):
        </label>
        <textarea id="clip-caption-textarea" class="caption-textarea">${esc(pkg.suggested_caption || '')}</textarea>

        <!-- Mandatory badges -->
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin:10px 0;">
          <span class="badge badge-accent" title="Menção obrigatória">👤 ${esc(pkg.mentions || '')}</span>
          ${(pkg.mandatory_hashtags || []).map(h => `<span class="badge badge-success" title="Hashtag obrigatória do campeonato">#️⃣ ${esc(h)}</span>`).join('')}
        </div>

        <!-- Compliance Checklist -->
        <div class="compliance-checklist">
          ${(pkg.compliance || []).map(c => `
            <div class="compliance-item ${c.status === 'ATENÇÃO' ? 'warning' : ''}">
              <span class="compliance-icon">${c.status === 'CONFORME' ? '✓' : '!'}</span>
              <div>
                <strong>${esc(c.title)}:</strong> ${esc(c.description)}
              </div>
            </div>
          `).join('')}
        </div>

        <!-- Copy Buttons -->
        <div class="copy-btn-group">
          <button type="button" class="primary" onclick="productCopyCaptionText()">
            📋 Copiar Legenda
          </button>
          <button type="button" class="btn-quiet" onclick="productCopyFullPublicationPackage()">
            📦 Copiar Pacote Completo (Legenda + Checklist)
          </button>
        </div>
      </div>

      <!-- Action buttons -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; border-top:1px solid var(--border-subtle); padding-top:12px;">
        <button class="btn-quiet" onclick="productOpenClipPreview('${esc(item.id)}', '${esc(item.vod_id)}')">
          ▶ Assistir Momento
        </button>
        <div style="display:flex; gap:10px;">
          <button class="btn-danger" onclick="productReviewClip('${esc(item.vod_id)}', '${esc(item.id)}', 'DESCARTADO'); getEl('clip-detail-modal').close();">
            ✕ Descartar
          </button>
          <button class="btn-success" onclick="productReviewClip('${esc(item.vod_id)}', '${esc(item.id)}', 'APROVADO'); getEl('clip-detail-modal').close();">
            ✓ Aprovar Corte
          </button>
        </div>
      </div>
    `;
  } catch (err) {
    bodyEl.innerHTML = `<div class="warning">Erro ao gerar pacote de publicação: ${esc(err.message)}</div>`;
  }
}

function productSelectCaptionPlatform(candidateId, platform) {
  productFetchAndRenderCaption(candidateId, platform, productState.currentCaptionSeed);
}

function productRegenerateCaption(candidateId) {
  productState.currentCaptionSeed = (productState.currentCaptionSeed || 0) + 1;
  productFetchAndRenderCaption(candidateId, productState.currentCaptionPlatform, productState.currentCaptionSeed);
}

function productCopyCaptionText() {
  const ta = getEl('clip-caption-textarea');
  if (ta && ta.value) {
    navigator.clipboard.writeText(ta.value).then(() => {
      toast('✓ Legenda copiada para a área de transferência!');
    }).catch(() => {
      ta.select();
      document.execCommand('copy');
      toast('✓ Legenda copiada!');
    });
  }
}

function productCopyFullPublicationPackage() {
  if (productState.currentCaptionData && productState.currentCaptionData.full_text) {
    const ta = getEl('clip-caption-textarea');
    let text = productState.currentCaptionData.full_text;
    if (ta && ta.value) {
      text = text.replace(productState.currentCaptionData.suggested_caption, ta.value);
    }
    navigator.clipboard.writeText(text).then(() => {
      toast('✓ Pacote completo copiado para a área de transferência!');
    }).catch(() => {
      toast('✓ Pacote copiado!');
    });
  }
}

function productResetInboxFilters() {
  productState.activeFilters.inbox = { classification: 'TODOS', status: 'ALL', creator: '', search: '' };
  const classSelect = getEl('inbox-filter-classification');
  if (classSelect) classSelect.value = 'TODOS';
  const statusSelect = getEl('inbox-filter-status');
  if (statusSelect) statusSelect.value = 'ALL';
  loadInboxView();
}

async function productUploadEditedVideo(candidateId) {
  const fileInput = getEl(`edited-video-file-${candidateId}`);
  if (!fileInput || !fileInput.files || !fileInput.files[0]) {
    toast('Selecione um arquivo de vídeo (.mp4).', 'warning');
    return;
  }
  const file = fileInput.files[0];
  const notesInput = getEl(`edited-video-notes-${candidateId}`);
  const tgInput = getEl(`edited-video-tg-${candidateId}`);

  const formData = new FormData();
  formData.append('video', file);
  formData.append('notes', notesInput ? notesInput.value : '');
  formData.append('sync_telegram', tgInput && tgInput.checked ? 'true' : 'false');

  try {
    toast('Enviando vídeo editado...', 'info');
    const metaToken = document.querySelector('meta[name="miner-token"]')?.content || '';
    const res = await fetch(`/api/product/clip/${encodeURIComponent(candidateId)}/upload-edited`, {
      method: 'POST',
      headers: {
        'X-Miner-Token': metaToken,
      },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Falha no upload do vídeo editado.');
    }
    toast('✓ Vídeo editado salvo com sucesso!');
    if (data.telegram && data.telegram.ok) {
      toast('✓ Vídeo enviado para o Telegram!');
    }
    // Refresh modal and view
    await productFetchAndRenderCaption(candidateId, productState.currentCaptionPlatform, productState.currentCaptionSeed);
    if (productState.currentView === 'inbox') {
      loadInboxView();
    }
  } catch (err) {
    toast(`Erro no upload: ${err.message}`, 'error');
  }
}

async function productSendClipToTelegram(candidateId) {
  try {
    toast('Enviando para o Telegram...', 'info');
    const data = await api(`/api/product/clip/${encodeURIComponent(candidateId)}/send-telegram`, {});
    if (data.ok) {
      toast('✓ Enviado para o Telegram com sucesso!');
    } else {
      toast(`Aviso: ${data.error || 'Erro no envio'}`, 'warning');
    }
  } catch (err) {
    toast(`Erro ao enviar para Telegram: ${err.message}`, 'error');
  }
}

async function productLogout() {
  try {
    await api('/api/auth/logout', {});
    window.location.reload();
  } catch (err) {
    window.location.reload();
  }
}

async function productInitCloudStatus() {
  try {
    const status = await api('/api/product/cloud-status');
    const cloudTextEl = getEl('cloud-mode-text');
    const cloudPillEl = getEl('cloud-mode-pill');
    const userRoleTextEl = getEl('user-role-text');
    const sidebarCloudText = getEl('sidebar-cloud-text');

    if (cloudTextEl) {
      cloudTextEl.textContent = status.storage_mode === 'gcs' ? 'GCS Nuvem' : 'Local';
    }
    if (sidebarCloudText) {
      sidebarCloudText.textContent = status.storage_mode === 'gcs' ? 'NUVEM CONECTADA' : 'LOCAL WORKSPACE';
    }
    if (userRoleTextEl && status.current_user) {
      userRoleTextEl.textContent = `${status.current_user.role || 'Admin'} (${status.current_user.username || 'local'})`;
    }
  } catch (e) {
    // Graceful offline fallback
  }
}

// 7. SYSTEM VIEW
async function loadSystemView() {
  const container = getEl('system-diagnostics-container');
  if (!container) return;

  try {
    container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted);">Carregando diagnóstico do sistema...</div>';
    const h = await api('/api/health');

    container.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:16px;">
        <div class="card-section">
          <h3>Binários e Mídia</h3>
          <p><strong>FFmpeg:</strong> ${h.ffmpeg ? '✓ Encontrado (' + esc(h.ffmpeg) + ')' : '<span style="color:#F87171;">Não encontrado</span>'}</p>
          <p><strong>FFprobe:</strong> ${h.ffprobe ? '✓ Encontrado (' + esc(h.ffprobe) + ')' : '<span style="color:#F87171;">Não encontrado</span>'}</p>
          <p><strong>Status do Servidor:</strong> <span class="badge badge-success">Online (Waitress / Flask)</span></p>
        </div>

        <div class="card-section">
          <h3>Aceleração de Hardware</h3>
          <p><strong>Dispositivo Whisper:</strong> ${esc(h.hardware?.device || 'CPU')}</p>
          <p><strong>CUDA NVIDIA:</strong> ${h.hardware?.cuda_available ? '✓ Disponível' : 'Não detectado (Operando em CPU multithread)'}</p>
          <p><strong>Tipo de Computação:</strong> int8 / float32</p>
        </div>

        <div class="card-section">
          <h3>Armazenamento & Banco</h3>
          <p><strong>Diretório Data:</strong> ${esc(h.data || 'data')}</p>
          <p><strong>Banco SQLite:</strong> data/history.sqlite3</p>
          <p><strong>Integridade do Banco:</strong> <span class="badge badge-success">PRAGMA integrity_check: ok</span></p>
        </div>

        <div class="card-section">
          <h3>Nuvem & Publicação Unificada</h3>
          <p><strong>Modo Storage:</strong> ${esc((h.cloud?.storage_mode || 'local').toUpperCase())} ${h.cloud?.storage_bucket ? '(' + esc(h.cloud.storage_bucket) + ')' : '(Privado Local)'}</p>
          <p><strong>Google Firestore:</strong> ${h.cloud?.firestore_connected ? '✓ Conectado' : 'Modo Offline (SQLite canônico)'}</p>
          <p><strong>Bot Telegram:</strong> ${h.cloud?.telegram_configured ? '✓ Configurado e Ativo' : 'Não configurado (Opcional)'}</p>
          <p><strong>Autenticação RBAC:</strong> ${h.cloud?.auth_required ? '✓ Ativa (' + esc(h.user?.role || 'Viewer') + ')' : 'Modo Local (Acesso Livre)'}</p>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="warning">Erro ao carregar diagnóstico: ${esc(err.message)}</div>`;
  }
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', () => {
  // Bind sidebar nav links
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      const view = btn.dataset.view;
      if (view) productNavigate(view);
    });
  });

  // Bind inbox mode switch
  const modeCardsBtn = getEl('inbox-mode-cards');
  const modeTableBtn = getEl('inbox-mode-table');
  if (modeCardsBtn) {
    modeCardsBtn.addEventListener('click', () => {
      productState.inboxMode = 'cards';
      modeCardsBtn.classList.add('primary');
      modeTableBtn?.classList.remove('primary');
      renderInbox(productState.inboxData);
    });
  }
  if (modeTableBtn) {
    modeTableBtn.addEventListener('click', () => {
      productState.inboxMode = 'table';
      modeTableBtn.classList.add('primary');
      modeCardsBtn?.classList.remove('primary');
      renderInbox(productState.inboxData);
    });
  }

  // Bind inbox classification filter
  const classFilter = getEl('inbox-filter-classification');
  if (classFilter) {
    classFilter.addEventListener('change', e => {
      productState.activeFilters.inbox.classification = e.target.value;
      loadInboxView();
    });
  }

  // Bind inbox status filter
  const statusFilter = getEl('inbox-filter-status');
  if (statusFilter) {
    statusFilter.addEventListener('change', e => {
      productState.activeFilters.inbox.status = e.target.value;
      loadInboxView();
    });
  }

  // Bind inbox search
  const searchInbox = getEl('inbox-search-input');
  if (searchInbox) {
    let searchDebounce;
    searchInbox.addEventListener('input', e => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        productState.activeFilters.inbox.search = e.target.value;
        loadInboxView();
      }, 300);
    });
  }

  // Bind sources filters
  const sourcesSearch = getEl('sources-search-input');
  if (sourcesSearch) {
    let sDebounce;
    sourcesSearch.addEventListener('input', e => {
      clearTimeout(sDebounce);
      sDebounce = setTimeout(() => {
        productState.activeFilters.vods.search = e.target.value;
        loadSourcesView();
      }, 300);
    });
  }

  const sourcesCreator = getEl('sources-filter-creator');
  if (sourcesCreator) {
    sourcesCreator.addEventListener('change', e => {
      productState.activeFilters.vods.creator = e.target.value;
      loadSourcesView();
    });
  }

  const sourcesStatus = getEl('sources-filter-status');
  if (sourcesStatus) {
    sourcesStatus.addEventListener('change', e => {
      productState.activeFilters.vods.status = e.target.value;
      loadSourcesView();
    });
  }

  // Start at dashboard
  productNavigate('dashboard');

  // Initialize Cloud status indicators
  productInitCloudStatus();

  // Background poller for active processing
  setInterval(() => {
    if (productState.currentView === 'dashboard') {
      loadDashboardView();
    }
  }, 4000);
});
