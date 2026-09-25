const fs = require('fs');
const vm = require('vm');
const http = require('http');

const remoteJs = fs.readFileSync('static/remote.js', 'utf8');

http.get('http://127.0.0.1:8765/api/remote/dddb669fff0c4321/backlog', (res) => {
  let body = '';
  res.on('data', c => body += c);
  res.on('end', async () => {
    const payload = JSON.parse(body);
    const nodes = {
      'backlog-panel': {}, 'bl-total': {}, 'bl-completed': {}, 'bl-processing': {},
      'bl-pending': {}, 'bl-failed': {}, 'bl-shortlists': {}, 'bl-candidates': {},
      'backlog-status-badge': {}, 'backlog-start': {}, 'backlog-pause': {}, 'backlog-resume': {},
      'backlog-current-card': {}, 'backlog-queue-count': {}, 'backlog-queue-items': {}
    };
    const ctx = {
      $: id => nodes[id] || (nodes[id] = {}),
      remoteRun: 'dddb669fff0c4321',
      api: async () => payload,
      esc: s => String(s || ''),
      time: s => String(s || 0),
      console
    };
    const fnSource = remoteJs.slice(remoteJs.indexOf('async function remoteRenderBacklog'), remoteJs.indexOf("$('backlog-refresh').onclick"));
    vm.runInNewContext(fnSource, ctx);
    try {
      await ctx.remoteRenderBacklog();
      console.log('SUCCESS for dddb669fff0c4321! Rendered values:');
      console.log('bl-total:', nodes['bl-total'].textContent);
      console.log('bl-completed:', nodes['bl-completed'].textContent);
      console.log('bl-processing:', nodes['bl-processing'].textContent);
      console.log('bl-pending:', nodes['bl-pending'].textContent);
      console.log('bl-failed:', nodes['bl-failed'].textContent);
      console.log('bl-shortlists:', nodes['bl-shortlists'].textContent);
      console.log('bl-candidates:', nodes['bl-candidates'].textContent);
    } catch(err) {
      console.error('ERROR rendering:', err);
    }
  });
});
