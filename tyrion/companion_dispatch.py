"""Persistent ChatGPT handoff queue, authoritative on the Tyrion PC.

A handoff is not task execution or task completion. Transitions are evidence-based:
queued -> claimed -> opened -> submitted -> progressing -> completed. No
automatic re-submission of uncertain/failed attempts; recovery is operator-only.
"""
from __future__ import annotations
import datetime as dt
import json
import sqlite3
from . import core

STATUSES=("queued","claimed","opened","submitted","progressing","needs_attention","completed","cancelled")
SETUP_SQL="""
CREATE TABLE IF NOT EXISTS companion_dispatch(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK(kind IN ('task','run')),
  entity_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  claimed_at TEXT,
  opened_at TEXT,
  submitted_at TEXT,
  last_error TEXT NOT NULL DEFAULT '',
  browser_tab_id INTEGER,
  attempt INTEGER NOT NULL DEFAULT 0,
  UNIQUE(kind,entity_id)
);
CREATE TABLE IF NOT EXISTS companion_dispatch_heartbeat (
  key TEXT PRIMARY KEY,
  last_seen TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
DROP TRIGGER IF EXISTS companion_dispatch_created_event;
DROP TRIGGER IF EXISTS companion_dispatch_changed_event;
"""

def setup():
    with core.LOCK, core.connection() as db:
        db.executescript(SETUP_SQL)
        db.commit()

def _row(kind,entity_id):
    return core.one("SELECT * FROM companion_dispatch WHERE kind=? AND entity_id=?",
                    (kind,int(entity_id)))

def enqueue(kind,entity_id,requested=False):
    if kind not in ("task","run"):raise ValueError("Invalid dispatch kind")
    entity_id=int(entity_id)
    if kind=="task":
        task=core.one("SELECT id,status,source FROM tasks WHERE id=?",(entity_id,))
        if not task:raise ValueError("Task not found")
        if task["status"]!="open":raise ValueError("Only open tasks may be dispatched")
        if not requested and task["source"]=="mcp":return None
        # If a task was already handled through ChatGPT, never dispatch it again automatically.
        if not requested and core.one("SELECT id FROM task_updates WHERE task_id=? AND source='chatgpt' LIMIT 1",(entity_id,)):
            return None
    else:
        from . import workflow_scheduler as workflows
        run=workflows.run_detail(entity_id)
        if run["status"] not in ("awaiting_chatgpt","failed"):
            raise ValueError("Only waiting or blocked scheduled runs may be dispatched")
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("INSERT OR IGNORE INTO companion_dispatch(kind,entity_id,status,created_at,updated_at) VALUES(?,?,?,?,?)",
            (kind,entity_id,"queued",core.now(),core.now()))
        db.commit()
    return _row(kind,entity_id)

def list_queue(limit=100):
    setup()
    rows=core.rows("""SELECT d.*,
         CASE WHEN d.kind='task' THEN t.title ELSE s.title END AS title,
         CASE WHEN d.kind='task' THEN t.project ELSE s.project END AS project,
         t.status AS task_status
         FROM companion_dispatch d
         LEFT JOIN tasks t ON d.kind='task' AND t.id=d.entity_id
         LEFT JOIN workflow_runs wr ON d.kind='run' AND wr.id=d.entity_id
         LEFT JOIN workflow_schedules s ON wr.schedule_id=s.id
         ORDER BY CASE d.status WHEN 'queued' THEN 0 WHEN 'needs_attention' THEN 1
           WHEN 'claimed' THEN 2 WHEN 'opened' THEN 3 WHEN 'submitted' THEN 4
           WHEN 'progressing' THEN 5 ELSE 6 END, d.id DESC LIMIT ?""",
         (min(150,max(1,int(limit))),))
    return rows

def summary():
    data=list_queue()
    types={}
    for d in data:types[d["status"]]=types.get(d["status"],0)+1
    hb=core.one("SELECT last_seen,detail FROM companion_dispatch_heartbeat WHERE key='chrome'")
    live=False
    if hb:
        try:
            seen=dt.datetime.fromisoformat(hb["last_seen"])
            live=(dt.datetime.now().astimezone()-seen).total_seconds()<125
        except (ValueError,TypeError):pass
    return {"counts":types,"queue":data,
        "browser":{"connected_recently":live,"last_seen":hb["last_seen"] if hb else None,
                   "detail":hb["detail"] if hb else ""},
        "mode":"PC-owned durable queue; browser extension starts regular ChatGPT Chat once"}

