const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
for(const remote of [false,true])test(`excerpt eligibility warning preserves review actions (${remote?'remote':'VOD'})`,()=>{
  const source=fs.readFileSync(remote?'static/remote.js':'static/app.js','utf8');
  const fn=remote?'remoteRenderCandidates':'renderCandidates';
  const end=remote?'async function remoteRefresh':'\nasync function action';
  const code=source.slice(source.indexOf('function '+fn),source.indexOf(end));
  const c={id:'c',creator:'brkk',start:10,end:30,score:80,status:'NOVO',summary:'fala',reason:'hook',exports:[],eligibility_review:{status:'REVISÃO DE ELEGIBILIDADE',reasons:['Possível filme; confira o trecho.']}};
  const nodes={'status-filter':{value:'all'},'candidate-count':{},candidates:{},'remote-candidates':{}};
  vm.runInNewContext(code+`\n${fn}();`,{$:id=>nodes[id],detail:{candidates:[c]},remoteRows:()=>[c],selected:new Set(),remoteSelected:new Set(),esc:String,time:String});
  const html=nodes[remote?'remote-candidates':'candidates'].innerHTML;
  assert.ok(html.includes('REVISÃO DE ELEGIBILIDADE'));
  assert.ok(html.includes('NOVO')&&html.includes('Preview')&&html.includes('Aprovar')&&html.includes('Descartar'));
});
