---
name: setup
description: Connect and verify Tyrion – The Hand's private local MCP tools and Work event notifications.
---

# Connect Tyrion

Tyrion stores work locally at `~/Documents/Tyrion-The-Hand`. Use the registered private Tyrion custom MCP server, never duplicate the user’s project/task/schedule in a second system. Check `tyrion_sync_inbox` and `tyrion_projects` to verify access and use `tyrion_add_task_update` only to record actual verified progress. For changes to sites, publishing or spending, apply the appropriate separate explicit approval.

For background event notifications, in a ChatGPT Work conversation subscribe to `task.created`, `project.created`, `project.updated`, `schedule.created`, `schedule.updated` and `run.queued` events supported by the connected Tyrion plugin. Do not say the events are live until an `events/subscribe` callback has been verified and a new test task is actually received in ChatGPT Work.

Keep the existing hourly ChatGPT dispatcher as a fallback until event delivery is verified. An ordinary ChatGPT chat may call MCP tools while active but cannot be awakened by local changes alone.

## Optional local knowledge retrieval
For an authorized follow-up where prior project history matters, first search Tyrion's locally indexed knowledge instead of assuming ChatGPT remembers every detail. The live local MCP endpoint now supports `tyrion_knowledge_status`, `tyrion_knowledge_search` and `tyrion_media_search`. An older ChatGPT plugin tool catalog may not list them until refreshed. A verified backward-compatible option is to call the already registered `tyrion_route_skills` with the query prefix **`Knowledge: <question>`**, or **`Media: <description>`** for previously indexed media. These are read-only source retrieval calls, not an instruction to execute or publish. Ordinary skill routing remains unchanged. The 270M text model and 740M multimodal model run locally on the Tyrion PC. Do not assume search covers every conversation, file or image; verify original task records and seek required approvals for consequential work.

## Preserve new project work for future ChatGPT sessions
Tyrion now stores source-labelled project history and indexes project, task, progress-update, schedule and selected local documentation changes automatically every ~120 seconds while the Tyrion PC service runs. When finishing substantive work for a known project, record **verified** progress in its original Tyrion task using `tyrion_add_task_update`. If there is no matching task and the dedicated `tyrion_record_project_history` tool is exposed, append an idempotent dated milestone with source, verification class and source ID. If the remote MCP catalog is stale, use the connected Local Files tool and `python3 -m tyrion.bridge history-add` only when task-specific authorization exists; do not create a duplicate task. Do not assert that outside apps or ChatGPT conversations are indexed unless a verified connector or a saved Tyrion record provided them. To review a project's latest work, the remote compatibility query `tyrion_route_skills({"query":"Knowledge: What was the latest work on Taiyo Munch?"})` is confirmed functional. `tyrion_project_history` gives a chronological, evidence-labelled timeline when exposed. Treat ChatGPT conversation summaries as historical reports, not current production verification; never bypass publishing/client approvals.

## ChatGPT ↔ Tyrion single-knowledge contract (2026-10-26)
For substantive work on an existing Advertpreneur project, read the source-labelled history before reporting the last completed change, and update the SAME Tyrion task or one idempotent project milestone after verified progress. Read the full protocol at ~/Documents/Tyrion-The-Hand/CHATGPT-KNOWLEDGE-CONTRACT.md when available. Never claim native ChatGPT Memory is directly synchronized; Tyrion's MCP-backed records are canonical. Keep disabled task-execution dispatchers disabled unless separately authorized.
