// One-time acceptance screenshot. Reads a temporary paired-device token from stdin.
// No token is included in the screenshot or browser URL.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process');
const URL='https://haseeb-optiplex-3050.tailb87e57.ts.net:8443/';
const token=fs.readFileSync(0,'utf8').trim();
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'tyrion-android-qa-'));
const browser=spawn('google-chrome',['--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--remote-allow-origins=*','--remote-debugging-port=0','--user-data-dir='+temp,'--window-size=440,880','about:blank'],{stdio:'ignore'});
const delay=t=>new Promise(resolve=>setTimeout(resolve,t));
let sock,seq=0;const awaiting=new Map();
function cdp(method,params={}){return new Promise((resolve,reject)=>{
 const id=++seq;awaiting.set(id,{resolve,reject});sock.send(JSON.stringify({id,method,params}));
 setTimeout(()=>{if(awaiting.has(id)){awaiting.delete(id);reject(Error('Timed out '+method))}},12000);
})}
async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,returnByValue:true});return r.result.result.value}
(async()=>{try{
 let port;for(let i=0;i<90;i++){try{port=Number(fs.readFileSync(path.join(temp,'DevToolsActivePort'),'utf8').split('\n')[0]);break}catch{}await delay(120)}
 if(!port)throw Error('Chrome startup failed');
 const pages=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 sock=new WebSocket(pages.find(v=>v.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{sock.onopen=resolve;sock.onerror=reject});
 sock.onmessage=e=>{const obj=JSON.parse(e.data);const task=awaiting.get(obj.id);if(task){awaiting.delete(obj.id);obj.error?task.reject(Error(obj.error.message)):task.resolve(obj)}};
 await cdp('Page.enable');await cdp('Network.enable');await cdp('Runtime.enable');
 await cdp('Emulation.setDeviceMetricsOverride',{width:393,height:852,deviceScaleFactor:2,mobile:true});
 const cookie=await cdp('Network.setCookie',{name:'tyrion_device',value:token,url:URL,secure:true,httpOnly:true,sameSite:'Strict'});
 if(!cookie.result.success)throw Error('Device token cookie not accepted');
 await cdp('Page.navigate',{url:process.env.COMPANION_VIEW==='dispatch'?URL+'#dispatch':URL});
 for(let i=0;i<60;i++){
   const ok=await evaluate(process.env.COMPANION_VIEW==='dispatch'?
    'Boolean(document.querySelector(".dispatch-browser"))' :
    'Boolean(document.querySelector(".stats-grid .stat"))');
   if(ok)break;await delay(160);
 }
 await delay(550);
 const info=await evaluate(`(()=>({title:document.title,stats:document.querySelectorAll('.stats-grid .stat').length,nav:document.querySelectorAll('[data-page]').length,viewport:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,styles:getComputedStyle(document.querySelector('.sidebar')).position,visible:document.body.innerText.slice(0,220)}))()`);
 const shot=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 fs.writeFileSync(process.env.COMPANION_VIEW==='dispatch'?'data/companion-dispatch-mobile.png':'data/companion-mobile-preview.png',Buffer.from(shot.result.data,'base64'));
 if(process.env.COMPANION_VIEW==='dispatch')info.dispatch=await evaluate('(()=>({cards:document.querySelectorAll(".dispatch-item").length,queue:document.querySelector("#dispatch-body")?.innerText?.slice(0,240)}))()');
 console.log(JSON.stringify(info));
 }catch(error){console.error('Capture error:',error.message);process.exitCode=1}
 finally{try{sock.close()}catch{}browser.kill('SIGTERM');fs.rmSync(temp,{recursive:true,force:true});}
})()
