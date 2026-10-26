# Tyrion Browser Companion · Chrome MV3 v1.2.0

The Chrome extension is a companion to **Tyrion — The Hand**. It shows shared task/dispatch state, lets an operator resume a specific task, and stores additional instructions against the **correct ChatGPT conversation** without stopping an ongoing response.

## Requirements

- Chrome/Chromium version 120 or newer.
- Tyrion PC service available at `http://127.0.0.1:17877` (and its optional paired local event bridge at port 17879).
- A deliberately authorized Tyrion MCP connection in ChatGPT to read/update tasks. The extension alone cannot work on project files or mark work complete.

## Install and pair

1. Go to `chrome://extensions`, switch on **Developer mode**, choose **Load unpacked**, and select the `browser-extension/` directory.
2. Open the Tyrion desktop dashboard, go to **Connections**, and obtain the Chrome Companion pairing key.
3. Open the extension popup, pair locally, and pin its gold hand-seal icon if desired.
4. Open the **Live panel** to view recent tasks, handoffs, and queued instructions.
5. Reload the unpacked extension after updating source files. Depending on permissions, Chrome may ask you to approve `chatgpt.com` access.

Pairing credentials are local secrets. Do **not** copy them into GitHub, an issue, a screenshot, or a ChatGPT prompt.

## What it does

- **Task dispatch:** view open tasks and pending scheduled handoffs, with durable dispatch status stored on the Tyrion PC.
- **Chat handoff:** copy or open a minimal, task-ID-based instruction referencing the original Tyrion record. Avoid duplicate tasks.
- **Optional one-shot auto-start:** for fresh handoffs, a specifically nonce-authorized content script may submit an unchanged prefilled task reference once. Automatic sends are rate-limited and recorded; a click is **not** proof of completed work. If the page differs from the expected ChatGPT composer, no blind retry is made.
- **Local event channel:** use paired localhost WebSocket events where available; a Chrome alarm provides a slower fallback. A sleeping browser cannot guarantee real-time action.
- **Per-conversation steering queue:** write additional instructions in the popup or panel while a response is still running. Tyrion stores the message against that conversation URL. The instructions are delivered only when intentionally copied or fetched at the next MCP checkpoint; they do **not** interrupt an in-progress model response.

The extension does not scrape ChatGPT conversations or output, harvest cookies/credentials, navigate user sites for content, or bypass usage limits.

## Permissions

| Permission | Purpose |
| --- | --- |
| `storage` | Local pairing and dispatch settings. |
| `alarms` | Service-worker fallback checks. |
| `tabs` | Open the authorized Tyrion/ChatGPT handoff tab. |
| `clipboardWrite` | Copy a user-requested handoff. |
| `sidePanel` | Compact companion panel. |
| `http://127.0.0.1:17877/*` | Local dashboard and paired task endpoints. |
| `http://127.0.0.1:17879/*` | Local event channel (when enabled). |
| `https://chatgpt.com/*` | Narrow handoff content-script permission. |

## Working with queued instructions

Open the relevant ChatGPT tab, enter an instruction in Tyrion’s **Queue instruction** control, and either **Copy pending updates** for manual delivery or ask the connected Tyrion MCP plugin to read `tyrion_steering_queue` at a deliberate checkpoint. Acknowledge only instructions actually incorporated. See [`../STEERING_QUEUE.md`](../STEERING_QUEUE.md).

## Recovery and verification

If a handoff stalls, inspect it on Tyrion’s **Dispatch** page. Recovery is operator-initiated; do not reopen and resubmit blindly. Verify work from the *same task’s updates*, not from a tab click, browser badge, or ChatGPT prose alone.

```bash
node --test browser-extension/tests/*.test.cjs
node --check browser-extension/background.js
node --check browser-extension/popup.js
```

**Last verified:** 9 extension tests and syntax checks passed on 2026-10-26. Physical Chrome reload/one-shot submission against a changing ChatGPT UI is a separate real-environment test.
