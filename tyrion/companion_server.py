"""Tyrion – The Companion: authenticated PC-relayed Android UI over Tailscale Serve.

Bindings: loopback-only HTTP on 127.0.0.1:17878, forwarded through private
Tailscale HTTPS port 8443. Do not expose with Funnel or public reverse proxies.
One-time 8-digit pairing, per-device revocable random tokens, no data copy on phone.
"""
from __future__ import annotations
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json
import re
import time
from . import core,companion_pairing as pairing,realtime

HOST="127.0.0.1"
PORT=17878
LOCAL="http://127.0.0.1:17877"
FILES=core.ROOT/"static"
STATIC={"/app.js","/scheduler.js","/projects.js","/companion.js","/style.css","/seal.svg","/companion.css"}
PREVIEW_MAX=150000
POST_MAX=50000

def local_request(path,method="GET",body=None):
    # Read session token from localhost-only dashboard, never share it with Android.
    with urlopen(LOCAL+"/",timeout=4) as response:
        html=response.read(100000).decode("utf8")
    found=re.search(r'<meta name="tyrion-session" content="([^"]+)"',html)
    if not found:raise RuntimeError("Local Tyrion desktop session is unavailable")
    session=found.group(1)
    if path=="/":return 200,html.replace(session,"__TYRION_SESSION__").encode("utf8"),"text/html; charset=utf-8"
    req=Request(LOCAL+path,method=method,
        headers={"X-Tyrion-Session":session,"Content-Type":"application/json"},
        data=body if method=="POST" else None)
    try:
        with urlopen(req,timeout=28) as res:
            blob=res.read(200000)
            if len(blob)>=200000:raise ValueError("Response exceeds relay limit")
            return res.status,blob,res.headers.get("Content-Type","application/json")
    except HTTPError as exc:
        return exc.code,exc.read(2500),"application/json"

