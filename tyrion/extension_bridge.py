"""Read-only Tyrion queue bridge for a user-paired browser extension.

The extension NEVER controls or reads ChatGPT's DOM, conversation content,
cookies, credentials, or network messages. Tyrion retains durable state.
"""
from __future__ import annotations
import hmac
import os
from pathlib import Path
import secrets
from . import core, workflow_scheduler as workflows

_KEYFILE_NAME = "browser_extension.token"

def setup():
    core.setup()
    path=core.DATA/_KEYFILE_NAME
    if not path.exists():
        # Never use the dashboard's session token or external OAuth credentials.
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"w") as stream:stream.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
    path.chmod(0o600)
    return path

def get_pairing_key():
    return setup().read_text(encoding="utf8").strip()

def validate(key):
    if not isinstance(key,str) or not 45<=len(key)<=120:return False
    return hmac.compare_digest(key,get_pairing_key())

def _last_updates(task_id):
    return core.rows("""SELECT source,note,created_at FROM task_updates WHERE task_id=?
              ORDER BY id DESC LIMIT 3""",(task_id,))

def state():
    tasks=core.rows("""SELECT id,title,project,priority,status,instructions,updated_at,created_at,source
         FROM tasks WHERE status!='done' ORDER BY
         CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
         id DESC LIMIT 60""")
    for t in tasks:t["updates"]=_last_updates(t["id"])
    runs=workflows.list_runs(limit=60)
    active=[r for r in runs if r["status"] in ("awaiting_chatgpt","generating","draft_ready","needs_review","failed")]
    # Do not expose full historic output or private authorizations to the extension.
    from . import change_feed
    try: newest=change_feed.status()["latest_event"]
    except Exception: newest=0
    return {"version":"0.8.0","time":core.now(),"latest_event_id":newest,
        "tasks":tasks,"runs":active,
        "counts":{"open_tasks":len(tasks),"due_handoffs":sum(r["status"]=="awaiting_chatgpt" for r in active),
                  "drafts_ready":sum(r["status"]=="draft_ready" for r in active)},
        "chatgpt_chat_mode":"one_shot_chat_handoff",
        "execution":"Tyrion queues all new work. The paired Chrome extension can launch one ChatGPT Chat handoff when Chrome and ChatGPT are active. Results return through Tyrion MCP."}

def handoff(kind,identifier):
    identifier=int(identifier)
    if kind=="task":
        item=core.one("SELECT * FROM tasks WHERE id=?",(identifier,))
        if not item:raise ValueError("Task not found")
        updates=_last_updates(identifier)
        details="\n".join(
            f"- {v['source']} ({v['created_at']}): {v['note'][:420]}" for v in updates)
        text=(
         f"Tyrion – The Hand, TASK #{identifier} ({item['project'] or 'General'}).\n"
         f"Title: {item['title']}\nPriority: {item['priority']}\nStatus: {item['status']}\n"
         f"Instructions: {item['instructions'] or 'No detailed instructions provided—ask before executing ambiguous work.'}\n"
         f"Verified progress recorded in Tyrion:\n{details or '- No progress recorded yet.'}\n\n"
         "Use the connected Tyrion MCP tools to fetch this SAME task and current updates. "
         "Continue from the persisted state, avoid duplicate operations, use permitted connectors and evidence, "
         "and write factual progress or blockers back to this original task using tyrion_add_task_update. "
         "Do not claim completion or perform any approval-gated external action without verification and consent. "
         "Return a brief status identifying remaining deliverables."
        )
        title=item["title"]
    elif kind=="run":
        run=workflows.run_detail(identifier)
        r=run["request"]
        title=run["schedule_title"]
        text=(f"Tyrion – The Hand, scheduled RUN #{identifier}: {title}.\n"
              f"Project: {run['project']}\nCurrent state: {run['status']}\n"
              f"Saved instructions: {r['instructions']}\n"
              "Access Tyrion with the connected MCP plugin. Check the actual run state again, "
              "research as required, create only the reviewable deliverable, avoid duplicate drafts "
              "and save verified results back to the SAME run. Do not publish without approval. "
              "Report any blocker honestly.")
    else:
        raise ValueError("Unknown handoff type")
    return {"kind":kind,"id":identifier,"title":title,"text":text[:12000]}

def manual_note(task_id,note):
    # Operator-written progress note, never silently mark as complete.
    if not isinstance(note,str) or not 5<=len(note.strip())<=1500:
        raise ValueError("Progress note must be 5–1500 characters")
    return core.add_task_update(int(task_id),note.strip(),"operator")
