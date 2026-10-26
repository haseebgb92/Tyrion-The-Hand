"""Real, bounded, READ-ONLY local integrations. No credentials copied or exposed."""
from __future__ import annotations
from collections import Counter
import json
import time
import urllib.request
import urllib.error
from . import core

MCP_META_URL="http://127.0.0.1:38939/mcp"
QA_URL="http://127.0.0.1:8742"
MAX_BYTES=1_800_000
# Method is strictly allowlisted. Never invoke arbitrary named MCP tools.
READ_TOOLS={"list_accounts","list_calendar","cloud_status","get_strategist_brief"}
WRITE_TOOLS={"create_post"} # only via explicit approved proposal execution

def _decode_mcp(body,content_type):
    if "text/event-stream" in content_type:
        events=[x[6:].strip() for x in body.splitlines() if x.startswith("data:")]
        if not events: raise RuntimeError("No MCP response event")
        obj=json.loads(events[-1])
    else: obj=json.loads(body)
    if "error" in obj:raise RuntimeError("MCP RPC error")
    result=obj.get("result",{})
    if result.get("isError"):raise RuntimeError("MCP tool rejected request")
    content=result.get("content",[])
    if content:
        chunk=next((a.get("text","") for a in content if a.get("type")=="text"),None)
        if chunk is None: return {}
        try:return json.loads(chunk)
        except ValueError:return {"text":chunk[:2000]}
    return result

def meta_call(name,args=None,*,approved_write=False):
    if name not in READ_TOOLS and not (approved_write and name in WRITE_TOOLS):
        raise ValueError("MCP method is not authorized")
    payload={"jsonrpc":"2.0","id":int(time.time()*1000)%100000000,"method":"tools/call",
             "params":{"name":name,"arguments":args or {}}}
    req=urllib.request.Request(MCP_META_URL,json.dumps(payload).encode("utf8"),
        {"Content-Type":"application/json","Accept":"text/event-stream, application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=8) as response:
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:raise RuntimeError("MCP response exceeded size limit")
        return _decode_mcp(body.decode("utf8"),response.headers.get("Content-Type",""))

def qa_get(path):
    if path not in ("/health","/api/scans"):
        raise ValueError("QA path not allowlisted")
    req=urllib.request.Request(QA_URL+path,headers={"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=5) as r:
        body=r.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:raise RuntimeError("QA response too large")
        return json.loads(body)

def count_status(items):
    return dict(Counter(str(x.get("status","unknown")).lower() for x in items if isinstance(x,dict)))

def meta_summary():
    accounts=meta_call("list_accounts")
    calendar=meta_call("list_calendar")
    if not isinstance(accounts,list) or not isinstance(calendar,list):
        raise RuntimeError("Unexpected Meta Manager response shape")
    return {
      "name":"Meta Manager","id":"meta_manager","status":"connected","mode":"local_mcp",
      "checked_at":core.now(),
      "metrics":{"accounts":len(accounts),"calendar_items":len(calendar),
                 "calendar_statuses":count_status(calendar)},
      "capabilities":["accounts.read","calendar.read","draft.create_with_approval"],
      "detail":"Local Meta Manager MCP responded. No publishing permissions granted."
    }

def qa_summary():
    health=qa_get("/health")
    if not health.get("ok"):raise RuntimeError("QA health probe was not healthy")
    scans=qa_get("/api/scans")
    if not isinstance(scans.get("items"),list):raise RuntimeError("Unexpected QA scans response")
    return {
       "name":"Advertpreneur QA","id":"advertpreneur_qa","status":"connected","mode":"local_api",
       "checked_at":core.now(),
       "metrics":{"scans":len(scans["items"]),"scan_statuses":count_status(scans["items"])},
       "capabilities":["scans.read","health.read"],
       "detail":"Read-only local API confirmed."
    }

def _safe_failure(name,identifier,mode,exc):
    return {"name":name,"id":identifier,"status":"unavailable","mode":mode,
            "checked_at":core.now(),"metrics":{},"capabilities":[],
            "detail":"Local service unavailable or response invalid: "+type(exc).__name__}

def live_report():
    from . import integration_extra
    entries=[]
    for fetch,name,identifier,mode in [
        (meta_summary,"Meta Manager","meta_manager","local_mcp"),
        (qa_summary,"Advertpreneur QA","advertpreneur_qa","local_api"),
        (integration_extra.security_fleet_summary,"ShieldPress Security Console","security_fleet","local_inventory_readonly"),
        (integration_extra.wp_lab_summary,"WP Lab","wp_lab","local_inventory_readonly"),
        (integration_extra.gbp_summary,"Advertpreneur GBP","advertpreneur_gbp","local_api_health")
    ]:
        try:entries.append(fetch())
        except Exception as exc:entries.append(_safe_failure(name,identifier,mode,exc))
    return {"checked_at":core.now(),"integrations":entries}

def stored_report():
    row=core.one("SELECT value FROM meta WHERE key='integration_report'")
    if not row:return {"checked_at":None,"integrations":[],
                       "note":"Integration sync has not run yet."}
    try:return json.loads(row["value"])
    except ValueError:return {"checked_at":None,"integrations":[]}

def synchronize():
    value=live_report()
    with core.LOCK,core.connection() as db:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('integration_report',?)",
                   (json.dumps(value),))
        db.commit()
    states=", ".join(x["name"]+": "+x["status"] for x in value["integrations"])
    core.log("integration","Connection sync: "+states)
    return value

def meta_accounts():
    accounts=meta_call("list_accounts")
    if not isinstance(accounts,list): raise RuntimeError("Invalid accounts response")
    return [{"id":str(a.get("id","")),"name":str(a.get("name",""))[:120],
             "status":str(a.get("status",""))[:40]} for a in accounts
            if isinstance(a,dict) and a.get("id") and a.get("name")]
