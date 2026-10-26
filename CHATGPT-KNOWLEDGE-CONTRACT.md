# Tyrion ↔ ChatGPT — Shared Knowledge Contract (2026-10-26)

## One authoritative record
Tyrion's existing projects, tasks, task progress, schedules and attributed project_history records are the source of truth. EmbeddingGemma vectors are a disposable search cache, not a second database or an alternative system of record. ChatGPT's separate platform memory is NOT automatically or bidirectionally synchronized with Tyrion. In every relevant connected project conversation, actively retrieve fresh Tyrion knowledge via MCP before asserting what the team last did.

## Beginning a project task
1. Identify the exact existing Tyrion project (do not invent a synonym or create a duplicate).
2. Consult its original task/schedule and the attributed history timeline when it matters to the decision.
3. For broad semantic discovery via connected remote MCP, prefer tyrion_knowledge_search if advertised; fallback to tyrion_route_skills using the prefix "Knowledge: <project + question>", which has been verified through the remote plugin. Read from the authoritative original record when asserting current task status.
4. Search history rather than trusting a potentially outdated ChatGPT conversation summary. Treat historical_report as earlier conversation evidence, not proof of actual live implementation.
5. Follow the task's existing authorizations. Index/retrieval never authorizes publishing, sending mail, spending money, changing client sites, or marking incomplete work done.

## Finishing substantive project work
1. When there is an original Tyrion task, append concise, dated factual progress, test evidence, unresolved blocker and next action using tyrion_add_task_update to the SAME task ID.
2. If the milestone is project-level (and has no matching task), append one project_history record with the correct existing project name, YYYY-MM-DD event date, accurate status, evidence classification and stable unique source_id. Use tyrion_record_project_history if exposed by MCP or authorized Local Files CLI "python3 -m tyrion.bridge history-add"; never create placeholder or duplicate tasks merely to log progress.
3. Reconcile project-level knowledge, not every trivial conversational reply. Do not write a retrospective claim as verified without evidence. Label past discussions historical_report; label current tested changes verified_at_date with precise test or file evidence.
4. Never write secrets, private credentials or protected content into vector-searchable notes. Fatir is discontinued and excluded; Advertpreneur Vault must stay excluded.
5. Tyrion's PC watcher refreshes search indexes of its recorded changes and allowlisted local documents. If unreachable or off, report that synchronization is pending and never claim it happened.

## Scheduled reconciliation
Any ChatGPT scheduled reconciliation should read Tyrion's existing records and commit only new, evidence-backed milestones when something changed. It should not create or execute a second task queue, acknowledge unseen events, or reactivate disabled task dispatchers. If the PC/MCP is unavailable, record the blocker rather than fabricate an update. No regular notification is needed when no change occurred.

## How the systems share information
- ChatGPT → Tyrion: explicit verified task update or dated attributed history append through an authorized connected tool.
- Tyrion → ChatGPT: direct MCP read during an active/scheduled ChatGPT run, with original timestamps and evidence labels.
- Tyrion → EmbeddingGemma: incremental local vector-index cache of allowed records; it does not silently index every ChatGPT conversation.
- External applications → Tyrion: only explicitly authorized integration or records; do not assume a site's production activity was observed.

Full implementation/commands: KNOWLEDGE-ENGINE.md and plugin/skills/setup/SKILL.md.
