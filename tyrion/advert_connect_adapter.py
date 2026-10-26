"""Credential-free, bounded Advert Connect status probes.

Only the two operator-verified site hosts are supported. This probe NEVER
authenticates, never reads secrets, never performs a write, and never treats a
protected WordPress route as an authenticated Tyrion connection.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import core

HOSTS = ("advertpreneur.com", "coocoobabys.com")
ROUTE = "/wp-json/advertpreneur-connect/v1/status"
MAX_BYTES = 16384

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _opener():
    # Do not forward requests to a proxy picked up from the environment.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

def _read_bounded(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized_status_response")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_status_shape")
    return data

def probe_host(host, *, opener=None):
    if host not in HOSTS:
        raise ValueError("Site host is not on the exact Advert Connect probe allowlist")
    url = "https://" + host + ROUTE
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "User-Agent": "Tyrion-ReadOnly-Probe/1.0"}
    )
    result = {
        "host": host, "mode": "unauthenticated_readonly_probe",
        "checked_at": core.now(), "authenticated": False,
        "read_only": True, "status": "unverified",
        "route_confirmed": False
    }
    opener = opener or _opener()
    try:
        with opener.open(request, timeout=5) as response:
            data = _read_bounded(response)
            if data.get("ok") is True and data.get("plugin") == "Advertpreneur Connect":
                result["route_confirmed"] = True
                result["status"] = "public_status_available"
                result["plugin_version"] = str(data.get("version", ""))[:40]
            else:
                result["status"] = "unexpected_public_response"
    except urllib.error.HTTPError as exc:
        # Route-specific WP rest_forbidden confirms an installed, protected
        # endpoint but does NOT confirm a logged-in connection.
        if exc.code in (401, 403):
            try:
                data = _read_bounded(exc)
            except (ValueError, UnicodeError, OSError):
                data = {}
            if data.get("code") == "rest_forbidden":
                result["route_confirmed"] = True
                result["status"] = "authentication_required"
            else:
                result["status"] = "authorization_or_gateway_blocked"
        elif exc.code in (301, 302, 303, 307, 308):
            result["status"] = "redirect_blocked"
        elif exc.code == 404:
            result["status"] = "route_missing"
        else:
            result["status"] = "http_error"
            result["http_status"] = int(exc.code)
    except (urllib.error.URLError, OSError, ValueError, UnicodeError):
        # No raw exceptions or response bodies (which could contain secrets)
        # are persisted or returned.
        result["status"] = "probe_failed"
    return result

def probe(site="all"):
    if site == "all":
        targets = HOSTS
    elif site in HOSTS:
        targets = (site,)
    else:
        raise ValueError("Unsupported site; expected an exact allowlisted host or all")
    sites = [probe_host(host) for host in targets]
    return {
        "mode": "unauthenticated_readonly_probe",
        "authenticated": False, "sites": sites,
        "note": "Protected route detection is not native authenticated WordPress API access. No credentials or write operations used."
    }
