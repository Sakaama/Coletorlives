const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/app.js', 'utf8');
const remote = fs.readFileSync('static/remote.js', 'utf8');
const campaign = JSON.parse(fs.readFileSync('config/campaigns/gabepeixe.json', 'utf8'));

test('GabePeixe UI renders mandatory obligations banner and championship rules', () => {
  const nodes = Object.fromEntries(
    ['remote-creator', 'remote-provider', 'remote-channel', 'remote-start', 'remote-end', 'remote-rules'].map(k => [k, {}])
  );
  nodes['remote-creator'].value = 'gabepeixe';

  const code = source.slice(source.indexOf('function rules('), source.indexOf('function library(')) +
    remote.slice(remote.indexOf('function remoteDefaults('), remote.indexOf('async function remoteList('));

  vm.runInNewContext(code + '\nremoteDefaults();', {
    $: k => nodes[k],
    state: { campaigns: { gabepeixe: campaign } },
    esc: s => String(s ?? '')
  });

  const html = nodes['remote-rules'].innerHTML;
  assert.ok(html.includes('LOWER OBRIGATÓRIO'), 'Must display LOWER OBRIGATÓRIO');
  assert.ok(html.includes('#gabepeixe'), 'Must display #gabepeixe');
  assert.ok(html.includes('MARCAR PERFIL OFICIAL'), 'Must display MARCAR PERFIL OFICIAL');
  assert.ok(html.includes('2026-09-01'), 'Must include min_date 2026-09-01');
  assert.ok(html.includes('2026-10-22'), 'Must include max_date 2026-10-22');
  assert.equal(nodes['remote-start'].value, '2026-09-01');
  assert.equal(nodes['remote-end'].value, '2026-10-22');
  assert.ok(nodes['remote-provider'].innerHTML.includes('Kick'), 'Provider select must offer Kick');
  assert.ok(!nodes['remote-provider'].innerHTML.includes('YouTube'), 'Provider select must not offer YouTube for GabePeixe');
});

test('static/app.js evaluates completely without ReferenceError and binds vod-obligations', () => {
  const dummyEl = {
    addEventListener: () => {},
    options: [],
    querySelectorAll: () => [],
    classList: { toggle: () => {} },
    value: '',
    textContent: '',
    innerHTML: '',
    hidden: false,
    checked: false,
    disabled: false
  };
  const mockDoc = {
    querySelector: (sel) => ({ content: 'token' }),
    querySelectorAll: () => [],
    getElementById: () => dummyEl
  };
  const context = {
    document: mockDoc,
    window: {},
    Image: function() {},
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    setInterval: () => {},
    setTimeout: () => {},
    clearTimeout: () => {},
    console: { log: () => {}, error: () => {} }
  };
  // Must execute the full app.js without throwing ReferenceError
  assert.doesNotThrow(() => {
    vm.runInNewContext(source, context);
  }, 'static/app.js top-level must not throw ReferenceError or syntax errors');
});
