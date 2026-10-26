"use strict";
const API = "http://127.0.0.1:17877";
let running = null;
let realtimeSocket = null;
let realtimeReconnect = null;
async function connectRealtime(){
  if(typeof WebSocket==="undefined")return;
  if(realtimeSocket && (realtimeSocket.readyState===0||realtimeSocket.readyState===1))return;
  const {pairingKey}=await chrome.storage.local.get(["pairingKey"]);
  if(!pairingKey)return;
  let socket;
  try{socket=new WebSocket("ws://127.0.0.1:17879/")}catch{return}
  realtimeSocket=socket;
  socket.onopen=async()=>{
    const {lastEventId}=await chrome.storage.local.get(["lastEventId"]);
    if(socket.readyState!==1)return;
    socket.send(JSON.stringify({pairingKey,after:lastEventId||0}));
  };
  socket.onmessage=async event=>{
    let payload;
    try{payload=JSON.parse(event.data)}catch{return}
    if(payload.type==="change"){
      if(Number.isInteger(payload.last_event_id))
        await chrome.storage.local.set({lastEventId:payload.last_event_id});
      refresh().catch(()=>{});
    }
  };
  socket.onclose=()=>{
    if(realtimeSocket===socket)realtimeSocket=null;
    if(realtimeReconnect)clearTimeout(realtimeReconnect);
    realtimeReconnect=setTimeout(()=>connectRealtime().catch(()=>{}),10000);
  };
  socket.onerror=()=>{};
}

async function api(path, method="GET",body){
  const {pairingKey} = await chrome.storage.local.get(["pairingKey"]);
  if(!pairingKey)throw Error("PAIR_REQUIRED");
  const res = await fetch(API+path,{
    method,cache:"no-store",headers:{"X-Tyrion-Extension":pairingKey,...(body?{"Content-Type":"application/json"}:{})},
    ...(body?{body:JSON.stringify(body)}:{})
  });
  if(!res.ok)throw Error((await res.json().catch(()=>({}))).error || ("HTTP "+res.status));
  return await res.json();
}
const CHAT_BASE="https://chatgpt.com/";
const MAX_OPEN_PER_HOUR=3;
const OPEN_COOLDOWN_MS=12000;

// PC queue replaces the 45-minute create-time filter. Nothing disappears after an outage.
function taskHandoffPrompt(kind,id){
  return kind==="run"
    ?`Using the connected Tyrion – The Hand MCP, inspect scheduled run #${id}. Follow the saved instructions, verify progress and report all results back into Tyrion. Never duplicate, publish, spend, or change client sites without required approval.`
    :`Using the connected Tyrion – The Hand MCP, inspect task #${id} and its existing updates. Work on its saved instructions with authorized tools. Write verified progress to the SAME Tyrion task, avoid duplicates, and never mark it done without evidence.`;
}
function taskHandoffUrl(kind,id){
  // URL contains only task reference and generic instructions, never private task body.
  return CHAT_BASE+"?q="+encodeURIComponent(taskHandoffPrompt(kind,id));
}

