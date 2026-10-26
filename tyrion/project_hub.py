"""Verified project/resource directory for Tyrion.
Sources are either explicitly known project references or local inventory.
Never infer completion, health or ownership from a project name.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from . import core

_INITIALIZED_DB=None

# Stable, evidence-backed references only. Do not fabricate unknown client URLs.
SEED_PROJECTS=[
 ("Tyrion – The Hand","Local operations / automation",None),
 ("Advertpreneur GBP","Local business / GBP",None),
 ("Advertpreneur QA","Website quality monitoring",None),
 ("Advertpreneur Remote","Android remote support",None),
 ("Advertpreneur Vault","Credential broker",None),
 ("Advertpreneur Prospect Intelligence","Client acquisition / prospecting",None),
 ("AURA Desktop","Linux Mint utilities",None),
 ("Kaufler Law","WordPress client","https://kauflerlaw.com"),
 ("Heaven in Style","Shopify courses","https://heaveninstyle.com"),
 ("CaliCurves Fajas","Shopify seminar landing","https://calicurvesfajas.com"),
 ("JRG Electric","WordPress client","https://jrgelectricinc.com"),
 ("Artigaps","WordPress support","https://artigaps.com"),
 ("WP Lab","WordPress testing and staging",None),
 ("Fatir","Linux desktop assistant",None),
 ("AURA Download Manager","Linux download management",None),
 ("ChatGPT MCP Bridge","Local MCP integration",None),
 ("Advertpreneur CLI","Developer tooling",None),
 ("E92 Keyword Explorer","SEO keyword research",None),
]
FOLDER_MAP={
  "Tyrion – The Hand":"Documents/Tyrion-The-Hand",
  "Advertpreneur GBP":"Documents/Advertpreneur-GBP",
  "Advertpreneur Remote":"Documents/Advertpreneur-Remote",
  "Advertpreneur Vault":"Documents/Advertpreneur-Vault",
  "Glissimo":"Downloads/Glimsco",
  "Meta Manager":"Downloads/meta-manager",
  "Advert Connect":"Downloads/Advertpreneur-Connect-Agensi",
  "CaliCurves Fajas":"Downloads/CaliCurves-TikTok-Seminar-Shopify",
  "Advertpreneur Prospect Intelligence":"Downloads/Advertpreneur-Prospect-Intelligence",
 "WP Lab":"Downloads/WP Lab",
 "ChatGPT MCP Bridge":"Downloads/ChatGPT-MCP-Bridge",
}
REPOSITORY_MAP={
 "Advert Connect":("advertpreneur-connect","https://github.com/haseebgb92/advertpreneur-connect"),
 "WP Lab":("WP-Lab","https://github.com/haseebgb92/WP-Lab"),
 "Meta Manager":("meta-manager","https://github.com/haseebgb92/meta-manager"),
 "Fatir":("Fatir","https://github.com/haseebgb92/Fatir"),
 "AURA Download Manager":("AURA-Download-Manager","https://github.com/haseebgb92/AURA-Download-Manager"),
 "ChatGPT MCP Bridge":("ChatGPT-MCp","https://github.com/haseebgb92/ChatGPT-MCp"),
 "Advertpreneur CLI":("advertpreneur-cli","https://github.com/haseebgb92/advertpreneur-cli"),
 "E92 Keyword Explorer":("e92","https://github.com/haseebgb92/e92"),
}
SITE_MAP={
 "Advertpreneur":"https://advertpreneur.com",
 "CooCoo Babys":"https://coocoobabys.com",
 "Azucar Cuban Bakery":"https://www.azucarcubanbakery.com",
 "Axxess VIP":"https://axxess.vip",
}
# These indicate domain/site associations, NOT a successful API authorization.
SERVICE_PROJECTS={
 "meta_manager":("Meta Manager","Advertpreneur"),
 "advertpreneur_qa":("Advertpreneur QA","CooCoo Babys","Advertpreneur"),
 "security_fleet":("ShieldPress","CooCoo Babys"),
 "wp_lab":("Taiyo Munch","Glissimo","Kaufler Law","Advertpreneur"),
 "advertpreneur_gbp":("Advertpreneur GBP","Advertpreneur"),
 "advert_connect":("CooCoo Babys","Advertpreneur"),
 "supabase":("Advert Connect",),
 "github":("Advert Connect","Meta Manager","WP Lab","Fatir","AURA Download Manager","ChatGPT MCP Bridge","Advertpreneur CLI","E92 Keyword Explorer"),
 "vercel":("Meta Manager","Advert Connect"),
 "gsc_wizard":("CooCoo Babys","Advertpreneur"),
 "shopify_development":("Advertpreneur",),
}

def initialize():
    global _INITIALIZED_DB
    if _INITIALIZED_DB==str(core.DB):return
    core.setup()
    with core.LOCK,core.connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS project_resources(
          id INTEGER PRIMARY KEY, project_name TEXT NOT NULL,
          label TEXT NOT NULL, kind TEXT NOT NULL, locator TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual', created_at TEXT NOT NULL,
          UNIQUE(project_name,kind,locator))""")
        for name,category,url in SEED_PROJECTS:
            db.execute("INSERT OR IGNORE INTO projects(name,category,updated_at) VALUES(?,?,?)",
                       (name,category,core.now()))
        for name,url in SITE_MAP.items():
            if not db.execute("SELECT 1 FROM projects WHERE name=?",(name,)).fetchone():continue
            db.execute("""INSERT OR IGNORE INTO project_resources
                (project_name,label,kind,locator,source,created_at)
                VALUES(?,?,?,?,?,?)""",(name,"Website","website",url,"known_project",core.now()))
        from pathlib import Path
        for name,relative in FOLDER_MAP.items():
            folder=(Path.home()/relative).resolve()
            if folder.is_dir() and db.execute("SELECT 1 FROM projects WHERE name=?",(name,)).fetchone():
                db.execute("""INSERT OR IGNORE INTO project_resources
                    (project_name,label,kind,locator,source,created_at)
                    VALUES(?,?,?,?,?,?)""",(name,"Local project files","local_folder",str(folder),"local_inventory",core.now()))
        for name,(repo,link) in REPOSITORY_MAP.items():
            if db.execute("SELECT 1 FROM projects WHERE name=?",(name,)).fetchone():
                db.execute("""INSERT OR IGNORE INTO project_resources
                    (project_name,label,kind,locator,source,created_at)
                    VALUES(?,?,?,?,?,?)""",(name,"GitHub: "+repo,"repository",link,"chatgpt_verified",core.now()))
        for name,category,url in SEED_PROJECTS:
            if url:
                db.execute("""INSERT OR IGNORE INTO project_resources
                    (project_name,label,kind,locator,source,created_at)
                    VALUES(?,?,?,?,?,?)""",(name,"Website","website",url,"known_project",core.now()))
        db.commit()
    _INITIALIZED_DB=str(core.DB)

