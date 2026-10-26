# Tyrion Knowledge Engine — EmbeddingGemma 2

Operational status: integrated and locally tested on 2026-10-26.

## What works
- Uses isolated Ollama 0.40.11 on 127.0.0.1:11435, separate from existing 11434.
- Uses embeddinggemma-2:270m-q8_0-text, 256-dimensional vectors and two CPU threads.
- Search in Tyrion dashboard > **Knowledge**.
- Project, task, progress-update, installed skill-description and explicitly allowlisted documentation indexing.
- Auto-incremental refresh on each search and manual "Refresh local index".
- Hybrid skill router returns precise semantic alternatives alongside deterministic suggestions.
- Local Ollama scheduled draft generator gets optional project-scoped context (never another client's project/task notes). If retrieval fails, draft workflow proceeds unchanged.
- Local MCP/CLI search provides relevant citations to existing records; no external tool execution.
- 70 unit tests passing; authorized HTTP status and search endpoints checked.

## Privacy / guardrails
- No vaults, credential exports, passwords, arbitrary directory traversal, or Fatir records are indexed.
- No automatic upload to cloud embeddings or paid APIs. Only Ollama localhost receives the embedded text.
- Search results returned through ChatGPT/MCP may be seen by the connected LLM provider; don't request or forward sensitive data.
- Task/project source records stay in authoritative Tyrion SQLite DB; knowledge.sqlite3 is a rebuildable derived cache (owner-only).
- Search snippets are **untrusted reference material**, never operational instructions or authorization.
- No automatic publishing, messages, spending, approval bypass, client-site writes, or credential access.
- Active CPU inference is limited to 2 threads; model unloads after idle. The embedding runner can consume about 528 MB when loaded.
- Excluded user-stated discontinued project: Fatir (no further integration work).

## Commands
From ~/Documents/Tyrion-The-Hand:

```bash
python3 -m tyrion.bridge knowledge-status
python3 -m tyrion.bridge knowledge-sync
python3 -m tyrion.bridge knowledge-search "How are duplicate Tyrion tasks prevented?"
python3 -m tyrion.bridge route "Optimize generative AI visibility for ecommerce content"
```

Existing independent CLI remains:

```bash
tyrion-search --query "What blocks Advert Connect?"
```

## Authenticated browser API
- GET /api/knowledge/status — requires dashboard session header.
- POST /api/knowledge/search — JSON {query, limit}, requires dashboard token and same-origin.
- POST /api/knowledge/sync — refreshes incremental derived index, requires session token and same-origin.

MCP stdio tools:
- tyrion_knowledge_status
- tyrion_knowledge_search (query, limit, optional project)

The dedicated remote Tyrion MCP plugin must refresh its tool manifest before the newly added tools can be assumed available to ChatGPT. Local stdio MCP tools/list was verified.

## Scope for adjacent Advertpreneur tools
- GSC Maestro: candidate for clustering search intents once connected to appropriate verified metrics; NOT automatically integrated into its reporting pipeline yet.
- Advert Connect: candidate for related-article and internal-link recommendations; NOT connected to its WordPress publishing path.
- Android Companion: should query Tyrion's existing authenticated PC relay, not expose the local embedding server or copy the index to the phone; NOT integrated yet.
- Shopify/WordPress projects: do not index or change production content automatically.

## Retrieval limitations
Vector similarity is not a truth score; always check the linked original record and its timestamp. New/modified selected records are reindexed on a search or manual refresh, not monitored every second. Adding additional data sources requires a targeted allowlist/privacy review.

## Upgrade and shared service (2026-10-26)
- Added full EmbeddingGemma 2 `embeddinggemma-2:740m-q8_0` to the **isolated Ollama on port 11435**. Validated 256-dimensional text, image, and audio requests. Text queries continue using the 270M Q8 model, as loading and running 740M is not inherently faster for text. Media embeddings use 740M only on demand.
- Image and video-frame semantic index: `data/knowledge-media.sqlite3` (derived/private/0600). Index **only individually selected approved files**. Videos are sampled locally with FFmpeg, max 10 scaled frames, 180 seconds and 350 MB per file, deleting temporary frames afterward. This is similarity search, not full video quality understanding.
- `python3 -m tyrion.bridge media-index plugin/assets/icon.png --project 'Tyrion – The Hand'`
- `python3 -m tyrion.bridge media-search 'gold ornate circular hand seal' --project 'Tyrion – The Hand'`
- Shared local read-only service: POST `http://127.0.0.1:17877/api/knowledge/shared/search` for text and `/api/knowledge/shared/media-search` for indexed media with JSON `{ "query": "...", "project": "optional exact project name", "limit": 5 }`.
- Requires `X-Tyrion-Knowledge-Key` loaded by trusted local processes from `data/knowledge-readonly.token` (0600). Never paste or log this token. All browser-originated requests rejected; no CORS. Service binds localhost; no public network listener, publishing or writes.
- Reusable standard-library client adapters: `clients/knowledge_client.py` and `clients/knowledge_client.cjs`. Example usage from a trusted local Node service:
  `const {searchKnowledge} = require('/home/haseeb/Documents/Tyrion-The-Hand/clients/knowledge_client.cjs');`
  `const hits = await searchKnowledge('How did we fix subscription renewals?', {project:'Taiyo Munch'});`
  For visual assets use `{project:'Tyrion – The Hand',media:true}`.
- Remote plugin has **cached tools**: its currently visible catalog predates `tyrion_knowledge_search`, `tyrion_knowledge_status`, and `tyrion_media_search`. Local stdio MCP lists all these tools, and the private tunnel was restarted healthy. Until ChatGPT refreshes the plugin tool catalog, the already connected `tyrion_route_skills` accepts the **explicit** prefixes `Knowledge: ...` or `Media: ...`; these return semantic matches rather than pretending to execute skills. The `Knowledge:` route was verified from ChatGPT through the real remote plugin.
- GSC Maestro, Advert Connect, Meta Manager and Android Companion are **not automatically modified**: their own app runtimes must opt into the shared local API under appropriate source/client authorization. Do not let production WordPress/Shopify sites access the local service, and do not copy the read-only token into published code, mobile APKs or repositories.

## Project history backfill and future capture — 26 October 2026
- Reviewed all 27 pre-existing Tyrion project records. They had empty `notes`; one more verified-active project, **GSC Maestro**, was registered locally for completeness, making 28 total, of which **26 are eligible for semantic project-history indexing** (Fatir is discontinued; Advertpreneur Vault remains excluded from the embedding index).
- Added `project_history` table in Tyrion's existing authoritative SQLite database; entries are append-only, individually dated, provenance-labelled and deduplicated by `source_id`. No task marked done and no client site modified.
- Seeded **41 history entries** from the user's previously discussed work and allowlisted local reports. For project areas without a grounded last milestone (e.g. Artigaps, JRG Electric), explicitly recorded *no verified recent milestone*, not fictitious completion. Sources have classifications such as `historical_report`, `documented`, `verified_at_date`, and `unverified`. Conversation-derived material is not treated as proof of production state.
- `Documents/Tyrion-The-Hand/data/knowledge-history-backfill-2026-10-26.json` is the owner-private idempotent seed audit trail; local evidence is indexed separately where allowlisted, not copied to unrelated clients.
- Added allowlisted project report indexing for `Advertpreneur-Revival-2026-10-24.md`, `Advertpreneur-US-SEO-Plan-2026-10-23.md`, `Glissimo_Client_Fixes_Handoff_2026-10-24.md`, `Glissimo_Duplicate_Audit_2026-10-24.md` and this operating guide. Changes to those known files trigger incremental re-embeddings on the next refresh. No arbitrary folder/repo/chat/credential scanning.
- Tyrion's running **knowledge_watcher** does a safe incremental `knowledge.sync()` shortly after startup and **every 120 seconds** thereafter, in a dedicated daemon thread. It picks up changes to existing Tyrion projects, tasks, task updates, schedules and history plus allowlisted report files. It reuses the original owner-only model and index and never publishes or performs external writes. A failed sync leaves the last valid index intact, records a sanitized error, and retries on the next cycle.
- Knowledge dashboard now includes a source-labelled last-work overview for the 26 eligible projects. The GET `/api/knowledge/history` endpoint requires the local dashboard session token.
- Newly added tools in local stdio MCP: `tyrion_project_history` and `tyrion_record_project_history`, for reading and appending provenance-labelled milestones. The remote plugin may cache the old MCP manifest; until refreshed, the already-working `tyrion_route_skills` query prefix `Knowledge:` still searches the expanded history. Actual future ChatGPT conversation actions must be explicitly recorded through an authorized tool to appear in Tyrion; Tyrion cannot silently read every past or future ChatGPT conversation.
- CLI review: `python3 -m tyrion.bridge history-list --project 'Taiyo Munch' --limit 10`; index: `python3 -m tyrion.bridge knowledge-search 'What was the latest work on Taiyo Munch?'`
- Future data from GSC Maestro, Advert Connect, Meta Manager, or other external systems is **not** silently polled, altered or independently authenticated by this index. Integrations must record verified updates into existing Tyrion project/task records or the project-history API. Their own original data stores remain authoritative.
