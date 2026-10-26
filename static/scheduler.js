"use strict";
/* Scheduler UI lives separately from the core dashboard; no browser polling outside local Tyrion. */
const TyrionScheduler=(()=>{
 let snapshot=null;
 let editingId=null;
 const fmt=utc=>utc?new Date(utc).toLocaleString("en-PK",{timeZone:"Asia/Karachi",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:true}):"No next run";
 const typeName={chatgpt_handoff:"ChatGPT handoff",ollama_local:"Local Ollama"};
 const stateName={awaiting_chatgpt:"Awaiting ChatGPT",generating:"Generating",draft_ready:"Draft ready",needs_review:"Needs review",failed:"Failed",completed:"Reviewed"};
 function statusLabel(v){return stateName[v]||v;}
 function whenLine(s){return s.cadence==="daily"?"Every day":s.cadence==="weekly"?"Selected weekdays":"One time";}
 function page(){
  const d=snapshot||{schedules:[],runs:[],counts:{schedules:0,active:0,awaiting_chatgpt:0,drafts_ready:0}};
  return '<div class="schedule-overview">'+
    '<div class="stats-grid">'+
      stat("clock","Schedules",d.counts.schedules,"Owned by Tyrion, not ChatGPT")+
      stat("zap","Enabled",d.counts.active,"Runs on your Linux computer","green")+
      stat("list","ChatGPT queue",d.counts.awaiting_chatgpt,"Requires an active chat","red")+
      stat("book","Drafts ready",d.counts.drafts_ready,"Saved locally for review")+
    '</div>'+
    '<div class="dispatcher-status"><span class="dispatcher-icon">'+icon("link")+'</span><div class="row-body"><strong>ChatGPT queue dispatcher</strong><p>'+(d.dispatcher?.configured?'Configured · '+escapeHTML(d.dispatcher.cadence||"hourly")+' · Last verified callback: '+escapeHTML(d.dispatcher.last_callback?fmt(d.dispatcher.last_callback):"Not received yet"):'Not configured; queued jobs require active ChatGPT pickup')+'</p></div>'+statusPill(d.dispatcher?.last_callback?"Confirmed callback":d.dispatcher?.configured?"Awaiting test":"Manual handoff",d.dispatcher?.last_callback?"green":"gray")+'</div>'+
    '<div class="integration-note scheduler-heartbeat"><strong>ChatGPT dispatcher:</strong> '+
       (d.dispatcher?.last_callback_at?'Last verified callback: '+escapeHTML(d.dispatcher.last_callback_at)+', '+(d.dispatcher.last_processed||0)+' jobs submitted':'No successful dispatcher callback has been verified yet. The hourly ChatGPT task is configured, but local access during a future run is not proven.')+'</div>'+
    '<div class="connect-head"><div><h2>Scheduled workflows</h2><p>Daily, weekly and one-time workflows. Jobs persist across restarts.</p></div><button id="sched-new" class="button-primary">'+icon("plus")+' Create schedule</button></div>'+
    '<div class="schedule-list">'+(d.schedules.length?d.schedules.map(s=>
      '<section class="schedule-item">'+
      '<div class="schedule-head"><div><div class="schedule-title">'+escapeHTML(s.title)+'</div><div class="schedule-meta">'+escapeHTML(s.project)+' · '+escapeHTML(whenLine(s))+' at '+escapeHTML(s.time_local)+' PKT</div></div>'+
      statusPill(s.enabled?"Enabled":"Paused",s.enabled?"green":"gray")+'</div>'+
      '<div class="schedule-instructions">'+escapeHTML(s.instructions)+'</div>'+
      '<div class="schedule-foot"><span class="schedule-hint">'+icon("clock")+' Next: '+escapeHTML(fmt(s.next_run_utc))+' · '+escapeHTML(typeName[s.engine]||s.engine)+'</span>'+
      '<div class="schedule-buttons"><button class="button-secondary" data-sched-now="'+s.id+'">Run now</button><button class="button-secondary" data-sched-edit="'+s.id+'">Edit</button><button class="button-secondary" data-sched-toggle="'+s.id+'" data-value="'+(!s.enabled)+'">'+(s.enabled?"Pause":"Resume")+'</button><button class="button-secondary archive-button" data-sched-archive="'+s.id+'">Archive</button></div></div></section>').join(""):empty("No schedules yet","Add a recurring workflow to build a local task queue."))+'</div>'+
    '<div class="connect-head schedule-heading"><div><h2>Execution queue</h2><p>Due tasks stay visible until reviewed or completed.</p></div></div>'+
    '<div class="panel"><div class="row-list">'+(d.runs.length?d.runs.map(r=>
      '<div class="schedule-run"><div class="schedule-run-head"><strong>'+escapeHTML(r.schedule_title)+'</strong>'+statusPill(statusLabel(r.status),r.status==="draft_ready"?"green":r.status==="needs_review"?"red":"gray")+'</div>'+
      '<div class="schedule-meta">#'+r.id+' · Due '+escapeHTML(fmt(r.due_at_utc))+' · '+escapeHTML(r.project)+'</div>'+
      (r.summary?'<p class="schedule-run-summary">'+escapeHTML(r.summary)+'</p>':"")+
      '<div class="schedule-buttons">'+
      (r.status==="awaiting_chatgpt"?'<button class="button-primary" data-sched-copy="'+r.id+'">'+icon("copy")+' Copy ChatGPT handoff</button>':"")+
      (r.output_path?'<button class="button-secondary" data-sched-output="'+r.id+'">View draft</button>':"")+
      (["draft_ready","failed","needs_review"].includes(r.status)?'<button class="button-secondary" data-sched-complete="'+r.id+'">Mark reviewed</button>':"")+
      '</div></div>').join(""):empty("Queue is clear","The next scheduled occurrence will appear here when it becomes due."))+'</div></div>'+
    '<div class="integration-note schedule-explain"><strong>How ChatGPT works with Tyrion:</strong> Tyrion queues scheduled assignments independently. In an active chat, I can read the queued instructions through Local Files or an installed MCP connection and save a completed draft back into Tyrion. Tyrion cannot start a new ChatGPT conversation on its own. For unattended writing, use the optional local Ollama engine, then review the draft before publication.</div></div>';
 }
 function setData(result){
  snapshot=result;
  app.schedulerData=result;
  const counter=document.getElementById("scheduler-navcount");
  if(counter)counter.textContent=result.counts.awaiting_chatgpt||"";
 }
 async function refresh(){const val=await api("/api/workflows");setData(val);if(app.page==="scheduler")render();}
 function render(){document.getElementById("page-content").innerHTML=page();}
 async function copy(text){
  try{await navigator.clipboard.writeText(text);return true}catch(e){
   const t=document.createElement("textarea");t.value=text;t.style.position="fixed";t.style.opacity="0";document.body.appendChild(t);t.select();let ok=document.execCommand("copy");t.remove();return ok;
  }
 }
 function updateForm(){
  const cadence=document.getElementById("sched-cadence").value;
  document.getElementById("sched-weekdays-wrap").hidden=cadence!=="weekly";
  document.getElementById("sched-once-wrap").hidden=cadence!=="once";
  const engine=document.getElementById("sched-engine").value;
  document.getElementById("sched-model-wrap").hidden=engine!=="ollama_local";
 }
 async function openCreate(editId=null){
  editingId=editId;
  const existing=editingId?snapshot?.schedules.find(s=>s.id===editingId):null;
  const form=document.getElementById("schedule-form");form.reset();
  const sel=document.getElementById("sched-project");
  sel.innerHTML=(app.overview?.projects||[]).map(p=>'<option value="'+escapeHTML(p.name)+'">'+escapeHTML(p.name)+'</option>').join("");
  document.getElementById("sched-once-date").min=new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Karachi",year:"numeric",month:"2-digit",day:"2-digit"});
  document.getElementById("sched-submit").textContent=existing?"Save changes":"Create schedule";
  if(existing){
   const mapping={"sched-title":existing.title,"sched-project":existing.project,"sched-kind":existing.kind,
     "sched-instructions":existing.instructions,"sched-cadence":existing.cadence,
     "sched-time":existing.time_local,"sched-engine":existing.engine,
     "sched-model":existing.model||"qwen3.5:4b","sched-once-date":existing.once_date||""};
   for(const [id,value] of Object.entries(mapping))document.getElementById(id).value=value;
   for(const check of document.querySelectorAll('#sched-weekdays-wrap input'))check.checked=existing.weekdays.includes(Number(check.value));
  }
  updateForm();document.getElementById("schedule-dialog").showModal();document.getElementById("sched-title").focus();
 }
 async function handleClick(event){
  const el=event.target.closest("[data-sched-now],[data-sched-edit],[data-sched-archive],[data-sched-toggle],[data-sched-copy],[data-sched-output],[data-sched-complete],#sched-new");
  if(!el)return;
  if(el.id==="sched-new"){openCreate();return}
  if(el.dataset.schedEdit){openCreate(Number(el.dataset.schedEdit));return}
  if(el.dataset.schedArchive){if(!window.confirm("Archive this schedule? Pending ChatGPT requests will be cancelled; past drafts and history are preserved."))return;
    try{el.disabled=true;await api("/api/workflows/schedules/"+el.dataset.schedArchive+"/archive","POST",{});await refresh();toast("Schedule archived")}catch(error){toast(error.message)}finally{el.disabled=false}return}
  try{
   el.disabled=true;
   if(el.dataset.schedNow){
    const v=await api("/api/workflows/schedules/"+el.dataset.schedNow+"/run-now","POST",{});
    toast("Run #"+v.result.id+" queued");
   }else if(el.dataset.schedToggle){
    await api("/api/workflows/schedules/"+el.dataset.schedToggle+"/enabled","POST",{enabled:el.dataset.value==="true"});
    toast("Schedule updated");
   }else if(el.dataset.schedCopy){
    const id=Number(el.dataset.schedCopy);
    const matching=snapshot?.schedules?.find(s=>snapshot.runs.some(r=>r.id===id&&r.schedule_id===s.id));
    const text="Tyrion – The Hand has a scheduled task ready, run #"+id+". Please use the connected Local Files tool or Tyrion MCP bridge to call tyrion_due_chatgpt_work (or run python3 -m tyrion.bridge due-work in ~/Documents/Tyrion-The-Hand), carry out the provided instructions, check existing content and factual claims, then save the completed Markdown draft with tyrion_submit_blog_draft. Do not auto-publish. The workflow is "+(matching?.title||"scheduled task")+".";
    if(await copy(text))toast("Handoff copied — paste it into a ChatGPT conversation");
    else toast("Clipboard unavailable");
   }else if(el.dataset.schedOutput){
    const id=el.dataset.schedOutput;const dialog=document.getElementById("output-dialog");
    document.getElementById("output-title").textContent="Draft · #"+id;
    document.getElementById("output-text").textContent="Opening local draft…";dialog.showModal();
    try{const r=await api("/api/workflows/runs/"+id+"/output");document.getElementById("output-text").textContent=r.markdown}catch(e){document.getElementById("output-text").textContent="Unable to open draft: "+e.message}
   }else if(el.dataset.schedComplete){
    await api("/api/workflows/runs/"+el.dataset.schedComplete+"/complete","POST",{});
    toast("Run marked reviewed — no post was published");
   }
   if(!el.dataset.schedOutput && !el.dataset.schedCopy)await refresh();
  }catch(e){toast(e.message)}finally{el.disabled=false}
 }
 function init(){
  document.addEventListener("click",handleClick);
  document.getElementById("close-schedule").addEventListener("click",()=>document.getElementById("schedule-dialog").close());
  document.getElementById("cancel-schedule").addEventListener("click",()=>document.getElementById("schedule-dialog").close());
  document.getElementById("close-output").addEventListener("click",()=>document.getElementById("output-dialog").close());
  document.getElementById("sched-cadence").addEventListener("change",updateForm);
  document.getElementById("sched-engine").addEventListener("change",updateForm);
  document.getElementById("schedule-form").addEventListener("submit",async e=>{
   e.preventDefault();const cadence=document.getElementById("sched-cadence").value,engine=document.getElementById("sched-engine").value;
   const body={
    title:document.getElementById("sched-title").value,
    project:document.getElementById("sched-project").value,
    kind:document.getElementById("sched-kind").value,
    instructions:document.getElementById("sched-instructions").value,
    cadence,time_local:document.getElementById("sched-time").value,
    timezone:"Asia/Karachi",
    weekdays:cadence==="weekly"?[...document.querySelectorAll('#sched-weekdays-wrap input:checked')].map(x=>Number(x.value)):[],
    once_date:cadence==="once"?document.getElementById("sched-once-date").value:null,
    engine,model:engine==="ollama_local"?document.getElementById("sched-model").value:""
   };
   try{await api(editingId?"/api/workflows/schedules/"+editingId+"/edit":"/api/workflows/schedules","POST",body);document.getElementById("schedule-dialog").close();e.target.reset();updateForm();await refresh();toast(editingId?"Schedule updated":"Independent schedule created");editingId=null}catch(error){toast(error.message)}
  });
  refresh().catch(e=>toast("Scheduler is unavailable: "+e.message));
  setInterval(()=>{if(app.page==="scheduler")refresh().catch(()=>{})},60000);
 }
 return {page,refresh,init,setData,openCreate};
})();
TyrionScheduler.init();
