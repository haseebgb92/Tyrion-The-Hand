"""Append-only, attributed project history for Tyrion.

History supplements authoritative projects/tasks. It never marks tasks completed,
edits client sites, or treats old chat claims as live verification.
"""
from __future__ import annotations
import datetime as dt
import re
from . import core

KINDS = {"decision","work_report","verified_local","request","blocker","next_step","context"}
SOURCES = {"prior_conversation","local_document","tyrion_task","local_review","operator"}
TRUST = {"historical_report","documented","verified_at_date","unverified"}
EXCLUDED = {"Fatir","Advertpreneur Vault"}

def setup():
    with core.LOCK,core.connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS project_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            event_date TEXT NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL,
            source TEXT NOT NULL,
            trust TEXT NOT NULL,
            source_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tyrion_project_history ON project_history(project,event_date DESC,id DESC)")
        db.commit()

def add(project,event_date,kind,title,detail,source,trust,source_id):
    if project in EXCLUDED:raise ValueError("This project is excluded from semantic history")
    if not isinstance(project,str) or len(project)>100 or not core.one("SELECT id FROM projects WHERE name=?",(project,)):
        raise ValueError("Project must exist in Tyrion")
    if kind not in KINDS or source not in SOURCES or trust not in TRUST:
        raise ValueError("Unknown source or verification classification")
    try:dt.date.fromisoformat(event_date)
    except (TypeError,ValueError) as e:raise ValueError("Use YYYY-MM-DD date") from e
    if not isinstance(title,str) or not 5<=len(title)<=150:raise ValueError("Invalid history title")
    if not isinstance(detail,str) or not 15<=len(detail)<=1600:raise ValueError("Invalid history details")
    if not isinstance(source_id,str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{8,180}",source_id):
        raise ValueError("Invalid deduplication source ID")
    from . import knowledge
    if not knowledge.scrub(title+" "+detail):
        raise ValueError("Potentially sensitive content: history not stored")
    setup()
    with core.LOCK,core.connection() as db:
        db.execute("""INSERT OR IGNORE INTO project_history(
               project,event_date,kind,title,detail,source,trust,source_id,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
               (project,event_date,kind,title.strip(),detail.strip(),source,trust,source_id,core.now()))
        row=db.execute("SELECT * FROM project_history WHERE source_id=?",(source_id,)).fetchone()
        if row["project"]!=project:raise ValueError("Conflicting source ID")
        db.commit()
    return dict(row)

def list_history(project=None,limit=200):
    setup()
    limit=min(5000,max(1,int(limit)))
    if project:
        return core.rows("""SELECT * FROM project_history WHERE project=?
          ORDER BY event_date DESC,id DESC LIMIT ?""",(project,limit))
    return core.rows("""SELECT * FROM project_history
          ORDER BY event_date DESC,id DESC LIMIT ?""",(limit,))

def coverage():
    setup()
    projects=[p for p in core.projects() if p["name"] not in EXCLUDED]
    counts={r["project"]:r["n"] for r in core.rows(
        "SELECT project,COUNT(*) AS n FROM project_history GROUP BY project")}
    return {"tracked":len(projects),"with_history":sum(bool(counts.get(p["name"])) for p in projects),
            "without_history":[p["name"] for p in projects if not counts.get(p["name"])],
            "history_entries":sum(counts.values()),
            "limitations":"Historical notes are dated and source-labelled; no automatic access to unconnected apps or chat transcripts."}
