# Tyrion — The Hand (v0.6.0)

Local-first operations dashboard for Advertpreneur, built without paid model APIs or external package dependencies.

## Run
- Linux Mint menu: **Tyrion - The Hand** (when the desktop launcher is installed)
- Terminal: `./launch.sh`
- Local dashboard: `http://127.0.0.1:17877/`
- Stop service: `./stop.sh`

## What is working
- Local light-mode dashboard and an original Seal icon.
- SQLite project records (external progress deliberately labelled **needs sync**).
- Task creation, priority, completion and approval state, with local audit history.
- Editable working identity (professional behavior rules, not automatic impersonation).
- Skill registry reading the existing Advertpreneur toolkit and its two registered external design skills. Uses **actual readable** SKILL.md files.
- Safe housekeeping: daily task brief and catalog refresh (runs while service remains running).
- Local command bridge callable from connected ChatGPT Local Files:
  `python3 -m tyrion.bridge snapshot`
  `python3 -m tyrion.bridge create-task 'Review image crop' --project Glissimo --priority high`
  `python3 -m tyrion.bridge tasks`
  `python3 -m tyrion.bridge skills WordPress`
- MCP stdio endpoint for future compatible MCP hosts: `python3 -m tyrion.bridge mcp`.

## Not yet implemented
- Live authentication or write adapters for WordPress, Shopify, Meta Manager, ShieldPress, etc.
- Direct ChatGPT plugin connection (account-dependent). ChatGPT can use the current Local Files connection to call the CLI bridge instead.
- AI reasoning when ChatGPT is not actively interacting; scheduled jobs work without an LLM.
- Automatic live website repairs, client messaging or publishing; those require explicit tool integrations and permission controls.
- Compiled Tauri binary; this version opens a native GTK/WebKitGTK desktop window using preinstalled system libraries.

## Security and performance
- UI server binds to `127.0.0.1` only and checks the Host header.
- State changes require same-origin requests and a volatile session token.
- No CORS and restrictive Content Security Policy; SQLite file is private to the user.
- No cloud model API, telemetry, analytics libraries, paid services, or heavy frontend framework.
- Third-party skill files are untrusted instructions; never execute them automatically.
- No generic shell executor in the web API or MCP bridge.

The operating data resides under `data/`. Back up that directory to preserve tasks and identity.

## v0.2 integrations and approval controls
- **Meta Manager:** Direct live read-only localhost MCP adapter on port 38939; list connected accounts and calendar status; optional **create-draft only** action with operator approval in the Tyrion desktop UI. No publishing tool is allowlisted.
- **Advertpreneur QA:** Direct localhost API adapter on port 8742; read scan status counts and health.
- **Advert Connect:** ChatGPT relay snapshot only, with two verified sites at the time of import. The WordPress credentials never enter Tyrion, and the relay is **not** an autonomous local connector.
- **ShieldPress / GBP / other cloud APIs:** Not natively connected. GBP localhost service requires authorization; never assume access.
- **Identity:** Editable local professional defaults, not actual ChatGPT memory or authority.
- **Skills:** Deterministic task-to-skill suggestions using existing catalog references. The skill instructions are not executable automation.
- **Scheduler:** In addition to local daily briefs and catalog checks, checks Meta Manager and QA every 15 minutes while user service runs.
- **Systemd service:** `systemctl --user status tyrion-hand.service`; enabled to start automatically on login. No AI model charges.
- **MCP:** `python3 -m tyrion.bridge mcp` exposes the approved read-only status and work-tracking tools plus a proposal-only draft tool. A dedicated remote ChatGPT MCP plugin/tunnel is **not yet connected**; the working ChatGPT integration uses the existing Local Files connector.

## Operator approval design
Only the local dashboard offers approval decisions. Creating an approval request never changes a remote system. The approve operation validates that the target Meta Manager account is still connected and calls only the Meta draft creation tool. Network timeouts become **needs review** without automatic retry to avoid duplicate drafts. Do not approve an action before reviewing its destination and content.

