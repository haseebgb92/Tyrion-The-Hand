"""Persistent local state and read-only catalog access. No model API required."""
from __future__ import annotations
import datetime as dt
import json
import os
import pathlib
import sqlite3
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "tyrion.sqlite3"
CATALOG = pathlib.Path.home() / "Documents/Advertpreneur-Design-Toolkit/CATALOG.json"
LOCAL_TIME = dt.datetime.now().astimezone
LOCK = threading.RLock()
PROJECTS = [
    ("Glissimo", "WordPress / commerce"),
    ("Taiyo Munch", "Ecommerce / subscriptions"),
    ("CooCoo Babys", "SEO / WordPress"),
    ("Advertpreneur", "Agency / growth"),
    ("Meta Manager", "Social / application"),
    ("Advert Connect", "WordPress / integration"),
    ("ShieldPress", "Security / application"),
    ("Axxess VIP", "WordPress / design"),
    ("Azucar Cuban Bakery", "Ecommerce / WordPress"),
]

def now() -> str:
    return LOCAL_TIME().isoformat(timespec="seconds")

def connection():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    return con

def setup(recover=False):
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    try: DATA.chmod(0o700)
    except OSError: pass
    with LOCK, connection() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'needs_sync',
            notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, project TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'open',
            source TEXT NOT NULL DEFAULT 'local', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS task_updates(
          id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL,
          source TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(task_id) REFERENCES tasks(id));
        CREATE INDEX IF NOT EXISTS idx_task_updates_task ON task_updates(task_id,id);
        CREATE TABLE IF NOT EXISTS activity(
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL, summary TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, label TEXT NOT NULL, schedule TEXT NOT NULL,
            enabled INTEGER NOT NULL, last_run TEXT, status TEXT NOT NULL DEFAULT 'waiting');
        CREATE TABLE IF NOT EXISTS approvals(
            id INTEGER PRIMARY KEY, action TEXT NOT NULL, title TEXT NOT NULL,
            project TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
            reviewed_at TEXT, result_summary TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        # Safe migration: preserve existing task IDs and progress notes.
        existing_cols={x[1] for x in db.execute("PRAGMA table_info(tasks)")}
        if "instructions" not in existing_cols:
            db.execute("ALTER TABLE tasks ADD COLUMN instructions TEXT NOT NULL DEFAULT ''")
        for name,category in PROJECTS:
            db.execute("INSERT OR IGNORE INTO projects(name,category,updated_at) VALUES(?,?,?)",
                       (name,category,now()))
        for job in [("catalog_refresh","Skill catalog refresh","Every 30 minutes",1),
                    ("daily_brief","Daily work summary","Daily after 08:00 local",1),
                    ("integration_refresh","Connected service health","Every 15 minutes",1)]:
            db.execute("INSERT OR IGNORE INTO jobs(id,label,schedule,enabled) VALUES(?,?,?,?)",job)
        identity = {
            "name":"Tyrion", "title":"The Hand",
            "mission":"Execute approved work reliably and maintain an accurate operational record.",
            "voice":"Direct, concise, practical, professional; lead with results.",
            "engineering":"Reuse working systems, favor lean implementations, test and verify.",
            "cost":"Prefer existing tools and free or locally available infrastructure.",
            "design":"Preserve each client's design language; deliver polished accessible interfaces.",
            "decisions":"Investigate root cause; prefer practical fixes to unnecessary rebuilds.",
            "boundaries":"Require explicit authorization for live publishing, pricing changes, sending, destructive operations and spending.",
            "truthfulness":"Never mark a task done without evidence. Mark external project data unverified until connected.",
        }
        db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('identity',?)",(json.dumps(identity),))
        # A previous process might die after dispatching a write but before recording a result.
        # Never retry uncertain writes automatically.
        if recover:
            db.execute("UPDATE approvals SET status='needs_review',result_summary='Execution interrupted; inspect remote service before retrying' WHERE status='executing'")
        db.commit()
    try: os.chmod(DB,0o600)
    except OSError: pass

def rows(query, params=()):
    with LOCK, connection() as db:
        return [dict(row) for row in db.execute(query,params).fetchall()]

def one(query,params=()):
    found=rows(query,params)
    return found[0] if found else None

def log(kind,summary):
    with LOCK, connection() as db:
        db.execute("INSERT INTO activity(kind,summary,created_at) VALUES(?,?,?)",(kind,summary[:500],now()))
        db.commit()

def projects():
    return rows("SELECT * FROM projects ORDER BY name COLLATE NOCASE")

def tasks():
    return rows("""SELECT * FROM tasks ORDER BY
        CASE status WHEN 'open' THEN 0 WHEN 'awaiting_approval' THEN 1 ELSE 2 END,
        CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
        id DESC""")

def task_updates(task_id):
    if not one("SELECT id FROM tasks WHERE id=?",(int(task_id),)):
        raise ValueError("Task not found")
    return rows("SELECT id,task_id,source,note,created_at FROM task_updates WHERE task_id=? ORDER BY id DESC LIMIT 80",(int(task_id),))

def add_task_update(task_id,note,source="chatgpt"):
    if source not in ("chatgpt","operator","tyrion"):
        raise ValueError("Unknown task update source")
    if not isinstance(note,str) or not 5<=len(note.strip())<=3500:
        raise ValueError("Task update must be 5–3500 characters")
    with LOCK,connection() as db:
        task=db.execute("SELECT id FROM tasks WHERE id=?",(int(task_id),)).fetchone()
        if not task:raise ValueError("Task not found")
        cur=db.execute("INSERT INTO task_updates(task_id,source,note,created_at) VALUES(?,?,?,?)",
           (int(task_id),source,note.strip(),now()))
        db.commit()
    log("task",f"Task #{task_id} received an update from {source}")
    if source=="chatgpt":
        from . import companion_dispatch
        companion_dispatch.mark_progress(task_id)
    return one("SELECT id,task_id,source,note,created_at FROM task_updates WHERE id=?",(cur.lastrowid,))

def activity(limit=16):
    return rows("SELECT * FROM activity ORDER BY id DESC LIMIT ?",(min(100,max(1,int(limit))),))

def identity():
    row=one("SELECT value FROM meta WHERE key='identity'")
    return json.loads(row["value"]) if row else {}

def update_identity(values):
    allowed={"mission","voice","engineering","cost","design","decisions","boundaries","truthfulness"}
    current=identity()
    for key,value in values.items():
        if key not in allowed or not isinstance(value,str) or not 2<=len(value)<=600:
            raise ValueError("Invalid identity field: "+str(key))
        current[key]=value.strip()
    with LOCK, connection() as db:
        db.execute("UPDATE meta SET value=? WHERE key='identity'",(json.dumps(current),))
        db.commit()
    log("identity","Working profile updated")
    return current

def create_task(title,project="",priority="normal",source="local",instructions=""):
    title=title.strip()
    project=project.strip()
    if not isinstance(instructions,str) or len(instructions)>7000:
        raise ValueError("Task instructions must be under 7000 characters")
    instructions=instructions.strip()
    if not 3<=len(title)<=200 or len(project)>90 or priority not in ("low","normal","high"):
        raise ValueError("Invalid task details")
    if project and not one("SELECT id FROM projects WHERE name=?",(project,)):
        raise ValueError("Unknown project")
    if source not in ("local","bridge","dashboard","mcp"):
        raise ValueError("Unknown source")
    with LOCK, connection() as db:
        cur=db.execute("""INSERT INTO tasks(title,project,priority,source,created_at,updated_at,instructions)
            VALUES(?,?,?,?,?,?,?)""",(title,project,priority,source,now(),now(),instructions))
        task_id=cur.lastrowid
        db.commit()
    log("task",f"Task #{task_id} created: {title}")
    try:
        from . import companion_dispatch
        companion_dispatch.enqueue("task",task_id)
    except Exception as exc:
        log("error",f"Task #{task_id} dispatch queue failure: {type(exc).__name__}")
    return one("SELECT * FROM tasks WHERE id=?",(task_id,))

def set_task_status(task_id,status):
    if status not in ("open","awaiting_approval","done"): raise ValueError("Invalid status")
    with LOCK, connection() as db:
        cur=db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?",(status,now(),int(task_id)))
        db.commit()
        if cur.rowcount==0: raise ValueError("Task not found")
    log("task",f"Task #{task_id} marked {status}")
    if status=="done":
        from . import companion_dispatch
        companion_dispatch.mark_completed(task_id)
    return one("SELECT * FROM tasks WHERE id=?",(int(task_id),))

def catalog():
    try:
        data=json.loads(CATALOG.read_text(encoding="utf8"))
        skills=[]
        base=CATALOG.parent.resolve()
        approved=(base,(pathlib.Path.home()/".claude/skills").resolve())
        for s in data.get("registered_skills",[]):
            path=pathlib.Path(s.get("path","")).resolve()
            # Include catalog paths only under the approved toolkit
            if any(path.is_relative_to(root) for root in approved) and (path/"SKILL.md").is_file():
                skills.append({"name":s.get("name",""),"description":s.get("description",""),
                               "path":str(path/"SKILL.md")})
        return {"skills":skills,"count":len(skills),"source":str(CATALOG),"available":True}
    except (OSError,ValueError,TypeError):
        return {"skills":[],"count":0,"source":str(CATALOG),"available":False}

def skill_text(name):
    entries=[s for s in catalog()["skills"] if s["name"]==name]
    if not entries: raise ValueError("Skill not found")
    content=pathlib.Path(entries[0]["path"]).read_text(encoding="utf8")
    return {"name":name,"content":content[:50000],"truncated":len(content)>50000}

def connections():
    from . import integrations
    report=integrations.stored_report()
    observed={v["id"]:v for v in report.get("integrations",[])}
    observed.update({v["id"]:v for v in relay_snapshot().get("services",[])})
    observed.update({v["id"]:v for v in external_connector_relay().get("services",[])})
    result=[
      {"name":"Advertpreneur Skills","kind":"Local library","status":"ready" if catalog()["available"] else "unavailable","description":str(catalog()["count"])+" readable skills"},
      {"name":"Tyrion Local Bridge","kind":"Local command tool","status":"ready","description":"CLI and stdio MCP tools"},
      {"name":"ChatGPT Local Files","kind":"ChatGPT connector","status":"external","description":"ChatGPT-side session connector; not a local autonomous link"},
    ]
    from . import mcp_events
    event_state=mcp_events.status()
    result.append({"name":"ChatGPT Work Events","kind":"MCP 2.0 event subscriptions",
        "status":"connected" if event_state["subscriptions_active"] else "not_connected",
        "description":str(event_state["subscriptions_active"])+" verified subscriptions; "
          +("signed event delivery ready" if event_state["subscriptions_active"] else "requires a ChatGPT Work plugin subscription"),
        "checked_at":None})
    for name,ident,kind in (
       ("Meta Manager","meta_manager","Local MCP"),
       ("Advertpreneur QA","advertpreneur_qa","Local API"),
       ("ShieldPress Security Console","security_fleet","Local inventory"),
       ("WP Lab","wp_lab","Local inventory"),
       ("Advertpreneur GBP","advertpreneur_gbp","Local API health"),
       ("Advert Connect","advert_connect","ChatGPT relay"),
       ("Shopify Development","shopify_development","ChatGPT relay"),
       ("Supabase","supabase","ChatGPT relay"),
       ("Google Business Profile OAuth","gbp_auth","ChatGPT relay"),
       ("GitHub","github","ChatGPT relay"),
       ("Vercel","vercel","ChatGPT relay"),
       ("GSC Wizard","gsc_wizard","Subscription required"),
    ):
        state=observed.get(ident)
        result.append({"name":name,"kind":kind,
            "status":state["status"] if state else "not_connected",
            "description":state.get("detail","Not connected or checked") if state else "No verified adapter yet",
            "checked_at":state.get("checked_at") if state else None})
    return result

def jobs():
    return rows("SELECT * FROM jobs ORDER BY id")

def set_job_enabled(job_id,enabled):
    if type(enabled) is not bool: raise ValueError("enabled must be boolean")
    with LOCK, connection() as db:
        cur=db.execute("UPDATE jobs SET enabled=? WHERE id=?",(int(enabled),job_id))
        db.commit()
        if not cur.rowcount: raise ValueError("Job not found")
    log("automation",f"Job {job_id} {'enabled' if enabled else 'disabled'}")
    return one("SELECT * FROM jobs WHERE id=?",(job_id,))

def mark_job(job_id,status):
    with LOCK,connection() as db:
        db.execute("UPDATE jobs SET last_run=?,status=? WHERE id=?",(now(),status,job_id))
        db.commit()

def relay_snapshot():
    row=one("SELECT value FROM meta WHERE key='chatgpt_relay'")
    try:return json.loads(row["value"]) if row else {"checked_at":None,"services":[]}
    except (ValueError,KeyError):return {"checked_at":None,"services":[]}

def record_advert_connect_relay(records):
    """Explicit ChatGPT-side evidence only, NOT a local connection and no credentials."""
    from urllib.parse import urlsplit
    if not isinstance(records,list) or len(records)>30:raise ValueError("Invalid site records")
    safe=[]
    for r in records:
        if not isinstance(r,dict) or not isinstance(r.get("ok"),bool):raise ValueError("Invalid site status")
        parsed=urlsplit(str(r.get("url","")))
        host=parsed.hostname
        if parsed.scheme!="https" or not host or len(host)>180:raise ValueError("Invalid site host")
        version=str(r.get("version",""))[:40]
        safe.append({"host":host,"ok":r["ok"],"plugin_version":version})
    report={"checked_at":now(),"services":[{"id":"advert_connect","name":"Advert Connect",
      "status":"relay_connected" if any(r["ok"] for r in safe) else "relay_unavailable",
      "mode":"chatgpt_relay","sites":safe,"detail":"Checked using ChatGPT's connected Advert Connect plugin; not directly authenticated by Tyrion."}]}
    with LOCK,connection() as db:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('chatgpt_relay',?)",(json.dumps(report),))
        db.commit()
    log("integration",f"ChatGPT Advert Connect relay updated for {len(safe)} sites")
    return report

CLOUD_CONNECTOR_IDS={"supabase","shopify_development","gbp_auth","github","vercel","gsc_wizard"}

def record_connector_relay(service_id,status,description,metrics=None):
    """Only record ChatGPT-side observations, never OAuth tokens/credentials."""
    if service_id not in CLOUD_CONNECTOR_IDS:raise ValueError("Unknown connector")
    if status not in ("relay_connected","needs_authorization","unavailable","subscription_required"):
        raise ValueError("Unsupported relay status")
    if not isinstance(description,str) or len(description)>320:
        raise ValueError("Invalid relay description")
    metrics=metrics or {}
    if not isinstance(metrics,dict) or len(metrics)>12:
        raise ValueError("Metrics must be a short sanitized dict")
    clean={}
    for key,value in metrics.items():
        if not isinstance(key,str) or not 1<=len(key)<=50 or any(bad in key.lower() for bad in ("key","token","password","secret","email","host")):
            raise ValueError("Unsupported metric key")
        if not isinstance(value,(bool,int,float,str)) or isinstance(value,str) and len(value)>120:
            raise ValueError("Unsupported metric value")
        clean[key]=value
    names={"supabase":"Supabase","shopify_development":"Shopify Development","gbp_auth":"Google Business Profile OAuth","github":"GitHub","vercel":"Vercel","gsc_wizard":"GSC Wizard"}
    datum={"id":service_id,"name":names[service_id],"mode":"chatgpt_relay",
           "status":status,"checked_at":now(),"metrics":clean,"detail":description}
    with LOCK,connection() as db:
        old=db.execute("SELECT value FROM meta WHERE key='external_connector_relay'").fetchone()
        data=json.loads(old["value"]) if old else {"services":[]}
        data["services"]=[v for v in data.get("services",[]) if v.get("id")!=service_id]+[datum]
        data["checked_at"]=now()
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('external_connector_relay',?)",(json.dumps(data),))
        db.commit()
    log("integration",f"ChatGPT relay evidence recorded for {datum['name']}")
    return datum

def external_connector_relay():
    row=one("SELECT value FROM meta WHERE key='external_connector_relay'")
    try:return json.loads(row["value"]) if row else {"checked_at":None,"services":[]}
    except (ValueError,TypeError):return {"checked_at":None,"services":[]}

def approval_requests():
    rows_ = rows("SELECT id,action,title,project,status,created_at,reviewed_at,result_summary,payload FROM approvals ORDER BY id DESC LIMIT 100")
    for item in rows_:
        payload=json.loads(item.pop("payload"))
        # Account identifiers are harmless routing metadata; never expose secrets in approvals.
        item["preview"]={k:v for k,v in payload.items() if k in ("account_id","title","platform","caption","hashtags")}
    return rows_

def create_meta_draft_proposal(account_id,title,platform,caption="",hashtags=None):
    account_id=str(account_id).strip();title=str(title).strip();caption=str(caption)
    hashtags=hashtags or []
    if not (1<=len(account_id)<=120 and account_id.replace("-","").replace("_","").isalnum()):
        raise ValueError("Invalid account ID")
    if not 3<=len(title)<=150 or platform not in ("facebook","instagram","both") or len(caption)>5000:
        raise ValueError("Invalid draft details")
    if not isinstance(hashtags,list) or len(hashtags)>15 or not all(isinstance(h,str) and len(h)<=60 for h in hashtags):
        raise ValueError("Invalid hashtags")
    payload={"account_id":account_id,"title":title,"platform":platform,
             "caption":caption,"hashtags":hashtags}
    with LOCK,connection() as db:
        cursor=db.execute("INSERT INTO approvals(action,title,project,payload,created_at) VALUES(?,?,?,?,?)",
                          ("meta_create_draft",title,"Meta Manager",json.dumps(payload),now()))
        approval_id=cursor.lastrowid
        db.commit()
    log("approval",f"Draft proposal #{approval_id} is awaiting a user decision")
    return next(a for a in approval_requests() if a["id"]==approval_id)

def decide_approval(approval_id,decision):
    """Called only from the authenticated local dashboard, never through MCP tools."""
    if decision not in ("approve","reject"):
        raise ValueError("Unknown approval decision")
    approval_id=int(approval_id)
    with LOCK,connection() as db:
        row=db.execute("SELECT * FROM approvals WHERE id=?",(approval_id,)).fetchone()
        if not row:raise ValueError("Approval not found")
        if row["status"]!="pending":raise ValueError("Approval has already been handled")
        status="executing" if decision=="approve" else "rejected"
        db.execute("UPDATE approvals SET status=?,reviewed_at=? WHERE id=? AND status='pending'",
                   (status,now(),approval_id))
        db.commit()
        payload=json.loads(row["payload"])
        action=row["action"]
    if decision=="reject":
        log("approval",f"Proposal #{approval_id} rejected by operator")
        return next(a for a in approval_requests() if a["id"]==approval_id)
    try:
        if action!="meta_create_draft":raise ValueError("Action not allowlisted")
        from . import integrations
        accounts=integrations.meta_accounts()
        if not any(a["id"]==payload["account_id"] and a["status"]=="connected" for a in accounts):
            raise ValueError("Meta Manager account is unavailable or disconnected")
        result=integrations.meta_call("create_post",payload,approved_write=True)
        # No publishing tool is available in this pathway.
        if not isinstance(result,(dict,list)):raise ValueError("Unexpected action result")
        if isinstance(result,dict) and (result.get("error") or result.get("ok") is False):
            raise RuntimeError("Draft service rejected the operation")
        status="executed";summary="Local draft creation request accepted by Meta Manager"
    except Exception as err:
        # Do not retry automatically: a request can succeed remotely but time out locally.
        status="needs_review";summary=f"Operation outcome uncertain or rejected: {type(err).__name__}; check Meta Manager before retrying"
    with LOCK,connection() as db:
        db.execute("UPDATE approvals SET status=?,result_summary=? WHERE id=?",(status,summary,approval_id))
        db.commit()
    log("approval",f"Proposal #{approval_id}: {status}")
    return next(a for a in approval_requests() if a["id"]==approval_id)

def overview():
    ps=__import__("tyrion.project_hub",fromlist=["mapped_projects"]).mapped_projects()
    ts=tasks()
    ss=catalog()
    cons=connections()
    return {
        "app":{"name":"Tyrion","subtitle":"The Hand","version":"0.8.0","time":now(),
               "mode":"Local-first · No AI API"},
        "counts":{"projects":len(ps),"open_tasks":sum(t["status"]=="open" for t in ts),
                  "approval_tasks":sum(t["status"]=="awaiting_approval" for t in ts),
                  "skills":ss["count"],"connected":sum(c["status"] in ("ready","connected") for c in cons),
                  "inventory":sum(c["status"]=="inventory_only" for c in cons),
                  "relay":sum(c["status"]=="relay_connected" for c in cons)},
        "projects":ps,"tasks":ts[:14],"connections":cons,"jobs":jobs(),
        "activity":activity(),"identity":identity(),"skills_available":ss["available"],
        "integrations":__import__("tyrion.integrations",fromlist=["stored_report"]).stored_report(),
        "approvals":approval_requests(),"chatgpt_relay":relay_snapshot(),
        "external_relay":external_connector_relay(),
    }
