const $ = id => document.getElementById(id);

const token = document.querySelector('meta[name="miner-token"]').content;

let state = {campaigns:{},vods:[],jobs:[]}, current = null, detail = null;

let selected = new Set(), pendingPreview = null, image = null, framePath = null;

let seenJobs = new Set(), toastTimer, polling = false;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const time = n => {n=Math.floor(n||0);return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].map(x=>String(x).padStart(2,'0')).join(':');};

function metricsText(metrics={}){const labels={preparation:'Preparação',audio:'Áudio',fast_scan:'Fast Scan',visual:'Visual',transcription:'Transcrição',deep_analysis:'Análise profunda',deduplication:'Deduplicação',ranking:'Ranking',total:'Total'};return Object.entries(metrics).filter(([k])=>labels[k]).map(([k,n])=>`${labels[k]}: ${time(n)}`).join(' · ')+(metrics.stage_timings?' · Medição detalhada (etapas inclusivas): '+Object.entries(metrics.stage_timings).map(([k,n])=>`${k}: ${Number(n).toFixed(2)}s`).join(' · '):'');}

function toast(text, error=false){$('toast').textContent=text;$('toast').className=error?'error':'';$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?16000:6500);}

async function api(url,body){const response=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json','X-Miner-Token':token},body:JSON.stringify(body)}:{});const data=await response.json();if(!response.ok)throw new Error(data.error||'Erro na solicitação');return data;}

function handle(fn){return async event=>{try{await fn(event);}catch(error){toast(error.message,true);}};}

function rules(c) {
  let obligations = [];
  if (c.id === 'gabepeixe') {
    obligations.push('⚠ LOWER OBRIGATÓRIO (abaixo do rosto do Gabe)');
    obligations.push('⚠ #gabepeixe');
    obligations.push('⚠ MARCAR PERFIL OFICIAL');
  } else {
    if (c.required_visuals?.length) obligations.push(...c.required_visuals.map(v => '⚠ OBRIGATÓRIO NO CORTE: ' + v));
    if (c.hashtags?.length) obligations.push(...c.hashtags.map(h => '⚠ HASHTAG: ' + h));
    if (c.required_texts?.length) obligations.push(...c.required_texts.map(t => '⚠ REQUISITO: ' + t));
  }
  let obHtml = obligations.length ? `<div class="warning" style="margin-bottom:8px;">${obligations.map(o => `<strong>${esc(o)}</strong>`).join(' · ')}</div>` : '';

  let html = `<strong>${esc(c.name)} · ${esc(c.min_date)}${c.max_date?' até '+esc(c.max_date):' em diante'}</strong><p>${esc(c.notes)}</p><p>${[...c.hashtags,...c.required_texts,...c.required_visuals].map(esc).join(' · ')}</p>`;

  if(c.date_dispute_note) html += `<p><strong>REVISÃO HUMANA — período divergente</strong><br>${esc(c.date_dispute_note)}</p>`;

  if(c.source_channels) html += `<p>Fontes originais: ${c.source_channels.map(esc).join(' · ')}</p>`;

  if(c.ai_policy) html += `<p>${esc(c.ai_policy)}</p>`;

  if(c.prohibitions) html += `<ul>${c.prohibitions.map(p=>`<li>${esc(p)}</li>`).join('')}</ul>`;

  if(c.publication_platforms) html += `<p>Publicação manual: ${c.publication_platforms.map(esc).join(', ')}. Não é obrigatório publicar em todas.</p>`;

  return obHtml + html;

}

function library(){ $('library-count').textContent=state.vods.length;$('library').innerHTML=state.vods.length?state.vods.map(v=>`<button class="library-item ${v.id===current?'selected':''}" data-vod="${esc(v.id)}"><strong>${esc(v.title)}</strong><small>${esc(state.campaigns[v.campaign]?.name)} · ${time(v.duration)}</small></button>`).join(''):'<p class="hint">As VODs importadas aparecem aqui.</p>';}

async function refresh() {

  state = await api('/api/state');

  library();

  if (!current) return;

  const active = state.jobs.some(j => j.vod_id === current && ['FILA', 'EXECUTANDO'].includes(j.state));

  renderJobs();

  const finished = state.jobs.filter(j => j.vod_id === current && !['FILA', 'EXECUTANDO'].includes(j.state) && !seenJobs.has(j.id));

  if (finished.length) {

    finished.forEach(j => seenJobs.add(j.id));

    await loadDetail(false);

  }

  if (pendingPreview) {

    const job = state.jobs.find(j => j.id === pendingPreview.job);

    if (job?.state === 'CONCLUÍDO') {

      await loadDetail(false);

      const c = detail.candidates.find(c => c.id === pendingPreview.cid);

      const exports = c?.exports.filter(e => e.kind === 'preview') || [];

      if (exports.length) showPreview(exports.at(-1), c);

      pendingPreview = null;

    } else if (job?.state === 'ERRO') {

      toast(job.message, true);

      pendingPreview = null;

    }

  }

  document.querySelectorAll('#analyze,#download,#metadata,#get-frame,#raw-selected,#prep-selected').forEach(b => b.disabled = active);

}

async function openVod(id){$('remote-panel').hidden=true;current=id;$('show-history').checked=false;selected.clear();$('select-all').checked=false;framePath=null;pendingPreview=null;$('welcome').hidden=true;$('vod-view').hidden=false;$('breadcrumb').textContent='REVISÃO DE VOD';library();await loadDetail(true);renderJobs();}

async function loadDetail(initial){if(!current)return;const vid=current;const data=await api('/api/vods/'+vid+($('show-history').checked?'?history=1':''));if(current!==vid)return;detail=data;const v=data.vod,c=state.campaigns[v.campaign];$('vod-title').textContent=v.title;$('vod-campaign').textContent=c.name.toUpperCase()+' / '+v.id;$('vod-meta').innerHTML=[v.platform,v.date||'Data não confirmada',time(v.duration),v.channel||'Canal não confirmado',v.local_path?'Vídeo disponível':'Aguardando vídeo'].map(s=>`<span>${esc(s)}</span>`).join('');$('eligibility').textContent=v.eligibility?.status||'REVISÃO HUMANA';$('vod-rules').innerHTML=rules(c)+`<ul>${(v.eligibility?.reasons||[]).map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`;$('vod-warnings').hidden=!v.warnings?.length;$('vod-warnings').textContent=v.warnings?.join('\n')||'';$('download-controls').hidden=!v.url;$('download').hidden=!!v.local_path||!!v.remote;$('attach-local').hidden=!!v.local_path;renderCandidates();$('analysis-metrics').textContent=metricsText(v.analysis_metrics);if(initial){$('raw-remote').checked=false;$('raw-url').value=v.url||'';$('mining-mode').value=v.mining_mode||'equilibrado';for(const region of ['camera','content']){const r=v[region]||{x:0,y:0,width:region==='content'?v.width||640:Math.min(320,v.width||320),height:region==='content'?v.height||360:Math.min(240,v.height||240)};for(const key of ['x','y','width','height'])$(region+'-'+key).value=r[key];}$('text-x').value=v.vertical?.text_x??c.vertical.text_x;$('text-y').value=v.vertical?.text_y??c.vertical.text_y;}if(v.frame&&framePath!==v.frame){framePath=v.frame;image=new Image();image.onload=()=>{const canvas=$('frame-canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.hidden=false;drawRegions();};image.src='/media/frame/'+vid+'?v='+encodeURIComponent(v.frame);}if(initial&&!v.frame){$('frame-canvas').hidden=true;image=null;} const ob = (c.id === 'gabepeixe') ? ['⚠ LOWER OBRIGATÓRIO (abaixo do rosto do Gabe)', '⚠ #gabepeixe', '⚠ MARCAR PERFIL OFICIAL'] : (c.required_visuals || []).map(v => '⚠ OBRIGATÓRIO: ' + v); if ($('vod-obligations')) { $('vod-obligations').hidden = !ob.length; $('vod-obligations').innerHTML = ob.map(o => `<strong>${esc(o)}</strong>`).join(' · '); }}

function renderJobs() {

  const jobs = state.jobs.filter(j=>j.vod_id===current).slice(0,4);

  const vod = state.vods.find(v=>v.id===current);

  const active = state.jobs.some(j=>j.vod_id===current && ['FILA','EXECUTANDO'].includes(j.state));

  $('jobs').innerHTML = jobs.map(j=>`<div class="job ${j.state==='ERRO'?'error':''}"><b>${esc(j.kind.toUpperCase())} · ${esc(j.state)}</b> <small>${j.progress}%</small><div>${esc(j.message)}</div>${j.fallback==='import_local' && !vod?.local_path ? `<div class="button-row"><button class="primary" data-import-fallback ${active?'disabled':''}>Importar arquivo local</button></div>` : ''}${['FILA','EXECUTANDO'].includes(j.state)?`<progress max="100" value="${j.progress}"></progress>`:''}</div>`).join('');

}

$('jobs').onclick = event => {

  if(event.target.closest('[data-import-fallback]')) $('attach-local').click();

};

function renderCandidates(){const filter=$('status-filter').value;const choice=$('editorial-filter')?.value||'TODOS';const rows=detail.candidates.filter(c=>(filter==='all'||c.status===filter)&&(choice==='TODOS'||!c.editorial_review||(choice==='SHORTLIST'?!c.refined_duplicate_of&&['RECOMENDADO','BOM'].includes(c.editorial_review.classification):c.editorial_review.classification===choice))).sort((a,b)=>(b.editorial_review?.editorial_score??b.score)-(a.editorial_review?.editorial_score??a.score));$('candidate-count').textContent=detail.candidates.length;$('candidates').innerHTML=rows.length?rows.map(c=>`<article class="candidate"><input type="checkbox" aria-label="Selecionar candidato ${esc(c.id)}" data-select="${esc(c.id)}" ${selected.has(c.id)?'checked':''}><div class="score">${c.editorial_review?.editorial_score??c.score}<small>${esc(c.editorial_review?.classification||'Score bruto')}<br>prioridade</small></div><div><div class="candidate-head"><strong>${time(c.start)} → ${time(c.end)} <span>· ${Math.round(c.end-c.start)}s</span></strong><div><span class="tag ${c.status==='APROVADO'?'approved':''}">${esc(c.status)}${c.archived?" · HISTÓRICO":""}</span> ${c.duplicate?'<span class="tag duplicate">POSSÍVEL DUPLICATA</span>':''}</div></div>${c.eligibility_review?.status?`<p class="warning"><b>${esc(c.eligibility_review.status)}</b> · ${esc((c.eligibility_review.reasons||[]).join(' · '))}</p>`:''}${c.editorial_review?`<p><strong>${esc(c.editorial_review.title)}</strong><br>${esc(c.editorial_review.content_type)} · Sugerido ${time(c.editorial_review.suggested_start)} → ${time(c.editorial_review.suggested_end)}<br>${esc(c.editorial_review.reason)}</p>`:''}${c.refined_alternatives?.length?'<p class="hint">Outros candidatos com este núcleo: '+c.refined_alternatives.map(a=>time(a.start)+' → '+time(a.end)).join(' · ')+'. Disponíveis em Todos.</p>':''}${c.refined_duplicate_of?'<p class="hint">Mesmo intervalo refinado de outro candidato; agrupado na shortlist.</p>':''}<p>${esc(c.summary)}</p><p class="reason">${esc(c.reason)}</p><small class="reason" title="Mudança visual amostrada; não mede qualidade do conteúdo.">Editorial: ${c.editorial_score ?? c.score} · Visual +${c.visual_boost ?? 0} · Visual: ${{HIGH:"Alto",MEDIUM:"Médio",LOW:"Baixo"}[c.visual_activity_level] || "Não medido"}</small><div class="candidate-actions"><button data-preview="${esc(c.id)}">▶ Preview</button><button data-review="APROVADO" data-id="${esc(c.id)}">✓ Aprovar</button><button data-review="DESCARTADO" data-id="${esc(c.id)}">✕ Descartar</button><button data-review="NOVO" data-id="${esc(c.id)}">↺ Novo</button>${c.exports.filter(e=>e.kind!=='preview').map(e=>`<a href="/media/export/${e.id}?download=1">↓ ${esc(e.kind.toUpperCase())}</a>`).join('')}</div></div></article>`).join(''):'<div class="empty">'+(detail.candidates.length?'Nenhum candidato neste filtro.':'Sua próxima descoberta começa aqui.<br>Analise a VOD para encontrar os primeiros candidatos.')+'</div>';}

async function action(kind,extra={}){const result=await api('/api/vods/'+current+'/action',{kind,pre:Number($('pre').value),post:Number($('post').value),...extra});await refresh();return result;}

async function review(status,ids=[...selected]){if(!ids.length)throw new Error('Selecione pelo menos um candidato.');await api('/api/vods/'+current+'/review',{status,ids});await loadDetail(false);toast('Revisão salva.');}

function showPreview(e,c){$('player').src='/media/export/'+e.id;$('preview-caption').textContent=`${time(e.start)} → ${time(e.end)} · ${c.editorial_review?'Editorial':'Score'} ${c.editorial_review?.editorial_score??c.score}/100 · Intervalo do arquivo`;$('preview-dialog').showModal();}

function rect(region){return Object.fromEntries(['x','y','width','height'].map(k=>[k,Number($(region+'-'+k).value)]));}

function drawRegions(){if(!image)return;const canvas=$('frame-canvas'),ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);for(const region of ['content','camera']){const r=rect(region);ctx.strokeStyle=region==='camera'?'#b9ed78':'#73b7ff';ctx.lineWidth=Math.max(2,canvas.width/400);ctx.strokeRect(r.x,r.y,r.width,r.height);ctx.fillStyle=ctx.strokeStyle;ctx.font=`bold ${Math.max(14,canvas.width/60)}px Segoe UI`;ctx.fillText(region==='camera'?'CÂMERA':'CONTEÚDO',r.x+5,r.y+25);}}

$('new-vod').onclick=()=>{current=null;$('welcome').hidden=false;$('vod-view').hidden=true;$('breadcrumb').textContent='VISÃO GERAL';library();};

$('library').onclick=handle(async e=>{const b=e.target.closest('[data-vod]');if(b)await openVod(b.dataset.vod);});

document.querySelectorAll('[data-import]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-import]').forEach(x=>x.classList.toggle('active',x===b));$('url-form').hidden=b.dataset.import!=='url';$('discover-form').hidden=b.dataset.import!=='discover';$('local-form').hidden=b.dataset.import!=='local';});



function renderDiscoverCatalog(data){

  $('discover-container').hidden = false;

  const s = data.summary;

  $('discover-summary').innerHTML = `<div><h3>${data.count} vídeos encontrados</h3><p class="hint">${esc(data.source_url)}</p></div><div class="chip-row">` +

    `<span class="tag approved">🟢 ${s.new} NOVOS</span> ` +

    `<span class="tag">⚪ ${s.known} JÁ CONHECIDOS</span> ` +

    (s.out_of_period ? `<span class="tag error">🔴 ${s.out_of_period} FORA DO PERÍODO</span> ` : '') +

    (s.needs_review ? `<span class="tag warning">⚠ ${s.needs_review} PRECISA REVISÃO</span> ` : '') +

    (s.live_now ? `<span class="tag">🔵 ${s.live_now} AO VIVO</span> ` : '') +

    (s.upcoming ? `<span class="tag">⏳ ${s.upcoming} AGENDADOS</span> ` : '') +

    `</div>`;

  if(!data.items.length){

    $('discover-items').innerHTML = '<p class="hint">Nenhum vídeo retornado para esta fonte.</p>';

    return;

  }

  $('discover-items').innerHTML = data.items.map(item => {

    const badgeMap = {

      'NEW': '<span class="tag approved">🟢 NOVO</span>',

      'KNOWN': '<span class="tag">⚪ JÁ CONHECIDO</span>',

      'OUT_OF_PERIOD': '<span class="tag error">🔴 FORA DO PERÍODO</span>',

      'NEEDS_REVIEW': '<span class="tag warning">⚠ PRECISA REVISÃO</span>',

      'LIVE_NOW': '<span class="tag">🔵 AO VIVO</span>',

      'UPCOMING': '<span class="tag">⏳ AGENDADO</span>'

    };

    const badge = badgeMap[item.status] || `<span class="tag">${esc(item.status)}</span>`;

    const actionBtn = item.status === 'KNOWN'

      ? `<button disabled>✓ Já importado</button>`

      : (item.status === 'LIVE_NOW' || item.status === 'UPCOMING')

      ? `<button disabled title="Transmissão ao vivo ou agendada">Indisponível</button>`

      : `<button class="primary" data-import-video="${esc(item.url)}">↓ Importar VOD</button>`;

    return `<article class="candidate discover-card" data-video-id="${esc(item.video_id)}">` +

      `<div>${badge}</div>` +

      `<div>` +

        `<div class="candidate-head"><strong>${esc(item.title || item.video_id)}</strong><span>${esc(item.duration_formatted || '')}</span></div>` +

        `<p class="hint">${esc(item.channel_name || '')} · Data: ${esc(item.upload_date || 'Desconhecida')}</p>` +

        `<p class="reason">${esc(item.status_reason || '')}</p>` +

        `<div class="candidate-actions">${actionBtn}</div>` +

      `</div>` +

    `</article>`;

  }).join('');

}



$('discover-form').onsubmit = handle(async e => {

  e.preventDefault();

  const campaign = $('campaign').value;

  const url = $('discover-url').value;

  const limit = Number($('discover-limit').value || 50);

  $('discover-submit').disabled = true;

  $('discover-submit').textContent = 'Descobrindo…';

  try {

    const res = await api('/api/discover', { campaign, url, limit });

    renderDiscoverCatalog(res);

  } finally {

    $('discover-submit').disabled = false;

    $('discover-submit').textContent = 'Descobrir vídeos →';

  }

});



$('discover-items').onclick = handle(async e => {

  const btn = e.target.closest('[data-import-video]');

  if (!btn) return;

  const url = btn.dataset.importVideo;

  const campaign = $('campaign').value;

  btn.disabled = true;

  btn.textContent = 'Importando…';

  const card = btn.closest('.discover-card');

  const res = await api('/api/import/url', { campaign, url });

  await refresh();

  if (card) {

    const badgeCol = card.children[0];

    if (badgeCol) badgeCol.innerHTML = '<span class="tag">⚪ JÁ CONHECIDO</span>';

    btn.textContent = '✓ Já importado';

    btn.disabled = true;

    btn.className = '';

  }

  toast(res.known ? 'Esta VOD já está no histórico. Abrimos o registro existente.' : 'VOD registrada. Consultando metadados…');

  await openVod(res.vod.id);

});

$('campaign').onchange=()=>$('campaign-rules').innerHTML=rules(state.campaigns[$('campaign').value]);

$('url-form').onsubmit=handle(async e=>{e.preventDefault();const data=await api('/api/import/url',{campaign:$('campaign').value,url:$('url').value});await refresh();await openVod(data.vod.id);toast(data.known?'Esta VOD já está no histórico. Abrimos o registro existente.':'VOD registrada. Consultando metadados…');});

$('local-form').onsubmit=handle(async e=>{e.preventDefault();const data=await api('/api/import/local',{campaign:$('campaign').value,path:$('local-path').value,title:$('local-title').value,date:$('local-date').value});await refresh();await openVod(data.vod.id);toast(data.known?'Arquivo já conhecido: histórico recuperado.':'Arquivo importado. Pronto para analisar.');});

$('pick-file').onclick=handle(async()=>{const data=await api('/api/pick-file',{});if(data.path)$('local-path').value=data.path;});

$('attach-local').onclick=handle(async()=>{const data=await api('/api/pick-file',{});if(!data.path)return;await api('/api/import/local',{campaign:detail.vod.campaign,path:data.path,existing:current});await loadDetail(true);await refresh();toast('Vídeo vinculado ao registro da VOD.');});

$('metadata').onclick=handle(()=>action('metadata'));

$('download').onclick=handle(()=>action('download',{reviewed:$('reviewed').checked}));

$('analyze').onclick=handle(()=>action('analyze',{transcribe:$('transcription').value==='yes',model:$('model').value,device:$('device').value,mining_mode:$('mining-mode').value}));

$('status-filter').onchange=renderCandidates;

$('show-history').onchange=handle(async()=>{selected.clear();$('select-all').checked=false;await loadDetail(false);});

$('select-all').onchange=()=>{$('candidates').querySelectorAll('[data-select]').forEach(box=>$('select-all').checked?selected.add(box.dataset.select):selected.delete(box.dataset.select));renderCandidates();};

$('candidates').onchange=e=>{if(e.target.dataset.select){e.target.checked?selected.add(e.target.dataset.select):selected.delete(e.target.dataset.select);}};

$('candidates').onclick=handle(async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.review)await review(b.dataset.review,[b.dataset.id]);if(b.dataset.preview){const c=detail.candidates.find(c=>c.id===b.dataset.preview);const start=Math.max(0,c.start-Number($('pre').value)),end=Math.min(detail.vod.duration,c.end+Number($('post').value));const ready=c.exports.find(e=>e.kind==='preview'&&Math.abs(e.start-start)<.01&&Math.abs(e.end-end)<.01);if(ready)showPreview(ready,c);else{const r=await action('preview',{ids:[c.id]});pendingPreview={cid:c.id,job:r.job};toast('Geração do preview iniciada…');}}});

