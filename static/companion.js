"use strict";
const TyrionCompanion=(()=>{
 const desktopHost=/^(127\.0\.0\.1|localhost):17877$/.test(location.host);
 const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 async function privilegedGet(path){
   const r=await fetch(path,{cache:"no-store",headers:{"X-Tyrion-Session":token}});
   const value=await r.json();
   if(!r.ok)throw Error(value.error||"Device registry unavailable");
   return value;
 }
 async function refresh(){
   if(!desktopHost)return;
   const list=document.getElementById("companion-devices");
   if(!list)return;
   try{
     const [status,devices]=await Promise.all([privilegedGet("/api/companion/status"),privilegedGet("/api/companion/devices")]);
     document.getElementById("companion-device-count").textContent=status.connected_devices+" paired device"+(status.connected_devices===1?"":"s");
     list.innerHTML=devices.filter(d=>!d.revoked).length?
       devices.filter(d=>!d.revoked).map(d=>'<div class="companion-device"><div><strong>'+esc(d.label)+'</strong><div><span>Paired '+esc(new Date(d.created_at).toLocaleDateString())+' · Last verified '+esc(new Date(d.last_seen).toLocaleString())+'</span></div></div><button class="button-secondary" data-revoke-companion="'+esc(d.id)+'">Revoke</button></div>').join(""):
       '<p class="section-caption">No Android devices paired yet.</p>';
   }catch(error){list.textContent="Companion service unavailable: "+error.message;}
 }
 async function generate(){
   const button=document.getElementById("companion-new-code");
   if(!button)return;
   button.disabled=true;
   try{
     const response=await api("/api/companion/pair/start","POST",{});
     const data=response.result;
     const panel=document.getElementById("companion-code-panel");
     panel.hidden=false;
     panel.innerHTML='<div class="companion-code"><img alt="Scan to pair Tyrion Android Companion" src="'+data.qr_data_url+'"><div><span class="eyebrow">PAIRING CODE · 5 MINUTES</span><div class="companion-code-num">'+esc(data.code)+'</div><div class="companion-pair-note">Scan the QR code with your phone camera, or enter the code in the Android app.<p><b>PC relay:</b> '+esc(data.server)+'</p><p>Connect Tailscale on both devices first. Never expose this relay with Funnel.</p></div><button class="button-secondary" id="companion-copy-pair-code">Copy code</button></div></div>';
     panel.dataset.code=data.code;
   }catch(error){toast("Cannot generate pairing code: "+error.message);}
   finally{button.disabled=false;}
 }
 document.addEventListener("click",async event=>{
   if(event.target.closest("#companion-new-code"))return generate();
   if(event.target.closest("#companion-copy-pair-code")){
     const code=document.getElementById("companion-code-panel")?.dataset.code;
     if(code)try{await navigator.clipboard.writeText(code);toast("Pairing code copied")}catch{toast("Clipboard unavailable")}
     return;
   }
   const revoke=event.target.closest("[data-revoke-companion]");
   if(!revoke)return;
   if(!confirm("Revoke this phone's access to Tyrion? It will need to pair again."))return;
   try{await api("/api/companion/revoke","POST",{device_id:revoke.dataset.revokeCompanion});toast("Device access revoked");refresh()}
   catch(error){toast(error.message)}
 });

 // One queue shared by the PC dashboard, Android Companion and Chrome extension.
 async function refreshDispatch(){
   const panel=document.getElementById("dispatch-body");
   if(!panel)return;
   try{
     const [data,tasks]=await Promise.all([api("/api/dispatch/status"),api("/api/tasks")]);
     const groups=data.counts||{}, browser=data.browser||{};
     const counts=(key)=>Number(groups[key]||0);
     const statuses={queued:"Waiting for ChatGPT",claimed:"Starting Chrome",opened:"Chat opened",submitted:"Sent to ChatGPT",progressing:"Progress recorded",needs_attention:"Needs attention",completed:"Completed",cancelled:"Cancelled"};
     const active=data.queue||[];
     const cards=active.filter(item=>!["completed","cancelled"].includes(item.status));
     const done=active.filter(item=>["completed","cancelled"].includes(item.status)).slice(-8);
     const known=new Set(active.filter(d=>d.kind==="task").map(d=>d.entity_id));
     const unqueued=(tasks||[]).filter(t=>t.status==="open"&&!known.has(t.id)).slice(0,15);
     function view(item){
       const canCancel=["queued","needs_attention"].includes(item.status);
       const canRetry=["needs_attention","cancelled","opened","submitted","progressing"].includes(item.status)
          && item.task_status!=="done";
       const canRequest=item.kind==="task"&&item.status==="cancelled"&&item.task_status!=="done";
       const stale=["opened","submitted","progressing"].includes(item.status)
          && (Date.now()-Date.parse(item.updated_at||""))>600000;
       const disabled=item.task_status==="done";
       const note=stale?"No new status in 10+ minutes. Review Tyrion progress before resuming.":
          item.status==="queued"&&!browser.connected_recently?"Waiting for the PC Chrome extension to reconnect.":
          item.status==="submitted"?"ChatGPT has received the handoff; this does not yet prove task completion.":
          item.status==="progressing"?"A verified ChatGPT update is saved in the original task.":
          item.status==="needs_attention"?(item.last_error||"Review the ChatGPT tab and resume if needed."):"";
       return '<article class="dispatch-item"><div class="dispatch-item-heading"><div><strong>'+esc(item.title||("Run #"+item.entity_id))+'</strong><div class="dispatch-meta">'
          +esc(item.kind)+" #"+item.entity_id+(item.project?" · "+esc(item.project):"")+
          ' · attempt '+esc(item.attempt)+'</div></div><span class="dispatch-badge dispatch-'+esc(item.status)+'">'+esc(statuses[item.status]||item.status)+'</span></div>'+
          (note?'<p class="dispatch-note">'+esc(note)+'</p>':"")+
          '<div class="dispatch-actions"><button class="button-secondary" data-dispatch-view="'+esc(item.entity_id)+'" data-dispatch-kind="'+esc(item.kind)+'">View task</button>'+
          (canRetry&&!disabled?'<button class="button-primary" data-dispatch-action="retry" data-dispatch-id="'+item.entity_id+'" data-dispatch-kind="'+esc(item.kind)+'">Resume handoff</button>':"")+
          (canCancel&&!disabled?'<button class="button-secondary" data-dispatch-action="cancel" data-dispatch-id="'+item.entity_id+'" data-dispatch-kind="'+esc(item.kind)+'">Remove from queue</button>':"")+
          (canRequest&&!disabled?'<button class="button-primary" data-dispatch-action="retry" data-dispatch-id="'+item.entity_id+'" data-dispatch-kind="'+esc(item.kind)+'">Queue again</button>':"")+
          '</div></article>';
     }
     const pendingCount=counts("queued")+counts("claimed")+counts("opened")+counts("submitted")+counts("progressing")+counts("needs_attention");
     panel.innerHTML='<div class="dispatch-summary"><div class="dispatch-metric"><strong>'+pendingCount+'</strong><span>Active handoffs</span></div><div class="dispatch-metric"><strong>'+counts("queued")+'</strong><span>Waiting</span></div><div class="dispatch-metric"><strong>'+counts("needs_attention")+'</strong><span>Attention</span></div></div>'+
       '<div class="dispatch-browser '+(browser.connected_recently?"online":"offline")+'"><span class="dispatch-dot"></span><div><strong>PC browser '+(browser.connected_recently?"connected":"not recently connected")+'</strong><small>'+
       (browser.connected_recently?"ChatGPT requests are picked up from Tyrion's shared queue.":"Tasks remain safely queued until the Chrome extension returns.")+'</small></div><button class="button-secondary" id="dispatch-refresh">Refresh</button></div>'+
       '<div class="panel"><div class="panel-head"><h2>Current handoffs</h2><span class="muted">'+cards.length+' active</span></div><div class="dispatch-list">'+
       (cards.length?cards.map(view).join(""):'<div class="empty"><strong>Queue is clear</strong>New tasks created here or on PC will be picked up when Chrome is connected.</div>')+'</div></div>'+
       (unqueued.length?'<div class="panel"><div class="panel-head"><h2>Unqueued existing tasks</h2></div><div class="dispatch-list">'+unqueued.map(t=>'<div class="dispatch-item"><div class="dispatch-item-heading"><strong>'+esc(t.title)+'</strong><span class="dispatch-badge">Task #'+t.id+'</span></div><div class="dispatch-actions"><button class="button-primary" data-dispatch-action="queue" data-dispatch-id="'+t.id+'" data-dispatch-kind="task">Send to ChatGPT</button></div></div>').join("")+'</div></div>':"")+
       '<div class="panel"><div class="panel-head"><h2>Recent completed / cancelled</h2></div><div class="dispatch-list">'+
       (done.length?done.reverse().map(view).join(""):'<div class="empty">No completed handoffs recorded yet.</div>')+'</div></div>'+
       '<p class="section-caption">The PC is the single source of truth. A submitted handoff is not the same as completed work. Recovery is always initiated by you to avoid duplicate actions.</p>';
   }catch(error){panel.innerHTML='<div class="panel"><div class="empty"><strong>Dispatch unavailable</strong>'+esc(error.message)+'</div></div>';}
 }
 document.addEventListener("click",async event=>{
   if(event.target.closest("#dispatch-refresh"))return refreshDispatch();
   const view=event.target.closest("[data-dispatch-view]");
   if(view){
     const kind=view.dataset.dispatchKind;
     if(kind==="task"){navigate("tasks");const item=document.querySelector('[data-task-detail="'+view.dataset.dispatchView+'"]');if(item)item.click()}
     else navigate("scheduler");
     return;
   }
   const button=event.target.closest("[data-dispatch-action]");
   if(!button)return;
   const action=button.dataset.dispatchAction;
   const id=Number(button.dataset.dispatchId),kind=button.dataset.dispatchKind;
   if(action==="retry" && !confirm("Resume this original Tyrion item in a fresh ChatGPT conversation? Review existing work first; retrying can duplicate external actions."))return;
   if(action==="cancel" && !confirm("Remove this handoff from the queue? The original Tyrion task will remain unchanged."))return;
   button.disabled=true;
   try{
     await api("/api/dispatch/request","POST",{kind,id,action});
     toast(action==="cancel"?"Handoff cancelled; task retained":"Handoff queued in Tyrion without creating a duplicate task");
     refreshDispatch();
   }catch(error){toast(error.message);button.disabled=false;}
 });

 return {refresh,refreshDispatch};
})();