## v0.3 — Tyrion-owned independent scheduler
- Installed persistent scheduler in `tyrion/workflow_scheduler.py` backed by SQLite. Supports daily, weekly and one-time tasks, using IANA timezone-aware times (default Asia/Karachi).
- Starts automatically alongside the existing `tyrion-hand.service`; checks due jobs every 10 seconds while computer is running, catch-up at startup enqueues at most one run per missed schedule.
- Create, edit, pause, resume, run-now, archive; archived histories and existing drafts remain inspectable. Queue max three unreviewed runs per schedule to prevent runaway jobs.
- Default schedule: **CooCoo Babys — Daily SEO Blog** at **20:00 Asia/Karachi**, with detailed instructions to verify site content overlap, research and create a quality-controlled draft. Mode is `chatgpt_handoff` by default; it queues work instead of pretending to wake ChatGPT.
- `chatgpt_handoff` exposes pending work as `tyrion_due_chatgpt_work` through MCP / Local Files CLI (`python3 -m tyrion.bridge due-work`), and accepts a completed draft through `tyrion_submit_blog_draft`. Works only during an active ChatGPT conversation, with no ChatGPT Tasks slots consumed by Tyrion's schedule itself.
- For unattended drafts, explicitly choose `ollama_local` and one of the already installed local models `qwen3.5:4b` or `qwen3.5:0.8b`. This uses the local Ollama endpoint (port 11434), with no OpenAI API and no cloud models. It can consume substantial CPU/RAM and outputs need factual/SEO/duplication review. No auto-publish.
- Drafts are saved under `data/generated/tyrion-run-XXXXXX.md` (owner-only permissions), and can be opened from the dashboard. No WordPress site is updated by Tyrion's scheduler.
- This **does not increase ChatGPT's five active scheduled-task slots** or provide a way to make ChatGPT execute arbitrary prompts unprompted. An MCP server is called by ChatGPT, not a persistent reverse-chat channel.
- CLI examples: `python3 -m tyrion.bridge schedules`, `python3 -m tyrion.bridge due-work`, `python3 -m tyrion.bridge run-schedule 1` (queues a real manual run).
- Browser: `http://127.0.0.1:17877/#scheduler`.

## Single ChatGPT dispatcher handoff (one ChatGPT scheduled slot)
1. Tyrion queues scheduled work independently, in local SQLite, with any number of local schedule definitions.
2. ChatGPT scheduled dispatcher (if connected Local Files plugin access is available at automation runtime) asks Local Files to run `python3 -m tyrion.bridge due-work` from `Documents/Tyrion-The-Hand` and reviews no more than 1–2 jobs per run.
3. ChatGPT creates a factual, researched `# Title

...Markdown content...` file via Local Files write_file to `Documents/Tyrion-The-Hand/data/inbox/tyrion-run-<ID>.md` (create folder first if needed).
4. It runs `python3 -m tyrion.bridge submit-draft <ID> data/inbox/tyrion-run-<ID>.md` via Local Files command and reads back the verified `draft_ready` state.
5. To review autonomous local Ollama drafts: `python3 -m tyrion.bridge review-queue` then `python3 -m tyrion.bridge read-draft <ID>`; save a revised Markdown file to inbox and run `python3 -m tyrion.bridge revise-draft <ID> data/inbox/<file>.md`.
6. No automatic publishing in this dispatcher. Quality review and any later WordPress publication remain separate and require their actual supported connected tools and approvals.

**Limitations:** A ChatGPT scheduled task still consumes one ChatGPT slot. The independent Tyrion schedules themselves do not. ChatGPT scheduled task runtime may lack access to a local computer or Local Files tunnel, in which case it must report the blocker and leave work queued. Do not try to control browser ChatGPT through automation or reuse account session cookies.

### Dispatcher callback verification
Tyrion's Scheduler page displays whether the ChatGPT dispatcher has been configured and the time of its last callback. The first callback is **not verified until an unattended scheduled run actually reaches the local bridge**. After successfully checking the queue, the dispatcher calls `python3 -m tyrion.bridge dispatcher-heartbeat --processed N`; this logs a callback but does not independently prove content quality. Check real draft artifacts and WordPress status separately.

## v0.4 — Project Hub and expanded connections (October 24, 2026)
- 27 known client, internal-tool and development projects registered. Status remains independent of existence or completion; imported project names do not imply current work is done.
- Project Hub offers filtering, project details, task/schedule counts, connector associations, and validated new projects/resources. Known HTTPS site references, verified GitHub repo URLs, and existing Documents/Downloads project folders are indexed; no files from those folders are copied into Tyrion.
- Live localhost integrations: Meta Manager MCP (account/calendar summary) and Advertpreneur QA API (scan/health summary). Both verified using real read-only calls.
- Local inventory only: ShieldPress security-console fleet database (nonsecret site names/counts only) and four WP Lab workspaces. Neither grants Tyrion external WordPress admin permissions.
- Local GBP server health probe: responds, but protected API requires authorization and Google Business Profile API approval remains pending.
- ChatGPT-side relay snapshots: Advert Connect (advertpreneur.com and coocoobabys.com, plugin v0.6.3), Shopify development store, Supabase advertpreneur-connect, GitHub account and verified repos, and Vercel project list. These are **not** persistent local OAuth sessions; the relay data is stamped and visually ages after 24 hours.
- GSC Wizard/Bing through that connector returned a subscription-required error. Tyrion does not pay for or attempt to circumvent the provider; independent read-only GSC/Bing access requires another supported authorization path.
- OAuth credentials, site application passwords and Vault contents were **not** imported into Tyrion.
- Local HTTP server remains loopback-only with approval-controlled external draft creation. No automatic WordPress publishing or changes to production client websites were enabled.
- See `data/VERIFICATION_V04.json` for measured connection levels, tests and outstanding blockers.

