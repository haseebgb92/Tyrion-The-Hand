"""Tyrion-owned persistent recurrence, queue and safe local draft execution.

This scheduler is independent of ChatGPT Tasks. ChatGPT is a PULL-BASED handoff:
it can consume due work through a tool during active conversations, but Tyrion
cannot automatically initiate or resume ChatGPT chats.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
import threading
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import core

UTC = dt.timezone.utc
DEFAULT_TZ = "Asia/Karachi"
KINDS = {"blog_draft", "general_task"}
CADENCES = {"daily", "weekly", "once"}
ENGINES = {"chatgpt_handoff", "ollama_local"}
RUN_STATES = {"awaiting_chatgpt", "generating", "draft_ready", "needs_review", "failed", "completed", "cancelled"}
MAX_PENDING_PER_SCHEDULE = 3
CURRENT_WORKER_LOCK = threading.Lock()
CURRENT_WORKER: threading.Thread | None = None

def utcnow() -> dt.datetime:
    return dt.datetime.now(UTC)

def utc_string(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")

def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value).astimezone(UTC)

def check_timezone(value):
    if not isinstance(value,str) or not 1 <= len(value) <= 80:
        raise ValueError("Invalid timezone")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("Unsupported timezone")

def next_occurrence(cadence,time_local,timezone,weekdays=None,after=None,once_date=None):
    """First occurrence strictly after the given instant. All storage is in UTC."""
    zone=check_timezone(timezone)
    after=after or utcnow()
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")
    if not isinstance(time_local,str) or len(time_local)!=5:
        raise ValueError("Time must be HH:MM")
    try:
        hh,mm=map(int,time_local.split(":"))
        if not (0<=hh<24 and 0<=mm<60):raise ValueError()
    except Exception:
        raise ValueError("Time must be HH:MM")
    local_now=after.astimezone(zone)
    today=local_now.date()
    if cadence=="once":
        if not isinstance(once_date,str):raise ValueError("One-time jobs require a date")
        try: day=dt.date.fromisoformat(once_date)
        except ValueError:raise ValueError("Invalid one-time date")
        if day < today:raise ValueError("Date is in the past")
        candidate=dt.datetime.combine(day,dt.time(hh,mm),tzinfo=zone)
        if candidate.astimezone(UTC)<=after:raise ValueError("One-time schedule has passed")
        return utc_string(candidate)
    if cadence not in ("daily","weekly"):raise ValueError("Unsupported cadence")
    if cadence=="weekly":
        if not isinstance(weekdays,list) or not 1<=len(weekdays)<=7:
            raise ValueError("Weekly schedule needs weekdays")
        if not all(type(x) is int and 0<=x<=6 for x in weekdays):
            raise ValueError("Weekdays must be 0–6 (Monday–Sunday)")
    for days in range(0,9):
        date=today+dt.timedelta(days=days)
        if cadence=="weekly" and date.weekday() not in weekdays:continue
        candidate=dt.datetime.combine(date,dt.time(hh,mm),tzinfo=zone)
        # On an ambiguous fall-back clock, explicitly use the first occurrence.
        if candidate.astimezone(UTC)>after:
            return utc_string(candidate)
    raise RuntimeError("Cannot determine next occurrence")

def setup(recover=False):
    core.setup()
    with core.LOCK,core.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS workflow_schedules(
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL, project TEXT NOT NULL,
          kind TEXT NOT NULL, instructions TEXT NOT NULL,
          cadence TEXT NOT NULL, time_local TEXT NOT NULL, timezone TEXT NOT NULL,
          weekdays TEXT NOT NULL DEFAULT '[]', once_date TEXT,
          engine TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1,
          next_run_utc TEXT, last_run_utc TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS workflow_runs(
          id INTEGER PRIMARY KEY,
          schedule_id INTEGER NOT NULL,
          due_at_utc TEXT NOT NULL,
          status TEXT NOT NULL,
          engine TEXT NOT NULL,
          request TEXT NOT NULL,
          generated_title TEXT,
          output_path TEXT,
          summary TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(schedule_id,due_at_utc),
          FOREIGN KEY(schedule_id) REFERENCES workflow_schedules(id));
        CREATE INDEX IF NOT EXISTS ix_workflow_due ON workflow_schedules(enabled,next_run_utc);
        CREATE INDEX IF NOT EXISTS ix_workflow_queue ON workflow_runs(status,created_at);
        """)
        columns={row[1] for row in db.execute("PRAGMA table_info(workflow_schedules)")}
        if "archived" not in columns:
            db.execute("ALTER TABLE workflow_schedules ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
        if recover:
            db.execute("""UPDATE workflow_runs SET status='needs_review',
                          summary='Generation interrupted; inspect before retrying',
                          updated_at=? WHERE status='generating'""",(core.now(),))
        db.commit()

def _sanitize_schedule(item):
    item=dict(item)
    item["weekdays"]=json.loads(item["weekdays"])
    return item

def list_schedules():
    return [_sanitize_schedule(x) for x in
        core.rows("SELECT * FROM workflow_schedules WHERE archived=0 ORDER BY enabled DESC,id DESC")]

def get_schedule(schedule_id):
    row=core.one("SELECT * FROM workflow_schedules WHERE id=? AND archived=0",(int(schedule_id),))
    if not row:raise ValueError("Scheduled workflow not found")
    return _sanitize_schedule(row)

def list_runs(status=None,limit=60):
    if status and status not in RUN_STATES:raise ValueError("Unknown run status")
    limit=min(max(int(limit),1),120)
    query="""SELECT r.id,r.schedule_id,r.due_at_utc,r.status,r.engine,
                 r.generated_title,r.output_path,r.summary,r.created_at,r.updated_at,
                 s.title as schedule_title,s.project,s.kind
              FROM workflow_runs r JOIN workflow_schedules s ON s.id=r.schedule_id"""
    if status:return core.rows(query+" WHERE r.status=? ORDER BY r.id DESC LIMIT ?",(status,limit))
    return core.rows(query+" ORDER BY r.id DESC LIMIT ?",(limit,))

def run_detail(run_id):
    run=core.one("""SELECT r.*,s.title as schedule_title,s.project,s.kind
                    FROM workflow_runs r JOIN workflow_schedules s ON s.id=r.schedule_id
                    WHERE r.id=?""",(int(run_id),))
    if not run:raise ValueError("Run not found")
    run["request"]=json.loads(run["request"])
    return run

def create_schedule(title,project,kind,instructions,cadence,time_local,
                    timezone=DEFAULT_TZ,weekdays=None,once_date=None,
                    engine="chatgpt_handoff",model="",enabled=True):
    if not isinstance(title,str) or not 3<=len(title.strip())<=170:raise ValueError("Title length invalid")
    if not isinstance(project,str) or project not in {x["name"] for x in core.projects()}:
        raise ValueError("Select a known project")
    if kind not in KINDS or cadence not in CADENCES or engine not in ENGINES:
        raise ValueError("Unsupported workflow")
    if not isinstance(instructions,str) or not 15<=len(instructions.strip())<=7000:
        raise ValueError("Write specific task instructions (15–7000 characters)")
    if type(enabled) is not bool:raise ValueError("enabled must be boolean")
    model=str(model).strip()
    if engine=="ollama_local":
        # Local-only model IDs. No cloud models, arbitrary addresses, tokens or shell commands.
        if model not in ("qwen3.5:4b","qwen3.5:0.8b"):
            raise ValueError("Select an installed local model")
    else:model=""
    weekdays=weekdays if weekdays is not None else []
    next_at=next_occurrence(cadence,time_local,timezone,weekdays,once_date=once_date)
    with core.LOCK,core.connection() as db:
        cursor=db.execute("""INSERT INTO workflow_schedules
          (title,project,kind,instructions,cadence,time_local,timezone,weekdays,
           once_date,engine,model,enabled,next_run_utc,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (title.strip(),project,kind,instructions.strip(),cadence,time_local,timezone,
           json.dumps(weekdays),once_date,engine,model,int(enabled),next_at,core.now(),core.now()))
        result_id=cursor.lastrowid
        db.commit()
    core.log("schedule",f"Schedule #{result_id} created: {title.strip()}")
    return get_schedule(result_id)

def set_enabled(schedule_id,enabled):
    if type(enabled) is not bool:raise ValueError("enabled must be boolean")
    schedule=get_schedule(schedule_id)
    next_run=schedule["next_run_utc"]
    if enabled and (not next_run or parse_utc(next_run)<=utcnow()):
        if schedule["cadence"]=="once" and next_run:
            raise ValueError("One-time schedule has already passed")
        next_run=next_occurrence(schedule["cadence"],schedule["time_local"],
             schedule["timezone"],schedule["weekdays"],once_date=schedule["once_date"])
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE workflow_schedules SET enabled=?,next_run_utc=?,updated_at=?
                      WHERE id=?""",(int(enabled),next_run,core.now(),int(schedule_id)))
        db.commit()
    core.log("schedule",f"Schedule #{schedule_id} {'enabled' if enabled else 'paused'}")
    return get_schedule(schedule_id)

def update_schedule(schedule_id,updates):
    if not isinstance(updates,dict):raise ValueError("Invalid schedule changes")
    allowed={"title","project","kind","instructions","cadence","time_local","timezone",
             "weekdays","once_date","engine","model","enabled"}
    if not set(updates).issubset(allowed):raise ValueError("Unsupported schedule field")
    old=get_schedule(schedule_id)
    record={key:updates.get(key,old[key]) for key in allowed}
    title=record["title"];project=record["project"];kind=record["kind"]
    instructions=record["instructions"];cadence=record["cadence"]
    engine=record["engine"];model=str(record["model"] or "").strip()
    if not isinstance(title,str) or not 3<=len(title.strip())<=170:raise ValueError("Title length invalid")
    if project not in {x["name"] for x in core.projects()}:raise ValueError("Select a known project")
    if kind not in KINDS or cadence not in CADENCES or engine not in ENGINES:raise ValueError("Unsupported workflow")
    if not isinstance(instructions,str) or not 15<=len(instructions.strip())<=7000:
        raise ValueError("Instructions must have 15–7000 characters")
    if engine=="ollama_local" and model not in ("qwen3.5:4b","qwen3.5:0.8b"):
        raise ValueError("Select a local Ollama model")
    if engine=="chatgpt_handoff":model=""
    if type(record["enabled"]) is not bool and type(record["enabled"]) is not int:
        raise ValueError("enabled must be boolean")
    next_run=next_occurrence(cadence,record["time_local"],record["timezone"],
                             record["weekdays"],once_date=record["once_date"])
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE workflow_schedules SET title=?,project=?,kind=?,instructions=?,
              cadence=?,time_local=?,timezone=?,weekdays=?,once_date=?,engine=?,model=?,
              enabled=?,next_run_utc=?,updated_at=? WHERE id=? AND archived=0""",
              (title.strip(),project,kind,instructions.strip(),cadence,record["time_local"],
               record["timezone"],json.dumps(record["weekdays"]),record["once_date"],
               engine,model,int(bool(record["enabled"])),next_run,core.now(),int(schedule_id)))
        db.commit()
    core.log("schedule",f"Schedule #{schedule_id} updated (future runs only)")
    return get_schedule(schedule_id)

def archive_schedule(schedule_id):
    s=get_schedule(schedule_id)
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        count=db.execute("SELECT COUNT(*) FROM workflow_runs WHERE schedule_id=? AND status='generating'",
                         (s["id"],)).fetchone()[0]
        if count:raise ValueError("Cannot archive a schedule while a local generation is running")
        db.execute("UPDATE workflow_schedules SET archived=1,enabled=0,next_run_utc=NULL,updated_at=? WHERE id=?",
                   (core.now(),s["id"]))
        db.execute("""UPDATE workflow_runs SET status='cancelled',summary='Cancelled after schedule archived',
                      updated_at=? WHERE schedule_id=? AND status='awaiting_chatgpt'""",
                   (core.now(),s["id"]))
        db.commit()
    core.log("schedule",f"Schedule #{schedule_id} archived; run history retained")
    return {"id":s["id"],"archived":True}

def _request_from_schedule(s):
    from . import skill_router
    suggested=skill_router.route(s["instructions"],limit=5)["skills"]
    return {"title":s["title"],"project":s["project"],"kind":s["kind"],
      "instructions":s["instructions"],"skills":[x["name"] for x in suggested],
      "rules":[
        "No automatic publishing. Deliver a reviewable local draft or documented result.",
        "For a blog: check existing published content and search intent for overlap, and verify factual claims before publishing.",
        "Avoid thin content, fake citations, invented research, or unverified prices and medical claims.",
        "If online research is unavailable, flag claims requiring verification.",
      ],
      "handoff":"ChatGPT must retrieve the request during an active conversation; an MCP server cannot wake ChatGPT.",
    }

def _pending_count(db,schedule_id):
    return db.execute("""SELECT COUNT(*) FROM workflow_runs WHERE schedule_id=?
           AND status IN ('awaiting_chatgpt','generating','needs_review','draft_ready')""",
          (schedule_id,)).fetchone()[0]

def _enqueue_with_db(db,s,when):
    payload=_request_from_schedule(s)
    status="awaiting_chatgpt" if s["engine"]=="chatgpt_handoff" else "generating"
    cursor=db.execute("""INSERT OR IGNORE INTO workflow_runs
        (schedule_id,due_at_utc,status,engine,request,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?)""",
        (s["id"],when,status,s["engine"],json.dumps(payload),core.now(),core.now()))
    return cursor.lastrowid if cursor.rowcount else None

def enqueue_due(now_override=None):
    """Durable, deduplicated enqueuing. One run per schedule per tick, no catch-up storms."""
    now_override=now_override or utcnow()
    if now_override.tzinfo is None:raise ValueError("Clock must be aware")
    now_iso=utc_string(now_override)
    created=[]
    skipped=[]
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        due=db.execute("""SELECT * FROM workflow_schedules WHERE enabled=1 AND archived=0
               AND next_run_utc IS NOT NULL AND next_run_utc<=?
               ORDER BY next_run_utc,id LIMIT 100""",(now_iso,)).fetchall()
        for row in due:
            s=_sanitize_schedule(row)
            scheduled=s["next_run_utc"]
            if s["cadence"]=="once": next_run=None; enabled=0
            else:
                # Advance to the NEXT future occurrence, and skip missed cycles safely.
                next_run=next_occurrence(s["cadence"],s["time_local"],s["timezone"],
                      s["weekdays"],after=now_override)
                enabled=1
            if _pending_count(db,s["id"])>=MAX_PENDING_PER_SCHEDULE:
                skipped.append(s["id"])
            else:
                new_id=_enqueue_with_db(db,s,scheduled)
                if new_id:created.append(new_id)
            db.execute("""UPDATE workflow_schedules SET next_run_utc=?,last_run_utc=?,
                       enabled=?,updated_at=? WHERE id=?""",
                       (next_run,scheduled,enabled,core.now(),s["id"]))
        db.commit()
    for run_id in created:core.log("schedule",f"Scheduled run #{run_id} queued")
    for schedule_id in skipped:core.log("schedule",f"Schedule #{schedule_id} skipped: review queue full")
    return created

def run_now(schedule_id):
    """Explicit manual run. Never dispatch external work directly."""
    s=get_schedule(schedule_id)
    instant=utcnow()
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if _pending_count(db,s["id"])>=MAX_PENDING_PER_SCHEDULE:
            raise ValueError("Schedule has three pending runs; complete or review them first")
        # Manual invocations need microsecond identity; second precision can collide.
        run_id=_enqueue_with_db(db,s,instant.isoformat(timespec="microseconds"))
        db.commit()
    if not run_id:raise RuntimeError("Run already exists")
    core.log("schedule",f"Manual run #{run_id} queued")
    return run_detail(run_id)

def pending_chatgpt(limit=15):
    """Safe pull interface for ChatGPT's Local Files or custom MCP integration."""
    ids=core.rows("""SELECT id FROM workflow_runs
                     WHERE status='awaiting_chatgpt'
                     ORDER BY due_at_utc,id LIMIT ?""",(min(max(int(limit),1),50),))
    return [run_detail(r["id"]) for r in ids]

def submit_chatgpt_result(run_id,title,markdown,needs_review=True):
    """Accept content from an active ChatGPT interaction; never publish automatically."""
    run=run_detail(run_id)
    if run["status"]!="awaiting_chatgpt" or run["engine"]!="chatgpt_handoff":
        raise ValueError("Run is not awaiting a ChatGPT result")
    return _store_draft(run,title,markdown,"chatgpt_handoff")

def _store_draft(run,title,markdown,origin):
    if not isinstance(title,str) or not 5<=len(title.strip())<=190:
        raise ValueError("Draft title must be 5–190 characters")
    if not isinstance(markdown,str) or not 200<=len(markdown)<=120000:
        raise ValueError("Draft body must be 200–120000 characters")
    directory=core.DATA/"generated"
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    target=directory/f"tyrion-run-{int(run['id']):06d}.md"
    tmp=directory/f".tyrion-run-{int(run['id']):06d}.tmp"
    content=f"# {title.strip()}\n\n"+markdown.lstrip()
    # Serialize draft submissions across processes via SQLite's write transaction.
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        latest=db.execute("SELECT status FROM workflow_runs WHERE id=?",(int(run["id"]),)).fetchone()
        if not latest or latest["status"] not in ("awaiting_chatgpt","generating"):
            raise ValueError("Run was already handled or changed state")
        tmp.write_text(content,encoding="utf8")
        tmp.chmod(0o600)
        tmp.replace(target)
        db.execute("""UPDATE workflow_runs SET status='draft_ready',
               generated_title=?,output_path=?,summary=?,updated_at=?
               WHERE id=?""",
               (title.strip(),str(target),"Local draft saved for editorial and duplication review",core.now(),run["id"]))
        db.commit()
    core.log("schedule",f"Draft for run #{run['id']} ready from {origin}")
    return run_detail(run["id"])

def ready_drafts(limit=20):
    ids=core.rows("""SELECT id FROM workflow_runs
          WHERE status='draft_ready' ORDER BY due_at_utc DESC,id DESC LIMIT ?""",
          (min(max(int(limit),1),80),))
    return [run_detail(item["id"]) for item in ids]

def read_run_draft(run_id):
    run=run_detail(run_id)
    if not run["output_path"]:raise ValueError("Run has no generated draft")
    target=pathlib.Path(run["output_path"]).resolve()
    if not target.is_relative_to((core.DATA/"generated").resolve()):
        raise ValueError("Draft path is outside the generated directory")
    text=target.read_text(encoding="utf8")
    return {"run_id":run["id"],"title":run["generated_title"],
            "markdown":text[:45000],"truncated":len(text)>45000,
            "instructions":run["request"]["instructions"]}

def revise_run_draft(run_id,title,markdown):
    """Human/ChatGPT review saves a versioned local draft; never publishes."""
    run=run_detail(run_id)
    if run["status"]!="draft_ready":raise ValueError("Run is not ready for revision")
    if not isinstance(title,str) or not 5<=len(title.strip())<=190:raise ValueError("Invalid title")
    if not isinstance(markdown,str) or not 200<=len(markdown)<=120000:raise ValueError("Invalid draft content")
    root=core.DATA/"generated"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    nonce=utcnow().strftime("%Y%m%d%H%M%S%f")
    target=root/f"tyrion-run-{run['id']:06d}-review-{nonce}.md"
    tmp=root/f".tyrion-run-{run['id']:06d}-review-{nonce}.tmp"
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        latest=db.execute("SELECT status FROM workflow_runs WHERE id=?",(run["id"],)).fetchone()
        if not latest or latest["status"]!="draft_ready":raise ValueError("Review state changed")
        tmp.write_text(f"# {title.strip()}\n\n"+markdown.lstrip(),encoding="utf8")
        tmp.chmod(0o600);tmp.replace(target)
        db.execute("""UPDATE workflow_runs SET generated_title=?,output_path=?,
              summary=?,updated_at=? WHERE id=?""",
              (title.strip(),str(target),"Revised draft saved; previous version retained",core.now(),run["id"]))
        db.commit()
    core.log("schedule",f"Run #{run['id']} revised; awaiting publication approval")
    return run_detail(run["id"])

def complete_run(run_id):
    run=run_detail(run_id)
    if run["status"] not in ("draft_ready","needs_review","failed"):
        raise ValueError("Run must have a reviewable outcome first")
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE workflow_runs SET status='completed',updated_at=?
              WHERE id=?""",(core.now(),run["id"]))
        db.commit()
    return run_detail(run["id"])

def local_model_available(model):
    if model not in ("qwen3.5:4b","qwen3.5:0.8b"):return False
    req=urllib.request.Request("http://127.0.0.1:11434/api/tags")
    with urllib.request.urlopen(req,timeout=2) as r:
        names={v.get("name") for v in json.load(r).get("models",[])}
    return model in names

def _generate_model_draft(run_id):
    run=run_detail(run_id)
    s=get_schedule(run["schedule_id"])
    try:
        if not local_model_available(s["model"]):
            raise RuntimeError("Local Ollama model unavailable")
        request=run["request"]
        task=request["instructions"]
        if request["kind"]=="blog_draft":
            prompt=("Create an original, detailed and useful blog DRAFT for editorial review.\n"
                "DO NOT invent news, statistics, websites, or sources. Mark claims needing research.\n"
                "Do not publish; no internet access is assumed. Use clear headings and helpful sections.\n"
                "Avoid medical advice or unsubstantiated product claims.\n"
                "OUTPUT Markdown content only with an original title.\n\n"
                f"Brand/project: {request['project']}\nJob: {task}\n")
        else:
            prompt=("Prepare a practical, detailed Markdown WORK PRODUCT for an operations assignment.\n"
                "Do not claim tools were used or steps executed. Flag any information requiring verification.\n"
                "Include a clear objective, researched-or-unknown inputs, a stepwise plan, safety checks and outcomes.\n"
                "Do not publish, modify systems, or send external messages.\n\n"
                f"Project: {request['project']}\nJob: {task}\n")
        # Retrieval is local-only and project-scoped: no other client task notes
        # enter a scheduled model prompt. Failure never blocks the original job.
        try:
            from . import knowledge
            context=knowledge.project_context(request.get("project",""),task)
            if context:prompt+="\n\nRelevant existing reference material:\n"+context+"\n"
        except Exception:
            # Retrieval is optional. A broken/mocked search must never fail draft generation.
            pass
        body=json.dumps({"model":s["model"],"prompt":prompt,"stream":False,"think":False,
                         "options":{"num_predict":1400,"temperature":0.55},
                         "keep_alive":"0s"}).encode("utf8")
        req=urllib.request.Request("http://127.0.0.1:11434/api/generate",body,
                 {"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=210) as response:
            text=json.load(response).get("response","")
        if not isinstance(text,str) or len(text)<500:
            raise RuntimeError("Local model returned an insufficient draft")
        lines=[x for x in text.splitlines() if x.strip()]
        title=lines[0].lstrip("# ").strip()[:185] if lines else s["title"]
        if len(title)<5:title=s["title"]
        _store_draft(run,title,text,"local Ollama")
    except Exception as exc:
        with core.LOCK,core.connection() as db:
            db.execute("""UPDATE workflow_runs SET status='needs_review',
                   summary=?,updated_at=? WHERE id=? AND status='generating'""",
                   (f"Local generation unavailable or failed: {type(exc).__name__}. Review before retrying.",core.now(),run_id))
            db.commit()
        core.log("schedule",f"Local generation run #{run_id} requires review: {type(exc).__name__}")

def dispatch_local_generations():
    global CURRENT_WORKER
    with CURRENT_WORKER_LOCK:
        if CURRENT_WORKER and CURRENT_WORKER.is_alive():return
        row=core.one("""SELECT id FROM workflow_runs WHERE status='generating'
                       AND engine='ollama_local' ORDER BY id LIMIT 1""")
        if row:
            CURRENT_WORKER=threading.Thread(target=_generate_model_draft,args=(row["id"],),daemon=True)
            CURRENT_WORKER.start()

def dispatcher_status():
    result=core.one("SELECT value FROM meta WHERE key='dispatcher_status'")
    if result:
        try:return json.loads(result["value"])
        except ValueError:pass
    return {"configured":False,"cadence":None,"last_callback":None,"jobs_reported":0}

def configure_dispatcher(cadence="hourly at minute 10"):
    # Explicitly configured externally through ChatGPT's scheduled-task service.
    state=dispatcher_status()
    state.update({"configured":True,"cadence":cadence})
    with core.LOCK,core.connection() as db:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('dispatcher_status',?)",(json.dumps(state),))
        db.commit()
    core.log("schedule","ChatGPT queue dispatcher configured; awaiting first real callback")
    return state

def record_dispatcher_callback(processed=0):
    if type(processed) is not int or not 0<=processed<=2:raise ValueError("Processed count must be 0–2")
    state=dispatcher_status()
    if not state.get("configured"):raise ValueError("No configured dispatcher")
    state["last_callback"]=core.now()
    state["jobs_reported"]=state.get("jobs_reported",0)+processed
    with core.LOCK,core.connection() as db:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('dispatcher_status',?)",(json.dumps(state),))
        db.commit()
    core.log("schedule",f"ChatGPT dispatcher callback received; {processed} jobs reported completed")
    return state

def summary():
    schedules=list_schedules()
    runs=list_runs(limit=70)
    return {"schedules":schedules,"runs":runs,"dispatcher":dispatcher_status(),
      "counts":{"schedules":len(schedules),
                "active":sum(bool(s["enabled"]) for s in schedules),
                "awaiting_chatgpt":sum(x["status"]=="awaiting_chatgpt" for x in runs),
                "drafts_ready":sum(x["status"]=="draft_ready" for x in runs)},
      "limitations":"Tyrion cannot proactively invoke the ChatGPT website through MCP; ChatGPT must fetch queued work while active."}

def seed_coocoobabys():
    """Existing requested example: daily 8 PM PKT, ChatGPT handoff, no automatic posting."""
    if core.one("SELECT id FROM workflow_schedules WHERE title=?",
                ("CooCoo Babys — Daily SEO Blog",)):
        return
    create_schedule(
      title="CooCoo Babys — Daily SEO Blog",project="CooCoo Babys",
      kind="blog_draft",cadence="daily",time_local="20:00",timezone=DEFAULT_TZ,
      engine="chatgpt_handoff",
      instructions=(
        "Prepare one original, useful US-market parenting or baby-products blog post for coocoobabys.com. "
        "Before choosing a topic, search the website's existing published and draft articles through Advert Connect; "
        "avoid duplicate topics and search-intent cannibalization. Consult installed SEO and content skills. "
        "Research and verify current factual claims, include natural internal links to real site pages and "
        "support any potentially sensitive claims with reliable sources. Use a meaningful heading structure, "
        "clear US English, informative depth and a relevant SEO title/meta description. "
        "Save a complete draft for quality review first. Never auto-publish from this scheduler."
      ))
