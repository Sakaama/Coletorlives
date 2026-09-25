const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const indexHtml = fs.readFileSync('templates/index.html', 'utf8');
const productJs = fs.readFileSync('static/product.js', 'utf8');
const productCss = fs.readFileSync('static/product.css', 'utf8');

test('index.html contains complete product navigation and views', () => {
  const views = [
    'view-dashboard',
    'view-campaigns',
    'view-creators',
    'view-sources',
    'view-inbox',
    'view-dna',
    'view-publisher',
    'view-analytics',
    'view-system',
  ];
  for (const v of views) {
    assert.ok(indexHtml.includes(`id="${v}"`), `index.html must include id="${v}"`);
  }

  // Check topbar breadcrumb and processing pill
  assert.ok(indexHtml.includes('id="product-breadcrumb"'));
  assert.ok(indexHtml.includes('id="topbar-processing-pill"'));

  // Check inbox containers and toggles
  assert.ok(indexHtml.includes('id="inbox-items-container"'));
  assert.ok(indexHtml.includes('id="inbox-mode-cards"'));
  assert.ok(indexHtml.includes('id="inbox-mode-table"'));
  assert.ok(indexHtml.includes('id="clip-detail-modal"'));
});

test('static/product.js defines core product navigation and interaction functions', () => {
  const fns = [
    'productNavigate',
    'loadDashboardView',
    'renderDashboard',
    'loadCampaignsView',
    'loadCreatorsView',
    'loadDnaView',
    'loadSourcesView',
    'renderSourcesTable',
    'loadInboxView',
    'renderInbox',
    'productReviewClip',
    'productOpenClipPreview',
    'productOpenClipDetail',
    'productResetInboxFilters',
    'loadSystemView',
  ];
  for (const fn of fns) {
    assert.ok(productJs.includes(`function ${fn}`), `product.js must define function ${fn}`);
  }
});

test('static/product.css defines dark-first design system tokens', () => {
  assert.ok(productCss.includes('--bg-app'));
  assert.ok(productCss.includes('--bg-sidebar'));
  assert.ok(productCss.includes('--accent'));
  assert.ok(productCss.includes('--success'));
  assert.ok(productCss.includes('.clip-card'));
  assert.ok(productCss.includes('.creator-card'));
  assert.ok(productCss.includes('.data-table'));
});

test('Pass 2: index.html contains Creator Workspace and Publishing Package elements', () => {
  assert.ok(indexHtml.includes('id="view-creator-workspace"'));
  assert.ok(indexHtml.includes('id="cw-tab-overview"'));
  assert.ok(indexHtml.includes('id="cw-tab-campaign"'));
  assert.ok(indexHtml.includes('id="cw-tab-lives"'));
  assert.ok(indexHtml.includes('id="cw-tab-cuts"'));
  assert.ok(indexHtml.includes('id="cw-tab-profile"'));
  assert.ok(indexHtml.includes('id="cw-pane-overview"'));
  assert.ok(indexHtml.includes('id="cw-pane-campaign"'));
  assert.ok(indexHtml.includes('id="cw-pane-lives"'));
  assert.ok(indexHtml.includes('id="cw-pane-cuts"'));
  assert.ok(indexHtml.includes('id="cw-pane-profile"'));
});

test('Pass 2: static/product.js defines Creator Workspace and Publishing Package functions', () => {
  const pass2Fns = [
    'loadCreatorWorkspaceView',
    'renderCreatorWorkspace',
    'productSwitchWorkspaceTab',
    'renderWorkspaceLivesTable',
    'renderWorkspaceCutsGrid',
    'renderClipCardHtml',
    'productFilterWorkspaceLives',
    'productFilterWorkspaceCuts',
    'productFetchAndRenderCaption',
    'productSelectCaptionPlatform',
    'productRegenerateCaption',
    'productCopyCaptionText',
    'productCopyFullPublicationPackage',
  ];
  for (const fn of pass2Fns) {
    assert.ok(productJs.includes(`function ${fn}`), `product.js must define function ${fn}`);
  }
});

test('Pass 2: static/product.css defines Creator Workspace and Publishing Package styles', () => {
  assert.ok(productCss.includes('.creator-workspace-header'));
  assert.ok(productCss.includes('.cw-tab-btn'));
  assert.ok(productCss.includes('.publishing-package-box'));
  assert.ok(productCss.includes('.platform-pill-btn'));
  assert.ok(productCss.includes('.caption-textarea'));
  assert.ok(productCss.includes('.compliance-checklist'));
});
