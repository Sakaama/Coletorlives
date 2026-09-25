const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/app.js','utf8');
const rendering = source.slice(source.indexOf('function renderCandidates'),source.indexOf('\nasync function action'));
for (const [level,label] of [['HIGH','Alto'],['MEDIUM','Médio'],['LOW','Baixo'],[null,'Não medido']]) {
  test(`candidate displays visual ${label} and keeps review actions`,()=>{
    const nodes={'status-filter':{value:'all'},'candidate-count':{},candidates:{}};
    const c={id:'one',start:10,end:30,score:75,status:'NOVO',summary:'fala',reason:'hook',exports:[],visual_activity_level:level};
    vm.runInNewContext(rendering+'\nrenderCandidates();',{$:id=>nodes[id],detail:{candidates:[c]},selected:new Set(),esc:String,time:String});
    assert.ok(nodes.candidates.innerHTML.includes(`Visual: ${label}`));
    for (const action of ['data-preview','data-review="APROVADO"','data-review="DESCARTADO"']) {
      assert.ok(nodes.candidates.innerHTML.includes(action));
    }
  });
}
