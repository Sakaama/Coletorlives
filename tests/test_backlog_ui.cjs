const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

const indexHtml = fs.readFileSync('templates/index.html', 'utf8');
const remoteJs = fs.readFileSync('static/remote.js', 'utf8');

test('index.html contains complete backlog panel elements', () => {
  const requiredIds = [
    'backlog-panel',
    'backlog-status-badge',
    'backlog-refresh',
    'backlog-start',
    'backlog-pause',
    'backlog-resume',
    'bl-total',
    'bl-completed',
    'bl-processing',
    'bl-pending',
    'bl-failed',
    'bl-shortlists',
    'bl-candidates',
    'backlog-current-card',
    'backlog-queue-count',
    'backlog-queue-items',
  ];
  for (const id of requiredIds) {
    assert.ok(indexHtml.includes(`id="${id}"`), `index.html must include id="${id}"`);
  }
});

test('remoteRenderBacklog renders metrics, active job, and queue items', async () => {
  const nodes = {
    'backlog-panel': { hidden: false },
    'bl-total': {},
    'bl-completed': {},
    'bl-processing': {},
    'bl-pending': {},
    'bl-failed': {},
    'bl-shortlists': {},
    'bl-candidates': {},
    'backlog-status-badge': {},
    'backlog-start': {},
    'backlog-pause': {},
    'backlog-resume': {},
    'backlog-current-card': {},
    'backlog-queue-count': {},
    'backlog-queue-items': {},
  };

  const fakeBacklogData = {
    campaign: { id: 'run123', creator: 'gabepeixe' },
    running_job: { id: 'j1', kind: 'backlog', progress: 45, message: 'Minerando trecho 01:10:00' },
    pause_requested: false,
    backlog: {
      total_found: 3,
      completed_count: 1,
      pending_count: 1,
      failed_count: 1,
      blocked_count: 0,
      shortlists_ready: 1,
      candidates_waiting: 5,
      processing: {
        id: 'v_proc',
        title: 'Live 23/09',
        date: '2026-09-23',
        duration: 7200,
        backlog_state: 'EXECUTANDO',
      },
      upcoming: [
        {
          id: 'v_pend',
          title: 'Live 22/09',
          date: '2026-09-22',
          duration: 5400,
          backlog_state: 'PENDENTE',
        },
      ],
      failed: [
        {
          id: 'v_fail',
          title: 'Live 21/09',
          date: '2026-09-21',
          duration: 3600,
          backlog_state: 'ERRO',
          remote_error: 'Timeout Kick HLS',
        },
      ],
      completed: [
        {
          id: 'v_done',
          title: 'Live 20/09',
          date: '2026-09-20',
          duration: 6000,
          backlog_state: 'CONCLUÍDO',
          candidates_count: 5,
        },
      ],
    },
  };

  const context = {
    $: id => nodes[id] || (nodes[id] = {}),
    remoteRun: 'run123',
    api: async () => fakeBacklogData,
    esc: s => String(s || ''),
    time: s => `${Math.floor((s || 0) / 60)}m`,
    console,
  };

  const fnSource = remoteJs.slice(
    remoteJs.indexOf('async function remoteRenderBacklog'),
    remoteJs.indexOf("$('backlog-refresh').onclick")
  );

  vm.runInNewContext(fnSource, context);
  await context.remoteRenderBacklog();

  assert.equal(nodes['bl-total'].textContent, 3);
  assert.equal(nodes['bl-completed'].textContent, 1);
  assert.equal(nodes['bl-processing'].textContent, 1);
  assert.equal(nodes['bl-pending'].textContent, 1);
  assert.equal(nodes['bl-failed'].textContent, 1);
  assert.equal(nodes['bl-shortlists'].textContent, 1);
  assert.equal(nodes['bl-candidates'].textContent, 5);

  assert.equal(nodes['backlog-status-badge'].textContent, 'EXECUTANDO (45%)');
  assert.equal(nodes['backlog-start'].disabled, true);
  assert.equal(nodes['backlog-pause'].disabled, false);

  assert.ok(nodes['backlog-current-card'].innerHTML.includes('Live 23/09'));
  assert.ok(nodes['backlog-current-card'].innerHTML.includes('Minerando trecho 01:10:00'));

  const queueHtml = nodes['backlog-queue-items'].innerHTML;
  assert.ok(queueHtml.includes('Live 23/09'));
  assert.ok(queueHtml.includes('Live 22/09'));
  assert.ok(queueHtml.includes('Live 21/09'));
  assert.ok(queueHtml.includes('data-retry-vod="v_fail"'));
  assert.ok(queueHtml.includes('Timeout Kick HLS'));
  assert.ok(queueHtml.includes('Ver candidatos (5)'));
});

test('backlog action buttons wire to remoteAction', async () => {
  const nodes = {
    'backlog-refresh': {},
    'backlog-start': {},
    'backlog-pause': {},
    'backlog-resume': {},
    'backlog-panel': {},
    'remote-mode': { value: 'equilibrado' },
  };

  const actionCalls = [];
  let refreshCalled = 0;

  const context = {
    $: id => nodes[id] || (nodes[id] = {}),
    handle: fn => fn,
    remoteAction: async (...args) => {
      actionCalls.push(args);
    },
    remoteRenderBacklog: async () => {
      refreshCalled++;
    },
    remoteRenderCandidates: () => {},
  };

  const buttonsSource = remoteJs.slice(remoteJs.indexOf("$('backlog-refresh').onclick"));
  vm.runInNewContext(buttonsSource, context);

  await nodes['backlog-refresh'].onclick();
  assert.equal(actionCalls[0][0], 'sync');

  await nodes['backlog-start'].onclick();
  assert.equal(actionCalls[1][0], 'backlog');
  assert.equal(actionCalls[1][1].mining_mode, 'equilibrado');

  await nodes['backlog-pause'].onclick();
  assert.equal(actionCalls[2][0], 'pause');

  await nodes['backlog-resume'].onclick();
  assert.equal(actionCalls[3][0], 'backlog');

  // Test retry click delegation
  const fakeEvent = {
    target: {
      closest: sel => (sel === '[data-retry-vod]' ? { dataset: { retryVod: 'v_failed_1' } } : null),
    },
  };
  await nodes['backlog-panel'].onclick(fakeEvent);
  assert.equal(actionCalls[4][0], 'retry_vod');
  assert.equal(actionCalls[4][1].vod_id, 'v_failed_1');
});
