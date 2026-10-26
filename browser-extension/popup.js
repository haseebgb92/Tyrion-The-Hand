"use strict";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let data=null,filter="tasks",refreshing=false,activeTaskId=null,streamCursor=null;
const streamController=new AbortController();
function toast(m){const el=$("toast");el.textContent=m;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2800)}
async function send(type,more={}){
 return await new Promise((resolve,reject)=>{
   chrome.runtime.sendMessage({type,...more},r=>{
     if(chrome.runtime.lastError)return reject(Error(chrome.runtime.lastError.message));
     if(!r?.ok)return reject(Error(r?.error||"Extension request failed"));
     resolve(r.result);
   });
 });
}
function render(){
 $("connection").textContent="Tyrion local bridge connected";$("connection").classList.add("ok");
 $("workspace").hidden=false;$("pairing").hidden=true;$("errorPanel").hidden=true;
 $("tasksCount").textContent=data.counts.open_tasks;
 $("dueCount").textContent=data.counts.due_handoffs;
 $("draftsCount").textContent=data.counts.drafts_ready;
 $("autoOpenChats").checked=data.companion?.autoOpenChats!==false;
 const last=data.companion?.lastLaunched;
 $("lastLaunched").hidden=!last;
 if(last){
   const state=last.status==="submit_clicked"?"The send button was clicked; check the chat for progress.":
     last.status==="submit_failed"?"Automatic submission failed. Open the tab and submit manually.":
     "Opening ChatGPT and preparing the one-shot handoff.";
   $("lastLaunched").textContent=(last.automatic?"Auto-started ":"Opened ")+
     (last.kind==="task"?"task #":"schedule run #")+last.id+". "+state;
 }
 const items=filter==="tasks"?data.tasks:data.runs;
 $("items").innerHTML=items.length?items.map(x=>{
   const task=filter==="tasks",id=x.id,title=task?x.title:x.schedule_title,
      project=x.project||"General",status=x.status,detail=task?x.instructions:(x.summary||""),
      when=task?x.updated_at:x.due_at_utc,updates=task?(x.updates?.[0]?.note||""):"";
   return `<article class="item"><div class="item-head"><div><h3>${esc(title)}</h3><div class="meta">#${id} · ${esc(project)} · ${esc(when?.slice(0,16)||"")}</div></div><span class="pill ${status==="draft_ready"?"ready":""}">${esc(status)}</span></div><p>${esc(detail?detail.slice(0,155):(updates?updates.slice(0,155):"No detailed task instructions yet."))}</p><div class="item-actions"><button class="action primary" data-command="handoff" data-kind="${task?"task":"run"}" data-id="${id}">Copy handoff</button><button class="action" data-command="open" data-kind="${task?"task":"run"}" data-id="${id}">Open chat</button>${task?'<button class="action" data-command="note" data-id="'+id+'">Add note</button>':""}</div></article>`;
 }).join(""):'<div class="item"><strong>Queue is clear</strong><p>Tyrion will keep watching locally for new work.</p></div>';
 $("lastCheck").textContent="Updated "+new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
}
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{data=await send("state");if(streamCursor===null)streamCursor=data.latest_event_id||0;render()}
 catch(e){
   if(e.message.includes("PAIR_REQUIRED")||e.message.includes("paired")){
     $("workspace").hidden=true;$("pairing").hidden=false;$("errorPanel").hidden=true;
     $("connection").textContent="Pairing needed";$("connection").classList.remove("ok");
   }else{$("errorPanel").hidden=false;$("errorMessage").textContent=e.message;$("workspace").hidden=true;$("connection").textContent="Tyrion unavailable"}
 }finally{refreshing=false}
}
$("pairForm").addEventListener("submit",async e=>{
 e.preventDefault();try{await send("pair",{key:$("pairKey").value.trim()});$("pairKey").value="";toast("This browser is now paired");await refresh()}
 catch(err){toast(err.message)}
});
$("refresh").addEventListener("click",refresh);
$("autoOpenChats").addEventListener("change",async e=>{
 try{const value=await send("setAutoOpen",{enabled:e.target.checked});toast(value.enabled?"Automatic chat opening enabled":"Automatic chat opening paused")}
 catch(error){toast(error.message);e.target.checked=!e.target.checked}
});
$("tryAgain").addEventListener("click",refresh);
$("openTyrion").addEventListener("click",()=>send("openTyrion").catch(e=>toast(e.message)));
$("openSidePanel").addEventListener("click",async()=>{
 try{await chrome.sidePanel.open({windowId:chrome.windows.WINDOW_ID_CURRENT});window.close()}
 catch(e){toast("Chrome side panel unavailable: "+e.message)}
});
$("unpair").addEventListener("click",async()=>{if(!confirm("Disconnect this browser from Tyrion?"))return;await send("unpair");await refresh()});
document.querySelectorAll(".tab").forEach(el=>el.addEventListener("click",()=>{
 filter=el.dataset.filter;document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x===el));if(data)render();
}));
$("items").addEventListener("click",async e=>{
 const button=e.target.closest("[data-command]");if(!button)return;
 const id=Number(button.dataset.id),kind=button.dataset.kind;
 try{
   if(button.dataset.command==="note"){
     activeTaskId=id;$("noteText").value="";
     $("noteTitle").textContent="Progress for task #"+id;
     $("noteDialog").showModal();return;
   }
   const packet=await send("packet",{id,kind});
   if(button.dataset.command==="open"){
     await send("launch",{id,kind});
     toast("ChatGPT handoff opened; automatic send will run if enabled.");
   } else {
     await navigator.clipboard.writeText(packet.text);
     toast("Handoff copied — paste into ChatGPT to resume safely");
   }
 }catch(error){toast(error.message)}
});
$("cancelNote").addEventListener("click",()=>$("noteDialog").close());
$("noteForm").addEventListener("submit",async e=>{
 e.preventDefault();
 try{
  await send("note",{id:activeTaskId,note:$("noteText").value.trim()});
  $("noteDialog").close();toast("Progress saved in Tyrion");await refresh();
 }catch(e){toast(e.message)}
});
// Live changes are read from Tyrion, never from the ChatGPT interface.
// The side panel remains open; a closed popup does not need background scraping.
async function stream(){
 while(!streamController.signal.aborted){
  try{
   if(streamCursor===null){await new Promise(r=>setTimeout(r,250));continue}
   const response=await fetch("http://127.0.0.1:17877/api/realtime/stream?after="+streamCursor,
      {signal:streamController.signal,cache:"no-store"});
   if(!response.ok)throw Error("Tyrion local events unavailable");
   const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
   while(!streamController.signal.aborted){
    const next=await reader.read();if(next.done)break;
    buffer+=decoder.decode(next.value,{stream:true});
    let position;
    while((position=buffer.indexOf("\n\n"))>=0){
     const frame=buffer.slice(0,position);buffer=buffer.slice(position+2);
     if(frame.includes("event: tyrion-change")){
       const match=frame.match(/(?:^|\n)id:\s*(\d+)/);
       if(match)streamCursor=Math.max(streamCursor,Number(match[1]));
       await refresh();
     }
    }
   }
  }catch(error){if(streamController.signal.aborted)break}
  await new Promise(resolve=>setTimeout(resolve,750));
 }
}
window.addEventListener("pagehide",()=>streamController.abort());
refresh();stream();steeringRefresh();
setInterval(()=>{if(!document.hidden)refresh()},15000);
/* Instruction inbox is scoped to an existing ChatGPT conversation URL.
   We never inspect the page DOM or submit messages into a running chat. */
