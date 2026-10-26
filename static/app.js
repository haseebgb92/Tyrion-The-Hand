"use strict";
const token=document.querySelector('meta[name="tyrion-session"]').content;
const app={page:"dashboard",overview:null,skills:[],query:""};
const icons={
layout:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
layers:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M8 4v5"/>',
list:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m7 9 2 2 3-3M14 9h4m-4 5h4m-11 0h3"/>',
zap:'<path d="m13 2-9 11h7l-1 9 10-12h-7l0-8Z"/>',
link:'<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2"/>',
book:'<path d="M12 7c-3-3-7-3-10-2v14c3-1 7-1 10 2 3-3 7-3 10-2V5c-3-1-7-1-10 2Z"/><path d="M12 7v14"/>',
fingerprint:'<path d="M3 12a9 9 0 0 1 18 0M7 12a5 5 0 0 1 10 0M12 11v3M8 16c.8 2.4 1.8 4 3 5m5-5c-.5 2.4-1.4 4.1-2.5 5M4 16c.2 1.1.6 2.2 1.2 3.1M19 16c-.3 1.5-.8 2.6-1.5 3.7"/>',
shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
refresh:'<path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7"/>',
plus:'<path d="M12 4v16M4 12h16"/>',
copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
spark:'<path d="m12 2 2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4L12 2Z"/>',
clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>',
check:'<path d="m4 12 5 5 11-11"/>',
alert:'<path d="M12 3 2 21h20L12 3Zm0 7v4m0 3h.01"/>'
};
function icon(k){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(icons[k]||icons.info)+'</svg>'}
for(const el of document.querySelectorAll('[data-icon]'))el.innerHTML=icon(el.dataset.icon);
const escapeHTML=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(path,method="GET",body=null){
 const opt={method,headers:{}};
 if(method!=="GET"){opt.headers["Content-Type"]="application/json";opt.headers["X-Tyrion-Session"]=token;opt.body=JSON.stringify(body)}
 const res=await fetch(path,opt);const data=await res.json();if(!res.ok)throw Error(data.error||"Request failed");return data;
}
let toastTimer;function toast(msg){const el=document.getElementById("toast");el.textContent=msg;el.classList.add("visible");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("visible"),3200)}
const panel=(name,content,right="")=>'<article class="panel"><div class="panel-head"><h2>'+escapeHTML(name)+'</h2>'+right+'</div>'+content+'</article>';
const linkBtn=(name,page)=>'<button class="subtle-button" data-linkpage="'+page+'">'+escapeHTML(name)+' '+icon("arrow")+'</button>';
const statusPill=(label,type="gray")=>'<span class="pill '+type+'">'+escapeHTML(label)+'</span>';
const empty=(name,detail)=>'<div class="empty"><strong>'+escapeHTML(name)+'</strong>'+escapeHTML(detail)+'</div>';
const dateFmt=t=>{try{return new Date(t).toLocaleDateString(undefined,{month:"short",day:"numeric"})}catch{return t}};
function stat(iconName,label,value,detail,tone=""){return '<div class="stat"><div class="stat-icon '+tone+'">'+icon(iconName)+'</div><div><div class="stat-label">'+label+'</div><div class="stat-value">'+value+'</div><div class="stat-detail">'+detail+'</div></div></div>'}
function projectRow(p){return '<div class="list-row"><span class="project-icon">'+escapeHTML(p.name.slice(0,1))+'</span><div class="row-body"><div class="row-title">'+escapeHTML(p.name)+'</div><div class="row-desc">'+escapeHTML(p.category)+'</div></div>'+statusPill((p.connectors||[]).some(c=>c.status==="connected")?"Local live":(p.connectors||[]).some(c=>c.status==="relay_connected")?"ChatGPT relay":(p.connectors||[]).some(c=>c.status==="inventory_only")?"Inventory only":"Needs link",(p.connectors||[]).some(c=>c.status==="connected")?"green":"gray")+'</div>'}
function taskRow(t){let status='<select class="task-status-select" data-taskstatus="'+t.id+'" aria-label="Status of '+escapeHTML(t.title)+'">'+["open","awaiting_approval","done"].map(v=>'<option value="'+v+'" '+(v===t.status?"selected":"")+'>'+({open:"Open",awaiting_approval:"Await approval",done:"Completed"}[v])+'</option>').join("")+'</select>';
return '<div class="task-item"><span class="task-marker '+escapeHTML(t.priority)+'"></span><div class="row-body"><div class="row-title '+(t.status==="done"?"task-line-through":"")+'">'+escapeHTML(t.title)+'</div><div class="row-desc">'+escapeHTML(t.project||"General")+' · '+escapeHTML(t.priority)+' priority · '+dateFmt(t.created_at)+'</div></div><div class="task-right"><button class="subtle-button" title="See task updates shared with ChatGPT" data-task-detail="'+t.id+'">Updates</button><button class="subtle-button" title="Recommend skills for this task" data-route-task="'+escapeHTML(t.title)+'">Skills</button>'+status+'</div></div>'}
function connectionsView(conns){return '<div class="connection-grid">'+conns.map(c=>'<div class="connection-card"><span class="connection-badge">'+icon(c.kind.includes("MCP")?"link":c.kind.includes("library")?"book":"database")+'</span><div class="row-body"><strong>'+escapeHTML(c.name)+'</strong><small>'+escapeHTML(c.kind)+'</small></div>'+statusPill(c.status==="ready"?"Ready":c.status==="connected"?"Live":c.status==="external"?"Via ChatGPT":c.status==="relay_connected"?"ChatGPT relay":c.status==="inventory_only"?"Inventory":c.status==="needs_authorization"?"Needs auth":c.status==="subscription_required"?"Paid connector blocked":c.status==="not_checked"?"Not checked":"Not connected",["ready","connected"].includes(c.status)?"green":["external","relay_connected"].includes(c.status)?"gray":"")+'</div>').join("")+'</div>'}
function activities(items){return '<div class="row-list">'+(items.length?items.map(a=>'<div class="activity-row"><span class="activity-icon">'+icon(a.kind==="task"?"check":a.kind==="error"?"alert":"clock")+'</span><span class="row-body">'+escapeHTML(a.summary)+'</span><span class="when">'+dateFmt(a.created_at)+'</span></div>').join(""):empty("No activity yet","Actions you perform in Tyrion will be recorded here."))+'</div>'}
const pageTitles={knowledge:["Knowledge engine","Private semantic search across Tyrion records and Advertpreneur skills."],dispatch:["ChatGPT dispatch","Live PC-owned handoff queue, task progress and operator-controlled recovery."],scheduler:["Independent scheduler","Tyrion owns recurring jobs, timed handoffs and locally generated drafts."],approvals:["Approvals & delegation","Keep consequential actions under your control. Tyrion never publishes automatically."],dashboard:["Your command center","One quiet place for projects, skills and the work that matters."],projects:["All projects","Live project summaries will appear as integrations are connected."],tasks:["Task ledger","Capture, prioritize and verify everything Tyrion is asked to do."],automations:["Automation control","Local recurring housekeeping, independently of ChatGPT."],connections:["Your connections","The systems Tyrion can reach, and what still needs configuration."],skills:["Skill library","Browse the instructions already installed in your Advertpreneur toolkit."],identity:["Working identity","The editable principles that guide Tyrion's behavior and permissions."]};
function dashboard(o){return '<div class="stats-grid">'+stat("layers","Tracked projects",o.counts.projects,"Project health pending verification")+stat("list","Open tasks",o.counts.open_tasks,"From the local task ledger","red")+stat("book","Available skills",o.counts.skills,"From installed skill catalog")+stat("link","Local capabilities",o.counts.connected,"Confirmed on this machine","green")+'</div><div class="dashboard-columns"><div>'+
panel("Project overview",'<div class="row-list">'+o.projects.slice(0,6).map(projectRow).join("")+'</div>',linkBtn("View all","projects"))+
panel("Recent activity",activities(o.activity),linkBtn("All tasks","tasks"))+'</div><div>'+
panel("Attention queue",'<div class="row-list">'+(o.tasks.filter(t=>t.status!=="done").length?o.tasks.filter(t=>t.status!=="done").slice(0,5).map(taskRow).join(""):empty("Nothing in the queue","Add a task to give Tyrion something meaningful to track."))+'</div>',linkBtn("View all","tasks"))+
panel("Connected systems",connectionsView(o.connections.filter(c=>["connected","ready"].includes(c.status)).slice(0,4)),linkBtn("Manage","connections"))+'</div></div>'}
function OLD_projects(o){return '<p class="section-caption">Projects are known by name only. No fabricated progress scores or live-status claims until their connections are verified.</p><div class="section-grid">'+o.projects.map(p=>'<div class="card"><div class="card-top"><span class="project-icon">'+escapeHTML(p.name[0])+'</span>'+statusPill("Needs sync")+'</div><h3 style="margin-top:14px">'+escapeHTML(p.name)+'</h3><p>'+escapeHTML(p.category)+'</p><div class="meta">Tracking initialized · '+dateFmt(p.updated_at)+'</div></div>').join("")+'</div>'}
function tasks(o){return '<div class="panel">'+'<div class="panel-head"><h2>All tasks</h2>'+statusPill(o.tasks.length+" recorded","gray")+'</div><div class="row-list">'+(o.tasks.length?o.tasks.map(taskRow).join(""):empty("An empty slate","Create your first task to start Tyrion's operational history."))+'</div></div><p class="section-caption">“Completed” is a manual verification state; no external work has been automatically executed.</p>'}
function autos(o){return '<div class="panel"><div class="panel-head"><h2>Local background jobs</h2>'+statusPill("No paid API","green")+'</div>'+o.jobs.map(j=>'<div class="job-row"><div><strong>'+escapeHTML(j.label)+'</strong><small>'+escapeHTML(j.schedule)+' · '+(j.last_run?"Last run "+dateFmt(j.last_run):"Not run yet")+' · '+escapeHTML(j.status)+'</small></div><button class="switch '+(j.enabled?"enabled":"")+'" data-job="'+escapeHTML(j.id)+'" data-enabled="'+(j.enabled?"0":"1")+'" role="switch" aria-label="Toggle '+escapeHTML(j.label)+'" aria-checked="'+Boolean(j.enabled)+'"><span></span></button></div>').join("")+'</div><div class="integration-note">Local jobs refresh connection health, inspect the skill catalog and write a daily local brief. Posting and publishing are never triggered by the scheduler.</div>'}
function connections(o){
 const reports=o.integrations?.integrations||[];
 const cloud=o.external_relay?.services||[];
 const wordPress=o.chatgpt_relay?.services||[];
 const statusText={connected:["Live verified","green"],inventory_only:["Local inventory","gray"],
   needs_authorization:["Approval required","red"],unavailable:["Unavailable","red"],
   relay_connected:["ChatGPT-side relay","gray"],relay_unavailable:["Relay unavailable","red"]};
 const health=reports.map(r=>{
   const [label,tone]=statusText[r.status]||[r.status,"gray"];
   return '<article class="card"><div class="card-top"><h3>'+escapeHTML(r.name)+'</h3>'+statusPill(label,tone)+'</div>'+
   '<p>Checked '+escapeHTML(r.checked_at||"Never")+'</p>'+Object.entries(r.metrics||{}).map(([k,v])=>'<div class="integration-metric"><strong>'+escapeHTML(k.replaceAll("_"," "))+'</strong><span>'+escapeHTML(typeof v==="object"?Object.entries(v).map(([a,b])=>a+": "+b).join(" · "):String(v))+'</span></div>').join("")+
   '<div class="meta">'+escapeHTML(r.detail)+'</div></article>';
 }).join("");
 const relays=[...cloud,...wordPress].map(r=>{
   const when=r.checked_at?Date.parse(r.checked_at):0;
   const stale=!when||Date.now()-when>24*60*60*1000;
   const sites=(r.sites||[]).map(x=>'<div class="integration-metric"><strong>'+escapeHTML(x.host)+'</strong><span>'+escapeHTML(x.ok?"Verified":"Unverified")+'</span></div>').join("");
   return '<article class="card"><div class="card-top"><h3>'+escapeHTML(r.name)+'</h3>'+statusPill(stale?"Snapshot older than 24h":r.status==="relay_connected"?"Relay verified":"Needs attention",!stale&&r.status==="relay_connected"?"green":"gray")+'</div><p>ChatGPT connector snapshot · '+escapeHTML(r.checked_at||"Not checked")+'</p>'+sites+
   Object.entries(r.metrics||{}).map(([k,v])=>'<div class="integration-metric"><strong>'+escapeHTML(k.replaceAll("_"," "))+'</strong><span>'+escapeHTML(String(v))+'</span></div>').join("")+
   '<div class="meta">'+escapeHTML(r.detail)+'</div></article>';
 }).join("");
 return '<div class="connect-head"><div><h2>Verified local integrations</h2><p>Real read-only health checks and inventory snapshots from installed services.</p></div><button class="button-primary" id="sync-integrations">'+icon("refresh")+' Check connections</button></div><div class="section-grid">'+health+'</div>'+
   '<div class="connect-head"><div><h2>Connected through ChatGPT</h2><p>Snapshots are refreshed when ChatGPT checks those external accounts; Tyrion holds no OAuth credentials.</p></div></div><div class="section-grid">'+(relays||empty("No ChatGPT relays","Check supported connectors from an active conversation."))+'</div>'+
   '<div class="panel" id="companion-pair-panel"><div class="panel-head"><h2>Tyrion – The Companion (Android)</h2>'+statusPill("Private tailnet","green")+'</div><div class="companion-pair-body"><p class="section-caption">Same Tyrion projects, tasks, schedules and reviews on Android. Private PC relay over Tailscale. Pair once by QR or 8-digit code.</p><p class="section-caption">Android APK: <a href="https://haseeb-optiplex-3050.tailb87e57.ts.net:8443/download/Tyrion-The-Companion-v1.0.apk" target="_blank" rel="noopener noreferrer">Download via private Tailscale</a> · Or install from PC Downloads / Tyrion-The-Companion-v1.0-debug.apk</p><div class="companion-actions"><button class="button-primary" id="companion-new-code">'+icon("smartphone")+' Pair Android phone</button><span id="companion-device-count" class="muted">Checking paired devices…</span></div><div id="companion-code-panel" hidden></div><div class="divider-label">PAIRED DEVICES</div><div id="companion-devices">Loading devices…</div></div></div>'+
   '<div class="panel" id="browser-extension-panel"><div class="panel-head"><h2>Tyrion Browser Companion</h2>'+statusPill("Local-first","green")+'</div><p class="section-caption">See tasks and due schedules in Chrome, copy a fresh recovery handoff into ChatGPT, and track work without duplicate entries. No automated ChatGPT clicks or conversation scraping.</p><div class="row" style="display:flex;gap:9px;flex-wrap:wrap;padding:0 0 9px"><button id="copy-browser-pairing" class="button-primary">'+icon("copy")+' Copy pairing code</button><button id="browser-extension-guide" class="button-secondary">Setup instructions</button></div><p class="section-caption">Extension location: ~/Documents/Tyrion-The-Hand/browser-extension</p></div>'+panel("Full connection directory",connectionsView(o.connections))+
   '<div class="integration-note"><strong>Permission boundaries:</strong> Local live means a successful localhost API/MCP call; inventory-only means a readable local index, not backend control; ChatGPT relay requires ChatGPT connectivity. The GBP local server is running, but Google API approval still blocks full management. ChatGPT Work Events require a verified MCP subscription; local desktop notifications do not activate ChatGPT. ShieldPress live actions, client Shopify stores and additional WordPress sites require separate authorized adapters.</div>';
}
function approvalsPage(o){const approvals=o.approvals||[];return '<div class="connect-head"><div><h2>Action proposals</h2><p>External changes require explicit approval. ChatGPT can propose drafts, but cannot approve them by MCP.</p></div><button class="button-primary" id="propose-draft">'+icon("plus")+' Propose Meta draft</button></div><div class="panel"><div class="panel-head"><h2>Approval queue</h2>'+statusPill(approvals.filter(x=>x.status==="pending").length+" pending")+'</div><div class="row-list">'+(approvals.length?approvals.map(a=>'<div class="approval-card"><div class="approval-top"><span>'+statusPill(a.status,a.status==="executed"?"green":a.status==="needs_review"?"red":"gray")+'</span><span class="muted">#'+a.id+' · '+dateFmt(a.created_at)+'</span></div><strong>'+escapeHTML(a.title)+'</strong><p>Meta Manager · '+escapeHTML(a.preview.platform||"")+' · '+escapeHTML(a.preview.caption||"No caption entered")+'</p>'+ (a.status==="pending"?'<div class="approval-buttons"><button class="button-secondary" data-approval-id="'+a.id+'" data-decision="reject">Reject</button><button class="button-primary" data-approval-id="'+a.id+'" data-decision="approve">Approve & create draft</button></div>':'<div class="meta">'+escapeHTML(a.result_summary||a.status)+'</div>')+'</div>').join(""):empty("No actions pending","Proposals from Tyrion will appear here before anything changes in external services."))+'</div></div><div class="integration-note">Only creating a local Meta Manager draft is supported. Automatic publishing, deletes, credential changes and live pricing edits are deliberately unavailable.</div>'}
function skillsPage(){return '<input class="skill-search" id="skill-search" type="search" placeholder="Search skills, e.g. WordPress, SEO, animation" value="'+escapeHTML(app.query)+'" aria-label="Filter installed skills"><div class="divider-label" id="skill-count"></div><div class="skill-grid" id="skill-results"></div>'}
function filterSkills(){const q=app.query.toLowerCase().trim();const matched=app.skills.filter(s=>(s.name+" "+s.description).toLowerCase().includes(q));document.getElementById("skill-count").textContent=matched.length+" SKILLS MATCHED";document.getElementById("skill-results").innerHTML=matched.length?matched.map(s=>'<button class="skill-tile" data-skill="'+escapeHTML(s.name)+'"><strong>'+escapeHTML(s.name)+'</strong><small>'+escapeHTML(s.description||"Skill instructions")+'</small></button>').join(""):empty("No matching skills","Try another term.")}
function identityPage(o){const i=o.identity;const labels={mission:"Mission",voice:"Communication",engineering:"Engineering standards",cost:"Cost principles",design:"Design approach",decisions:"Decision making",boundaries:"Approval boundaries",truthfulness:"Accountability"};
return '<div class="integration-note" style="margin-bottom:18px">Tyrion’s persistent preferences are stored locally. They guide supported tools and workflows; they do not grant automatic access to ChatGPT memory or bypass permission checks.</div><form id="identity-form"><div class="identity-grid">'+Object.keys(labels).map(key=>'<div class="identity-field"><label for="identity-'+key+'">'+labels[key]+'</label><textarea id="identity-'+key+'" name="'+key+'" minlength="2" maxlength="600" required>'+escapeHTML(i[key])+'</textarea></div>').join("")+'</div><div class="profile-actions"><button class="button-primary" type="submit">'+icon("check")+' Save working profile</button></div></form>'}
async function load(){
 try{const o=await api("/api/overview");app.overview=o;
 if(app.page==="dashboard" && pageTitles[location.hash.replace("#","")]) app.page=location.hash.replace("#","");document.getElementById("task-navcount").textContent=o.counts.open_tasks||"";document.getElementById("approval-navcount").textContent=(o.approvals||[]).filter(x=>x.status==="pending").length||"";
 document.getElementById("footer-time").textContent="LOCAL RECORD · "+dateFmt(o.app.time);
 const sel=document.getElementById("task-project");sel.innerHTML='<option value="">General / unassigned</option>'+o.projects.map(p=>'<option value="'+escapeHTML(p.name)+'">'+escapeHTML(p.name)+'</option>').join("");
 render();
 }catch(err){document.getElementById("page-content").innerHTML=empty("Connection unavailable","Tyrion's local server did not return a valid response.");toast(err.message)}
}
function render(){
 const o=app.overview;if(!o)return;
 document.getElementById("breadcrumb").textContent=app.page.charAt(0).toUpperCase()+app.page.slice(1);
 document.getElementById("page-title").innerHTML=pageTitles[app.page][0].replace(/\.$/,"")+'<span class="period">.</span>';
 document.getElementById("page-subtitle").textContent=pageTitles[app.page][1];
 document.getElementById("new-task").innerHTML=icon("plus")+(app.page==="scheduler"?" New schedule":" New task");
 for(const n of document.querySelectorAll("[data-page]")){n.classList.toggle("active",n.dataset.page===app.page);n.setAttribute("aria-current",n.dataset.page===app.page?"page":"false")}
 const content={knowledge:()=>TyrionKnowledge.page(),dispatch:()=>'<div id="dispatch-body"><div class="loading">Reading PC dispatch queue…</div></div>',scheduler:()=>TyrionScheduler.page(),approvals:()=>approvalsPage(o),dashboard:()=>dashboard(o),projects:()=>ProjectsHub.page(),tasks:()=>tasks(o),automations:()=>autos(o),connections:()=>connections(o),skills:()=>skillsPage(),identity:()=>identityPage(o)};
 document.getElementById("page-content").innerHTML=content[app.page]();
 if(app.page==="knowledge")TyrionKnowledge.mount();
 if(app.page==="connections" && typeof TyrionCompanion!=="undefined")TyrionCompanion.refresh();
 if(app.page==="dispatch" && typeof TyrionCompanion!=="undefined")TyrionCompanion.refreshDispatch();
 if(app.page==="skills"){if(!app.skills.length){api("/api/skills").then(v=>{app.skills=v.skills;filterSkills()}).catch(e=>toast(e.message))}else filterSkills();
 document.getElementById("skill-search").addEventListener("input",e=>{app.query=e.target.value;filterSkills()})}
 const form=document.getElementById("identity-form");
 if(form)form.addEventListener("submit",async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));try{await api("/api/identity","POST",data);toast("Working profile saved");await load()}catch(e){toast(e.message)}})
}
function navigate(page){if(!pageTitles[page])return;app.page=page;location.hash=page;render();window.scrollTo(0,0)}
document.addEventListener("click",async e=>{
  if(e.target.closest("#copy-browser-pairing")){
   try{
    const r=await fetch("/api/extension/key",{headers:{"X-Tyrion-Session":token}});
    if(!r.ok)throw Error("Pairing not available");
    const value=(await r.json()).key;
    await navigator.clipboard.writeText(value);
    toast("Pairing key copied. Paste it into the Tyrion extension.");
   }catch(error){toast("Unable to copy pairing code: "+error.message)}
   return;
  }
  if(e.target.closest("#browser-extension-guide")){
   toast("Chrome → chrome://extensions → Developer mode → Load unpacked → choose Tyrion-The-Hand/browser-extension");
   return;
  }

 const p=e.target.closest("[data-page],[data-linkpage]");if(p){navigate(p.dataset.page||p.dataset.linkpage);return}
 if(e.target.closest("#sync-integrations")){const button=e.target.closest("#sync-integrations");button.disabled=true;try{await api("/api/integrations/sync","POST",{});toast("Live integrations checked");await load()}catch(err){toast(err.message);button.disabled=false}return}
 if(e.target.closest("#propose-draft")){const dlg=document.getElementById("draft-dialog");const sel=document.getElementById("draft-account");sel.innerHTML='<option value="">Checking available accounts…</option>';dlg.showModal();try{const accounts=await api("/api/meta/accounts");sel.innerHTML=accounts.filter(a=>a.status==="connected").map(a=>'<option value="'+escapeHTML(a.id)+'">'+escapeHTML(a.name)+'</option>').join("");if(!sel.options.length){sel.innerHTML='<option value="">No connected accounts</option>';toast("Connect an account in Meta Manager first")}}catch(err){toast(err.message)}return}
 const approval=e.target.closest("[data-approval-id]");if(approval){const id=approval.dataset.approvalId,decision=approval.dataset.decision;const message=decision==="approve"?"Create this draft in Meta Manager? It will not publish.":"Reject this action proposal?";if(!window.confirm(message))return;approval.disabled=true;try{const result=await api("/api/approvals/"+id+"/decide","POST",{decision});toast(result.result.status==="needs_review"?"Outcome needs review in Meta Manager":"Action decision recorded");await load()}catch(err){toast(err.message);await load()}return}
 const job=e.target.closest("[data-job]");if(job){try{await api("/api/jobs/"+job.dataset.job+"/enabled","POST",{enabled:job.dataset.enabled==="1"});toast("Automation preference saved");await load()}catch(err){toast(err.message)}return}
 const details=e.target.closest("[data-task-detail]");if(details){
   const id=Number(details.dataset.taskDetail),task=(app.overview?.tasks||[]).find(t=>t.id===id);
   if(!task)return toast("Task not found");
   window.tyrionDetailTaskId=id;
   document.getElementById("task-detail-title").textContent=task.title;
   document.getElementById("task-detail-meta").textContent="#"+task.id+" · "+(task.project||"General")+" · "+task.priority+" priority";
   const instructionBox=document.getElementById("task-detail-instructions");
   instructionBox.hidden=!task.instructions;
   instructionBox.textContent=task.instructions?"WORK BRIEF\n"+task.instructions:"";
   const pane=document.getElementById("task-detail-updates");pane.textContent="Loading updates…";
   document.getElementById("task-detail-dialog").showModal();
   try{
    const updates=await api("/api/tasks/"+id+"/updates");
    document.getElementById("task-detail-count").textContent=updates.length+" update"+(updates.length===1?"":"s");
    pane.innerHTML=updates.length?updates.map(x=>{
      const when=new Date(x.created_at).toLocaleString(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
      return '<article class="task-update-card"><span class="update-avatar">'+escapeHTML(x.source==="chatgpt"?"AI":x.source==="operator"?"YOU":"T")+'</span><div class="task-update-body"><div class="task-update-head"><strong>'+escapeHTML(x.source==="chatgpt"?"ChatGPT":x.source==="operator"?"Operator":"Tyrion")+'</strong><time>'+escapeHTML(when)+'</time></div><p>'+escapeHTML(x.note)+'</p></div></article>';
    }).join(""):'<div class="empty"><strong>No progress updates</strong>Notes from Tyrion and ChatGPT will appear here.</div>';
   }catch(error){pane.textContent=error.message}return;
 }
 const matchedTask=e.target.closest("[data-route-task]");if(matchedTask){const modal=document.getElementById("skill-dialog");document.getElementById("skill-title").textContent="Suggested skill routing";document.getElementById("skill-body").textContent="Matching installed skills…";modal.showModal();try{const result=await api("/api/skills/route?q="+encodeURIComponent(matchedTask.dataset.routeTask));document.getElementById("skill-body").textContent=result.skills.map((x,i)=>((i+1)+". "+x.name+"\n"+x.description)).join("\n\n")||"No suitable match found"}catch(err){document.getElementById("skill-body").textContent=err.message}return}
 const skill=e.target.closest("[data-skill]");if(skill){
  const modal=document.getElementById("skill-dialog");document.getElementById("skill-title").textContent=skill.dataset.skill;document.getElementById("skill-body").textContent="Reading instruction file…";modal.showModal();
  try{const result=await api("/api/skill?name="+encodeURIComponent(skill.dataset.skill));document.getElementById("skill-body").textContent=result.content+(result.truncated?"\n[Preview truncated]":"")}catch(err){document.getElementById("skill-body").textContent="Could not read this skill: "+err.message}return}
});
document.addEventListener("change",async e=>{
 const el=e.target;if(el.matches("[data-taskstatus]")){try{await api("/api/tasks/"+el.dataset.taskstatus+"/status","POST",{status:el.value});toast("Task status saved");await load()}catch(err){toast(err.message);await load()}}
});
document.getElementById("close-draft").addEventListener("click",()=>document.getElementById("draft-dialog").close());
document.getElementById("cancel-draft").addEventListener("click",()=>document.getElementById("draft-dialog").close());
document.getElementById("draft-form").addEventListener("submit",async e=>{e.preventDefault();const body={account_id:document.getElementById("draft-account").value,title:document.getElementById("draft-title").value,platform:document.getElementById("draft-platform").value,caption:document.getElementById("draft-caption").value};try{await api("/api/approvals/draft","POST",body);document.getElementById("draft-dialog").close();e.target.reset();toast("Draft queued for your approval");navigate("approvals");await load()}catch(err){toast(err.message)}});
document.getElementById("close-task-detail").addEventListener("click",()=>document.getElementById("task-detail-dialog").close());
document.getElementById("task-update-form").addEventListener("submit",async e=>{e.preventDefault();const id=window.tyrionDetailTaskId;try{await api("/api/tasks/"+id+"/updates","POST",{note:document.getElementById("task-update-text").value});document.getElementById("task-update-text").value="";toast("Update saved to shared task");document.getElementById("task-detail-dialog").close();await load()}catch(error){toast(error.message)}});
document.getElementById("close-skill").addEventListener("click",()=>document.getElementById("skill-dialog").close());
async function refreshChatgptSync(){
 const state=document.getElementById("chatgpt-sync-state");
 if(!state)return;
 try{
  const [v,events]=await Promise.all([api("/api/chatgpt/sync-status"),api("/api/chatgpt/event-status")]);
  const pending=Number(v.pending_changes||0);
  if(events.chatgpt_realtime_connected){
    state.textContent="ChatGPT Work live · "+events.subscriptions_active+" events";
    state.title="Verified signed MCP subscriptions: "+events.subscriptions_active+". Successful webhook deliveries: "+events.deliveries_successful+". Last delivered event: "+(events.last_delivered_event?.kind||"none yet")+". Work executes asynchronously after webhook receipt.";
    state.classList.remove("has-pending");
  }else{
    state.textContent=pending?pending+" change"+(pending===1?"":"s")+" awaiting ChatGPT":
      v.last_consumed_at?"ChatGPT handoff last checked":"Awaiting first ChatGPT read";
    state.title="No active event subscriptions. Tyrion change feed has "+pending+" outstanding changes.";
    state.classList.toggle("has-pending",pending>0);
  }
 }catch(e){state.textContent="Handoff status unavailable"}
}
// Real-time local updates over the single same-origin EventSource connection.
// This does not send notifications into an inactive ChatGPT conversation.
let tyrionStream=null;
let tyrionRefreshPending=false;
let tyrionRefreshTimer=null;
function refreshOnTyrionEvent(){
  if(document.querySelector("dialog[open]")){
    tyrionRefreshPending=true;
    return;
  }
  tyrionRefreshPending=false;
  clearTimeout(tyrionRefreshTimer);
  tyrionRefreshTimer=setTimeout(()=>{
    load();
    if(app.page==="scheduler" && typeof TyrionScheduler!=="undefined")TyrionScheduler.refresh().catch(()=>{});
  },180);
}
async function openTyrionLiveStream(){
  if(!window.EventSource)return;
  try{
    const newest=await api("/api/chatgpt/sync-status");
    const start=Number(newest.latest_event||0);
    tyrionStream=new EventSource("/api/realtime/stream?after="+start);
    tyrionStream.addEventListener("tyrion-change",()=>refreshOnTyrionEvent());
    tyrionStream.onopen=()=>{const el=document.getElementById("local-stream-state");if(el){el.textContent="Local events live";el.title="Instant updates within Tyrion; external ChatGPT MCP events require a subscription."}};
    tyrionStream.onerror=()=>{const el=document.getElementById("local-stream-state");if(el)el.textContent="Local feed reconnecting"};
  }catch(error){/* Existing regular refresh remains available. */}
}
openTyrionLiveStream();
document.addEventListener("close",()=>{if(tyrionRefreshPending)refreshOnTyrionEvent()},true);
setInterval(()=>{if(document.visibilityState==="visible")refreshChatgptSync()},7000);
refreshChatgptSync();
const dialog=document.getElementById("task-dialog");
document.getElementById("new-task").addEventListener("click",()=>{if(app.page==="scheduler")return TyrionScheduler.openCreate();dialog.showModal();document.getElementById("task-title").focus()});
document.getElementById("close-dialog").addEventListener("click",()=>dialog.close());
document.getElementById("cancel-task").addEventListener("click",()=>dialog.close());
document.getElementById("refresh").addEventListener("click",()=>{load();toast("Workspace refreshed")});
document.getElementById("task-form").addEventListener("submit",async event=>{event.preventDefault();const title=document.getElementById("task-title").value.trim();if(!title)return;
 try{await api("/api/tasks","POST",{title,project:document.getElementById("task-project").value,priority:document.getElementById("task-priority").value,instructions:document.getElementById("task-instructions").value});dialog.close();event.target.reset();toast("Task created");navigate("tasks");await load()}catch(err){toast(err.message)}});
document.getElementById("copy-brief").addEventListener("click",async()=>{
 if(!app.overview)return;const o=app.overview;
 const brief="Tyrion — The Hand | Local brief\n"+o.app.time+"\nTracked projects: "+o.counts.projects+" (unverified externally)\nOpen tasks: "+o.counts.open_tasks+"\nAwaiting approval: "+o.counts.approval_tasks+"\nSkills: "+o.counts.skills+"\n\nTasks:\n"+o.tasks.map(t=>"- ["+t.status+"] "+t.title+(t.project?" — "+t.project:"")).join("\n");
 try{await navigator.clipboard.writeText(brief);toast("Local status brief copied")}catch{toast("Clipboard access not available")}
});
load();

// Lightweight foreground refresh supplements change events for progress notes,
// which do not need to create a separate global Tyrion change-feed event.
setInterval(()=>{
 if(document.visibilityState==="visible"&&app.page==="dispatch"&&typeof TyrionCompanion!=="undefined")
   TyrionCompanion.refreshDispatch();
},5000);
