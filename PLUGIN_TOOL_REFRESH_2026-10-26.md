# Tyrion — ChatGPT MCP Tool Refresh Verification (2026-10-26)

**CLOSED: Tool refresh completed in authenticated ChatGPT plugin settings.** The original pending instructions below are retained as historical context; they are no longer required.

## Local implementation — verified

Tyrion's private MCP bridge is active (`tyrion-hand.service` and `tyrion-mcp-tunnel.service`). The bridge currently advertises 42 tools locally and its new on-demand read-only actions are:

- `tyrion_engine_status` — no arguments; reports the four local skill capabilities.
- `tyrion_recent_research` — input `{"topic":"WordPress AI search optimization"}`; public, bounded Reddit/Hacker News research, no browser cookies or paid web backend.
- `tyrion_rea_aura_extension` — no arguments; read-only REA static analysis of the specifically allowlisted AURA Download Manager Chrome extension.

Local MCP `initialize`, `tools/list` and `tools/call` all passed; 16 regression tests passed. The connected ChatGPT plugin's **current 31-tool snapshot** does **not** yet expose these three tools. Its existing `tyrion_route_skills` successfully uses updated routing through the live connection. Restarting the local tunnel is insufficient to update ChatGPT's frozen action snapshot.

## One remaining ChatGPT-side administrative action

Per OpenAI's updated MCP documentation, actions added to an already-approved MCP app are not enabled automatically. An authorized app manager/admin needs to open the ChatGPT Plugins / Workspace app settings for **Tyrion – The Hand**, select its action configuration/management screen, choose **Refresh** to retrieve new actions, review and enable the three new read-only actions, and save/publish the updated configuration if prompted. Depending on plan/workspace UI, the labels may be **Workspace settings → Apps → Action control → Refresh** or the app's **Manage / Configure Actions** screen. Preserve the existing plugin registration and authentication; **do not uninstall it**. Test from a new chat after the refresh.

OpenAI Help Center: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

## Post-refresh acceptance

1. Confirm all three new tool names appear in ChatGPT's available Tyrion actions.
2. Invoke `tyrion_engine_status` and verify `mode=on_demand_read_only`.
3. Invoke `tyrion_rea_aura_extension`: expected graph with 15 nodes / 16 edges for the prior fixed AURA snapshot, subject to changes in extension sources.
4. Invoke `tyrion_recent_research` for a current topic; report time range, actual source count and freshness.
5. Verify existing Tyrion tasks/projects and events are still accessible.

No new services or production client actions are required; the user action is solely to update ChatGPT's frozen plugin action set.

## Action performed in ChatGPT settings, 2026-10-26

Opened the existing installed Tyrion – The Hand developer plugin under ChatGPT Settings → Plugins in the already-authenticated Chrome session. Located the actual **Manage app → Refresh tools** control and clicked it. The button showed an in-progress spinner and returned to the normal enabled state, without any visible error or requirement to reconnect. The plugin remained installed. The existing conversation still showed the old 31-tool action snapshot immediately afterward; a new conversation/tool catalog is necessary for independent verification of the new tool names. No browser passwords, cookies, API tokens or messages were accessed or submitted.

## Final direct ChatGPT verification — successful

- Used the authenticated ChatGPT Settings → Plugins → Tyrion – The Hand → Refresh tools action. Did not uninstall or reauthorize the app.
- ChatGPT now exposes all three previously missing tool names: `tyrion_engine_status`, `tyrion_recent_research`, `tyrion_rea_aura_extension`.
- Executed `tyrion_engine_status` via its ChatGPT plugin action: all four skill capabilities reported available, on-demand read-only.
- Executed `tyrion_rea_aura_extension` via ChatGPT plugin: AURA Chrome extension static graph returned 15 nodes and 16 edges, not executable behavior.
- Executed `tyrion_recent_research` via ChatGPT plugin for WordPress AI search optimization: 12 dated items from Reddit and Hacker News, 30-day interval, browser-cookies disabled and no paid providers.
- Invoked `tyrion_route_skills` four times via ChatGPT plugin: Ponytail, Scrapling, REA, Last30Days each ranked first for the matching task.
- Verified Scrapling live extraction via the connected GSC Maestro plugin: www.w3.org one-page audit, `scraplingPages=1`, semantic main-content words=312, paragraphs=9, headings=5, no crawl failures.
- Posted a verified milestone into the existing Tyrion project history (source id `tyrion-four-skills-chatgpt-e2e-20261026`). No duplicate tasks, publishing, site modifications or new daemons.

**Status: complete.**
