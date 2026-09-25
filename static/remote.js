let remoteRun = null, remoteDetail = null, remoteBusy = false, remoteEdit = null, remotePreview = null;
let remoteSelected = new Set();
function remoteFiltered(rows, filters) {
  return rows.filter(c => (!filters.vod || c.vod_id === filters.vod) && (!filters.date || c.date === filters.date) &&
    (!filters.classification || filters.classification==='TODOS' || (filters.classification==='SHORTLIST' ? !c.refined_duplicate_of && (!c.editorial_review || ['RECOMENDADO','BOM'].includes(c.editorial_review.classification)) : c.editorial_review?.classification===filters.classification)) && (!filters.status || c.status === filters.status) && (c.editorial_review?.editorial_score??c.score) >= Number(filters.score || 0) && (!filters.type || (c.editorial_review?.content_type||c.type) === filters.type));
}
function remoteClock(value) {
  const parts=String(value).trim().split(':').map(Number);
  if(!String(value).trim() || parts.length>3 || parts.some((n,i)=>!Number.isFinite(n)||n<0||(i>0&&n>=60))) throw new Error('Horário inválido. Use HH:MM:SS.');
  return parts.reduce((a,n)=>a*60+n,0);
}
function remoteRows() {
  return remoteFiltered(remoteDetail?.candidates || [], {vod:$('remote-filter-vod').value,date:$('remote-filter-date').value,
    classification:$('remote-filter-editorial').value,status:$('remote-filter-status').value,score:$('remote-filter-score').value,type:$('remote-filter-type').value});
}
function remoteDefaults() {
  const c=state.campaigns[$('remote-creator').value]; if(!c)return;
  $('remote-provider').innerHTML=c.allowed_sources.map(p=>`<option>${esc(p)}</option>`).join('');
  $('remote-channel').value=c.channel_aliases?.[0]||c.id;
  $('remote-start').value=c.min_date||'';$('remote-end').value=c.max_date||'';
  $('remote-rules').innerHTML=rules(c);
}
async function remoteList() {
  const data=await api('/api/remote/campaigns');
  $('remote-runs').innerHTML='<option value="">Nova campanha operacional</option>'+data.campaigns.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
  $('remote-runs').value=remoteRun||'';
}
async function remoteAction(kind, body={}) {
  if(!remoteRun) throw new Error('Salve uma campanha operacional primeiro.');
  const result=await api('/api/remote/'+remoteRun+'/action',{kind,...body});
  await remoteRefresh();return result;
}
function remoteRenderCandidates() {
  const rows=remoteRows();
  $('remote-candidates').innerHTML=rows.length?rows.map((c,i)=>`<article class="candidate"><input type="checkbox" data-remote-select="${esc(c.id)}" aria-label="Selecionar ${esc(c.id)}" ${remoteSelected.has(c.id)?'checked':''}><div class="score">${c.editorial_review?.editorial_score??c.score}<small>#${i+1} ${esc(c.editorial_review?.classification||'BRUTO')}</small></div><div><strong>${esc(c.creator.toUpperCase())} · ${esc(c.date||'Data pendente')} · ${time(c.start)} → ${time(c.end)} · ${Math.round(c.end-c.start)}s</strong><p>${esc(c.vod_title)}</p>${c.editorial_review?`<p><strong>${esc(c.editorial_review.title||'Conferir momento')}</strong> · ${esc(c.editorial_review.content_type)}${c.editorial_review.title_alt?`<br>Outra opção: ${esc(c.editorial_review.title_alt)}`:''}<br>Sugerido: ${time(c.editorial_review.suggested_start)} → ${time(c.editorial_review.suggested_end)} · ${Math.round(c.editorial_review.suggested_duration)}s<br>HOOK: ${esc(c.editorial_review.hook)}<br>MOTIVO: ${esc(c.editorial_review.reason)}<br>LAYOUT: ${esc(c.editorial_review.layout)} · EDIÇÃO: ${esc(c.editorial_review.difficulty)}</p><p class="hint">${esc((c.editorial_review.warnings||[]).join(' · '))}</p>`:''}${c.refined_alternatives?.length?`<p class="hint">Mesmo núcleo em ${c.refined_alternatives.map(a=>`${time(a.start)} → ${time(a.end)}`).join(' · ')}. Originais disponíveis em Todos.</p>`:''}${c.refined_duplicate_of?'<p class="hint">Mesmo intervalo refinado de outro candidato; agrupado na shortlist.</p>':''}<span class="tag">${esc(c.status)}</span> <span class="tag">${esc(c.type)}</span>${c.eligibility_review?.status?`<p class="warning"><b>${esc(c.eligibility_review.status)}</b> · ${esc((c.eligibility_review.reasons||[]).join(' · '))}</p>`:''}<p>${esc(c.summary)}</p><p class="reason">${esc(c.reason)} · Score bruto ${c.score} (preservado)</p><div class="candidate-actions"><button data-remote-preview="${esc(c.id)}">Preview</button><button data-remote-review="APROVADO" data-id="${esc(c.id)}">Aprovar</button><button data-remote-review="DESCARTADO" data-id="${esc(c.id)}">Descartar</button><button data-remote-edit="${esc(c.id)}">Pacote editorial</button><button data-remote-vod="${esc(c.vod_id)}">Abrir VOD</button>${c.exports.filter(e=>e.kind==='raw').map(e=>`<a href="/media/export/${e.id}?download=1">RAW</a>`).join('')}</div></div></article>`).join(''):'<p class="hint">Nenhum candidato neste filtro. Regiões sem conteúdo podem gerar zero.</p>';
}
async function remoteRefresh(force=false) {
  if(!remoteRun || (remoteBusy&&!force))return;remoteBusy=true;
  try {
    const rid=remoteRun,data=await api('/api/remote/'+rid);if(rid!==remoteRun)return;
    remoteDetail=data;const s=data.summary;
    $('remote-summary').textContent=`${s.found} VODs · ${s.hours.toFixed(1)}h · ${s.processed} processadas · ${s.pending} pendentes · ${s.blocked} bloqueadas pelas regras · ${s.candidates} candidatos · ${s.approved} aprovados · ${s.raws} RAWs · Temporários: ${(data.temporary_bytes/1024**2).toFixed(1)} MB`;
    $('remote-sync-status').textContent=`Última sincronização: ${data.campaign.last_sync||'Ainda não executada'} · ${data.campaign.sync_message||''}`;
    const chosen=$('remote-filter-vod').value;
    $('remote-filter-vod').innerHTML='<option value="">Todas</option>'+data.vods.map(v=>`<option value="${esc(v.id)}">${esc(v.date||'')} · ${esc(v.title)}</option>`).join('');$('remote-filter-vod').value=chosen;
    $('remote-vods').innerHTML=data.vods.map(v=>`<p><b>${esc(v.remote_state||'PENDENTE')}</b> · ${esc(v.date||'Data pendente')} · ${esc(v.title)} · ${time(v.duration)}<br><small>${esc(v.remote_error||v.eligibility?.reasons?.join(' · ')||'')}${v.reviewer_metrics?` · Revisor ${v.reviewer_metrics.seconds.toFixed(2)}s (${v.reviewer_metrics.cached} em cache)`:''}${v.preview_metrics?` · Preview ${v.preview_metrics.seconds.toFixed(2)}s ${v.preview_metrics.cache_hit?'(cache)':''}`:''}</small></p>`).join('')||'Nenhuma VOD descoberta. Sincronize ou inclua uma URL.';
    $('remote-jobs').innerHTML=data.jobs.slice(0,12).map(j=>`<div class="job ${j.state==='ERRO'?'error':''}"><b>${esc(j.kind.toUpperCase())} · ${esc(j.state)}</b> ${j.progress}%<div>${esc(j.message)}</div>${['FILA','EXECUTANDO'].includes(j.state)?`<progress max="100" value="${j.progress}"></progress>`:''}${['ERRO','CANCELADO','INTERROMPIDO'].includes(j.state)?`<button data-remote-retry="${esc(j.id)}">Tentar novamente</button>${j.kind==='raw'?`<button data-remote-best="${esc(j.id)}">Tentar melhor qualidade disponível</button>`:''}`:''}</div>`).join('');
    $('remote-editorial-counts').textContent=['RECOMENDADO','BOM','TALVEZ','FRACO'].map(k=>`${k}: ${data.candidates.filter(c=>c.editorial_review?.classification===k).length}`).join(' · ');
    remoteRenderCandidates();
    await remoteRenderBacklog();
    if(remotePreview){const job=data.jobs.find(j=>j.id===remotePreview.job);if(job?.state==='CONCLUÍDO'){const c=data.candidates.find(c=>c.id===remotePreview.id);const e=c?.exports.filter(e=>e.kind==='preview').at(-1);if(e)showPreview(e,c);remotePreview=null;}else if(['ERRO','CANCELADO'].includes(job?.state)){toast(job.message,true);remotePreview=null;}}
  } finally {remoteBusy=false;}
}
$('remote-open').onclick=handle(async()=>{
  current=null;$('welcome').hidden=true;$('vod-view').hidden=true;$('remote-panel').hidden=false;$('breadcrumb').textContent='CAMPANHAS / REMOTE';
  if(!$('remote-creator').options.length){state=await api('/api/state');$('remote-creator').innerHTML=Object.values(state.campaigns).map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');remoteDefaults();}
  await remoteList();await remoteRefresh();
});
$('new-vod').addEventListener('click',()=>{$('remote-panel').hidden=true;});
$('remote-creator').onchange=remoteDefaults;
$('remote-runs').onchange=handle(async()=>{
  remoteRun=$('remote-runs').value||null;remoteSelected.clear();remoteDetail=null;remotePreview=null;
  if(!remoteRun){remoteDefaults();$('remote-summary').textContent='';$('remote-jobs').innerHTML='';$('remote-vods').innerHTML='';remoteRenderCandidates();if($('backlog-panel'))$('backlog-panel').hidden=true;return;}
  await remoteRefresh(true);if(!remoteDetail)return;const c=remoteDetail.campaign;$('remote-creator').value=c.creator;remoteDefaults();$('remote-provider').value=c.provider;$('remote-channel').value=c.channel;$('remote-start').value=c.start;$('remote-end').value=c.end;
});
$('remote-config').onsubmit=handle(async e=>{e.preventDefault();const r=await api('/api/remote/campaigns',{id:remoteRun,creator:$('remote-creator').value,provider:$('remote-provider').value,channel:$('remote-channel').value,start:$('remote-start').value,end:$('remote-end').value});remoteRun=r.campaign.id;await remoteList();await remoteRefresh();toast('Campanha operacional salva. Regras oficiais preservadas.');});
$('remote-sync').onclick=handle(()=>remoteAction('sync'));
$('remote-mine').onclick=handle(()=>remoteAction('mine',{mining_mode:$('remote-mode').value}));
$('remote-cancel').onclick=handle(()=>remoteAction('cancel'));
$('remote-manual').onclick=handle(()=>remoteAction('manual',{urls:$('remote-urls').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean)}));
for(const name of ['vod','date','status','score','type','editorial'])$('remote-filter-'+name).onchange=remoteRenderCandidates;
$('remote-select-all').onclick=()=>{remoteSelected=new Set(remoteRows().map(c=>c.id));remoteRenderCandidates();};
$('remote-select-approved').onclick=()=>{remoteSelected=new Set(remoteRows().filter(c=>c.status==='APROVADO').map(c=>c.id));remoteRenderCandidates();};
for(const [id,status] of [['remote-approve','APROVADO'],['remote-discard','DESCARTADO']])$(id).onclick=handle(()=>remoteAction('review',{ids:[...remoteSelected],status,feedback:$('remote-feedback').value}));
$('remote-download').onclick=handle(()=>remoteAction('download',{ids:[...remoteSelected],pre:Number($('remote-pre').value),post:Number($('remote-post').value),best:$('remote-best').checked}));
$('remote-jobs').onclick=handle(async e=>{const retry=e.target.closest('[data-remote-retry],[data-remote-best]');if(retry)await remoteAction('retry',{job:retry.dataset.remoteRetry||retry.dataset.remoteBest,best:!!retry.dataset.remoteBest});});
$('remote-candidates').onchange=e=>{if(e.target.matches('[data-remote-select]')){const id=e.target.dataset.remoteSelect;e.target.checked?remoteSelected.add(id):remoteSelected.delete(id);}};
$('remote-candidates').onclick=handle(async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.remotePreview){const r=await remoteAction('preview',{candidate_id:b.dataset.remotePreview,pre:0,post:0});if(r.export){showPreview(r.export,remoteDetail.candidates.find(c=>c.id===b.dataset.remotePreview));}else{remotePreview={id:b.dataset.remotePreview,job:r.job};await remoteRefresh();}}
  if(b.dataset.remoteReview)await remoteAction('review',{ids:[b.dataset.id],status:b.dataset.remoteReview,feedback:$('remote-feedback').value});
  if(b.dataset.remoteVod)await openVod(b.dataset.remoteVod);
  if(b.dataset.remoteEdit){remoteEdit=b.dataset.remoteEdit;const c=remoteDetail.candidates.find(c=>c.id===remoteEdit),p={...(c.editorial_review?{title:c.editorial_review.title,hook:c.editorial_review.hook,note:c.editorial_review.reason,layout:c.editorial_review.layout,recommended_start:c.editorial_review.suggested_start,recommended_end:c.editorial_review.suggested_end}:{}),...c.editorial_package};for(const key of ['title','publication_title','hook','note','layout'])$('editorial-'+key).value=p[key]||'';for(const key of ['start','end'])$('editorial-recommended_'+key).value=String(p['recommended_'+key]??c[key]);const cmp=state.campaigns[c.creator||c.campaign];if(cmp&&$('editorial-obligations')){const ob=(cmp.id==='gabepeixe')?['⚠ LOWER OBRIGATÓRIO (abaixo do rosto do Gabe)','⚠ #gabepeixe','⚠ MARCAR PERFIL OFICIAL']:(cmp.required_visuals||[]);$('editorial-obligations').hidden=!ob.length;$('editorial-obligations').innerHTML=ob.map(o=>`<strong>${esc(o)}</strong>`).join('<br>');}$('editorial-dialog').showModal();}
});
$('editorial-close').onclick=()=>$('editorial-dialog').close();
$('editorial-form').onsubmit=handle(async e=>{e.preventDefault();const values=Object.fromEntries(['title','publication_title','hook','note','layout'].map(k=>[k,$('editorial-'+k).value]));for(const key of ['start','end'])values['recommended_'+key]=remoteClock($('editorial-recommended_'+key).value);await remoteAction('package',{candidate_id:remoteEdit,values});$('editorial-dialog').close();toast('Pacote editorial salvo.');});
setInterval(()=>{if(!$('remote-panel').hidden&&!$('editorial-dialog').open)remoteRefresh().catch(e=>toast(e.message,true));},3000);

