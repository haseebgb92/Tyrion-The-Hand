"""Bounded local service discovery. Inventory is not equivalent to authenticated API access."""
import json
import pathlib
import sqlite3
import urllib.request
from . import core

def _safe_json(url, timeout=3):
    req=urllib.request.Request(url,headers={"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        if resp.status!=200:raise RuntimeError("HTTP unavailable")
        blob=resp.read(40000)
        if len(blob)>=40000:raise ValueError("Response too large")
        return json.loads(blob)

def security_fleet_summary():
    # Read only nonsecret, explicitly selected columns from local ShieldPress console.
    file=pathlib.Path.home()/".local/share/advertpreneur-security-console/fleet.db"
    if not file.is_file():raise FileNotFoundError("Security console inventory absent")
    db=sqlite3.connect(f"file:{file}?mode=ro",uri=True,timeout=3)
    try:
        sites=[{"label":row[0],"url":row[1]} for row in db.execute(
              "SELECT label,url FROM sites ORDER BY label LIMIT 40")]
        snapshots=db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        events=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        operations=db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
    finally:db.close()
    return {"id":"security_fleet","name":"ShieldPress Security Console",
        "mode":"local_inventory_readonly","status":"inventory_only","checked_at":core.now(),
        "metrics":{"sites":len(sites),"snapshots":snapshots,"events":events,"operations":operations},
        "sites":sites,
        "capabilities":["inventory.read"],
        "detail":"Local security console SQLite inventory read-only; no live ShieldPress WordPress action/API has been tested. Credentials were not read."}

def wp_lab_summary():
    file=pathlib.Path.home()/".local/share/wp-lab/instances.json"
    value=json.loads(file.read_text(encoding="utf8"))
    if not isinstance(value,list):raise ValueError("Unexpected WP Lab configuration")
    items=[{"name":str(x.get("name",""))[:100],"id":str(x.get("id",""))[:60]}
           for x in value if isinstance(x,dict) and isinstance(x.get("name"),str)]
    return {"id":"wp_lab","name":"WP Lab","mode":"local_inventory_readonly",
      "status":"inventory_only","checked_at":core.now(),
      "metrics":{"instances":len(items)},
      "instances":items,"capabilities":["inventory.read"],
      "detail":"Local WP Lab instance list only; running instances and admin access were not verified."}

def gbp_summary():
    doc=_safe_json("http://127.0.0.1:8787/health",3)
    if doc.get("app")!="Advertpreneur GBP" or doc.get("status")!="ok":
        raise RuntimeError("Unexpected local GBP server")
    return {"id":"advertpreneur_gbp","name":"Advertpreneur GBP","mode":"local_api_health",
      "status":"needs_authorization","checked_at":core.now(),
      "metrics":{"service_running":True},
      "capabilities":["health.read"],
      "detail":"Local GBP server responds, but protected API and Google Business Profile API approval are not verified."}
