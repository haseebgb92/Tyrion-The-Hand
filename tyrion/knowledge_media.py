"""Opt-in local image/video frame semantic retrieval.

No automatic folder crawling, media uploads or video understanding claims.
Only explicit user-selected files under ~/Documents or ~/Downloads, never vaults.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from . import core, knowledge

MODEL = "embeddinggemma-2:740m-q8_0"
DB = core.DATA / "knowledge-media.sqlite3"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}
DENY_PARTS = {"fatir", "advertpreneur-vault", ".ssh", ".gnupg",
              "secrets", "credentials", "private", "passwords"}
MAX_BYTES = 350*1024*1024

def conn():
    DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS media_vectors(
        id TEXT PRIMARY KEY, project TEXT NOT NULL,
        path TEXT NOT NULL, timestamp REAL, kind TEXT NOT NULL,
        source_sha256 TEXT NOT NULL, embedding TEXT NOT NULL,
        indexed_at TEXT NOT NULL)""")
    db.commit()
    os.chmod(DB, 0o600)
    return db

def approved_path(value):
    f = Path(value).expanduser().resolve(strict=True)
    allowed=[(Path.home()/n).resolve() for n in ("Documents", "Downloads")]
    if not f.is_file() or not any(f.is_relative_to(r) for r in allowed):
        raise ValueError("Media must be a file under Documents or Downloads")
    if any(x.casefold() in DENY_PARTS for x in f.parts):
        raise ValueError("Sensitive folders cannot be indexed")
    if f.suffix.lower() not in IMAGE_EXTS | VIDEO_EXTS:
        raise ValueError("Only local image and video files are supported")
    if f.stat().st_size > MAX_BYTES:raise ValueError("Media exceeds 350 MB cap")
    return f

def input_embed(value, image=False):
    knowledge.ensure_server()
    data = {"image":base64.b64encode(value).decode("ascii")} if image else (
        "task: search query | "+str(value))
    request = urllib.request.Request(
        knowledge.URL+"/api/embed",
        data=json.dumps({"model":MODEL,"input":data,"dimensions":256,
                         "truncate":True,"keep_alive":"25s",
                         "options":{"num_thread":2}}).encode(),
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=95) as response:
        result=json.load(response)
    vector=result["embeddings"][0]
    if len(vector)!=256:raise RuntimeError("Unexpected vector dimension")
    return knowledge.unit(vector)

def _sample_video(path, output):
    """Reduced, bounded sample frames; never retain frame copies."""
    probe=subprocess.run(["ffprobe","-v","error","-show_entries",
         "format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],
         capture_output=True,text=True,timeout=10,check=True)
    duration=float(probe.stdout.strip())
    if not 0<duration<=180:raise ValueError("Supported video length is 1–180 seconds")
    interval=max(3,int(math.ceil(duration/10)))
    command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-i",str(path),
             "-vf",f"fps=1/{interval},scale=480:-2",
             "-frames:v","10","-q:v","5",str(output/"frame_%03d.jpg")]
    subprocess.run(command,check=True,capture_output=True,timeout=90)
    return [(f,round(i*interval,1)) for i,f in enumerate(sorted(output.glob("frame_*.jpg")))]

def index_media(file,project):
    if not isinstance(project,str) or project in knowledge.EXCLUDED:
        raise ValueError("A non-excluded existing project is required")
    if not core.one("SELECT id FROM projects WHERE name=?",(project,)):
        raise ValueError("Project must exist in Tyrion")
    path=approved_path(file)
    sha=hashlib.sha256(path.read_bytes()).hexdigest() if path.stat().st_size<=20_000_000 else (
        f"{path.stat().st_size}:{path.stat().st_mtime_ns}")
    if path.suffix.lower() in IMAGE_EXTS:
        pairs=[(path,None)]
        with conn() as db:
            old=db.execute("SELECT source_sha256 FROM media_vectors WHERE path=? AND project=?",
                           (str(path),project)).fetchone()
            if old and old["source_sha256"]==sha:
                return {"indexed":0,"cached":True,"project":project}
        vectors=[(None,input_embed(path.read_bytes(),image=True))]
    else:
        with tempfile.TemporaryDirectory(prefix="tyrion-frame-",dir=core.DATA) as tmp:
            pairs=_sample_video(path,Path(tmp))
            vectors=[(stamp,input_embed(f.read_bytes(),image=True)) for f,stamp in pairs]
    with conn() as db:
        db.execute("DELETE FROM media_vectors WHERE path=? AND project=?",(str(path),project))
        for stamp,v in vectors:
            ident=hashlib.sha256((project+"|"+str(path)+"|"+str(stamp)).encode()).hexdigest()
            db.execute("""INSERT INTO media_vectors
                (id,project,path,timestamp,kind,source_sha256,embedding,indexed_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (ident,project,str(path),stamp,
                 "image" if stamp is None else "video-frame",sha,json.dumps(v),core.now()))
        db.commit()
    return {"indexed":len(vectors),"project":project,"type":"video" if path.suffix.lower() in VIDEO_EXTS else "image",
            "cloud_upload":False}

def search_media(query,project=None,limit=5):
    if not isinstance(query,str) or not 3<=len(query.strip())<=600:
        raise ValueError("Query must be 3–600 characters")
    if project is not None and (not isinstance(project,str) or len(project)>90):
        raise ValueError("Invalid project")
    with conn() as db:
        items=[dict(x) for x in db.execute("SELECT project,path,timestamp,kind,embedding FROM media_vectors")]
    if project:items=[x for x in items if x["project"]==project]
    if not items:return {"matches":[],"indexed":0,"model":MODEL}
    q=input_embed(query)
    for m in items:
        v=json.loads(m.pop("embedding"))
        m["similarity"]=round(sum(a*b for a,b in zip(q,v)),4)
    items.sort(key=lambda x:x["similarity"],reverse=True)
    return {"matches":items[:max(1,min(10,int(limit)))],"indexed":len(items),
            "model":MODEL,"cloud_upload":False,
            "note":"Similarity is retrieval only, not visual or audio critique."}
