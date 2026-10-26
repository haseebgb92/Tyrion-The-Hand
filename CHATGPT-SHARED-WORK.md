# Tyrion ↔ ChatGPT shared-work protocol (v0.5)

## Operator experience: enter each task once
- Create a project, task or schedule in **Tyrion** only. Do not duplicate it in ChatGPT.
- All creates and important changes generate durable SQLite change events. One change feed is authoritative for Tyrion.
- During an active ChatGPT chat with the Local Files connection, read `python3 -m tyrion.bridge inbox` from `~/Documents/Tyrion-The-Hand`.
- For new ordinary tasks, fetch the task and its notes. Record truthful findings using `python3 -m tyrion.bridge note-task TASK_ID "verified note"` or `tyrion_add_task_update`. Do not create duplicate tasks.
- For scheduled jobs, follow the run's instructions and submit a genuine local draft via `submit-draft` or the corresponding MCP tool. No automatic production publishing.
- After handling/reviewing **all** events on the current page, acknowledge the last consumed cursor via `python3 -m tyrion.bridge ack-events EVENT_ID`. Acknowledgement means *seen*, not *completed*; a task remains open until verified.
- Tasks given in an active ChatGPT conversation should be saved in Tyrion directly using the authorized bridge, with normal approval checks. Do not keep an independent phantom checklist.

## What works today
- Local bridge command/MCP read/write for the common task ledger.
- Persistent SQLite triggers for project, task, schedule, and run events.
- Bidirectional task notes shared between this ChatGPT connection and the local Tyrion UI.
- An hourly ChatGPT scheduled dispatcher polls the Tyrion inbox and processes bounded work if Local Files is accessible in that scheduled run.
- Dashboard displays pending ChatGPT pickup status every five seconds while open.

## What is NOT connected
- Tyrion cannot spontaneously call the ChatGPT consumer model from arbitrary local events via stdio MCP or Local Files. The ChatGPT task worker is hourly, not real-time.
- Real event-triggered ChatGPT responses would require a supported, authenticated custom MCP plugin with MCP Events webhook subscriptions, a trusted remote endpoint or Secure MCP Tunnel, and an authorized Work/dot subscription. Those are **not yet installed/verified**; do not represent them as active.
- Do not automate browser ChatGPT by scraping cookies/session data or simulating messages, and do not buy an API subscription as a hidden dependency.

## Integrity rules
- Remote writes/publishing/pricing/payment/destructive changes keep normal per-tool authorization, backups and evidence requirements.
- Local task notes never count as external implementation evidence.
- A schedule is not a ChatGPT native Task: Tyrion stores its own schedules, and one existing ChatGPT dispatcher checks its queue.

## CLI reference
- `python3 -m tyrion.bridge inbox`
- `python3 -m tyrion.bridge ack-events EVENT_ID`
- `python3 -m tyrion.bridge tasks`
- `python3 -m tyrion.bridge note-task TASK_ID "Status and verified findings"`
- `python3 -m tyrion.bridge task-updates TASK_ID`
- `python3 -m tyrion.bridge schedules`
- `python3 -m tyrion.bridge due-work`
- `python3 -m tyrion.bridge review-queue`

## Ongoing shared knowledge (2026-10-26)
Tyrion's authoritative project/task records and attributed project_history are the ONE shared source. For relevant new ChatGPT work, retrieve current Tyrion context before acting; on verified completion, update the existing task or append one source-labelled project milestone. Do not create a separate task/memory database. A local EmbeddingGemma cache indexes the recorded sources; it cannot automatically capture every ChatGPT message or external app action. See CHATGPT-KNOWLEDGE-CONTRACT.md for the exact read/write protocol and permission safeguards.
