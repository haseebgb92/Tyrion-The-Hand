"""Private localhost WebSocket event bridge for Tyrion's Chrome Companion.

Chrome MV3 workers receive low-volume notifications by ID, never task bodies.
Origin must be a chrome-extension:// ID and the user-paired secret is mandatory.
The 30-second extension alarm remains a fallback if WebSocket is unavailable.
"""
from __future__ import annotations
import asyncio
import json
import re
from http import HTTPStatus
from . import extension_bridge,realtime,core
import websockets

HOST="127.0.0.1"
PORT=17879
ORIGIN_RE=re.compile(r"^chrome-extension://[a-p]{32}$")

async def check_handshake(path,headers):
    origin=headers.get("Origin","")
    if not ORIGIN_RE.fullmatch(origin):
        return (HTTPStatus.FORBIDDEN,[("Content-Type","text/plain")],b"Chrome extension only")

async def handle(socket,path):
    try:
        auth=await asyncio.wait_for(socket.recv(),timeout=5)
        info=json.loads(auth)
        if not isinstance(info,dict) or not extension_bridge.validate(info.get("pairingKey")):
            await socket.close(code=1008,reason="Not paired")
            return
        cursor=int(info.get("after",0))
        cursor=max(0,cursor)
        # On first connection, the Chrome extension fetches the complete PC queue itself.
        newest=realtime.events_since(cursor,limit=1)
        await socket.send(json.dumps({"type":"ready","latest_seen":cursor}))
        elapsed=0.0
        last_pending=None
        while True:
            await asyncio.sleep(.75)
            # Detect queue changes directly as well. A task.created event can fire
            # milliseconds before the task is inserted into the dispatch queue.
            # Watching queued IDs closes that race without altering global feed counts.
            pending=tuple((r["id"],r["attempt"]) for r in core.rows(
                 "SELECT id,attempt FROM companion_dispatch WHERE status='queued' ORDER BY id LIMIT 32"))
            if pending!=last_pending and pending:
                await socket.send(json.dumps({"type":"change","reason":"dispatch_queue","queued":len(pending)}))
            last_pending=pending
            events=realtime.events_since(cursor,limit=30)
            if events:
                cursor=events[-1]["id"]
                await socket.send(json.dumps({"type":"change","last_event_id":cursor,
                    "count":len(events)}))
            elapsed+=.75
            if elapsed>=12:
                await socket.send('{"type":"keepalive"}')
                elapsed=0
    except (websockets.exceptions.ConnectionClosed,asyncio.TimeoutError,ValueError,
            TypeError,json.JSONDecodeError):
        return

async def start():
    async with websockets.serve(handle,HOST,PORT,process_request=check_handshake,
                                max_size=2048,max_queue=4,ping_interval=15,
                                ping_timeout=15,close_timeout=3):
        print(f"Tyrion Chrome realtime events: ws://{HOST}:{PORT} (private)",flush=True)
        await asyncio.Future()

def main():
    extension_bridge.setup()
    realtime.setup()
    asyncio.run(start())

if __name__=="__main__":main()
