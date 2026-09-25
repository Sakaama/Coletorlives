const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('static/app.js','utf8');
test('stage summary exposes measured timings without ETA or counts as time',()=>{
  const code=source.slice(source.indexOf('function metricsText'),source.indexOf('function toast'));
  const context={time:n=>String(n)};
  vm.runInNewContext(code,context);
  assert.equal(context.metricsText({visual:12,total:60,chunks:72}),'Visual: 12 · Total: 60');
  assert.equal(context.metricsText(), '');
});
for(const enabled of [false,true]) {
  test(`RAW remote remains an explicit aligned-proxy option: ${enabled}`,async()=>{
    const nodes={'raw-selected':{},'prep-selected':{},'raw-remote':{checked:enabled},'raw-url':{value:'https://kick.com/channel/videos/id'}};
    const calls=[];
    const code=source.split('\n').find(line=>line.startsWith("for(const kind of ['raw','prep'])"));
    vm.runInNewContext(code,{$:id=>nodes[id],handle:fn=>fn,selected:new Set(['c']),action:async(...args)=>calls.push(args)});
    await nodes['raw-selected'].onclick();
    assert.equal(!!calls[0][1].remote_raw,enabled);
    if(enabled) assert.equal(calls[0][1].remote_raw.aligned,true);
    await nodes['prep-selected'].onclick();
    assert.equal(calls[1][1].remote_raw,undefined);
  });
}
