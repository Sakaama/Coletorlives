const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/app.js', 'utf8');

test('A2 discovery catalog renders items and status badges correctly', () => {
  const nodes = {
    'discover-container': { hidden: true },
    'discover-summary': { innerHTML: '' },
    'discover-items': { innerHTML: '' }
  };
  const code = source.slice(
    source.indexOf('function renderDiscoverCatalog('),
    source.indexOf("$('discover-form').onsubmit")
  );

  const sampleData = {
    campaign: 'joaopichau',
    source_url: 'https://www.youtube.com/@joaopichau/videos',
    count: 6,
    summary: {
      new: 1,
      known: 1,
      out_of_period: 1,
      needs_review: 1,
      live_now: 1,
      upcoming: 1
    },
    items: [
      { video_id: 'vid00000001', title: 'Vídeo Novo', upload_date: '2026-09-02', duration_formatted: '10:00', status: 'NEW', status_reason: 'Dentro do período', url: 'https://www.youtube.com/watch?v=vid00000001' },
      { video_id: 'vid00000002', title: 'Vídeo Conhecido', upload_date: '2026-09-02', duration_formatted: '05:00', status: 'KNOWN', status_reason: 'Já cadastrado', url: 'https://www.youtube.com/watch?v=vid00000002' },
      { video_id: 'vid00000003', title: 'Vídeo Fora do Período', upload_date: '2026-08-20', duration_formatted: '15:00', status: 'OUT_OF_PERIOD', status_reason: 'Anterior à data mínima', url: 'https://www.youtube.com/watch?v=vid00000003' },
      { video_id: 'vid00000004', title: 'Vídeo Sem Data', upload_date: null, duration_formatted: '20:00', status: 'NEEDS_REVIEW', status_reason: 'Data não confirmada', url: 'https://www.youtube.com/watch?v=vid00000004' },
      { video_id: 'vid00000005', title: 'Live Ativa', upload_date: '2026-09-23', duration_formatted: null, status: 'LIVE_NOW', status_reason: 'Transmissão ao vivo', url: 'https://www.youtube.com/watch?v=vid00000005' },
      { video_id: 'vid00000006', title: 'Live Agendada', upload_date: '2026-09-24', duration_formatted: null, status: 'UPCOMING', status_reason: 'Transmissão agendada', url: 'https://www.youtube.com/watch?v=vid00000006' },
    ]
  };

  vm.runInNewContext(code + '\nrenderDiscoverCatalog(sampleData);', {
    sampleData,
    $: k => nodes[k],
    esc: s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
  });

  assert.equal(nodes['discover-container'].hidden, false);
  const sumHtml = nodes['discover-summary'].innerHTML;
  assert.ok(sumHtml.includes('6 vídeos encontrados'));
  assert.ok(sumHtml.includes('🟢 1 NOVOS'));
  assert.ok(sumHtml.includes('⚪ 1 JÁ CONHECIDOS'));
  assert.ok(sumHtml.includes('🔴 1 FORA DO PERÍODO'));
  assert.ok(sumHtml.includes('⚠ 1 PRECISA REVISÃO'));
  assert.ok(sumHtml.includes('🔵 1 AO VIVO'));
  assert.ok(sumHtml.includes('⏳ 1 AGENDADOS'));

  const itemsHtml = nodes['discover-items'].innerHTML;
  assert.ok(itemsHtml.includes('data-import-video="https://www.youtube.com/watch?v=vid00000001"'));
  assert.ok(itemsHtml.includes('✓ Já importado'));
  assert.ok(itemsHtml.includes('Indisponível'));
  assert.ok(itemsHtml.includes('🔴 FORA DO PERÍODO'));
  assert.ok(itemsHtml.includes('⚠ PRECISA REVISÃO'));
});
