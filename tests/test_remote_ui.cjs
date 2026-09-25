const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('static/remote.js','utf8');
const ctx={};
vm.runInNewContext(source.slice(source.indexOf('function remoteFiltered'),source.indexOf('function remoteRows')),ctx);
test('campaign ranking filters compose without changing source order',()=>{
  const rows=[{id:'a',vod_id:'v1',date:'2026-09-16',score:95,type:'VISUAL',status:'APROVADO'},
    {id:'b',vod_id:'v2',date:'2026-09-17',score:90,type:'TALKING',status:'NOVO'}];
  assert.equal(ctx.remoteFiltered(rows,{}).length,2);
  assert.equal(ctx.remoteFiltered(rows,{vod:'v1',date:'2026-09-16',score:90,type:'VISUAL',status:'APROVADO'})[0].id,'a');
  assert.equal(ctx.remoteFiltered(rows,{score:96}).length,0);
  assert.equal(ctx.remoteFiltered(rows,{type:'TALKING'})[0].id,'b');
});
test('editorial time parses absolute six-hour timestamps and rejects malformed time',()=>{
  assert.equal(ctx.remoteClock('06:17:38'),22658);
  assert.equal(ctx.remoteClock('22658.5'),22658.5);
  for(const bad of ['', '-1', '1:99', 'NaN', '1:2:3:4'])assert.throws(()=>ctx.remoteClock(bad));
});
test('selecting approved candidates respects visible filters and sends multiple IDs',async()=>{
  const nodes={'remote-select-all':{},'remote-select-approved':{},'remote-download':{},'remote-pre':{value:'5'},'remote-post':{value:'7'},'remote-best':{checked:false}};
  const calls=[];
  const context={$:id=>nodes[id],remoteRows:()=>[{id:'a',status:'APROVADO'},{id:'b',status:'NOVO'},{id:'c',status:'APROVADO'}],remoteRenderCandidates:()=>{},handle:fn=>fn,remoteAction:(...a)=>calls.push(a)};
  vm.runInNewContext('let remoteSelected=new Set();\n'+source.split('\n').filter(l=>l.startsWith("$('remote-select-")||l.startsWith("$('remote-download')")).join('\n'),context);
  nodes['remote-select-approved'].onclick();
  await nodes['remote-download'].onclick();
  assert.deepEqual(Array.from(calls[0][1].ids),['a','c']);
  assert.equal(calls[0][1].pre,5);assert.equal(calls[0][1].post,7);assert.equal(calls[0][1].best,false);
});
