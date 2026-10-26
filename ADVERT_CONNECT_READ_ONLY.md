# Advert Connect — Tyrion read-only probe (Task #1)

This adapter is **only an unauthenticated HTTPS status-route probe** for the
two allowlisted hosts, `advertpreneur.com` and `coocoobabys.com`.
It does not replace ChatGPT's authorized Advert Connect MCP connector.

## Safe usage
- Command: `python3 -m tyrion.bridge probe-advert-connect`
- MCP tool (after bridge restart/reload): `tyrion_probe_advert_connect` with
  `{"site":"all"}` or a single exact allowlisted host.
- Sends one GET per host to `/wp-json/advertpreneur-connect/v1/status`,
  with a five-second timeout, a 16 KiB response cap, no proxy and no
  automatic redirects. It sends no tokens, cookies or Authorization headers.
- `authentication_required` with `route_confirmed=true` means an installed
  WordPress route rejected an anonymous client; it **does not mean Tyrion
  authenticated**. `public_status_available` also does not imply auth.
- Unexpected responses, arbitrary domains, redirects, or failures never
  produce a connected/authenticated status.

## Remaining integration blocker
The real WordPress /status route requires `edit_posts` access. A genuine
native, authenticated Tyrion adapter needs an explicitly approved,
read-only-scoped auth mechanism (with proof that write endpoints are denied).
Existing WordPress application passwords may include write privileges, so
none were copied, read, imported or reused. No production site or external
service has been modified. ChatGPT-side relays remain separately labeled.

## Offline validation
Run `python3 -m unittest discover -s tests -q` from Tyrion's root. The
adapter's offline tests mock all HTTP operations and verify GET-only,
allowlisting, redirect blocking, lack of auth, and fail-closed parsing.
