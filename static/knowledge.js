"use strict";
/* Optional semantic knowledge search. Preserves Tyrion's burgundy/gold UI. */
const TyrionKnowledge = {
  page(){
    return '<div class="panel"><div class="panel-head"><h2>Local knowledge search</h2><span class="pill green" id="knowledge-state">Checking model</span></div>'+
      '<div class="knowledge-body"><p class="section-caption">Find related projects, historical task notes, approved documentation and installed skills by meaning. Embeddings stay on this PC. No file vaults or inactive Fatir data are indexed.</p>'+
      '<label for="knowledge-kind" class="knowledge-mode-label">Search area</label><select id="knowledge-kind" class="knowledge-select"><option value="text">Projects, tasks, documents and skills</option><option value="media">Indexed images and video frames (740M)</option></select>'+
      '<form id="knowledge-form" class="knowledge-search"><label for="knowledge-query">Ask about a project, issue or workflow</label><div class="knowledge-search-row"><input id="knowledge-query" type="search" required minlength="3" maxlength="600" placeholder="e.g. What prevents duplicate tasks in Tyrion?"><button class="button-primary" type="submit">Search knowledge</button></div></form>'+
      '<div class="knowledge-meta"><span id="knowledge-count">Checking index…</span><button id="knowledge-sync" class="button-secondary" type="button">Refresh local index</button></div>'+
      '<div id="knowledge-results" role="status" aria-live="polite"><div class="empty"><strong>Search your work</strong>Try a natural-language question. Results cite original source references.</div></div></div></div>'+
      '<div class="integration-note"><strong>Private by default.</strong> Tyrion sends embedding inputs only to localhost Ollama. Selected search excerpts may be shared with a cloud LLM only when you explicitly send them through a connected tool. This search never executes a retrieved instruction or modifies a client website.</div>';
  },
  async mount(){
    const form=document.getElementById('knowledge-form'), results=document.getElementById('knowledge-results');
    if(!form)return;
    const headers={'X-Tyrion-Session':token};
    const check=async()=>{
      try{
        const r=await fetch('/api/knowledge/status',{headers});
        if(!r.ok)throw Error('Status unavailable');
        const s=await r.json();
        document.getElementById('knowledge-state').textContent=s.available?'EmbeddingGemma ready':'Model offline';
        document.getElementById('knowledge-count').textContent=s.indexed+' indexed references · '+Object.entries(s.by_type).map(([k,v])=>v+' '+k).join(' · ');
      }catch(error){document.getElementById('knowledge-state').textContent='Not connected'}
    };
    await check();
    const action=async(endpoint,body)=>{
      const res=await fetch(endpoint,{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body)});
      const json=await res.json();
      if(!res.ok)throw Error(json.error||'Search failed');
      return json.result;
    };
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      const query=document.getElementById('knowledge-query').value.trim();
      if(query.length<3)return;
      results.innerHTML='<div class="loading">Searching the local knowledge index…</div>';
      const btn=form.querySelector('button[type="submit"]');btn.disabled=true;
      try {
        const media=document.getElementById('knowledge-kind').value==='media';
        const data=await action(media?'/api/knowledge/media-search':'/api/knowledge/search',{query,limit:7});
        if(media){
          results.innerHTML=data.matches.length?'<div class="knowledge-matches">'+data.matches.map(m=>
            '<article class="knowledge-result"><div class="knowledge-result-top"><span class="pill gray">'+escapeHTML(m.kind)+'</span><span class="muted">'+Math.round(m.similarity*100)+'% similarity</span></div>'+
            '<h3>'+escapeHTML(m.path.split('/').pop())+'</h3><p>'+escapeHTML(m.project)+(m.timestamp===null?'':' · frame at '+m.timestamp+'s')+'</p><small>'+escapeHTML(m.path)+'</small></article>').join('')+'</div>':
            '<div class="empty"><strong>No visual assets indexed</strong>Index approved images or videos with Tyrion’s media-index CLI before searching.</div>';
          return;
        }
        results.innerHTML=data.matches.length?'<div class="knowledge-matches">'+data.matches.map((m,i)=>
          '<article class="knowledge-result"><div class="knowledge-result-top"><span class="pill gray">'+escapeHTML(m.type)+'</span><span class="muted">'+Math.round(m.score*100)+'% similarity</span></div>'+
          '<h3>'+escapeHTML(m.title)+'</h3><p>'+escapeHTML(m.excerpt)+'</p><small>Source: '+escapeHTML(m.reference)+'</small></article>').join('')+'</div>':
          '<div class="empty"><strong>No matches</strong>Try another question.</div>';
        await check();
      }catch(error){results.innerHTML='<div class="empty"><strong>Search unavailable</strong>'+escapeHTML(error.message)+'</div>'}
      finally{btn.disabled=false}
    });
    document.getElementById('knowledge-sync').addEventListener('click',async event=>{
      const button=event.currentTarget;button.disabled=true;button.textContent='Refreshing index…';
      try{
        const result=await action('/api/knowledge/sync',{});
        toast('Index updated: '+result.updated+' changed, '+result.indexed+' total');
        await check();
      }catch(error){toast(error.message)}
      finally{button.disabled=false;button.textContent='Refresh local index'}
    });
  }
};