def heartbeat(info=""):
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("""INSERT INTO companion_dispatch_heartbeat(key,last_seen,detail) VALUES('chrome',?,?)
            ON CONFLICT(key) DO UPDATE SET last_seen=excluded.last_seen,detail=excluded.detail""",
            (core.now(),str(info)[:120]))
        db.commit()
    return {"ok":True}

def claim():
    """Atomic claim. Never claim stale or already submitted work automatically."""
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("""SELECT id,kind,entity_id FROM companion_dispatch
                       WHERE status='queued' ORDER BY id LIMIT 1""").fetchone()
        if not row:
            db.commit()
            return None
        if row["kind"]=="task":
            t=db.execute("SELECT status FROM tasks WHERE id=?",(row["entity_id"],)).fetchone()
            if not t or t["status"]!="open":
                db.execute("UPDATE companion_dispatch SET status='cancelled',updated_at=? WHERE id=?",(core.now(),row["id"]))
                db.commit()
                return None
        db.execute("""UPDATE companion_dispatch SET status='claimed',claimed_at=?,
                  updated_at=?,attempt=attempt+1 WHERE id=?""",(core.now(),core.now(),row["id"]))
        db.commit()
        return dict(row)

def report(dispatch_id,stage,tab_id=None,error=""):
    stage=str(stage)
    if stage not in ("opened","submitted","needs_attention"):
        raise ValueError("Invalid dispatch report")
    dispatch_id=int(dispatch_id)
    setup()
    with core.LOCK,core.connection() as db:
        row=db.execute("SELECT * FROM companion_dispatch WHERE id=?",(dispatch_id,)).fetchone()
        if not row:raise ValueError("Dispatch not found")
        legal={"claimed":("opened","needs_attention"),
               "opened":("submitted","needs_attention")}
        if stage not in legal.get(row["status"],()):
            raise ValueError("Dispatch state cannot move from "+row["status"]+" to "+stage)
        tab=tab_id if isinstance(tab_id,int) and 0<tab_id<100000000 else None
        db.execute("""UPDATE companion_dispatch SET status=?,updated_at=?,
          opened_at=CASE WHEN ?='opened' THEN ? ELSE opened_at END,
          submitted_at=CASE WHEN ?='submitted' THEN ? ELSE submitted_at END,
          last_error=?,browser_tab_id=COALESCE(?,browser_tab_id)
          WHERE id=?""",(stage,core.now(),stage,core.now(),stage,core.now(),
                          str(error or "")[:200],tab,dispatch_id))
        db.commit()
    return core.one("SELECT * FROM companion_dispatch WHERE id=?",(dispatch_id,))

def mark_progress(task_id):
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE companion_dispatch SET status='progressing',updated_at=?
                    WHERE kind='task' AND entity_id=? AND status IN
                    ('queued','claimed','opened','submitted','needs_attention')""",
                    (core.now(),int(task_id)))
        db.commit()

def mark_completed(task_id):
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE companion_dispatch SET status='completed',updated_at=?
                    WHERE kind='task' AND entity_id=? AND status NOT IN ('completed','cancelled')""",
                    (core.now(),int(task_id)))
        db.commit()

def manual(kind,entity_id,action):
    if kind not in ("task","run"):raise ValueError("Unknown kind")
    if action not in ("queue","retry","cancel"):raise ValueError("Unknown dispatch action")
    entity_id=int(entity_id)
    if action=="queue":
        return enqueue(kind,entity_id,requested=True)
    setup()
    row=_row(kind,entity_id)
    if not row:raise ValueError("No dispatch exists for this item")
    if action=="retry":
        if row["status"] not in ("needs_attention","cancelled","opened","submitted","progressing"):
            raise ValueError("Only blocked or previously started items can be manually resumed")
        if kind=="task":
            t=core.one("SELECT status FROM tasks WHERE id=?",(entity_id,))
            if not t or t["status"]!="open":raise ValueError("Task not open")
        target="queued"
    else:
        if row["status"] in ("completed","cancelled"):return row
        target="cancelled"
    with core.LOCK,core.connection() as db:
        db.execute("""UPDATE companion_dispatch SET status=?,updated_at=?,last_error='' WHERE id=?""",
                   (target,core.now(),row["id"]))
        db.commit()
    return _row(kind,entity_id)


def sync_waiting_runs():
    """Durably enqueue due ChatGPT schedules independently of Chrome/browser age."""
    from . import workflow_scheduler as workflows
    for run in workflows.list_runs(status="awaiting_chatgpt",limit=80):
        try:enqueue("run",run["id"])
        except ValueError:continue
