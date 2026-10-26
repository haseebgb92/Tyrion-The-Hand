"""Opt-in read-only client for local Advertpreneur Python applications.

Run under the same OS user as Tyrion. No independent model, scheduler or API key.
"""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ADDRESS = "http://127.0.0.1:17877/api/knowledge/shared/search"
KEY_PATH = Path.home() / "Documents/Tyrion-The-Hand/data/knowledge-readonly.token"

def search(query: str, project: str | None = None, limit: int = 5, media: bool = False):
    if not isinstance(query, str) or len(query.strip()) < 3:
        raise ValueError("A meaningful query is required")
    if project is not None and not isinstance(project, str):
        raise ValueError("Invalid project")
    token = KEY_PATH.read_text(encoding="utf8").strip()
    data = json.dumps({"query": query, "project": project, "limit": limit}).encode()
    request = Request(ADDRESS.replace("/shared/search", "/shared/media-search") if media else ADDRESS, data=data, headers={
        "Content-Type": "application/json", "X-Tyrion-Knowledge-Key": token}, method="POST")
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    return payload["result"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--project")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--media", action="store_true")
    opts = parser.parse_args()
    print(json.dumps(search(opts.query, opts.project, opts.limit, opts.media), indent=2))
