"""Tyrion shared change feed: one source of truth for both local UI and ChatGPT.

Writes are journaled by SQLite triggers, so changes made through dashboard, CLI, or
MCP are all visible. The journal does NOT wake ChatGPT: an authorized client
consumes it when the client is active or its scheduled task runs.
"""
from __future__ import annotations

from . import core

SYNC_KEY="chatgpt_change_cursor"

def setup():
    core.setup()
    with core.LOCK,core.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS change_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL, entity_type TEXT NOT NULL,
          entity_id INTEGER NOT NULL, project TEXT NOT NULL DEFAULT '',
          summary TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_change_event_id ON change_events(id);
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_project_added AFTER INSERT ON projects
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('project.created','project',NEW.id,NEW.name,NEW.name,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_project_changed AFTER UPDATE ON projects
        WHEN OLD.name<>NEW.name OR OLD.category<>NEW.category OR OLD.status<>NEW.status OR OLD.notes<>NEW.notes
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('project.updated','project',NEW.id,NEW.name,NEW.name,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_project_resource_added AFTER INSERT ON project_resources
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          SELECT 'project.updated','project',p.id,p.name,'Resource added: '||NEW.label,
                 strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM projects p WHERE p.name=NEW.project_name;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_task_added AFTER INSERT ON tasks
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('task.created','task',NEW.id,NEW.project,NEW.title,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_task_changed AFTER UPDATE ON tasks
        WHEN OLD.status<>NEW.status OR OLD.priority<>NEW.priority OR OLD.title<>NEW.title
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('task.updated','task',NEW.id,NEW.project,NEW.title,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_schedule_added AFTER INSERT ON workflow_schedules
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('schedule.created','schedule',NEW.id,NEW.project,NEW.title,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_schedule_changed AFTER UPDATE ON workflow_schedules
        WHEN OLD.title<>NEW.title OR OLD.instructions<>NEW.instructions OR OLD.enabled<>NEW.enabled
          OR OLD.archived<>NEW.archived OR OLD.time_local<>NEW.time_local
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('schedule.updated','schedule',NEW.id,NEW.project,NEW.title,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_run_created AFTER INSERT ON workflow_runs
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('run.queued','run',NEW.id,'','Scheduled run #'||NEW.id,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        CREATE TRIGGER IF NOT EXISTS trg_tyrion_run_changed AFTER UPDATE ON workflow_runs
        WHEN OLD.status<>NEW.status
        BEGIN
          INSERT INTO change_events(kind,entity_type,entity_id,project,summary,created_at)
          VALUES('run.updated','run',NEW.id,'','Scheduled run #'||NEW.id||' ('||NEW.status||')',
                 strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        END;
        """)
        db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)",(SYNC_KEY,"0"))
        db.commit()

def feed(after=None,limit=40):
    if after is None:
        row=core.one("SELECT value FROM meta WHERE key=?",(SYNC_KEY,))
        after=int(row["value"]) if row else 0
    after=int(after)
    if after<0:raise ValueError("Cursor must be nonnegative")
    limit=max(1,min(100,int(limit)))
    items=core.rows("""SELECT id,kind,entity_type,entity_id,project,summary,created_at
                   FROM change_events WHERE id>? ORDER BY id ASC LIMIT ?""",(after,limit))
    high=core.one("SELECT MAX(id) as id FROM change_events")["id"] or 0
    count=core.one("SELECT COUNT(*) AS n FROM change_events WHERE id>?",(after,))["n"]
    return {"cursor":after,"max_event_id":high,"total_unread":count,
            "events":items,"more":count>len(items)}

def status():
    x=feed(limit=1)
    row=core.one("SELECT value FROM meta WHERE key='chatgpt_last_consumed_at'")
    return {"pending_changes":x["total_unread"],"last_acknowledged_event":x["cursor"],
            "latest_event":x["max_event_id"],"last_consumed_at":row["value"] if row else None,
            "chatgpt_access":"pull_or_scheduled_only"}

def ack(last_event_id):
    last_event_id=int(last_event_id)
    if last_event_id<0:raise ValueError("Invalid acknowledgment")
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT value FROM meta WHERE key=?",(SYNC_KEY,)).fetchone()
        current=int(row["value"]) if row else 0
        latest=db.execute("SELECT COALESCE(MAX(id),0) FROM change_events").fetchone()[0]
        if last_event_id>latest:raise ValueError("Cannot acknowledge future events")
        if last_event_id<current:raise ValueError("Cursor cannot move backwards")
        if last_event_id==current:
            return {"acknowledged_through":current,"pending_changes":latest-current}
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(SYNC_KEY,str(last_event_id)))
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('chatgpt_last_consumed_at',?)",(core.now(),))
        pending=db.execute("SELECT COUNT(*) FROM change_events WHERE id>?",(last_event_id,)).fetchone()[0]
        db.commit()
    return {"acknowledged_through":last_event_id,"pending_changes":pending}

def inbox(limit=35):
    from . import workflow_scheduler as workflows
    item=feed(limit=limit)
    return {"changes":item,"scheduled_work":workflows.pending_chatgpt(limit=5),
            "review_ready":workflows.ready_drafts(limit=5),"sync_status":status(),
            "instruction":"Items were entered once in Tyrion. Review and handle through authorized tools; do not publish, send or delete without required approval."}
