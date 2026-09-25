const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/app.js','utf8');
const rendering = source.slice(source.indexOf('function renderJobs()'), source.indexOf('\nfunction renderCandidates'));
function render({local=false, active=false, fallback=true}={}) {
  let clicks=0;
  const nodes={jobs:{innerHTML:''},'attach-local':{click:()=>clicks++}};
  const context={$:id=>nodes[id],current:'vod',esc:s=>String(s),state:{
    vods:[{id:'vod',local_path:local?'manual.mp4':null}],
    jobs:[{id:'job',vod_id:'vod',state:'ERRO',kind:'metadata',progress:0,message:'Kick incompatível',fallback:fallback?'import_local':undefined},
      ...(active?[{id:'work',vod_id:'vod',state:'EXECUTANDO',kind:'download',progress:0,message:''}]:[])]}};
  vm.runInNewContext(rendering+'\nrenderJobs();', context);
  return {html:nodes.jobs.innerHTML,click:()=>nodes.jobs.onclick({target:{closest:()=>({})}}),clicks:()=>clicks};
}
test('fallback immediately shows local import and invokes existing attachment flow',()=>{
  const result=render();
  assert.match(result.html,/>Importar arquivo local<\/button>/);
  result.click();assert.equal(result.clicks(),1);
});
test('ordinary errors have no Kick fallback',()=>assert.doesNotMatch(render({fallback:false}).html,/data-import-fallback/));
test('fallback disappears when original record has local media',()=>assert.doesNotMatch(render({local:true}).html,/data-import-fallback/));
test('fallback disabled while the VOD has active work',()=>assert.match(render({active:true}).html,/data-import-fallback disabled/));
