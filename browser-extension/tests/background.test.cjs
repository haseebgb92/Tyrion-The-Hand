const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const crypto=require('node:crypto').webcrypto;
const source=fs.readFileSync('browser-extension/background.js','utf8').replace(/init\(\)\.catch\(\(\)=>\{\}\);\s*$/,'');
function harness(queue=[{id:50,kind:'task',entity_id:9}]){
 const storage={pairingKey:'pairing_test_'.repeat(6),autoOpenChats:true};
 const opened=[],updates=[],backend=[];
 let index=0;
 const state={counts:{open_tasks:1,due_handoffs:0,drafts_ready:0},tasks:[],runs:[]};
 const chrome={
   storage:{local:{get:async keys=>Object.fromEntries(keys.map(k=>[k,storage[k]])),set:async values=>Object.assign(storage,values),remove:async ks=>ks.forEach(k=>delete storage[k])}},
   tabs:{create:async args=>{const tab={id:42,...args};opened.push(tab);return tab},update:async(id,args)=>{updates.push({id,...args});return {id,...args}}},
   action:{setBadgeText:async()=>{},setBadgeBackgroundColor:async()=>{}},
   alarms:{get:async()=>({}),create:async()=>{},onAlarm:{addListener:()=>{}}},
   runtime:{onInstalled:{addListener:()=>{}},onStartup:{addListener:()=>{}},onMessage:{addListener:()=>{}}}
 };
 const fetch=async(url,options={})=>{
   backend.push({url,method:options.method||'GET',body:options.body});
   let result;
   if(url.endsWith('/api/extension/state'))result=state;
   else if(url.endsWith('/api/extension/dispatch/claim'))result={ok:true,result:queue[index++]||null};
   else if(url.endsWith('/api/extension/dispatch/report'))result={ok:true,result:{status:JSON.parse(options.body).stage}};
   else if(url.endsWith('/api/extension/dispatch/heartbeat'))result={ok:true,result:{ok:true}};
   else if(url.endsWith('/api/extension/dispatch/status'))result={queue};
   else throw Error('Unexpected '+url);
   return {ok:true,json:async()=>result};
 };
 const context=vm.createContext({chrome,URL,Date,console,crypto,fetch});vm.runInContext(source,context);
 return {storage,opened,updates,backend,context,refresh:()=>vm.runInContext('refresh()',context)};
}
test('PC queue opens once, includes nonce and persists tab before navigation',async()=>{
 const h=harness();await h.refresh();await h.refresh();
 assert.equal(h.opened.length,1);
 assert.equal(h.opened[0].url,'about:blank');
 assert.equal(h.updates.length,1);
 assert.match(h.updates[0].url,/^https:\/\/chatgpt.com\/\?q=/);
 assert.match(decodeURIComponent(h.updates[0].url),/task #9/);
 assert.match(h.updates[0].url,/tyrion_auto=[a-f0-9]{32}/);
 assert.equal(Object.keys(h.storage.pendingHandoffs).length,1);
 const reports=h.backend.filter(x=>x.url.endsWith('/report')).map(x=>JSON.parse(x.body));
 assert.deepEqual(reports.map(x=>x.stage),['opened']);
 assert.equal(reports[0].dispatch_id,50);
});
test('old queued work is not filtered by timestamp',async()=>{
 const h=harness([{id:81,kind:'task',entity_id:22,created_at:'2020-01-01'}]);await h.refresh();
 assert.match(decodeURIComponent(h.updates[0].url),/task #22/);
});
test('MCP-sourced work cannot leak task details into URL',async()=>{
 const h=harness([{id:88,kind:'run',entity_id:4,title:'Secret customer',instructions:'dont share'}]);await h.refresh();
 assert.match(decodeURIComponent(h.updates[0].url),/run #4/);
 assert.ok(!h.updates[0].url.includes('Secret'));
 assert.ok(!h.updates[0].url.includes('customer'));
});
test('disabled auto-start leaves PC queue unclaimed',async()=>{
 const h=harness();h.storage.autoOpenChats=false;await h.refresh();
 assert.equal(h.opened.length,0);
 assert.equal(h.backend.filter(x=>x.url.endsWith('/claim')).length,0);
});
test('throttle preserves pending queue, does not lose claims',async()=>{
 const h=harness();h.storage.openedTimes=[Date.now(),Date.now(),Date.now()];await h.refresh();
 assert.equal(h.opened.length,0);
 assert.equal(h.backend.filter(x=>x.url.endsWith('/claim')).length,0);
});
test('Chrome heartbeats PC independently of task availability',async()=>{
 const h=harness([]);await h.refresh();
 assert.ok(h.backend.find(x=>x.url.endsWith('/heartbeat')));
 assert.equal(h.opened.length,0);
});
