const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'tyrion-pair-card-'));
const browser=spawn('google-chrome',['--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--remote-allow-origins=*','--remote-debugging-port=0','--user-data-dir='+temp,'http://127.0.0.1:17877/#connections'],{stdio:'ignore'});
let ws,seq=0;const pending=new Map();const pause=ms=>new Promise(r=>setTimeout(r,ms));
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timed out'))}},7000)});
const evaluate=async code=>(await send('Runtime.evaluate',{expression:code,returnByValue:true,awaitPromise:true})).result.result.value;
(async()=>{try{
 let port;for(let i=0;i<70;i++){try{port=Number(fs.readFileSync(path.join(temp,'DevToolsActivePort'),'utf8').split('\n')[0]);break}catch{}await pause(100)}
 if(!port)throw Error('Chrome failed');
 const target=(await(await fetch('http://127.0.0.1:'+port+'/json/list')).json()).find(x=>x.type==='page');
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
 ws.onmessage=e=>{const m=JSON.parse(e.data),w=pending.get(m.id);if(w){pending.delete(m.id);m.error?w.reject(Error(m.error.message)):w.resolve(m)}};
 await send('Runtime.enable');await send('Page.enable');
 for(let i=0;i<60;i++){if(await evaluate('Boolean(document.getElementById("companion-pair-panel"))'))break;await pause(110)}
 const card=await evaluate('(()=>{const x=document.getElementById("companion-pair-panel");return {exists:!!x,button:!!document.getElementById("companion-new-code"),deviceCount:document.getElementById("companion-device-count")?.innerText||""}})()');
 if(!card.exists||!card.button)throw Error('Android card missing');
 await evaluate('document.getElementById("companion-new-code").click()');
 for(let i=0;i<40;i++){if(await evaluate('Boolean(document.querySelector("#companion-code-panel img"))'))break;await pause(90)}
 const qr=await evaluate('(()=>{const p=document.getElementById("companion-code-panel");return {shown:!p?.hidden,image:p?.querySelector("img")?.getAttribute("src")?.startsWith("data:image/png;base64,")||false,eightDigitCode:(p?.dataset.code||"").length===8}})()');
 console.log(JSON.stringify({card,qr}));if(!qr.shown||!qr.image||!qr.eightDigitCode)process.exitCode=1;
 }catch(e){console.log('UI ERROR',e.message);process.exitCode=1}
 finally{try{ws.close()}catch{}browser.kill('SIGTERM');try{fs.rmSync(temp,{recursive:true,force:true,maxRetries:4,retryDelay:200})}catch{}}
})();
