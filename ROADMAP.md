# Roadmap & partner notes

What the original CreatorHub AI did (from the resume): a React/TypeScript dashboard, OpenAI for content
planning, Notion sync of plans into users' workspaces, Deno serverless functions, and Stripe subscriptions.
v0.1 here rebuilds the brain of that as a personal, always-on agent. Below is what I'd do next and why.

## Shipped in v0.1
- Background watcher across Reddit, Hacker News, YouTube (with key), and any RSS feed
- Scoring = relevance to your niches + **momentum** (growth between scans, not just raw size) + freshness
- Claude judges top candidates as core / **adjacent niche** / noise, so alerts stay high-signal
- Alerts to desktop, phone (ntfy.sh), Discord; no duplicate alerts
- MCP server: alerts, trends, idea generation, backlog, Notion export, `add_niche`, `weekly_plan` prompt

## Next up (highest leverage first)
1. **Learn from your own performance.** Pull your channel stats (YouTube Analytics, TikTok/IG via their APIs)
   and feed "what worked for *me*" into scoring and idea prompts. This is the moat: generic trend tools exist,
   but none of them know your audience's reaction.
2. **Feedback loop on alerts.** 👍/👎 on each alert (Discord buttons or an MCP tool) to tune keyword weights and
   the alert threshold automatically. Right now the threshold is a number you guess.
3. **Trend clustering.** Group items about the same story across sources (embeddings or Claude) so one trend =
   one alert, and cross-source spread becomes a strong "this is real" signal.
4. **More sources:** TikTok Creative Center trending hashtags, Google Trends, X/Bluesky, GitHub trending
   (great for the "building with AI" niche), and newsletters.
5. **Daily digest** instead of (or alongside) instant pings: one 8am message with the top 3 trends + 3 ideas.
6. **Content calendar**: ideas → scheduled slots, and a "made" status that later pulls the post's stats.
7. **Dashboard**: bring back the React/TS dashboard from the original as a front end over this same
   database (or expose the server over `creatorhub serve --http`).

## If this becomes a SaaS again
- Multi-tenant: Postgres instead of SQLite, a profile per user, the watcher as a queue worker.
- Notion OAuth instead of a pasted token; Stripe tiers by number of niches / scan frequency / sources.
- Run the MCP server remotely (streamable HTTP + auth) so users connect Claude to it with a URL instead of
  installing Python.
- Cost control: keep Claude on the top-N candidates only (already the case), batch overnight idea
  generation with the Message Batches API at 50% cost.

## Things I'd push back on
- **Don't alert on everything.** The fastest way to make this useless is notification fatigue. Default
  `max_alerts_per_scan = 5` and `min_score = 65` are deliberately strict; loosen only if you miss things.
- **Respect platform rules.** Use official APIs where they exist (YouTube, Reddit OAuth for higher limits),
  and don't scrape TikTok/IG pages.
