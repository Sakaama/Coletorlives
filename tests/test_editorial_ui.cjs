const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/remote.js','utf8');
const context={};
vm.runInNewContext(source.slice(source.indexOf('function remoteFiltered'),source.indexOf('function remoteClock')),context);
test('shortlist has no quota and weak candidates remain accessible',()=>{
  const rows=Array.from({length:30},(_,i)=>({id:String(i),score:60,editorial_review:{classification:i<25?'BOM':'FRACO',editorial_score:i<25?75:30}}));
  assert.equal(context.remoteFiltered(rows,{classification:'SHORTLIST'}).length,25);
  assert.equal(context.remoteFiltered(rows,{classification:'FRACO'}).length,5);
  assert.equal(context.remoteFiltered(rows,{classification:'TODOS'}).length,30);
  assert.equal(context.remoteFiltered(rows,{classification:'RECOMENDADO'}).length,0);
});
test('editorial score and refined range displayed without losing original or review controls',()=>{
  const nodes={'remote-candidates':{}};
  const c={id:'one',creator:'brkk',start:100,end:200,score:57,status:'NOVO',summary:'original',reason:'reason',exports:[],editorial_review:{editorial_score:89,classification:'RECOMENDADO',suggested_start:120,suggested_end:145,suggested_duration:25,title:'Título',content_type:'BASTIDOR',reason:'Relação contextual',warnings:[]}};
  const code=source.slice(source.indexOf('function remoteRenderCandidates'),source.indexOf('async function remoteRefresh'));
  vm.runInNewContext(code+'\nremoteRenderCandidates();',{$:id=>nodes[id],remoteRows:()=>[c],remoteSelected:new Set(),esc:String,time:String});
  const html=nodes['remote-candidates'].innerHTML;
  for(const expected of ['89','RECOMENDADO','100 → 200','120 → 145','Score bruto 57','Preview','Aprovar','Descartar'])assert.ok(html.includes(expected),expected);
});

test('identical refined moments grouped only in shortlist; all records remain reviewable',()=>{
 const rows=[{id:'a',score:90,editorial_review:{classification:'RECOMENDADO'}},{id:'b',score:89,editorial_review:{classification:'RECOMENDADO'},refined_duplicate_of:'a'}];
 assert.equal(context.remoteFiltered(rows,{classification:'SHORTLIST'}).length,1);
 assert.equal(context.remoteFiltered(rows,{classification:'TODOS'}).length,2);
 assert.equal(context.remoteFiltered(rows,{classification:'RECOMENDADO'}).length,2);
});
