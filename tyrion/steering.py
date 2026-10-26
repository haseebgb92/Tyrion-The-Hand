"""Per-conversation operator instruction queue for the paired Tyrion browser companion.

This is an inbox, NOT a way to inject instructions into an active ChatGPT turn.
ChatGPT can read it only at an explicit MCP/Local Files checkpoint.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from . import core

_PATTERN = re.compile(r"^/(?:g/[^/]+/)?c/[A-Za-z0-9-]{8,}$")

def canonical_chat(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ValueError("Invalid ChatGPT conversation URL")
    u = urllib.parse.urlsplit(value)
    if (u.scheme != "https" or u.netloc != "chatgpt.com"
            or not _PATTERN.fullmatch(u.path.rstrip("/"))):
        raise ValueError("Open a saved ChatGPT conversation first")
    return "https://chatgpt.com" + u.path.rstrip("/")

def setup():
    core.setup()
    with core.LOCK, core.connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS steering_instructions(
            id INTEGER PRIMARY KEY,
            chat_url TEXT NOT NULL,
            instruction TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_steering_chat ON steering_instructions(chat_url,id)")
        db.commit()

def pending(chat_url):
    chat = canonical_chat(chat_url)
    setup()
    return core.rows("SELECT id,instruction,created_at FROM steering_instructions WHERE chat_url=? ORDER BY id ASC LIMIT 100",(chat,))

def add(chat_url,instruction):
    chat = canonical_chat(chat_url)
    if not isinstance(instruction,str) or not 2 <= len(instruction.strip()) <= 1500:
        raise ValueError("Instruction must be 2–1500 characters")
    setup()
    with core.LOCK, core.connection() as db:
        count = db.execute("SELECT COUNT(*) FROM steering_instructions WHERE chat_url=?", (chat,)).fetchone()[0]
        if count >= 50:
            raise ValueError("Queue full. Review or clear existing instructions.")
        cur = db.execute(
            "INSERT INTO steering_instructions(chat_url,instruction,created_at) VALUES(?,?,?)",
            (chat,instruction.strip(),core.now()))
        db.commit()
        return dict(db.execute("SELECT id,instruction,created_at FROM steering_instructions WHERE id=?",(cur.lastrowid,)).fetchone())

def remove(chat_url,instruction_id):
    chat = canonical_chat(chat_url)
    if type(instruction_id) is not int or instruction_id < 1:
        raise ValueError("Invalid instruction ID")
    setup()
    with core.LOCK, core.connection() as db:
        changed = db.execute("DELETE FROM steering_instructions WHERE chat_url=? AND id=?",(chat,instruction_id)).rowcount
        db.commit()
    return {"removed":changed == 1}

def clear(chat_url):
    chat=canonical_chat(chat_url)
    setup()
    with core.LOCK, core.connection() as db:
        count=db.execute("DELETE FROM steering_instructions WHERE chat_url=?",(chat,)).rowcount
        db.commit()
    return {"removed":count}

def conversations():
    """Only chat URLs and counts. Do not infer which one is this ChatGPT session."""
    setup()
    return core.rows("""SELECT chat_url,COUNT(*) AS pending_count,MAX(created_at) AS updated_at
        FROM steering_instructions GROUP BY chat_url ORDER BY MAX(id) DESC LIMIT 20""")

def acknowledge(chat_url,ids):
    """Explicitly remove only instructions incorporated into the response."""
    chat=canonical_chat(chat_url)
    if not isinstance(ids,list) or not 1<=len(ids)<=50 or any(type(i) is not int or i<1 for i in ids):
        raise ValueError("Expected 1–50 numeric instruction IDs")
    if len(set(ids))!=len(ids):
        raise ValueError("Duplicate instruction IDs")
    setup()
    with core.LOCK,core.connection() as db:
        placeholders=",".join("?" for _ in ids)
        existing=db.execute(
            f"SELECT id FROM steering_instructions WHERE chat_url=? AND id IN ({placeholders})",
            (chat,*ids)).fetchall()
        if len(existing)!=len(ids):
            raise ValueError("One or more instructions are not queued for this conversation")
        cur=db.execute(f"DELETE FROM steering_instructions WHERE chat_url=? AND id IN ({placeholders})",
                       (chat,*ids))
        db.commit()
    return {"acknowledged":cur.rowcount}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 -m tyrion.steering https://chatgpt.com/c/CONVERSATION_ID")
    print(json.dumps({"chat":canonical_chat(sys.argv[1]),"pending":pending(sys.argv[1])},ensure_ascii=False,indent=2))