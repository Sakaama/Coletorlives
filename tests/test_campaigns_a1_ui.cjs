const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const remote=fs.readFileSync('static/remote.js','utf8');
for(const id of ['joaopichau','juninhomanella']) test(`A1 existing rules and remote controls render ${id}`,()=>{
  const campaign=JSON.parse(fs.readFileSync(`config/campaigns/${id}.json`,'utf8'));
  const nodes=Object.fromEntries(['remote-creator','remote-provider','remote-channel','remote-start','remote-end','remote-rules'].map(k=>[k,{}]));
  nodes['remote-creator'].value=id;
  const code=source.slice(source.indexOf('function rules('),source.indexOf('function library('))+
    remote.slice(remote.indexOf('function remoteDefaults('),remote.indexOf('async function remoteList('));
  vm.runInNewContext(code+'\nremoteDefaults();',{$:k=>nodes[k],state:{campaigns:{[id]:campaign}},esc:s=>String(s??'')});
  const html=nodes['remote-rules'].innerHTML;
  assert.ok(html.includes(campaign.name)&&html.includes(campaign.hashtags[0]));
  assert.ok(html.includes('WhatsApp')&&html.includes('plataformas de IA'));
  assert.ok(!html.includes('undefined'));
  assert.equal(nodes['remote-start'].value,campaign.min_date||'');
  if(id==='joaopichau') assert.ok(html.includes('09/10/2026')&&html.includes('Evento Pichau Arena'));
  else assert.ok(html.includes('NO PRÓPRIO CORTE')&&html.includes('Kings League'));
});
