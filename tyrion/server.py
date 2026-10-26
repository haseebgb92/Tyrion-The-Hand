"""Lightweight localhost dashboard, no third-party dependencies."""
from __future__ import annotations
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
import secrets
import os
import threading
import time
import urllib.parse
from . import core,integrations,workflow_scheduler as workflows,project_hub,change_feed,realtime,mcp_events,extension_bridge,companion_pairing,companion_dispatch,steering

STATIC=core.ROOT/"static"
HOST="127.0.0.1"
PORT=17877
TOKEN=secrets.token_urlsafe(32)

def scheduler(stop):
    """Bounded health checks and local task briefs. No paid model API."""
    previous=0.0
    integration_previous=0.0
    while not stop.wait(10):
        try:
            enabled={j["id"]:j for j in core.jobs() if j["enabled"]}
            now=core.LOCAL_TIME()
            if "catalog_refresh" in enabled and time.monotonic()-previous>=1800:
                previous=time.monotonic()
                count=core.catalog()["count"]
                core.mark_job("catalog_refresh","ok" if count else "unavailable")
            if "integration_refresh" in enabled and time.monotonic()-integration_previous>=900:
                integration_previous=time.monotonic()
                result=integrations.synchronize()
                core.mark_job("integration_refresh", "ok" if all(i["status"]=="connected" for i in result["integrations"]) else "attention")
            if "daily_brief" in enabled and now.hour>=8:
                date=now.strftime("%Y-%m-%d")
                with core.LOCK,core.connection() as db:
                    last=db.execute("SELECT value FROM meta WHERE key='brief_date'").fetchone()
                    if last is None or last["value"]!=date:
                        outstanding=core.rows("SELECT COUNT(*) AS n FROM tasks WHERE status='open'")[0]["n"]
                        approval=core.rows("SELECT COUNT(*) AS n FROM tasks WHERE status='awaiting_approval'")[0]["n"]
                        core.log("brief",f"Daily brief: {outstanding} open tasks, {approval} task approvals, {len([x for x in core.approval_requests() if x['status']=='pending'])} pending action approvals.")
                        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('brief_date',?)",(date,))
                        db.commit()
                        core.mark_job("daily_brief","ok")
        except Exception as error:
            try:core.log("error","Background check failed: "+type(error).__name__)
            except Exception:pass

def knowledge_watcher(stop):
    """Incremental project memory updates every 2 minutes, on the Tyrion PC.

    No other app, filesystem folder or conversation is silently monitored.
    Source changes are discovered only from Tyrion records and allowlisted docs.
    """
    if stop.wait(5):return
    while not stop.is_set():
        try:
            from . import knowledge,project_history
            result=knowledge.sync()
            report={"ok":True,"checked_at":core.now(),"updated":result["updated"],
                    "removed":result["removed"],"indexed":result["indexed"]}
            with core.LOCK,core.connection() as db:
                db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('knowledge_auto_status',?)",
                           (json.dumps(report),))
                db.commit()
        except Exception as error:
            try:
                report={"ok":False,"checked_at":core.now(),"error":type(error).__name__}
                with core.LOCK,core.connection() as db:
                    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('knowledge_auto_status',?)",
                               (json.dumps(report),))
                    db.commit()
            except Exception:pass
        if stop.wait(120):break

def due_work_watcher(stop):
    """Independent 1-second due watcher; scheduled handoffs persist until picked up."""
    last_dispatch_sync=0
    while not stop.wait(1.0):
        try:
            workflows.enqueue_due()
            workflows.dispatch_local_generations()
            if time.monotonic()-last_dispatch_sync>=10:
                last_dispatch_sync=time.monotonic()
                companion_dispatch.sync_waiting_runs()
        except Exception:
            continue