$('approve-selected').onclick=handle(()=>review('APROVADO'));

$('discard-selected').onclick=handle(()=>review('DESCARTADO'));

for(const kind of ['raw','prep'])$(kind+'-selected').onclick=handle(async()=>{if(!selected.size)throw new Error('Selecione candidatos aprovados.');await action(kind,{ids:[...selected],...(kind==='raw'&&$('raw-remote').checked?{remote_raw:{url:$('raw-url').value,aligned:true}}:{})});});

$('get-frame').onclick=handle(()=>action('frame',{time:Number($('frame-time').value)}));

$('save-regions').onclick=handle(async()=>{await api('/api/vods/'+current+'/regions',{camera:rect('camera'),content:rect('content'),text_x:Number($('text-x').value),text_y:Number($('text-y').value)});toast('Composição salva para todos os clips desta VOD.');});

let drag=null;

function point(e){const canvas=$('frame-canvas'),r=canvas.getBoundingClientRect();return {x:Math.round(Math.max(0,Math.min(canvas.width,(e.clientX-r.left)*canvas.width/r.width))),y:Math.round(Math.max(0,Math.min(canvas.height,(e.clientY-r.top)*canvas.height/r.height)))};}

$('frame-canvas').onpointerdown=e=>{drag=point(e);$('frame-canvas').setPointerCapture(e.pointerId);};

