# Content research integration — verified 2026-10-26

## Working path

- Tyrion's on-demand `tyrion_content_research(track)` and `tyrion_content_research_latest(track)` assemble separate packets for Instagram, LinkedIn, and CooCoo Babys. Each packet retains sourced Google Search Console snapshot dates, recent Reddit/Hacker News discussions from Last30Days, Google Ads Keyword Planner seed phrases, and optional source-labelled Ubersuggest keyword suggestions.
- `tyrion_content_keyword_import(track, rows)` accepts strictly checked keyword data supplied by the authenticated E92 connector after it succeeds; no fabricated monthly search volumes.
- Source packets: `~/.local/share/tyrion/content-research/{instagram,linkedin,coocoobabys}.json` (file mode 0600).
- Meta Manager's locally installed MCP service `127.0.0.1:38939` exposes `strategist_research_evidence(account_id)` and adds a short research status to `get_strategist_brief`. Exact account mapping prevents client data mixing; unrelated clients receive no mapped track. Its running bundle lives at `/usr/lib/Meta Manager/resources/meta-manager-mcp.cjs`, with pre-change backup `meta-manager-mcp.cjs.backup-content-research-20261026`.
- GSC Maestro's installed MCP service `127.0.0.1:8798` exposes `maestro_content_research(siteUrl,channel)` for verified synchronized properties; its installed bundle at `~/.local/opt/gsc-maestro/mcp/gsc-maestro-mcp.mjs` has a pre-change backup `gsc-maestro-mcp.mjs.backup-content-research-20261026`.
- Three refreshed ChatGPT plugin action catalogs were triggered in a separate browser settings tab. Direct tool-call verification in a fresh ChatGPT session remains the final UI-side check; live local MCP API tests passed.

## Verified tests

- Tyrion: 21 unit/regression tests passed; 45 advertised MCP tools including 3 content-research tools; Tyrion core and tunnel active.
- Meta Manager: 15 strategist tests passed; live MCP tools/list includes strategist_research_evidence and account isolation tested for LinkedIn, Advertpreneur Instagram, and unrelated clients.
- GSC Maestro: 18 tests passed; live local authenticated service active; optional packet reader returns 15 CooCoo Babys Google queries and 6 source-labelled Ubersuggest related keyword ideas.
- CooCoo Babys data period: 2026-09-26 to 2026-10-23, synced 2026-10-26. "best baby monitor without wifi" 180 impressions, average Google position 10.24; "best baby monitor no wifi" 111 impressions, avg position 9.37. These are actual GSC organic impressions, not Google Ads monthly volume.
- Ubersuggest fallback for US/en: `shopify seo` 1,900 estimated monthly searches; `ai search optimization` 1,300 estimated monthly searches (both source-labelled as Ubersuggest, not Google Keyword Planner). Baby monitor keyword rows returned zeros; volume recorded as null/unknown rather than proof of zero demand. Related phrases retained as ideas.

## Remaining limitation

The connected E92 Keyword Explorer fails with generic internal errors for both `search_keyword_ideas` and `get_keyword_metrics`, including tiny valid US/en requests. Even its `list_meta_assets` fails; this suggests a connector/backend problem rather than an individual seed-keyword failure. The Google Ads Keyword Planner import connector is wired but unverified end-to-end. Never claim E92 volumes are available until a successful real API call.

## AURA test URL

`http://127.0.0.1:19641/aura-test.zip` is a local URL served on the user's machine. Read-only probe returned HTTP 200, `Content-Type: application/zip`, 5,242,880-byte length, and a non-ZIP first-byte signature (`4f1f3588...`, not `PK`). It appears to be a test payload and is **not** a usable public keyword research URL. No arbitrary archive was executed, decompressed or submitted to E92.

## Safe boundaries

No social posts were created, scheduled or published; no client WordPress websites modified; no new ChatGPT automations or daemons added; no browser cookies read. Research packets are source evidence for editorial review, not autonomous claims of trend or search volume.

## Follow-on quiet improvements (2026-10-26)

- Discarded the accidental AURA ZIP reference, with no archive processing or new AURA work.
- Added `editorialOpportunities` to all three saved research packets. Instagram/LinkedIn receive fact-check-gated social education/leadership ideas; CooCoo Babys gets five search-backed topic clusters.
- Compared CooCoo Babys topic clusters with *actual GSC landing page rows* before proposing content. All five major topics already have established blog URLs: non-Wi-Fi monitors, lightweight travel strollers, bottle warmers, nursery humidifiers and newborn baby carriers. The plan explicitly sets `recommendedAction=refresh_existing_page`, not create duplicates.
- CooCoo Babys non-Wi-Fi monitor article's 2026-09-26..2026-10-23 GSC page figures: **1,136 impressions, 1 click, avg position 18.08**. Baby-carrier page: 811 impressions, zero clicks, avg position 48.57. These are observed per-URL figures, not keyword demand or ranking forecasts.
- Added a provenance-safe preservation rule: regenerating Last30Days/GSC research no longer silently overwrites imported E92 metrics or previous Ubersuggest suggestions; stale provider evidence is marked rather than presented as freshly retrieved. Failed recent-source refresh can retain a clearly labelled older report.
- Added editorial safety gates: promotional forum headlines cannot be mistaken for unbiased trend proof, medical/child safety claims require authoritative evidence, and GSC impression sums are marked as potentially overlapping observations.
- Fresh read-only Ubersuggest keyword suggestions for US/en non-Wi-Fi baby monitors were stored with unavailable monthly volume set to null (not zero).
- Tightened Meta Manager's research scope to exact locally verified workspace UUIDs rather than display-name similarity, and included reviewable editorial angles in the existing strategist brief. Live Meta MCP account-isolation tests passed for personal LinkedIn, Instagram, Advertpreneur and an unrelated workspace.
- Extended GSC Maestro's `maestro_content_research` response with page-level GSC evidence, existing-page editorial actions and source-quality metadata. Native MCP bundle was deployed and authenticated service restarted; public unauthenticated endpoint still returns expected HTTP 401. All 18 GSC tests passed.
- All **28 Tyrion content/core/engine tests**, **15 Meta Manager strategist tests**, and **18 GSC Maestro tests** passed. No posts published, no WP production changes, no additional daemons or paid APIs introduced.
- Saved reviewer report: `~/Documents/Tyrion-The-Hand/CONTENT_RESEARCH_EDITORIAL_PRIORITIES_2026-10-26.md`.
- E92 Keyword Explorer remains unavailable: three distinct tool families (Keyword Planner ideas, exact metrics, Meta asset listing) returned the same internal error on valid calls. This is a connector-side blocker, not evidence that keyword volumes are zero. Existing Ubersuggest/GSC/Last30Days workflows remain usable.