## v0.5 — One-entry shared work
Tyrion now has a durable single-entry change feed for project/task/schedule/run mutations and task-update notes writable by ChatGPT through the Local Files or MCP bridge. The operator should enter each work item only once. See **CHATGPT-SHARED-WORK.md** for CLI actions, change acknowledgments, scheduler integration, authorization boundaries and the present lack of instant ChatGPT push events.

## v0.6 — Instant local events, refreshed task dialog, MCP 2.0 events readiness
- Redesigned Shared Task dialog; padded header, progress timeline, accessible close control, readable notes and mobile layout. Rendered and checked with real Chrome screenshot in `data/modal-v06.png`.
- Local desktop notifications for newly created tasks/projects, edited project briefs, new/edited schedules, and queued due runs, typically within one second. They do not wake ChatGPT.
- Browser dashboard real-time event feed over same-origin SSE (`/api/realtime/stream`), with resume cursor and automatic reconnect; UI refreshes without manually reloading the page.
- Dedicated 1-second due-work scheduler thread, not blocked by slow external health checks.
- Project editor for category/brief with `project.updated` change feed and MCP tool; client websites remain untouched.
- MCP 2.0 `server/discover` + `events/list` / `events/subscribe` / `events/unsubscribe` in local STDIO bridge. Six types, persisted verified subscriptions, signed public HTTPS callbacks, retry queues and destination SSRF restrictions.
- **Important:** ZERO external ChatGPT event subscriptions at installation time. Instant delivery to ChatGPT requires a dedicated authenticated MCP Tunnel and subscription from a compatible ChatGPT Work conversation or dot. See `TYRION_CHATGPT_WORK_EVENTS.md`. The existing hourly ChatGPT dispatcher remains the fallback.
- No new paid model API; the existing MCP Bridge and `tunnel-client` are installed, but no Tyrion-specific tunnel identity/key has been provisioned.

## v0.7 — Tyrion Browser Companion (Chat mode)
- Independent Chrome Manifest V3 extension in `browser-extension/` using Tyrion's original gold hand seal. Isolated service worker tested in Chrome.
- Pairs locally through a separate 0600-permission random key, copied from the Tyrion Connections page. API uses a secret header and origin/host validation; no ChatGPT account cookies or model APIs.
- Displays current open tasks, due handoffs, review-ready drafts; Chrome badge updates periodically and popup refreshes every 3 seconds while open. Local Tyrion daemon still receives changes immediately.
- One-click **Copy handoff** or **Open chat** prepares a fresh recovery instruction from actual task/run IDs, saved instructions and latest notes. You paste it manually into ChatGPT Chat with Tyrion MCP selected. The extension does not scrape ChatGPT output, send prompts, force Stop/Regenerate or defeat service limits.
- Browser popup can add an operator-entered note to the same Tyrion task. It cannot auto-complete, publish or modify sites.
- Local Ollama remains available for genuinely unattended *draft* work through explicit scheduler engine settings; original publication and verification gates stay intact.
- The previous ChatGPT hourly Tyrion Sync Dispatcher was disabled at the user's request. Other ChatGPT automations were not changed.
- Installation instructions: `browser-extension/README.md`, ZIP in `~/Downloads/Tyrion-Browser-Companion-v0.7.zip`.
- More capable autonomous task execution would require an authorized model/agent runtime and explicit verification/approval per action. A Chrome extension cannot reliably turn interactive ChatGPT Chat into a background API.

## v0.8 — ChatGPT tab handoff (October 25, 2026)
- User's Chrome extension detects new local tasks and due handoff runs, then opens a visible ChatGPT chat tab with a non-sensitive task-ID prompt, default enabled and toggleable.
- Deduplicates by task/run ID, limited to three automatic tabs per hour, and excludes older completed tasks. A persistent Chrome storage ledger prevents reopens after reloads.
- Actual ChatGPT prompt submission and work execution remain user-initiated in regular Chat mode; the extension cannot infer or claim completion by opening a tab. ChatGPT MCP writes progress to the same Tyrion record.
- Keep Chromium extension reloaded after updating unpacked extension files; automatic opening typically polls every 30 seconds when no Tyrion popup is visible.

