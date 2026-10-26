const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('browser-extension/handoff.js','utf8');
const nonce='a'.repeat(32);
const prompt='Using the connected Tyrion – The Hand MCP, inspect task #9.';
async function run(url,editorValue=prompt){
 let clicks=0,auth=0,reported=0;
 const editor={innerText:editorValue};
 const button={disabled:false,click(){clicks++}};
 const document={querySelector(s){return s.startsWith('div.ProseMirror')?editor:button}};
 const chrome={runtime:{lastError:null,sendMessage(message,cb){
   if(message.type==='authorizeAutoSubmit'){auth++;cb({ok:true,result:{expectedPrompt:prompt}})}
   else if(message.type==='reportAutoSubmit'){reported++;cb({ok:true,result:{status:'submit_clicked'}})}
 }}};
 const context=vm.createContext({location:new URL(url),URL,chrome,document,Date,console,setTimeout});
 await vm.runInContext(source,context);
 return {clicks,auth,reported};
}
test('extension-generated nonce submits exactly once, no output read',async()=>{
 const result=await run('https://chatgpt.com/?q='+encodeURIComponent(prompt)+'&tyrion_auto='+nonce);
 assert.deepEqual(result,{clicks:1,auth:1,reported:1});
});
test('ordinary ChatGPT tabs do not submit',async()=>{
 const result=await run('https://chatgpt.com/?q='+encodeURIComponent(prompt));
 assert.deepEqual(result,{clicks:0,auth:0,reported:0});
});
test('user-edited composer is never auto-submitted',async()=>{
 const result=await run('https://chatgpt.com/?q='+encodeURIComponent(prompt)+'&tyrion_auto='+nonce,'This is my edited prompt');
 assert.deepEqual(result,{clicks:0,auth:0,reported:0});
});