def _project_exists(name):
    return core.one("SELECT id FROM projects WHERE name=?",(name,)) is not None

def create_project(name,category):
    if not isinstance(name,str) or not 2<=len(name.strip())<=90:
        raise ValueError("Project name must contain 2–90 characters")
    if not isinstance(category,str) or not 3<=len(category.strip())<=120:
        raise ValueError("Category must contain 3–120 characters")
    with core.LOCK,core.connection() as db:
        db.execute("INSERT INTO projects(name,category,updated_at) VALUES(?,?,?)",
                   (name.strip(),category.strip(),core.now()))
        db.commit()
    core.log("project",f"Registered project {name.strip()}")
    return core.one("SELECT * FROM projects WHERE name=?",(name.strip(),))

def update_project(name,category,notes=""):
    """Update a local project brief; triggers project.updated in the shared change feed."""
    initialize()
    if not _project_exists(name):raise ValueError("Project not found")
    if not isinstance(category,str) or not 3<=len(category.strip())<=120:
        raise ValueError("Category must contain 3–120 characters")
    if not isinstance(notes,str) or len(notes)>1800:
        raise ValueError("Project notes must be 1800 characters or less")
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE projects SET category=?,notes=?,updated_at=? WHERE name=?""",
                   (category.strip(),notes.strip(),core.now(),name))
        db.commit()
    core.log("project",f"Project {name} brief updated")
    return core.one("SELECT * FROM projects WHERE name=?",(name,))

def add_resource(project,label,kind,locator):
    if not _project_exists(project):raise ValueError("Project not found")
    if kind not in ("website","local_folder","repository"):
        raise ValueError("Unsupported resource kind")
    if not isinstance(label,str) or not 2<=len(label.strip())<=90:
        raise ValueError("Invalid label")
    if kind=="website":
        parsed=urlsplit(str(locator))
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Website must be an HTTPS URL without embedded credentials")
        locator=parsed.scheme+"://"+parsed.netloc+parsed.path.rstrip("/")
    elif kind=="local_folder":
        from pathlib import Path
        resolved=__import__("pathlib").Path(locator).expanduser().resolve()
        home=__import__("pathlib").Path.home().resolve()
        # limit project resource introspection to user's Documents/Downloads project folders
        if not (resolved.is_relative_to(home/"Documents") or resolved.is_relative_to(home/"Downloads")):
            raise ValueError("Local path outside approved project folders")
        locator=str(resolved)
    else:
        parsed=urlsplit(str(locator))
        if parsed.scheme!="https" or parsed.hostname not in ("github.com","gitlab.com"):
            raise ValueError("Repository URL must be HTTPS GitHub/GitLab")
        locator=str(locator)
    with core.LOCK,core.connection() as db:
        cursor=db.execute("""INSERT OR IGNORE INTO project_resources
        (project_name,label,kind,locator,source,created_at) VALUES(?,?,?,?,?,?)""",
        (project,label.strip(),kind,str(locator),"manual",core.now()))
        db.commit()
        rid=cursor.lastrowid
    return {"id":rid,"project_name":project,"label":label,"kind":kind,"locator":locator}

def resources():
    return core.rows("SELECT * FROM project_resources ORDER BY project_name COLLATE NOCASE,kind,label")

def mapped_projects():
    initialize()
    from . import integrations
    live=integrations.stored_report().get("integrations",[])
    relay=core.relay_snapshot().get("services",[])
    # Merge strictly observed integration statuses, never infer that projects are live.
    state={v["id"]:v for v in live}
    state.update({v["id"]:v for v in relay})
    state.update({v["id"]:v for v in core.external_connector_relay().get("services",[])})
    import datetime
    for item in state.values():
        if item.get("mode")!="chatgpt_relay" or item.get("status")!="relay_connected":continue
        try:
            age=datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(item["checked_at"]).astimezone(datetime.timezone.utc)
            if age.total_seconds()>86400:item["status"]="relay_stale"
        except (ValueError,KeyError,TypeError):item["status"]="relay_stale"
    attached={}
    for item in resources():
        attached.setdefault(item["project_name"],[]).append(item)
    activity=core.rows("""SELECT project,COUNT(*) as total,
             SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as open_count
             FROM tasks WHERE project!='' GROUP BY project""")
    task_counts={a["project"]:a for a in activity}
    try:
        from . import workflow_scheduler as scheduler
        schedules=scheduler.list_schedules()
    except Exception:schedules=[]
    byschedule={}
    for item in schedules:byschedule[item["project"]]=byschedule.get(item["project"],0)+1
    result=[]
    for project in core.projects():
        project=dict(project)
        name=project["name"]
        project["resources"]=attached.get(name,[])
        project["tasks_open"]=task_counts.get(name,{}).get("open_count",0) or 0
        project["schedules"]=byschedule.get(name,0)
        project["connectors"]=[]
        for ident,names in SERVICE_PROJECTS.items():
            if name not in names:continue
            evidence=state.get(ident)
            status=evidence.get("status","not_checked") if evidence else "not_checked"
            if ident=="advert_connect" and evidence:
                hosts={x["host"]:x["ok"] for x in evidence.get("sites",[])}
                site=next((r["locator"] for r in project["resources"] if r["kind"]=="website"),None)
                host=urlsplit(site).hostname if site else None
                if host not in hosts or not hosts[host]:
                    status="not_verified_for_project"
            project["connectors"].append({
                "id":ident,"status":status,"mode":evidence.get("mode","") if evidence else "",
                "checked_at":evidence.get("checked_at") if evidence else None})
        result.append(project)
    return result