async function reportDispatch(dispatchId,stage,tabId=null,error=""){
 if(!dispatchId)return;
 await api("/api/extension/dispatch/report","POST",{
   dispatch_id:dispatchId,stage,tab_id:tabId,error:String(error).slice(0,180)
 });
}
async function openHandoff(kind,id,autostart=false,dispatchId=null){
 if(!["task","run"].includes(kind)||!Number.isInteger(id)||id<1)throw Error("Invalid work item");
 const nonce=crypto.randomUUID().replaceAll("-","");
 const prompt=taskHandoffPrompt(kind,id);
 const saved=await chrome.storage.local.get(["pendingHandoffs"]);
 const pending=saved.pendingHandoffs||{};
 for(const key of Object.keys(pending))if(Date.now()-pending[key].created>600000)delete pending[key];
 // Open a blank tab first so the content script cannot race the authorization.
 const tab=await chrome.tabs.create({url:"about:blank",active:true});
 pending[nonce]={kind,id,prompt,created:Date.now(),tabId:tab.id,status:"armed",dispatchId};
 await chrome.storage.local.set({pendingHandoffs:pending});
 try{
   await reportDispatch(dispatchId,"opened",tab.id);
   await chrome.tabs.update(tab.id,{url:taskHandoffUrl(kind,id)+"&tyrion_auto="+nonce});
   await chrome.storage.local.set({lastLaunched:{kind,id,tabId:tab.id,at:Date.now(),automatic:autostart,status:"opened",dispatchId}});
   return {id,kind,tabId:tab.id,status:"handoff_opened"};
 }catch(error){
   try{await reportDispatch(dispatchId,"needs_attention",tab.id,error.message)}catch{}
   pending[nonce].status="submit_failed";
   await chrome.storage.local.set({pendingHandoffs:pending});
   throw error;
 }
}
async function pumpQueue(){
 const saved=await chrome.storage.local.get(["autoOpenChats","openedTimes","lastLaunched"]);
 if(saved.autoOpenChats===false)return;
 const recent=(saved.openedTimes||[]).filter(t=>Date.now()-t<3600000);
 if(recent.length>=MAX_OPEN_PER_HOUR)return;
 if(saved.lastLaunched?.at && Date.now()-saved.lastLaunched.at<OPEN_COOLDOWN_MS)return;
 // Atomic claim on the PC, not local timestamp filtering.
 const claim=(await api("/api/extension/dispatch/claim","POST",{})).result;
 if(!claim)return;
 try{
   await openHandoff(claim.kind,claim.entity_id,true,claim.id);
   await chrome.storage.local.set({openedTimes:[...recent,Date.now()]});
 }catch(error){
   await chrome.storage.local.set({lastAutoOpenError:{kind:claim.kind,id:claim.entity_id,error:error.message,at:Date.now()}});
 }
}

