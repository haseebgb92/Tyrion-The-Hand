# Advertpreneur Content Research — 26 October 2026

**Scope:** research and editorial recommendations only. No posts, drafts or site content were published, scheduled or changed.

## Sources and credibility

- Google Search Console: directly synced and verified properties through GSC Maestro. Impressions, clicks and position below are **observed organic metrics**, not Google Ads Keyword Planner monthly keyword volumes.
- Last30Days: public Reddit/Hacker News discussions; used as questions or content inspiration, never proof of product claims or broad population trends.
- Ubersuggest: separately labelled related keyword suggestions and third-party volume estimates; not equivalent to Google Ads data.
- E92 Keyword Explorer: **unavailable** as of October 26; multiple Google keyword operations and the separate Meta-asset operation returned internal errors. Google Ads keyword search volumes are explicitly **unknown**, not zero.

## CooCoo Babys — update existing articles first

Google Search Console period: 2026-09-26 to 2026-10-23.

| Priority | Target existing article | Page impressions | Clicks | Avg Google position | Action |
|---|---|---:|---:|---:|---|
| High | [Non-Wi-Fi baby monitors: which features matter?](https://coocoobabys.com/blog/best-non-wifi-baby-monitors/) | 1,136 | 1 | 18.08 | Refresh current page; verify content, CTR snippet, internal links and intent; avoid duplicate URL |
| Medium | [Travel stroller buying checklist for families](https://coocoobabys.com/blog/best-lightweight-strollers-for-travel/) | 185 | 0 | 23.63 | Refresh current page; verify content, CTR snippet, internal links and intent; avoid duplicate URL |
| Medium | [Choosing a bottle warmer: practical features to compare](https://coocoobabys.com/blog/best-bottle-warmers-for-breast-milk-and-formula/) | 335 | 1 | 32.67 | Refresh current page; verify content, CTR snippet, internal links and intent; avoid duplicate URL |
| Medium | [Nursery humidifiers: buying considerations](https://coocoobabys.com/blog/baby-room-humidifier/) | 210 | 1 | 31.81 | Refresh current page; verify content, CTR snippet, internal links and intent; avoid duplicate URL |
| Medium | [Choosing a carrier that suits a newborn](https://coocoobabys.com/blog/best-baby-carriers-for-newborns/) | 811 | 0 | 48.57 | Refresh current page; verify content, CTR snippet, internal links and intent; avoid duplicate URL |

**Strongest immediate opportunity:** The existing non-Wi-Fi baby monitor article has 1,136 page impressions and one click in the GSC period. Investigate the title/snippet, intent fit, content helpfulness and overlap with other baby-monitor articles before editing. Its query variants include 180 impressions for “best baby monitor without wifi” (position 10.24) and 111 for “best baby monitor no wifi” (position 9.37). Query impressions must not be added up and represented as unique searches.

**Supporting questions from Last30Days:** reliability of Wi-Fi vs dedicated monitors, features parents actually use, dual-camera/audio-only setups. Keep child-safety and security guidance sourced to reliable evidence; do not infer privacy, medical or device guarantees from community threads.

**Related keyword candidates (Ubersuggest, metrics unavailable):** `non wifi baby monitor audio only`, `non wifi baby monitor dual`, `best dual baby monitor without wifi`, `baby monitor without wifi 2 cameras`, `can you use vtech baby monitor without wifi`, `split screen video baby monitor no wifi`.

## Instagram — practical ecommerce education

Saved to Tyrion track `instagram`; imported into the intended Meta Manager workspace by ID. Current site-wide GSC offers very few suitable ecommerce queries, so these social topics are editorial hypotheses backed by selected discussion questions, not claims of a measured Instagram trend.

- **What to check before redesigning an ecommerce product page** — Instagram educational carousel; primary seed `shopify store seo`. Fact-check real examples and use a practical checklist before drafting.
- **What an ecommerce automation should actually save you** — Instagram short tutorial; primary seed `AI ecommerce automation`. Fact-check real examples and use a practical checklist before drafting.

Ubersuggest fallback: `shopify seo` had a third-party estimated 1,900 US monthly searches when last retrieved; treat as a vendor estimate, not Google Ads Planner verification.

## LinkedIn — technical thought leadership

Saved to Tyrion track `linkedin` and scoped to the connected LinkedIn workspace. Separate promoted Reddit posts from independent discussion; do not republish a promotional plugin claim as verified news.

- **How to evaluate an AI-search optimization claim** — LinkedIn evidence-based explainer; primary seed `ai search optimization`. Label hypotheses and cite independently checked facts.
- **Why practical ecommerce SEO matters more than plugin hype** — LinkedIn technical opinion; primary seed `ecommerce seo consultant`. Label hypotheses and cite independently checked facts.

Ubersuggest fallback: `ai search optimization` had a third-party estimated 1,300 US monthly searches when last retrieved; not a verified Google Ads Planner value.

## Execution and safeguards

1. Feed the relevant saved Tyrion packet into Meta Manager `strategist_research_evidence` or GSC Maestro `maestro_content_research`, always using the correct brand/workspace.
2. Read the saved source period and **review existing URLs** before recommending a new article.
3. Validate factual claims and product details; cross-check SEO metadata and user intent on the current page. Medical/child safety guidance requires authoritative sources.
4. Create reviewable drafts only after editorial approval. Never automatically publish, spend, modify client sites or reuse another client’s media.
5. When E92 comes back, import exact US/en Google Ads rows using Tyrion `tyrion_content_keyword_import`; keep separate provider provenance, freshness and missing-value markers.

**Research packets:** `~/.local/share/tyrion/content-research/{coocoobabys,instagram,linkedin}.json` (mode 0600).