let steeringChat=null, steeringItems=[], steeringBusy=false;
async function detectChat(){
  const tabs=await chrome.tabs.query({active:true,lastFocusedWindow:true});
  const url=tabs[0]?.url;
  if(!url)return null;
  try{
    const u=new URL(url);
    if(u.origin!=="https://chatgpt.com" || !/^\/(?:g\/[^/]+\/)?c\/[A-Za-z0-9-]{8,}\/?$/.test(u.pathname))return null;
    return u.origin+u.pathname.replace(/\/$/,"");
  }catch{return null}
}
function showSteering(){
  $("steerCount").textContent=steeringItems.length+" queued";
  $("steerContext").textContent=steeringChat
    ?"Attached to this ChatGPT conversation"
    :"Open a saved ChatGPT conversation to queue instructions";
  $("steerText").disabled=!steeringChat;
  $("steerAdd").disabled=!steeringChat;
  $("steerCopy").disabled=!steeringChat||!steeringItems.length;
  $("steerClear").disabled=!steeringChat||!steeringItems.length;
  $("steerList").innerHTML=steeringItems.length
    ?steeringItems.map((item,index)=>`<div class="steer-entry"><div class="date">#${index+1}</div><p>${esc(item.instruction)}</p><button class="remove" type="button" aria-label="Remove queued instruction" data-steer-remove="${item.id}" title="Remove this instruction">×</button></div>`).join("")
    :'<div class="steer-empty">No updates queued for this conversation.</div>';
}
async function steeringRefresh(){
  if(steeringBusy)return;
  steeringBusy=true;
  try{
    const nextChat=await detectChat();
    if(!nextChat){steeringChat=null;steeringItems=[];showSteering();return}
    const result=await send("steeringList",{chat:nextChat});
    steeringChat=nextChat;steeringItems=result.pending||[];
    showSteering();
  }catch(e){
    $("steerContext").textContent="Instruction queue unavailable: "+e.message;
  }finally{steeringBusy=false}
}
$("steerForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const instruction=$("steerText").value.trim();
  if(!instruction)return;
  try{
    const active=await detectChat();
    if(!active || active!==steeringChat)throw Error("Active conversation changed. Refresh the queue first.");
    $("steerAdd").disabled=true;
    await send("steeringAdd",{chat:active,instruction});
    $("steerText").value="";
    toast("Instruction queued locally — no interruption");
    await steeringRefresh();
  }catch(error){toast(error.message);await steeringRefresh()}
  finally{$("steerAdd").disabled=false;showSteering()}
});
$("steerList").addEventListener("click",async e=>{
  const btn=e.target.closest("[data-steer-remove]");if(!btn||!steeringChat)return;
  try{
    const current=await detectChat();
    if(current!==steeringChat)throw Error("Conversation changed");
    await send("steeringRemove",{chat:current,id:Number(btn.dataset.steerRemove)});
    toast("Instruction removed");await steeringRefresh();
  }catch(error){toast(error.message)}
});
$("steerCopy").addEventListener("click",async()=>{
  try{
    if(!steeringItems.length||!steeringChat)throw Error("Queue is empty");
    const current=await detectChat();if(current!==steeringChat)throw Error("Conversation changed");
    const message="Additional updates to my ongoing request, in order. Keep the original task and apply these unless superseded:\n"+
      steeringItems.map((v,i)=>(i+1)+". "+v.instruction).join("\n");
    await navigator.clipboard.writeText(message);
    toast("Updates copied. Paste into ChatGPT when ready.");
  }catch(error){toast(error.message)}
});
$("steerClear").addEventListener("click",async()=>{
  if(!steeringChat||!steeringItems.length)return;
  if(!confirm("Clear all queued instructions for this conversation? This does not send them to ChatGPT."))return;
  try{
    const current=await detectChat();if(current!==steeringChat)throw Error("Conversation changed");
    await send("steeringClear",{chat:current});
    toast("Queue cleared");await steeringRefresh();
  }catch(error){toast(error.message)}
});
chrome.tabs.onActivated.addListener(()=>steeringRefresh().catch(()=>{}));
chrome.tabs.onUpdated.addListener((tabId,change)=>{if(change.url)steeringRefresh().catch(()=>{})});
window.addEventListener("focus",()=>steeringRefresh().catch(()=>{}));