class Handler(BaseHTTPRequestHandler):
    server_version="TyrionCompanion/1.0"
    def log_message(self,*args):pass
    def _origin_ok(self):
        origin=self.headers.get("Origin")
        return origin is None or origin==pairing.PUBLIC_URL

    def _check_host(self):
        host=self.headers.get("Host","")
        return host in (f"127.0.0.1:{PORT}",f"localhost:{PORT}",
                 urlsplit(pairing.PUBLIC_URL).netloc)

    def _token(self):
        bearer=self.headers.get("X-Tyrion-Session") or self.headers.get("X-Tyrion-Device")
        if not bearer and self.headers.get("Cookie"):
            c=SimpleCookie()
            try:c.load(self.headers["Cookie"]);bearer=c["tyrion_device"].value if "tyrion_device" in c else None
            except Exception:bearer=None
        return bearer

    def _auth(self):
        device=pairing.validate(self._token())
        if device:
            from datetime import datetime
            try:
                age=(datetime.now().astimezone()-datetime.fromisoformat(device["last_seen"])).total_seconds()
            except (TypeError,ValueError):age=61
            if age>=60:pairing.validate(self._token(),refresh=True)
        return device

    def response(self,body,status=200,mime="application/json",extra=None):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy",
          "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
          "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if extra:
            for key,value in extra.items():self.send_header(key,value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._check_host():return self.response({"error":"Unrecognized relay host"},403)
        path=urlsplit(self.path).path
        if path=="/download/Tyrion-The-Companion-v1.0.apk":
            apk=Path.home()/"Downloads/Tyrion-The-Companion-v1.0-debug.apk"
            if not apk.is_file():return self.response({"error":"APK unavailable"},404)
            return self.response(apk.read_bytes(),200,"application/vnd.android.package-archive",
               {"Content-Disposition":"attachment; filename=Tyrion-The-Companion-v1.0.apk"})
        if path=="/api/mobile/health":
            return self.response({"ok":True,"name":"Tyrion Companion Relay",
                                  "version":"1.0","access":"tailnet-only","paired":False})
        device=self._auth()
        if not device:return self.response({"error":"Companion device not paired or revoked"},401)
        if path=="/api/mobile/session":
            pairing.validate(self._token(),refresh=True)
            return self.response({"ok":True,"device":{"id":device["id"],"label":device["label"]},
                  "pc_time":core.now(),"relay":"connected"})
        if path in STATIC:
            mime={"css":"text/css; charset=utf-8","js":"application/javascript; charset=utf-8",
                  "svg":"image/svg+xml"}.get(path.rsplit(".",1)[-1],"text/plain")
            filename="companion.css" if path=="/companion.css" else path.lstrip("/")
            return self.response((FILES/filename).read_bytes(),200,mime)
        if path=="/":
            _,html,_=local_request("/")
            html=html.decode("utf8")
            token=self._token()
            html=html.replace("__TYRION_SESSION__",token)
            html=html.replace("</head>",'<link rel="stylesheet" href="/companion.css"></head>')
            html=html.replace("<title>Tyrion — The Hand</title>",
                 "<title>Tyrion – The Companion</title>")
            return self.response(html.encode("utf8"),200,"text/html; charset=utf-8")
        if path=="/api/realtime/stream":
            q=parse_qs(urlsplit(self.path).query)
            try:cursor=max(0,int(self.headers.get("Last-Event-ID") or q.get("after",["0"])[0]))
            except (ValueError,TypeError):cursor=0
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Accel-Buffering","no")
            self.end_headers()
            self.wfile.write(b": connected\n\n");self.wfile.flush()
            end=time.monotonic()+40
            try:
                while time.monotonic()<end:
                    events=realtime.events_since(cursor,limit=30)
                    for item in events:
                        cursor=item["id"]
                        payload=json.dumps({"id":item["id"],"kind":item["kind"],
                                "entity_type":item["entity_type"],"entity_id":item["entity_id"]})
                        self.wfile.write((f"id: {cursor}\nevent: tyrion-change\ndata: {payload}\n\n").encode())
                    if events:self.wfile.flush()
                    time.sleep(.8)
            except (OSError,ConnectionError):pass
            return
        if path.startswith("/api/") and not path.startswith((
                "/api/extension/","/api/mobile/","/api/companion/")):
            try:
                status,body,mime=local_request(self.path)
                return self.response(body,status,mime)
            except Exception as exc:return self.response({"error":"PC unavailable: "+type(exc).__name__},503)
        return self.response({"error":"Not found"},404)

    def do_POST(self):
        if not self._check_host() or not self._origin_ok():
            return self.response({"error":"Request origin denied"},403)
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            return self.response({"error":"JSON only"},415)
        try:n=int(self.headers.get("Content-Length",0))
        except ValueError:n=-1
        if not 1<=n<=POST_MAX:return self.response({"error":"Invalid request size"},413)
        try:
            raw=self.rfile.read(n)
            data=json.loads(raw)
            if not isinstance(data,dict):raise ValueError("Object expected")
        except (ValueError,UnicodeError):
            return self.response({"error":"Invalid JSON"},400)
        path=urlsplit(self.path).path
        if path=="/api/mobile/pair":
            try:
                value=pairing.claim(data.get("code"),data.get("name"))
                return self.response(value,200)
            except ValueError as exc:return self.response({"error":str(exc)},400)
        if not self._auth():return self.response({"error":"Device not paired or revoked"},401)
        if path.startswith("/api/") and not path.startswith((
                "/api/extension/","/api/mobile/","/api/companion/")):
            try:
                status,body,mime=local_request(self.path,"POST",raw)
                return self.response(body,status,mime)
            except Exception as exc:return self.response({"error":"PC unavailable: "+type(exc).__name__},503)
        return self.response({"error":"Not found"},404)

def main():
    pairing.setup()
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    server.daemon_threads=True
    print(f"Companion private relay: http://{HOST}:{PORT}",flush=True)
    try:server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=="__main__":main()