## v0.9 — One-shot ChatGPT Chat starter
- An extension-controlled, nonce-authorized handoff now opens a visible new ChatGPT Chat with a generic Tyrion task ID, verifies the unmodified prefilled composer text, and clicks Send exactly once when Auto-start is enabled. The extension never reads ChatGPT output or loops Stop/Regenerate.
- A per-task ledger and existing ChatGPT task-update notes prevent duplicate chats; maximum three automatic starts per hour. Local service checks roughly every 30 seconds while the extension is active. A send-button click is not a verified completed task; Tyrion MCP receives the real progress notes.
- Requires Chrome extension reload and approval of the new chatgpt.com host permission. When unsigned in or unsupported ChatGPT UI, the user must manually submit.

## Tyrion – The Companion · Android v1.0 (2026-10-25)

A real Android APK sharing the PC Tyrion UI and database, using a **tailnet-only** Tailscale HTTPS proxy on port 8443. There is no cloud task replica. The PC runs `tyrion-companion.service` loopback port 17878, and the existing `tyrion-hand.service` remains unchanged. A one-time QR/8-digit pairing code and encrypted/revocable per-phone token grant mobile access; actions always go to the original PC APIs with their existing approval boundaries. The existing public Funnel on 443 was not modified.

APK: `/home/haseeb/Downloads/Tyrion-The-Companion-v1.0-debug.apk`.
Private installer: `https://haseeb-optiplex-3050.tailb87e57.ts.net:8443/download/Tyrion-The-Companion-v1.0.apk`.
Phone-specific pairing and installation guide: `android-companion/README.md`.

Unit tests cover pairing expiry, single-use codes, revocation, authenticated read/write relay, and origin rejection. Android Gradle debug build and lint pass. Mobile-origin 393px viewport rendering was verified using PC Chromium, screenshot `data/companion-mobile-preview.png`. Physical Android install awaits the user's phone reconnecting to Tailscale.

## Tyrion Companion v1.1 — realtime PC dispatch and Android recovery (2026-10-25)

Root cause of missed Android task pickup: the old Chrome MV3 extension ignored tasks outside a 45-minute creation window. Mobile delivery itself worked, but Task #7 lacked a ChatGPT handoff. v1.1 replaces timestamp filtering with a **persistent SQLite dispatch queue**, atomically claims each task, and preserves work through browser outages. New PC/dashboard/Android tasks are queued automatically, except MCP-authored tasks (to avoid self-trigger loops). Scheduled ChatGPT runs are queued by Tyrion's own due watcher; existing older tasks can be queued explicitly from the **Dispatch** page.

Dispatch stages: `queued → claimed → opened → submitted → progressing → completed`. A Chromium browser or ChatGPT UI error is recorded as `needs_attention`. Tyrion detects stale claims (2 minutes), opened tabs (10 minutes), and unconfirmed submissions (20 minutes), **without blind retries**. Only an operator can choose `Resume handoff`, and the original task is reused. The browser extension reports task pickup status to the PC and offers one-shot ChatGPT submission with its nonce-verified task ID. No chat scraping, forced Stop/Regenerate, or automatic unsafe operations.

The extension v1.1.1 also opens a private authenticated `ws://127.0.0.1:17879` channel using a per-install pairing secret and strict Chrome extension Origin. The PC emits small event IDs within approximately a second; the Chrome MV3 worker pumps the SQLite queue on event and retains 30-second alarm fallback. New user service `tyrion-companion-events.service` auto-starts alongside `tyrion-hand.service` and `tyrion-companion.service`.

PC and Android use the same **Dispatch** screen, live status, Chrome availability check, and verified progress. Android reuses its existing v1.0 APK/WebView; updates are served from the PC on WebView reload, no app reinstall. No private app credentials are sent through event notifications. The existing Tailscale 443 public Funnel is unchanged; mobile HTTPS remains tailnet-only 8443.

Reload unpacked Chrome extension once in `chrome://extensions` to activate v1.1.1. Check the Dispatch page for a fresh **PC browser connected** indicator. The mobile Companion itself must be refreshed (long-press → Refresh live workspace, or relaunch) to fetch the new page. Validation: 61 Python backend tests; 9 extension tests; HTTPS mobile viewport screenshot `data/companion-dispatch-mobile.png`; WebSocket authentication and realtime event delivery tested. Real auto-submit with the updated extension still needs a browser reload and new task to verify; do not call it fully verified until then.

