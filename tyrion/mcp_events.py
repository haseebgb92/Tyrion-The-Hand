"""MCP 2.0 webhook event subscriptions for Tyrion.

This is a private, STDIO-hosted MCP component to be used through an operator-
controlled Secure MCP Tunnel; it exposes no public listener or OpenAI API usage.
Subscriptions are dormant until a compatible ChatGPT Work/dot explicitly
subscribes and proves ownership of a public HTTPS callback via a signed challenge.
"""
from __future__ import annotations
import base64
import datetime as dt
import hashlib
import hmac
import http.client
import ipaddress
import json
import secrets
import sqlite3
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
from . import core,change_feed

EVENT_TYPES=("task.created","project.created","project.updated","schedule.created","schedule.updated","run.queued")
SUBSCRIPTION_LIFETIME=7*24*3600
MAX_RETRIES=4


def setup():
    change_feed.setup()
    with core.LOCK,core.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS mcp_event_subscriptions(
          id TEXT PRIMARY KEY,name TEXT NOT NULL,arguments TEXT NOT NULL,
          callback TEXT NOT NULL,signing_secret TEXT NOT NULL,
          expires_at REAL NOT NULL,cursor INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mcp_event_delivery(
          subscription_id TEXT NOT NULL,event_id INTEGER NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0,next_at REAL NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued',
          PRIMARY KEY(subscription_id,event_id));
        CREATE INDEX IF NOT EXISTS ix_mcp_delivery_due ON mcp_event_delivery(status,next_at);
        """)
        db.commit()


def event_catalog():
    result=[]
    for event in EVENT_TYPES:
        result.append({
          "name":event,
          "description":{
              "task.created":"A new Tyrion task was created; triage it without duplicating it.",
              "project.created":"A new project was registered in Tyrion.",
              "project.updated":"A tracked project or its resources changed.",
              "schedule.created":"A new independent Tyrion schedule was configured.",
              "schedule.updated":"A schedule was edited, enabled, paused or archived.",
              "run.queued":"A scheduled assignment has become due and entered Tyrion's queue."
          }[event],
          "delivery":["webhook"],
          "inputSchema":{"type":"object","properties":{"project":{"type":"string",
                    "description":"Optional exact Tyrion project name to filter notifications."}},
                    "additionalProperties":False},
          "payloadSchema":{"type":"object", "properties":{
                  "entity_id":{"type":"integer"},"project":{"type":"string"},
                  "summary":{"type":"string"},"event_id":{"type":"integer"}},
                  "required":["entity_id","project","summary","event_id"],
                  "additionalProperties":False}
        })
    return {"events":result}


def _callback_host(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError("Invalid callback URL")
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Callback requires an HTTPS URL without embedded credentials")
    if parsed.port not in (None,443):raise ValueError("Callback requires standard HTTPS port")
    host=parsed.hostname
    if not host or "." not in host or len(host)>253:raise ValueError("Callback must have a public DNS hostname")
    if host.lower() in ("localhost",) or host.lower().endswith((".localhost",".local",".internal",".test")):
        raise ValueError("Callback hostname must be public")
    try:
        ipaddress.ip_address(host)
        raise ValueError("Callback must use a public hostname, not an IP literal")
    except ValueError as exc:
        if str(exc).startswith("Callback must use"):raise
    try:host=host.encode('idna').decode('ascii')
    except UnicodeError:raise ValueError("Invalid callback hostname")
    if not all(x.isalnum() or x in '-.' for x in host):raise ValueError("Invalid hostname")
    return host,parsed


def _public_addresses(host):
    try:
        records=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)
    except OSError:
        raise ValueError("Callback DNS resolution failed")
    addresses=[]
    for rec in records:
        ip=ipaddress.ip_address(rec[4][0])
        if not ip.is_global:raise ValueError("Callback resolves to a non-public address")
        if str(ip) not in addresses:addresses.append(str(ip))
    if not addresses:raise ValueError("No valid public callback addresses")
    return addresses


def _send_https(url,body,headers,timeout=5):
    """SSRF-resistant callback: DNS-validate then connect to PINNED IP with TLS hostname verification.
    Redirect responses are not followed. This sender is used for verification and deliveries.
    """
    host,parsed=_callback_host(url)
    addresses=_public_addresses(host)
    request_target=(parsed.path or '/')+('?' + parsed.query if parsed.query else '')
    content=body if isinstance(body,bytes) else body.encode('utf8')
    if len(content)>262144:raise ValueError("Webhook payload exceeds maximum")
    req_headers={"Host":host,"Content-Type":"application/json","Content-Length":str(len(content)),
                 "Connection":"close","User-Agent":"Tyrion-MCP-Events/0.6"}
    req_headers.update(headers)
    header_bytes=(f"POST {request_target} HTTP/1.1\r\n"+
        ''.join(f"{key}: {val}\r\n" for key,val in req_headers.items())+'\r\n').encode()
    ssl_context=ssl.create_default_context()
    last_error=None
    for ip in addresses[:3]:
        try:
            with socket.create_connection((ip,443),timeout=timeout) as raw:
                with ssl_context.wrap_socket(raw,server_hostname=host) as channel:
                    channel.settimeout(timeout)
                    channel.sendall(header_bytes+content)
                    reply=http.client.HTTPResponse(channel)
                    reply.begin()
                    if reply.status in (301,302,303,307,308):
                        raise ValueError("Webhook redirects are forbidden")
                    return reply.status,reply.read(4096)
        except (OSError,ssl.SSLError) as exc:
            last_error=exc
            continue
    raise RuntimeError("Webhook destination could not be reached") from last_error


def _secret_bytes(secret):
    if not isinstance(secret,str) or not secret.startswith('whsec_'):
        raise ValueError("Standard webhook signing secret is required")
    try:key=base64.b64decode(secret[6:],validate=True)
    except ValueError:raise ValueError("Invalid webhook signing secret")
    if not 24<=len(key)<=64:raise ValueError("Webhook signing key must be 24–64 bytes")
    return key


def sign(secret,msg_id,seconds,body):
    key=_secret_bytes(secret)
    content=body if isinstance(body,bytes) else body.encode('utf8')
    payload=msg_id.encode()+b'.'+str(seconds).encode()+b'.'+content
    signature=base64.b64encode(hmac.new(key,payload,hashlib.sha256).digest()).decode('ascii')
    return 'v1,'+signature


def _post_signed(url,secret,subscription_id,message,event_id):
    encoded=json.dumps(message,ensure_ascii=False,separators=(',',':')).encode('utf8')
    sec=int(time.time())
    return _send_https(url,encoded,{
       'webhook-id':event_id,'webhook-timestamp':str(sec),
       'webhook-signature':sign(secret,event_id,sec,encoded),
       'X-MCP-Subscription-Id':subscription_id},timeout=7)


def subscribe(params):
    setup()
    if not isinstance(params,dict):raise ValueError('Invalid subscription')
    name=params.get('name')
    if name not in EVENT_TYPES:raise ValueError('Unknown event')
    args=params.get('arguments') or {}
    if not isinstance(args,dict) or set(args)-{'project'}:raise ValueError('Invalid event filters')
    if 'project' in args and (not isinstance(args['project'],str) or len(args['project'])>100):
        raise ValueError('Invalid project filter')
    delivery=params.get('delivery') or {}
    if delivery.get('mode')!='webhook':raise ValueError('Only webhook delivery supported')
    target=delivery.get('url');secret=delivery.get('secret')
    _secret_bytes(secret)
    host,_=_callback_host(target)
    _public_addresses(host)
    identity=json.dumps({'name':name,'args':args,'url':target},sort_keys=True,separators=(',',':'))
    sub_id='sub_'+hashlib.sha256(('tyrion-local-user:'+identity).encode()).hexdigest()[:32]
    ttl=params.get('ttlMs')
    if ttl is not None:
        if type(ttl) is not int or ttl<=0:raise ValueError('Invalid requested TTL')
        ttl_secs=max(60,min(SUBSCRIPTION_LIFETIME,ttl//1000))
    else:ttl_secs=SUBSCRIPTION_LIFETIME
    refresh=dt.datetime.fromtimestamp(time.time()+ttl_secs,dt.timezone.utc).isoformat()
    challenge=secrets.token_urlsafe(24)
    message={'type':'verification','challenge':challenge}
    try:
        code,body=_post_signed(target,secret,sub_id,message,'msg_verify_'+secrets.token_hex(12))
        response=json.loads(body) if 200<=code<300 else None
        if not isinstance(response,dict) or not hmac.compare_digest(str(response.get('challenge','')),challenge):
            raise RuntimeError('Callback challenge failed')
    except Exception as exc:
        raise RuntimeError('Callback verification failed: '+type(exc).__name__) from exc
    with core.LOCK,core.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT cursor FROM mcp_event_subscriptions WHERE id=?',(sub_id,)).fetchone()
        first_cursor=db.execute('SELECT COALESCE(MAX(id),0) FROM change_events').fetchone()[0]
        cursor=old['cursor'] if old else first_cursor
        db.execute('''INSERT INTO mcp_event_subscriptions
           (id,name,arguments,callback,signing_secret,expires_at,cursor,active,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET signing_secret=excluded.signing_secret,
             expires_at=excluded.expires_at,active=1''',
          (sub_id,name,json.dumps(args),target,secret,time.time()+ttl_secs,cursor,1,core.now()))
        db.commit()
    return {'id':sub_id,'refreshBefore':refresh,'cursor':None,'truncated':False}


def unsubscribe(params):
    if not isinstance(params,dict):raise ValueError('Invalid unsubscribe')
    name=params.get('name')
    args=params.get('arguments') or {}
    delivery=params.get('delivery') or {}
    target=delivery.get('url')
    if name not in EVENT_TYPES or not isinstance(args,dict) or not target:
        raise ValueError('Malformed unsubscribe')
    identity=json.dumps({'name':name,'args':args,'url':target},sort_keys=True,separators=(',',':'))
    sub_id='sub_'+hashlib.sha256(('tyrion-local-user:'+identity).encode()).hexdigest()[:32]
    with core.LOCK,core.connection() as db:
        db.execute('UPDATE mcp_event_subscriptions SET active=0 WHERE id=?',(sub_id,))
        db.execute("UPDATE mcp_event_delivery SET status='cancelled' WHERE subscription_id=? AND status='queued'",(sub_id,))
        db.commit()
    return {}


def status():
    """Measured event-channel status only; never expose callback URLs or secrets."""
    try:
        count=core.one("SELECT COUNT(*) n FROM mcp_event_subscriptions WHERE active=1 AND expires_at>?",(time.time(),))['n']
        pending=core.one("SELECT COUNT(*) n FROM mcp_event_delivery WHERE status='queued'")['n']
        delivered=core.one("SELECT COUNT(*) n FROM mcp_event_delivery WHERE status='delivered'")['n']
        latest=core.one("SELECT e.id,e.kind,e.created_at FROM mcp_event_delivery d JOIN change_events e ON e.id=d.event_id WHERE d.status='delivered' ORDER BY e.id DESC LIMIT 1")
        active=core.rows("SELECT DISTINCT name FROM mcp_event_subscriptions WHERE active=1 AND expires_at>? ORDER BY name",(time.time(),))
    except (sqlite3.OperationalError,TypeError):
        count,pending,delivered,latest,active=0,0,0,None,[]
    return {'protocol':'MCP 2.0 events','subscriptions_active':count,
            'subscribed_events':[x['name'] for x in active],
            'deliveries_queued':pending,'deliveries_successful':delivered,
            'last_delivered_event':latest,
            'chatgpt_realtime_connected':bool(count),
            'note':('Signed ChatGPT Work subscriptions active.' if count else
               'No verified ChatGPT Work event subscriptions; scheduled fallback may be needed.')}

def _event_project(event,db=None):
    if event["kind"]!="run.queued" or event["project"]:
        return event["project"]
    query="""SELECT s.project FROM workflow_runs r
       JOIN workflow_schedules s ON s.id=r.schedule_id WHERE r.id=?"""
    if db is not None:
        row=db.execute(query,(event["entity_id"],)).fetchone()
        return row["project"] if row else ""
    row=core.one(query,(event["entity_id"],))
    return row["project"] if row else ""

def queue_events():
    """Prepare matching events transactionally, bounded and durable across service restarts."""
    count=0
    with core.LOCK,core.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        active=db.execute('''SELECT * FROM mcp_event_subscriptions
             WHERE active=1 AND expires_at>?''',(time.time(),)).fetchall()
        for sub in active:
            rows=db.execute('''SELECT * FROM change_events WHERE id>? ORDER BY id LIMIT 75''',(sub['cursor'],)).fetchall()
            if not rows:continue
            arguments=json.loads(sub['arguments'])
            for event in rows:
                project=_event_project(event,db)
                if event['kind']==sub['name'] and (not arguments.get('project') or arguments['project']==project):
                    db.execute('''INSERT OR IGNORE INTO mcp_event_delivery
                        (subscription_id,event_id,next_at) VALUES(?,?,?)''',(sub['id'],event['id'],time.time()))
                    count+=1
            db.execute('UPDATE mcp_event_subscriptions SET cursor=? WHERE id=?',(rows[-1]['id'],sub['id']))
        db.commit()
    return count


def deliver_one():
    with core.LOCK,core.connection() as db:
        row=db.execute('''SELECT d.*,s.name,s.callback,s.signing_secret,s.active,s.expires_at
             FROM mcp_event_delivery d JOIN mcp_event_subscriptions s ON s.id=d.subscription_id
             WHERE d.status='queued' AND d.next_at<=? ORDER BY d.event_id,d.subscription_id LIMIT 1''',
             (time.time(),)).fetchone()
        if not row:return None
        # Claim before network request; active dispatch thread is only one per server.
        db.execute("UPDATE mcp_event_delivery SET status='sending' WHERE subscription_id=? AND event_id=? AND status='queued'",
                   (row['subscription_id'],row['event_id']))
        db.commit()
    event=core.one('SELECT * FROM change_events WHERE id=?',(row['event_id'],))
    if not event or not row['active'] or row['expires_at']<=time.time():
        final='cancelled';message='Not active';next_at=time.time()
    else:
        payload={'eventId':'evt_tyrion_'+str(event['id']),'name':row['name'],
             'timestamp':event['created_at'],'data':{
              'event_id':event['id'],'entity_id':event['entity_id'],
              'project':_event_project(event),'summary':event['summary'][:200]},'cursor':None}
        try:
            code,_=_post_signed(row['callback'],row['signing_secret'],row['subscription_id'],
                                payload,payload['eventId'])
            final='delivered' if 200<=code<300 else ('failed' if code in (410,413) else 'queued')
            message=str(code)
        except Exception as exc:
            final='queued';message=type(exc).__name__
        attempt=row['attempts']+1
        if attempt>=MAX_RETRIES and final=='queued':final='failed'
        next_at=time.time()+min(300,2**(min(attempt,7))*5)
    with core.LOCK,core.connection() as db:
        db.execute('''UPDATE mcp_event_delivery SET status=?,attempts=attempts+1,next_at=?
                      WHERE subscription_id=? AND event_id=?''',
                 (final,next_at,row['subscription_id'],row['event_id']))
        db.commit()
    return {'event_id':row['event_id'],'status':final,'response':message}


def start(stop):
    def loop():
        setup()
        # Interrupted attempts on process restart may be delivered again with identical event IDs.
        with core.LOCK,core.connection() as db:
            db.execute("UPDATE mcp_event_delivery SET status='queued' WHERE status='sending'")
            db.commit()
        while not stop.wait(.9):
            try:
                queue_events()
                deliver_one()
            except Exception:
                continue
    worker=threading.Thread(target=loop,daemon=True,name='tyrion-mcp-events')
    worker.start()
    return worker
