# Tyrion — Instant ChatGPT Work Events

## Local component status (v0.6)

Tyrion supports six MCP 2.0 events: `task.created`, `project.created`, `project.updated`, `schedule.created`, `schedule.updated`, and `run.queued`. Its SQLite-backed event dispatcher, signed callback verification, retries, and unsubscribe handling are implemented. The local service sends Linux desktop notifications for these changes and updates Tyrion's open UI over SSE.

**Not yet connected:** an actual ChatGPT Work event subscription. In a normal ChatGPT chat, MCP tools are called during active turns; they cannot awaken the chat simply because Tyrion writes an event. The existing hourly dispatcher is retained until the end-to-end event flow is verified.

## One-time ChatGPT connection

1. In the OpenAI Platform **tunnel settings**, create a **new, dedicated Tyrion** Secure MCP Tunnel endpoint; don't repurpose the active Chrome, Meta Manager, or Local Files tunnels. Associate it with your target ChatGPT workspace. The tunnel control plane uses a restricted Platform runtime key; this is transport authentication, **not model inference**. Do not put keys into Tyrion projects, documents or chat text.
2. On Linux Mint, the installed `tunnel-client` can create a profile. From the Tyrion directory use the documented `tunnel-client init --sample sample_mcp_stdio_local --profile tyrion --tunnel-id <ACTUAL_TUNNEL_ID> --mcp-command "/home/haseeb/Documents/Tyrion-The-Hand/bin/tyrion-mcp"`, with the platform runtime key entered through the supported secure mechanism. Run `tunnel-client doctor --profile tyrion --explain`, then `tunnel-client run --profile tyrion`. The profile is **not yet created**, because a dedicated tunnel ID/key is not available to Tyrion.
3. In ChatGPT Plugins, select **Add custom MCP server → Tunnel**, choose the new Tyrion tunnel, and verify the tool `tyrion_sync_inbox` is available. This action requires the ChatGPT account/workspace to allow custom MCP plugins.
4. Start a **ChatGPT Work (Cloud) conversation**. Ask it to subscribe to Tyrion events for new tasks, project creations/updates, schedules and due runs. Set instructions to investigate the specific task and write verified progress into the original Tyrion record, never duplicate work and never publish or spend without appropriate approval. The MCP Events feature in ChatGPT works in Work chats and dots, subject to account/workspace access.
5. Create one harmless Tyrion task and inspect `python3 -m tyrion.bridge event-status`. This should report an active verified subscription and, after sending an event, the Work chat must actually receive and act on it. Do **not** mark the connection finished on a local-only test. Confirm unsubscribing works.

This setup does **not** bypass ChatGPT's subscription limits or give normal instant chats permanent server-initiated conversations. It replaces manual polling only where the Work MCP Events integration is available and explicitly subscribed.

## Local checks

- `python3 -m tyrion.bridge event-status` — subscriptions active and queued deliveries, no secrets.
- `python3 -m tyrion.bridge inbox` — existing durable work queue for fallback.
- `systemctl --user status tyrion-hand.service` — local daemon and event worker.
- `http://127.0.0.1:17877/#connections` — live/inventory/relay/subscription state.

References: https://developers.openai.com/plugins/build/mcp-events and https://developers.openai.com/api/docs/guides/secure-mcp-tunnels.
