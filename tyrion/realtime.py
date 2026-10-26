"""Instant local notifications for new Tyrion work; no paid model API.

Reads the append-only SQLite change feed. Runs inside the Tyrion background service,
independently of whether the UI or ChatGPT is open.
"""
from __future__ import annotations
import os
import pathlib
import subprocess
import threading
from . import core

CURSOR_KEY='local_notifications_cursor'
NOTIFY_KINDS={'task.created','project.created','project.updated','schedule.created','schedule.updated','run.queued'}
TITLES={'task.created':'New task in Tyrion','project.created':'Project added',
        'project.updated':'Project updated','schedule.created':'New schedule',
        'schedule.updated':'Schedule changed','run.queued':'Scheduled job is due'}


def setup():
    from . import change_feed
    change_feed.setup()
    with core.LOCK,core.connection() as db:
        row=db.execute('SELECT value FROM meta WHERE key=?',(CURSOR_KEY,)).fetchone()
        if row is None:
            newest=db.execute('SELECT COALESCE(MAX(id),0) FROM change_events').fetchone()[0]
            db.execute('INSERT INTO meta(key,value) VALUES(?,?)',(CURSOR_KEY,str(newest)))
        db.commit()


def events_since(after,limit=30):
    return core.rows('''SELECT id,kind,entity_type,entity_id,project,summary,created_at
                        FROM change_events WHERE id>? ORDER BY id LIMIT ?''',
                     (int(after),min(50,max(1,int(limit)))))


def notify(event):
    if event['kind'] not in NOTIFY_KINDS:return False
    binary='/usr/bin/notify-send'
    if not pathlib.Path(binary).is_file():return False
    label=TITLES[event['kind']]
    body=str(event['summary'])[:150]
    if event['project'] and event['project']!=event['summary']:
        body=f"{event['project']} · {body}"
    # Notifications contain no credentials or request text beyond 150 chars.
    icon=str(core.ROOT/'static/seal.svg')
    try:
        subprocess.run([binary,'--app-name=Tyrion – The Hand','--icon='+icon,
                        '--expire-time=4500',label,body],timeout=3,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        return True
    except (OSError,subprocess.SubprocessError):
        return False


def dispatch(stop,interval=0.8):
    """Deliver fresh changes exactly once per local observer cursor (no old popups on first start)."""
    setup()
    while not stop.wait(interval):
        try:
            row=core.one('SELECT value FROM meta WHERE key=?',(CURSOR_KEY,))
            cursor=int(row['value']) if row else 0
            events=events_since(cursor)
            if not events:continue
            for event in events:
                # Mark first so GUI/session errors cannot create notification spam.
                with core.LOCK,core.connection() as db:
                    db.execute('UPDATE meta SET value=? WHERE key=?',(str(event['id']),CURSOR_KEY))
                    db.commit()
                notify(event)
        except Exception:
            # Retry on next tick; never terminate scheduler on notification failure.
            continue


def start(stop):
    setup()
    thread=threading.Thread(target=dispatch,args=(stop,),daemon=True,name='tyrion-notifications')
    thread.start()
    return thread
