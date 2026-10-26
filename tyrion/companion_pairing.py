"""Device pairing and revocation for Tyrion – The Companion.

No passwords, OAuth secrets, or production credentials cross this boundary.
Uses Tailscale for private routing and a separate randomly generated device token
stored only as a SHA256 digest in the Tyrion SQLite database.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
import time
from . import core

PAIR_WINDOW=300
PAIR_ATTEMPTS=6
PUBLIC_URL="https://haseeb-optiplex-3050.tailb87e57.ts.net:8443"
_SETUP=False
FAILED=[]

def setup():
    global _SETUP
    if _SETUP:return
    core.setup()
    with core.LOCK,core.connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS companion_codes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS companion_devices(
          id TEXT PRIMARY KEY, label TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
          created_at TEXT NOT NULL, last_seen TEXT NOT NULL,
          revoked INTEGER NOT NULL DEFAULT 0);
        """)
        db.commit()
    _SETUP=True

def _hash(value):
    return hashlib.sha256(value.encode("utf8")).hexdigest()

def pairing_code():
    setup()
    code=f"{secrets.randbelow(100_000_000):08d}"
    expire=int(time.time())+PAIR_WINDOW
    with core.LOCK,core.connection() as db:
        db.execute("UPDATE companion_codes SET used=1 WHERE used=0")
        db.execute("INSERT INTO companion_codes(code_hash,expires_at,created_at) VALUES(?,?,?)",
                   (_hash(code),expire,core.now()))
        db.commit()
    core.log("companion","New 5-minute Android pairing code generated")
    deep_link=f"tyrioncompanion://pair?server={PUBLIC_URL}&code={code}"
    import base64,io,qrcode
    qr=qrcode.QRCode(box_size=6,border=2,error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(deep_link)
    qr.make(fit=True)
    buf=io.BytesIO()
    qr.make_image(fill_color="#742936",back_color="#ffffff").save(buf,format="PNG")
    return {"code":code,"expires_at":expire,"server":PUBLIC_URL,
      "deep_link":deep_link,"qr_data_url":"data:image/png;base64,"+base64.b64encode(buf.getvalue()).decode("ascii")}

def claim(code,name):
    setup()
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{8}",code):
        raise ValueError("Eight-digit pairing code required")
    if not isinstance(name,str) or not 2<=len(name.strip())<=64:
        raise ValueError("Device name must contain 2–64 characters")
    now=int(time.time())
    FAILED[:]=[t for t in FAILED if now-t<60]
    if len(FAILED)>=12:raise ValueError("Pairing temporarily rate-limited")
    with core.LOCK,core.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("""SELECT * FROM companion_codes WHERE used=0
                     ORDER BY id DESC LIMIT 1""").fetchone()
        if (not row or row["expires_at"]<=now or row["attempts"]>=PAIR_ATTEMPTS or
                not hmac.compare_digest(row["code_hash"],_hash(code))):
            FAILED.append(now)
            if row:
                db.execute("UPDATE companion_codes SET attempts=attempts+1 WHERE id=?",(row["id"],))
            db.commit()
            raise ValueError("Pairing code invalid, expired, or used")
        token=secrets.token_urlsafe(48)
        identifier=secrets.token_hex(12)
        db.execute("UPDATE companion_codes SET used=1 WHERE id=?",(row["id"],))
        db.execute("""INSERT INTO companion_devices
             (id,label,token_hash,created_at,last_seen) VALUES(?,?,?,?,?)""",
              (identifier,name.strip(),_hash(token),core.now(),core.now()))
        db.commit()
    core.log("companion",f"Android companion paired: {name.strip()}")
    return {"device_id":identifier,"token":token,"server":PUBLIC_URL}

def validate(token,refresh=False):
    if not isinstance(token,str) or not 40<=len(token)<=130:return None
    setup()
    row=core.one("""SELECT id,label,last_seen FROM companion_devices
             WHERE token_hash=? AND revoked=0""",(_hash(token),))
    if not row:return None
    if refresh:
        with core.LOCK,core.connection() as db:
            db.execute("UPDATE companion_devices SET last_seen=? WHERE id=?",(core.now(),row["id"]))
            db.commit()
    return row

def devices():
    setup()
    return core.rows("""SELECT id,label,created_at,last_seen,revoked
                 FROM companion_devices ORDER BY created_at DESC LIMIT 50""")

def revoke(device_id):
    setup()
    if not isinstance(device_id,str) or not re.fullmatch(r"[0-9a-f]{24}",device_id):
        raise ValueError("Invalid device identifier")
    with core.LOCK,core.connection() as db:
        cur=db.execute("UPDATE companion_devices SET revoked=1 WHERE id=? AND revoked=0",(device_id,))
        db.commit()
    if cur.rowcount:core.log("companion",f"Revoked Android companion device {device_id[:8]}")
    return {"revoked":bool(cur.rowcount),"id":device_id}

def status():
    setup()
    active=core.one("SELECT COUNT(*) n FROM companion_devices WHERE revoked=0")["n"]
    code=core.one("SELECT expires_at,attempts FROM companion_codes WHERE used=0 ORDER BY id DESC LIMIT 1")
    return {"connected_devices":active,"pairing_active":bool(code and code["expires_at"]>time.time()),
            "pairing_expires_at":code["expires_at"] if code and code["expires_at"]>time.time() else None,
            "relay":PUBLIC_URL,"mode":"Tailscale tailnet-only HTTPS","phone_online_unverified":True}
