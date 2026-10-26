# Tyrion Live Instruction Queue — v1.2 (2026-10-26)

Purpose: append new instructions to an ongoing ChatGPT conversation **without clicking Stop or editing the original message**. Instructions are stored on the PC and can be fetched at explicit checkpoints; this does not create native real-time ChatGPT steering.

## What was added
- Existing Chrome extension now contains an **Instruction Queue** panel above task controls.
- The panel recognizes only an active, saved `https://chatgpt.com/c/...` conversation (including `/g/.../c/...`).
- The user can queue up to 50 updates per conversation, each up to 1500 characters; remove individually; copy the ordered group into the clipboard; or explicitly clear them.
- Queued instructions are stored in Tyrion's local SQLite database, not Chrome's cloud sync.
- New paired extension endpoints: `GET /api/extension/steering?chat=...`, `POST /api/extension/steering/add`, `POST /api/extension/steering/remove`, `POST /api/extension/steering/clear`.
- New local MCP bridge tools: `tyrion_steering_queue` and `tyrion_steering_ack`, available once the bridge advertises its refreshed tool schema.
- Local Files fallback: `python3 -m tyrion.steering https://chatgpt.com/c/CONVERSATION_ID`.

## Activate
1. Restart `tyrion-hand.service` **at a safe time**, so its HTTP process loads the new Python routes. Do not restart during a running scheduled job.
2. In Chrome `chrome://extensions`, press **Reload** for the existing unpacked `Tyrion – The Hand` extension, sourced from `~/Documents/Tyrion-The-Hand/browser-extension`. No new extension install is needed.
3. Open an existing ChatGPT conversation, pin the Tyrion side panel via **Live panel**, and type instructions in its queue. It displays the number waiting.
4. At an explicit assistant checkpoint, use the MCP bridge to inspect the queue for the **exact conversation URL** and acknowledge only IDs already incorporated. If the new MCP tool has not appeared yet, reconnect/refresh the Tyrion custom MCP registration. As a manual fallback use **Copy pending updates**, then send the pasted updates normally after the current response ends.

## Important limits
- The ChatGPT consumer chat runtime does not receive push notifications from this local queue, cannot be guaranteed to check it during an active reply, and cannot securely infer the current chat's browser URL from the MCP bridge alone.
- The queue does **not** read ChatGPT output, click Stop or Send, inject content into ChatGPT, bypass usage limits, or guarantee same-response updates. An instruction added after the final MCP checkpoint remains pending for the next turn.
- A queued update is an **operator request**, not evidence that any live site or client data was changed. Existing approval rules still apply.
- Local storage includes the instruction text; do not enter passwords or secrets. Only the paired browser extension can write through the local HTTP endpoints.
- New code was syntax-checked and unit-tested, but a manual Chrome panel smoke test is still required after activation.