$('remote-editorial').onclick=handle(()=>remoteAction('editorial'));
$('remote-previews').onclick=handle(()=>remoteAction('shortlist_previews'));

async function remoteRenderBacklog() {
  const panel = $('backlog-panel');
  if(!panel) return;
  if(!remoteRun) { panel.hidden = true; return; }
  panel.hidden = false;
  try {
    const res = await api('/api/remote/' + remoteRun + '/backlog');
    const bl = res.backlog;
    const running = res.running_job;
    const pauseReq = res.pause_requested;

    $('bl-total').textContent = bl.total_found;
    $('bl-completed').textContent = bl.completed_count;
    $('bl-processing').textContent = bl.processing ? 1 : 0;
    $('bl-pending').textContent = bl.pending_count;
    $('bl-failed').textContent = bl.failed_count;
    $('bl-shortlists').textContent = bl.shortlists_ready;
    $('bl-candidates').textContent = bl.candidates_waiting;

    const badge = $('backlog-status-badge');
    if (pauseReq) {
      badge.textContent = 'PAUSA SOLICITADA';
      badge.className = 'chip warning';
    } else if (running) {
      badge.textContent = `EXECUTANDO (${running.progress}%)`;
      badge.className = 'chip primary';
    } else {
      badge.textContent = bl.pending_count > 0 ? 'AGUARDANDO' : 'CONCLUÍDO';
      badge.className = 'chip';
    }

    $('backlog-start').disabled = Boolean(running);
    $('backlog-pause').disabled = !running || Boolean(pauseReq);
    $('backlog-resume').disabled = Boolean(running);

    const curCard = $('backlog-current-card');
    if (bl.processing) {
      const p = bl.processing;
      curCard.innerHTML = `<div class="job" style="border:1px solid var(--accent); background:#172518;">
        <b>PROCESSANDO AGORA · ${esc(p.date || 'Data pendente')}</b>
        <p style="margin:4px 0;"><strong>${esc(p.title)}</strong> (${time(p.duration)})</p>
        <small>${esc(running?.message || 'Em processamento...')}</small>
        ${pauseReq ? '<div class="warning" style="margin-top:8px; padding:8px;">⏸ <b>Pausa solicitada</b>: o runner finalizará esta VOD com segurança e salvará o progresso antes de pausar a fila.</div>' : '<p class="hint" style="margin-top:6px;">Pausa segura: pausar aguarda a conclusão da VOD atual antes de parar.</p>'}
      </div>`;
    } else {
      curCard.innerHTML = '<p class="hint">Nenhuma VOD em processamento no momento.</p>';
    }

    const allVods = [...(bl.processing ? [bl.processing] : []), ...bl.upcoming, ...bl.failed, ...bl.completed];
    $('backlog-queue-count').textContent = bl.upcoming.length + (bl.processing ? 1 : 0);

    $('backlog-queue-items').innerHTML = allVods.length ? allVods.map((v, i) => {
      const isFailed = v.backlog_state === 'ERRO';
      const isDone = v.backlog_state === 'CONCLUÍDO';
      return `<div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border); font-size:12px;">
        <div style="flex:1; min-width:0; padding-right:10px;">
          <span style="color:var(--muted); margin-right:6px;">#${i + 1}</span>
          <span class="tag ${isFailed ? 'error' : isDone ? 'approved' : ''}">${esc(v.backlog_state)}</span>
          <strong style="margin-left:6px;">${esc(v.date || 'Data pendente')}</strong> · ${esc(v.title)} (${time(v.duration)})
          ${v.remote_error ? `<br><small style="color:#fca5a5;">${esc(v.remote_error)}</small>` : ''}
        </div>
        <div>
          ${isFailed ? `<button type="button" data-retry-vod="${esc(v.id)}">↺ Tentar novamente</button>` : ''}
          ${isDone ? `<button type="button" data-view-candidates="${esc(v.id)}">Ver candidatos (${v.candidates_count || 0})</button>` : ''}
        </div>
      </div>`;
    }).join('') : '<p class="hint">Nenhuma VOD no catálogo desta campanha.</p>';
  } catch (err) {
    console.error('Backlog view error:', err);
  }
}

$('backlog-refresh').onclick = handle(async () => {
  await remoteAction('sync');
  await remoteRenderBacklog();
});
$('backlog-start').onclick = handle(async () => {
  await remoteAction('backlog', {mining_mode: $('remote-mode').value});
  await remoteRenderBacklog();
});
$('backlog-pause').onclick = handle(async () => {
  await remoteAction('pause');
  await remoteRenderBacklog();
});
$('backlog-resume').onclick = handle(async () => {
  await remoteAction('backlog', {mining_mode: $('remote-mode').value});
  await remoteRenderBacklog();
});
$('backlog-panel').onclick = handle(async e => {
  const retryBtn = e.target.closest('[data-retry-vod]');
  if (retryBtn) {
    await remoteAction('retry_vod', {vod_id: retryBtn.dataset.retryVod});
    await remoteRenderBacklog();
    return;
  }
  const viewBtn = e.target.closest('[data-view-candidates]');
  if (viewBtn) {
    $('remote-filter-vod').value = viewBtn.dataset.viewCandidates;
    remoteRenderCandidates();
  }
});