class Handler(BaseHTTPRequestHandler):
    server_version="Tyrion/0.8"
    def log_message(self,fmt,*args):
        # Prevent noisy access logging and accidental token disclosure
        pass
    def _host_ok(self):
        host=self.headers.get("Host","")
        return host in (f"127.0.0.1:{PORT}",f"localhost:{PORT}")
    def headers_out(self,mime,length,status=200):
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(length))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Cross-Origin-Resource-Policy","same-origin")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
    def output(self,payload,status=200):
        data=json.dumps(payload,ensure_ascii=False).encode()
        self.headers_out("application/json; charset=utf-8",len(data),status)
        self.wfile.write(data)
    def do_GET(self):
        if not self._host_ok():return self.output({"error":"Invalid host"},403)
        path=urllib.parse.urlsplit(self.path).path
        try:
            if path=="/api/extension/key":
                if self.headers.get("X-Tyrion-Session","")!=TOKEN:
                    return self.output({"error":"Local dashboard authorization required"},403)
                return self.output({"key":extension_bridge.get_pairing_key()})
            if path in ("/api/extension/state","/api/extension/packet","/api/extension/dispatch/status","/api/extension/steering"):
                if not extension_bridge.validate(self.headers.get("X-Tyrion-Extension","")):
                    return self.output({"error":"Browser extension is not paired"},403)
                if path=="/api/extension/state":return self.output(extension_bridge.state())
                if path=="/api/extension/steering":
                    q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    chat=q.get("chat",[""])[0]
                    return self.output({"chat":steering.canonical_chat(chat),"pending":steering.pending(chat)})
                if path=="/api/extension/dispatch/status":return self.output(companion_dispatch.summary())
                args=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                return self.output(extension_bridge.handoff(args.get("kind",[""])[0],args.get("id",[""])[0]))
            if path in ("/api/companion/status","/api/companion/devices"):
                if self.headers.get("X-Tyrion-Session","")!=TOKEN:
                    return self.output({"error":"Local dashboard authorization required"},403)
                return self.output(companion_pairing.devices() if path.endswith("devices") else companion_pairing.status())
            if path=="/api/dispatch/status":return self.output(companion_dispatch.summary())
            if path=="/api/knowledge/history":
                if self.headers.get("X-Tyrion-Session","")!=TOKEN:
                    return self.output({"error":"Local dashboard authorization required"},403)
                from . import project_history
                coverage=project_history.coverage()
                rows=project_history.list_history(limit=5000)
                all_latest={}
                counts={}
                for entry in rows:
                    name=entry["project"]
                    counts[name]=counts.get(name,0)+1
                    if name not in all_latest:
                        all_latest[name]={"project":name,"event_date":entry["event_date"],
                            "title":entry["title"],"kind":entry["kind"],
                            "source":entry["source"],"trust":entry["trust"]}
                entries=[dict(v,history_count=counts[k]) for k,v in all_latest.items()]
                entries.sort(key=lambda item:(item["event_date"],item["project"]),reverse=True)
                return self.output({"coverage":coverage,"latest":entries})
            if path=="/api/knowledge/status":
                if self.headers.get("X-Tyrion-Session","")!=TOKEN:
                    return self.output({"error":"Local dashboard authorization required"},403)
                from . import knowledge
                status=knowledge.status()
                status["background_worker_active"]=any(
                    t.name=="tyrion-knowledge-watcher" and t.is_alive()
                    for t in threading.enumerate())
                return self.output(status)
            if path=="/api/overview":return self.output(core.overview())
            if path=="/api/tasks":return self.output(core.tasks())
            if path.startswith("/api/tasks/") and path.endswith("/updates"):
                return self.output(core.task_updates(path.split("/")[3]))
            if path=="/api/projects":return self.output(project_hub.mapped_projects())
            if path=="/api/skills":
                q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q",[""])[0].lower()
                cat=core.catalog()
                return self.output({"count":cat["count"],"available":cat["available"],
                                    "skills":[{"name":s["name"],"description":s["description"]} for s in cat["skills"]
                                              if q in (s["name"]+" "+s["description"]).lower()][:125]})
            if path=="/api/activity":return self.output(core.activity(50))
            if path=="/api/skill":
                name=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("name",[""])[0]
                return self.output(core.skill_text(name))
            if path=="/api/identity":return self.output(core.identity())
            if path=="/api/skills/route":
                from . import skill_router
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q",[""])[0]
                return self.output(skill_router.route(query))
            if path=="/api/connections":return self.output(core.connections())
            if path=="/api/relay":return self.output(core.external_connector_relay())
            if path=="/api/jobs":return self.output(core.jobs())
            if path=="/api/integrations":return self.output(integrations.stored_report())
            if path=="/api/approvals":return self.output(core.approval_requests())
            if path=="/api/workflows":return self.output(workflows.summary())
            if path=="/api/chatgpt/sync-status":return self.output(change_feed.status())
            if path=="/api/chatgpt/event-status":return self.output(mcp_events.status())
            if path=="/api/realtime/stream":
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                try:cursor=max(0,int(self.headers.get("Last-Event-ID") or query.get("after",["0"])[0]))
                except (TypeError,ValueError):cursor=0
                self.send_response(200)
                self.send_header("Content-Type","text/event-stream; charset=utf-8")
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Accel-Buffering","no")
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                self.wfile.write(b": connected\n\n");self.wfile.flush()
                until=time.monotonic()+45
                while time.monotonic()<until:
                    events=realtime.events_since(cursor,limit=35)
                    if events:
                        for item in events:
                            cursor=item["id"]
                            # Browser only needs entity IDs to fetch fresh data.
                            payload=json.dumps({"id":item["id"],"kind":item["kind"],
                                  "entity_type":item["entity_type"],"entity_id":item["entity_id"]})
                            self.wfile.write(("id: "+str(cursor)+"\nevent: tyrion-change\ndata: "+payload+"\n\n").encode())
                        self.wfile.flush()
                    time.sleep(0.6)
                return
            if path=="/api/workflows/schedules":return self.output(workflows.list_schedules())
            if path=="/api/workflows/runs":return self.output(workflows.list_runs())
            if path.startswith("/api/workflows/runs/") and path.endswith("/output"):
                rid=int(path.split("/")[4])
                run=workflows.run_detail(rid)
                if not run["output_path"]:return self.output({"error":"No output"},404)
                target=Path(run["output_path"]).resolve()
                if not target.is_relative_to((core.DATA/"generated").resolve()):
                    return self.output({"error":"Invalid output path"},400)
                return self.output({"run_id":rid,"markdown":target.read_text(encoding="utf8")[:130000]})
            if path=="/api/meta/accounts":return self.output(integrations.meta_accounts())
            if path=="/api/health":return self.output({"ok":True,"version":"0.8.0","local_only":True})
            if path=="/":
                data=(STATIC/"index.html").read_text(encoding="utf8").replace("__TYRION_SESSION__",TOKEN).encode("utf8")
                self.headers_out("text/html; charset=utf-8",len(data))
                return self.wfile.write(data)
            name={"/app.js":"app.js","/scheduler.js":"scheduler.js","/projects.js":"projects.js","/companion.js":"companion.js","/knowledge.js":"knowledge.js","/style.css":"style.css","/seal.svg":"seal.svg"}.get(path)
            if name:
                data=(STATIC/name).read_bytes()
                self.headers_out(mimetypes.guess_type(name)[0] or "application/octet-stream",len(data))
                return self.wfile.write(data)
            return self.output({"error":"Not found"},404)
        except Exception as e:
            return self.output({"error":type(e).__name__},500)

    def do_POST(self):
        if not self._host_ok():return self.output({"error":"Invalid host"},403)
        origin=self.headers.get("Origin","")
        path_for_auth=urllib.parse.urlsplit(self.path).path
        shared_knowledge_route=(path_for_auth in ("/api/knowledge/shared/search","/api/knowledge/shared/media-search"))
        extension_route=path_for_auth.startswith("/api/extension/")
        # Authenticated extensions must originate from an extension context, never a website.
        origin_ok=not origin or origin in (f"http://127.0.0.1:{PORT}",f"http://localhost:{PORT}")
        if extension_route and origin.startswith("chrome-extension://"):
            import re
            origin_ok=bool(re.fullmatch(r"chrome-extension://[a-p]{32}",origin))
        if not origin_ok:return self.output({"error":"Origin not allowed"},403)
        if shared_knowledge_route:
            # Trusted local services only. Deny ALL browser Origin headers, even same-origin.
            # No CORS, no filesystem access, no operations beyond bounded retrieval.
            from . import knowledge
            if origin or not knowledge.validate_shared_key(self.headers.get("X-Tyrion-Knowledge-Key","")):
                return self.output({"error":"Knowledge access denied"},403)
        elif extension_route:
            if not extension_bridge.validate(self.headers.get("X-Tyrion-Extension","")):
                return self.output({"error":"Extension not paired"},403)
        elif self.headers.get("X-Tyrion-Session","")!=TOKEN:
            return self.output({"error":"Unauthorized"},403)
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            return self.output({"error":"JSON required"},415)
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=16384:return self.output({"error":"Invalid body size"},413)
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict):raise ValueError("Expected JSON object")
            path=urllib.parse.urlsplit(self.path).path
            if path in ("/api/knowledge/shared/media-search","/api/knowledge/media-search"):
                from . import knowledge_media
                value=knowledge_media.search_media(payload.get("query",""),payload.get("project"),payload.get("limit",5))
            elif path in ("/api/knowledge/search","/api/knowledge/sync","/api/knowledge/shared/search"):
                from . import knowledge
                if path=="/api/knowledge/sync":value=knowledge.sync()
                else:
                    project=payload.get("project") if path.endswith("/shared/search") else None
                    if project is not None and (not isinstance(project,str) or len(project)>90):
                        raise ValueError("Invalid project scope")
                    value=knowledge.search(payload.get("query",""),payload.get("limit",5),project=project)
            elif path=="/api/extension/steering/add":
                value=steering.add(payload.get("chat"),payload.get("instruction"))
            elif path=="/api/extension/steering/remove":
                value=steering.remove(payload.get("chat"),payload.get("id"))
            elif path=="/api/extension/steering/clear":
                value=steering.clear(payload.get("chat"))
            elif path=="/api/extension/dispatch/heartbeat":
                value=companion_dispatch.heartbeat(payload.get("detail","Chrome extension"))
            elif path=="/api/extension/dispatch/claim":
                value=companion_dispatch.claim()
            elif path=="/api/extension/dispatch/report":
                value=companion_dispatch.report(payload.get("dispatch_id"),payload.get("stage"),payload.get("tab_id"),payload.get("error",""))
            elif path=="/api/dispatch/request":
                value=companion_dispatch.manual(payload.get("kind"),payload.get("id"),payload.get("action"))
            elif path=="/api/companion/pair/start":
                value=companion_pairing.pairing_code()
            elif path=="/api/companion/revoke":
                value=companion_pairing.revoke(payload.get("device_id"))
            elif path=="/api/extension/note":
                value=extension_bridge.manual_note(payload.get("task_id"),payload.get("note"))
            elif path=="/api/projects":
                value=project_hub.create_project(payload.get("name",""),payload.get("category",""))
            elif path=="/api/projects/update":
                value=project_hub.update_project(payload.get("name",""),payload.get("category",""),payload.get("notes",""))
            elif path=="/api/projects/resources":
                value=project_hub.add_resource(payload.get("project",""),payload.get("label",""),
                    payload.get("kind",""),payload.get("locator",""))
            elif path=="/api/tasks":
                value=core.create_task(payload.get("title",""),payload.get("project",""),payload.get("priority","normal"),"dashboard",payload.get("instructions",""))
            elif path.startswith("/api/tasks/") and path.endswith("/updates"):
                value=core.add_task_update(path.split("/")[3],payload.get("note",""),"operator")
            elif path.startswith("/api/tasks/") and path.endswith("/status"):
                task_id=path.split("/")[3]
                value=core.set_task_status(task_id,payload.get("status"))
            elif path.startswith("/api/jobs/") and path.endswith("/enabled"):
                job_id=path.split("/")[3]
                value=core.set_job_enabled(job_id,payload.get("enabled"))
            elif path=="/api/identity":
                value=core.update_identity(payload)
            elif path=="/api/workflows/schedules":
                value=workflows.create_schedule(payload.get("title",""),payload.get("project",""),
                    payload.get("kind",""),payload.get("instructions",""),
                    payload.get("cadence",""),payload.get("time_local",""),
                    payload.get("timezone","Asia/Karachi"),payload.get("weekdays",[]),
                    payload.get("once_date"),payload.get("engine","chatgpt_handoff"),
                    payload.get("model",""),payload.get("enabled",True))
            elif path.startswith("/api/workflows/schedules/") and path.endswith("/edit"):
                value=workflows.update_schedule(path.split("/")[4],payload)
            elif path.startswith("/api/workflows/schedules/") and path.endswith("/archive"):
                value=workflows.archive_schedule(path.split("/")[4])
            elif path.startswith("/api/workflows/schedules/") and path.endswith("/enabled"):
                value=workflows.set_enabled(path.split("/")[4],payload.get("enabled"))
            elif path.startswith("/api/workflows/schedules/") and path.endswith("/run-now"):
                value=workflows.run_now(path.split("/")[4])
                workflows.dispatch_local_generations()
            elif path.startswith("/api/workflows/runs/") and path.endswith("/complete"):
                value=workflows.complete_run(path.split("/")[4])
            elif path=="/api/integrations/sync":
                value=integrations.synchronize()
                core.mark_job("integration_refresh","ok" if all(i["status"]=="connected" for i in value["integrations"]) else "attention")
            elif path=="/api/approvals/draft":
                value=core.create_meta_draft_proposal(payload.get("account_id",""),payload.get("title",""),payload.get("platform",""),payload.get("caption",""),payload.get("hashtags",[]))
            elif path.startswith("/api/approvals/") and path.endswith("/decide"):
                value=core.decide_approval(path.split("/")[3],payload.get("decision"))
            else:return self.output({"error":"Not found"},404)
            return self.output({"ok":True,"result":value})
        except (ValueError,TypeError,KeyError,AttributeError) as e:
            return self.output({"error":str(e)[:250]},400)
        except Exception as e:
            return self.output({"error":type(e).__name__},500)

def main():
    core.setup(recover=True)
    workflows.setup(recover=True)
    workflows.seed_coocoobabys()
    project_hub.initialize()
    change_feed.setup()
    realtime.setup()
    mcp_events.setup()
    extension_bridge.setup()
    companion_pairing.setup()
    companion_dispatch.setup()
    # Catch up a missed occurrence once; no backlog floods.
    workflows.enqueue_due()
    pidfile=core.DATA/"server.pid"
    stop=threading.Event()
    realtime.start(stop)
    mcp_events.start(stop)
    threading.Thread(target=due_work_watcher,args=(stop,),daemon=True,name="tyrion-due-watcher").start()
    threading.Thread(target=knowledge_watcher,args=(stop,),daemon=True,name="tyrion-knowledge-watcher").start()
    thread=threading.Thread(target=scheduler,args=(stop,),daemon=True)
    thread.start()
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    server.daemon_threads=True
    pidfile.write_text(str(os.getpid()))
    print(f"Tyrion local dashboard: http://{HOST}:{PORT}",flush=True)
    try:server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:pass
    finally:
        stop.set();server.server_close()
        try:
            if pidfile.read_text().strip()==str(os.getpid()): pidfile.unlink()
        except OSError: pass

if __name__=="__main__":main()