$('frame-canvas').onpointermove=e=>{if(!drag)return;const p=point(e),region=$('region-target').value;for(const [key,val] of Object.entries({x:Math.min(drag.x,p.x),y:Math.min(drag.y,p.y),width:Math.abs(p.x-drag.x),height:Math.abs(p.y-drag.y)}))$(region+'-'+key).value=val;drawRegions();};

$('frame-canvas').onpointerup=()=>drag=null;

document.querySelectorAll('.region-fields input').forEach(i=>i.oninput=drawRegions);

$('close-preview').onclick=()=>{$('player').pause();$('preview-dialog').close();};

$('preview-dialog').onclose=()=>$('player').pause();

$('diagnostics').onclick=handle(async()=>{const d=await api('/api/health');toast(`FFmpeg e SQLite disponíveis.\n${d.hardware.gpu||'CPU disponível'}\n${d.hardware.note}\nDados: ${d.data}`);});

handle(async()=>{await refresh();$('campaign').innerHTML=Object.values(state.campaigns).map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');$('campaign').onchange();seenJobs=new Set(state.jobs.map(j=>j.id));setInterval(async()=>{if(polling)return;polling=true;try{await refresh();}catch(e){toast('Conexão com o aplicativo interrompida. Mantenha a janela de inicialização aberta.',true);}finally{polling=false;}},2000);})({});



$('editorial-filter').onchange=renderCandidates;