async function refresh(){
  if(running)return running;
  running=(async()=>{
    try{
      const state=await api("/api/extension/state");
      const count=state.counts.open_tasks+state.counts.due_handoffs;
      await chrome.action.setBadgeText({text:count?String(Math.min(count,99)):""});
      await chrome.action.setBadgeBackgroundColor({color:"#792a39"});
      await chrome.storage.local.set({lastStatus:{ok:true,checkedAt:Date.now(),counts:state.counts},
        lastEventId:state.latest_event_id||0});
      await api("/api/extension/dispatch/heartbeat","POST",{detail:"Chrome extension v1.1"});
      await pumpQueue();
      return state;
    }catch(e){
      await chrome.action.setBadgeText({text:"!"});
      await chrome.action.setBadgeBackgroundColor({color:"#977a4a"});
      await chrome.storage.local.set({lastStatus:{ok:false,error:e.message,checkedAt:Date.now()}});
      throw e;
    }finally{running=null;}
  })();
  return running;
}
async function init(){
  const settings=await chrome.storage.local.get(["autoOpenChats"]);
  if(settings.autoOpenChats===undefined)await chrome.storage.local.set({autoOpenChats:true});
  const alarm=await chrome.alarms.get("tyrionQueue");
  if(!alarm)await chrome.alarms.create("tyrionQueue",{periodInMinutes:0.5});
  try{await refresh()}catch{}
  try{await connectRealtime()}catch{}
}
chrome.runtime.onInstalled.addListener(()=>{init()});
chrome.runtime.onStartup.addListener(()=>{init()});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==="tyrionQueue"){
  refresh().catch(()=>{});
  connectRealtime().catch(()=>{});
}});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  (async()=>{
    if(!message || typeof message.type!=="string")throw Error("Invalid message");
    switch(message.type){
      case "authorizeAutoSubmit":{
        const nonce=message.nonce;
        if(typeof nonce!=="string"||!(/^[a-f0-9]{32}$/.test(nonce)))throw Error("Invalid handoff");
        const x=await chrome.storage.local.get(["pendingHandoffs","autoOpenChats"]);
        const pending=x.pendingHandoffs||{};
        const record=pending[nonce];
        if(!record||record.status!=="armed"||Date.now()-record.created>180000||
           !sender.tab||sender.tab.id!==record.tabId||
           !sender.url?.startsWith(CHAT_BASE)||x.autoOpenChats===false)
            throw Error("Handoff authorization unavailable");
        record.status="submit_authorized";
        record.authorizedAt=Date.now();
        await chrome.storage.local.set({pendingHandoffs:pending});
        return {expectedPrompt:record.prompt,kind:record.kind,id:record.id};
      }
      case "reportAutoSubmit":{
        const nonce=message.nonce;
        const x=await chrome.storage.local.get(["pendingHandoffs","lastLaunched"]);
        const pending=x.pendingHandoffs||{},record=pending[nonce];
        if(!record||record.status!=="submit_authorized"||!sender.tab||sender.tab.id!==record.tabId)
          throw Error("Unknown submit report");
        record.status=message.clicked===true?"submit_clicked":"submit_failed";
        record.reportedAt=Date.now();
        try{await reportDispatch(record.dispatchId,message.clicked===true?"submitted":"needs_attention",
          record.tabId,message.clicked===true?"":"ChatGPT send button not clicked");}
        catch(e){record.dispatchReportError=String(e.message||e).slice(0,160)}
        if(x.lastLaunched?.tabId===record.tabId)
          await chrome.storage.local.set({lastLaunched:{...x.lastLaunched,status:record.status}});
        await chrome.storage.local.set({pendingHandoffs:pending});
        return {status:record.status};
      }
      case "pair":{
        if(typeof message.key!=="string"||message.key.length<45)throw Error("Invalid pairing code");
        const original=(await chrome.storage.local.get(["pairingKey"])).pairingKey;
        await chrome.storage.local.set({pairingKey:message.key.trim()});
        try{
          const data=await refresh();
          connectRealtime().catch(()=>{});
          return {connected:true,counts:data.counts};
        }catch(e){
          if(original)await chrome.storage.local.set({pairingKey:original});
          else await chrome.storage.local.remove("pairingKey");
          throw e;
        }
      }
      case "state":{
        const current=await refresh();
        const settings=await chrome.storage.local.get(["autoOpenChats","lastLaunched"]);
        const dispatch=(await api("/api/extension/dispatch/status")).queue;
        return {...current,dispatch,companion:{autoOpenChats:settings.autoOpenChats!==false,lastLaunched:settings.lastLaunched||null}};
      }
      case "setAutoOpen":{
        if(typeof message.enabled!=="boolean")throw Error("Invalid setting");
        await chrome.storage.local.set({autoOpenChats:message.enabled});
        return {enabled:message.enabled};
      }
      case "launch":return await openHandoff(message.kind,message.id,false);
      case "packet":{
        if(!["task","run"].includes(message.kind)||!Number.isInteger(message.id))throw Error("Invalid item");
        return await api("/api/extension/packet?kind="+encodeURIComponent(message.kind)+"&id="+message.id);
      }
      case "steeringList":{
        if(typeof message.chat!=="string")throw Error("Missing conversation URL");
        return await api("/api/extension/steering?chat="+encodeURIComponent(message.chat));
      }
      case "steeringAdd":{
        if(typeof message.chat!=="string"||typeof message.instruction!=="string")throw Error("Invalid instruction");
        return await api("/api/extension/steering/add","POST",{chat:message.chat,instruction:message.instruction});
      }
      case "steeringRemove":{
        if(typeof message.chat!=="string"||!Number.isInteger(message.id))throw Error("Invalid instruction");
        return await api("/api/extension/steering/remove","POST",{chat:message.chat,id:message.id});
      }
      case "steeringClear":{
        if(typeof message.chat!=="string")throw Error("Invalid conversation");
        return await api("/api/extension/steering/clear","POST",{chat:message.chat});
      }
      case "note":{
        if(!Number.isInteger(message.id)||typeof message.note!=="string")throw Error("Invalid note");
        return await api("/api/extension/note","POST",{task_id:message.id,note:message.note});
      }
      case "openTyrion":await chrome.tabs.create({url:API+"/#tasks"});return {ok:true};
      case "openChat":await chrome.tabs.create({url:CHAT_BASE});return {ok:true};
      case "unpair":{
        if(realtimeSocket)realtimeSocket.close();
        realtimeSocket=null;
        await chrome.storage.local.remove(["pairingKey","lastStatus"]);
        await chrome.action.setBadgeText({text:""});
        return {ok:true};
      }
      default:throw Error("Unsupported command");
    }
  })().then(result=>reply({ok:true,result}),e=>reply({ok:false,error:String(e.message||e)}));
  return true;
});
init().catch(()=>{});