## EmbeddingGemma knowledge engine (2026-10-26)
- **Knowledge** page added to the existing desktop dashboard: semantic retrieval of approved local projects, tasks, task updates, catalog descriptions and documentation.
- Local-only EmbeddingGemma 2 270M Q8 model on isolated Ollama port 11435; original Ollama 11434 and all existing models remain unchanged.
- CLI: `python3 -m tyrion.bridge knowledge-search "query"`; `knowledge-sync`; `knowledge-status`. MCP tools: `tyrion_knowledge_search` and `tyrion_knowledge_status`.
- Semantic skill alternatives and optional project-scoped local model draft context. No client writes, credentials, payment APIs or vault indexing. Fatir is discontinued and excluded.
- Source of truth remains the existing Tyrion database; derived vector index is rebuildable. **See KNOWLEDGE-ENGINE.md** for access control, privacy and deployment limits.

### ChatGPT shared memory protocol
Read `CHATGPT-KNOWLEDGE-CONTRACT.md` for the one-source-of-truth project retrieval and verified-progress writeback policy. Independent ChatGPT platform memory does not automatically mirror Tyrion.

## Live on-demand Advertpreneur skill engines (2026-10-26)

Tyrion's existing `tyrion_route_skills` now prioritizes Ponytail for minimal/reuse-first code changes, REA for shipped-app inspection, Scrapling for crawling, and Last30Days for current community research. Router reads the canonical Advertpreneur skill catalog; all four newly registered skills were verified.

The **private stdio MCP bridge** now additionally advertises three strictly allowlisted tools:

- `tyrion_engine_status` — read-only local capability status.
- `tyrion_recent_research(topic)` — cookie-free, 30-day, bounded Reddit/Hacker News retrieval via Last30Days. No paid search providers or publishing. Third-party evidence remains untrusted and must be checked for source freshness.
- `tyrion_rea_aura_extension()` — inert static JavaScript analysis of the single fixed AURA Download Manager Chrome extension target, returning structured graph/evidence facts. No arbitrary target path or executable runtime access.

Scrapling runs inside GSC Maestro's existing security-preserving public crawler; Ponytail is an instruction workflow, not a resident process. These handlers execute **only on request** and create no new always-on agent. The Tyrion tunnel service has been restarted and the local MCP protocol advertises/answers all three tools. ChatGPT's current plugin tool catalog may still require a refresh/reconnect before their names become available as native actions; existing skill-routing tools remain usable.

Tests: `python3 -m unittest tests.test_skill_engines tests.test_core -q` (16 tests passing on 2026-10-26). `tyrion_recent_research` was also exercised against live public discussions; REA returned matching earlier AURA static evidence. No production client sites, credentials or account actions were altered.

### October 26, 2026 — ChatGPT action refresh completed

The existing Tyrion developer plugin's **Refresh tools** action was invoked in authenticated ChatGPT settings. All three new MCP tools are now discoverable and callable by ChatGPT, and their engine status, REA static AURA analysis and cookie-free Last30Days execution were verified with real responses. Four capability-routing requests each ranked the corresponding skill first. Prior caveats in this README about needing a future ChatGPT action refresh are superseded by this verification. See `PLUGIN_TOOL_REFRESH_2026-10-26.md`.

## October 26, 2026 — Combined Editorial Research

Added account- and brand-scoped on-demand editorial research in `tyrion/content_research.py`. New MCP actions are `tyrion_content_research`, `tyrion_content_research_latest`, `tyrion_content_keyword_import` for Instagram, LinkedIn, and CooCoo Babys tracks. Each combines available Last30Days public discussions, directly synced GSC data and Google Ads keyword seeds; source-labelled Ubersuggest fallback ideas are separate from the unavailable E92 Google Ads Planner metrics. Saved packets are consumed by Meta Manager and GSC Maestro with explicit brand authorization. See `CONTENT_RESEARCH_STATUS_2026-10-26.md`.

### October 26 follow-on: Existing-page editorial targeting

The content research packet now includes review-only `editorialOpportunities` and verified Google Search Console landing-page rows. CooCoo Babys' baby monitor, stroller, warmer, humidifier and carrier topics map to **existing** URLs to avoid duplicate article creation. `tyrion_content_research` preserves prior provider evidence across refreshes while flagging stale data. Meta Manager reads only explicit authorized local account IDs; GSC Maestro's native MCP now exposes page-targeted research. See `CONTENT_RESEARCH_EDITORIAL_PRIORITIES_2026-10-26.md` for the saved recommendations and `CONTENT_RESEARCH_STATUS_2026-10-26.md` for test evidence.
