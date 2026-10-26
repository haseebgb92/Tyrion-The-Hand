"use strict";
const ProjectsHub=(()=>{
 let filter="",focused="",editingProject=null;
 const classification={
  connected:["Live verified","green"],ready:["Ready","green"],
  relay_connected:["ChatGPT relay","gray"],relay_stale:["Relay needs recheck","gray"],inventory_only:["Inventory only","gray"],
  needs_authorization:["Needs authorization","red"],subscription_required:["Subscription needed","gray"],not_checked:["Not checked","gray"],
  not_verified_for_project:["Site not verified","gray"],not_connected:["Unconnected","gray"]
 };
 const summaryStatus=p=>{
  const c=p.connectors||[];
  if(c.some(x=>x.status==="connected"))return ["Local live","green"];
  if(c.some(x=>x.status==="relay_connected"))return ["ChatGPT relay","gray"];
  if(c.some(x=>x.status==="inventory_only"))return ["Inventory","gray"];
  if(c.some(x=>x.status==="needs_authorization"))return ["Needs auth","red"];
  return ["Not linked","gray"];
 };
 function page(){
  const all=app.overview?.projects||[];
  const q=filter.trim().toLowerCase();
  const displayed=all.filter(p=>(p.name+" "+p.category+" "+(p.resources||[]).map(x=>x.locator).join(" ")).toLowerCase().includes(q));
  const cards=displayed.map(p=>{
    const [label,tone]=summaryStatus(p);
    const site=(p.resources||[]).find(x=>x.kind==="website");
    return '<div class="project-hub-card" data-project-details="'+escapeHTML(p.name)+'" role="button" tabindex="0" aria-label="Open '+escapeHTML(p.name)+' project">'+
      '<div class="card-top"><span class="project-icon">'+escapeHTML(p.name.slice(0,1))+'</span>'+statusPill(label,tone)+'</div>'+
      '<strong class="project-hub-title">'+escapeHTML(p.name)+'</strong>'+
      '<span class="project-hub-category">'+escapeHTML(p.category)+'</span>'+
      '<div class="project-hub-site">'+(site?icon("link")+' '+escapeHTML(site.locator.replace(/^https:\/\//,"")):'No verified website reference')+'</div>'+
      '<div class="project-hub-footer"><span>'+icon("list")+' '+(p.tasks_open||0)+' open</span><span>'+icon("clock")+' '+(p.schedules||0)+' jobs</span><span>'+icon("link")+' '+(p.connectors?.length||0)+' tools</span></div>'+
    '</div>';
   }).join("");
  const body='<div class="connect-head"><div><h2>Project directory</h2><p>Known projects, local workspaces and explicitly verified connector associations.</p></div><button id="project-create" class="button-primary">'+icon("plus")+' Add project</button></div>'+
    '<input id="project-filter" class="skill-search" type="search" placeholder="Find a client, project or website..." aria-label="Search project directory" value="'+escapeHTML(filter)+'">'+
    '<div class="divider-label">'+displayed.length+' PROJECTS MATCHED · '+all.length+' IN DIRECTORY</div>'+
    '<div class="project-hub-grid">'+(cards||empty("No matching project","Try a different client or service name."))+'</div>'+
    '<div class="integration-note">Connection badges reflect the highest verified integration level, not whether website work has been completed. ChatGPT-relayed services cannot run unattended through Tyrion unless a separate adapter is available.</div>';
  return body;
 }
 function details(name){
  const p=(app.overview?.projects||[]).find(x=>x.name===name);
  if(!p)return;
  focused=name;
  const root=document.getElementById("project-detail-dialog");
  document.getElementById("project-detail-title").textContent=name;
  document.getElementById("project-detail-category").textContent=p.category;
  const sources=(p.resources||[]).map(r=>
     '<div class="project-resource"><div><strong>'+escapeHTML(r.label)+'</strong><span>'+escapeHTML(r.kind)+' · '+escapeHTML(r.locator)+'</span></div><button class="subtle-button" data-copy-resource="'+escapeHTML(r.locator)+'">'+icon("copy")+' Copy</button></div>').join("");
  const integrations=(p.connectors||[]).map(c=>{
     const [label,tone]=classification[c.status]||["Not checked","gray"];
     const displayName=({"meta_manager":"Meta Manager","advertpreneur_qa":"Advertpreneur QA","security_fleet":"ShieldPress inventory","wp_lab":"WP Lab","advertpreneur_gbp":"GBP","advert_connect":"Advert Connect","shopify_development":"Shopify development","supabase":"Supabase"}[c.id]||c.id);
     return '<div class="project-resource"><div><strong>'+escapeHTML(displayName)+'</strong><span>'+escapeHTML(c.mode||"No authenticated adapter")+(c.checked_at?" · "+escapeHTML(new Date(c.checked_at).toLocaleDateString()):"")+'</span></div>'+statusPill(label,tone)+'</div>'
  }).join("");
  document.getElementById("project-detail-body").innerHTML=
    '<div class="project-detail-stats"><span>'+icon("list")+' '+(p.tasks_open||0)+' open tasks</span><span>'+icon("clock")+' '+(p.schedules||0)+' schedules</span></div>'+
    (p.notes?'<div class="integration-note">'+escapeHTML(p.notes)+'</div>':'')+
    '<div class="divider-label">RESOURCES & LINKS</div>'+(sources||empty("No resources yet","Attach a known website or local folder."))+
    '<div class="divider-label">LINKED INTEGRATIONS</div>'+(integrations||empty("No adapter linked","Link an authenticated integration when available."))+
    '<div class="project-detail-actions"><button class="button-secondary" id="project-edit">'+icon("list")+' Edit brief</button><button class="button-secondary" id="project-add-resource">'+icon("plus")+' Add a resource</button></div>';
  root.showModal();
 }
 function formProject(name=null){
  editingProject=name;
  document.getElementById("create-project-form").reset();
  const project=name?(app.overview?.projects||[]).find(p=>p.name===name):null;
  document.getElementById("project-name").value=project?.name||"";
  document.getElementById("project-name").readOnly=!!project;
  document.getElementById("project-category").value=project?.category||"";
  document.getElementById("project-notes").value=project?.notes||"";
  document.getElementById("project-save-button").textContent=project?"Save changes":"Save project";
  document.getElementById("create-project-dialog").showModal();
 }
 function formResource(){
  document.getElementById("resource-project").value=focused;
  document.getElementById("resource-form").reset();
  document.getElementById("resource-project").value=focused;
  document.getElementById("project-resource-dialog").showModal();
 }
 function init(){
  document.addEventListener("click",async e=>{
   if(e.target.closest("#project-create")){formProject();return}
   if(e.target.closest("[data-project-details]")){details(e.target.closest("[data-project-details]").dataset.projectDetails);return}
   if(e.target.closest("#project-add-resource")){formResource();return}
   if(e.target.closest("#project-edit")){
     document.getElementById("project-detail-dialog").close();
     formProject(focused);return;
   }
   const clip=e.target.closest("[data-copy-resource]");
   if(clip){try{await navigator.clipboard.writeText(clip.dataset.copyResource);toast("Project resource copied")}catch{toast("Clipboard is unavailable")}return}
  });
  document.addEventListener("keydown",e=>{
   const card=e.target.closest("[data-project-details]");
   if(card && (e.key==="Enter"||e.key===" ")){e.preventDefault();details(card.dataset.projectDetails)}
  });
  document.getElementById("close-project-detail").addEventListener("click",()=>document.getElementById("project-detail-dialog").close());
  document.getElementById("close-project-create").addEventListener("click",()=>document.getElementById("create-project-dialog").close());
  document.getElementById("close-project-resource").addEventListener("click",()=>document.getElementById("project-resource-dialog").close());
  document.addEventListener("input",e=>{
    if(e.target?.id==="project-filter"){
      filter=e.target.value;
      const cursor=e.target.selectionStart;
      document.getElementById("page-content").innerHTML=page();
      const input=document.getElementById("project-filter");
      input.focus();input.setSelectionRange(cursor,cursor);
    }
  });
  document.getElementById("create-project-form").addEventListener("submit",async e=>{
   e.preventDefault();
   try{
    const name=document.getElementById("project-name").value,category=document.getElementById("project-category").value,notes=document.getElementById("project-notes").value;
    await api(editingProject?"/api/projects/update":"/api/projects","POST",{name,category,notes});
    if(!editingProject && notes.trim())await api("/api/projects/update","POST",{name,category,notes});
    const wasEditing=!!editingProject;editingProject=null;
    document.getElementById("create-project-dialog").close();await load();toast(wasEditing?"Project brief saved":"Project registered");
   }catch(error){toast(error.message)}
  });
  document.getElementById("resource-form").addEventListener("submit",async e=>{
   e.preventDefault();
   const values={project:focused,label:document.getElementById("resource-label").value,
     kind:document.getElementById("resource-kind").value,
     locator:document.getElementById("resource-locator").value};
   try{await api("/api/projects/resources","POST",values);
      document.getElementById("project-resource-dialog").close();
      document.getElementById("project-detail-dialog").close();
      await load();details(focused);toast("Project resource attached");
   }catch(error){toast(error.message)}
  });
 }
 return {page,init};
})();
ProjectsHub.init();
