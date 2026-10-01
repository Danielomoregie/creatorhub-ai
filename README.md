# CreatorHub AI

Your always-on content partner. CreatorHub runs in the background, watches the places your audience
hangs out, and pings you when something takes off in your niche or when a **new niche** you could
own starts trending. It learns from **your own YouTube stats** which niches land with your audience,
sends a **daily 8am digest** to your phone, and has a **web dashboard** for trends, alerts and an idea
board. It also plugs into Claude as an **MCP server**, so you can ask *"what popped up today and what
should I post?"* and push the ideas you like to Notion.

**New here? Follow [SETUP.md](SETUP.md)**: a step-by-step VS Code guide.

| | |
|---|---|
| `creatorhub dashboard` | Web dashboard at http://127.0.0.1:8765: Today, Trends, Ideas board, My stats, Settings |
| `creatorhub watch` | Background watcher: scans hourly, sends alerts and the daily digest |
| `creatorhub serve` | MCP server for Claude Desktop / Claude Code |
| `creatorhub scan` | One scan, printed to the terminal |
| `creatorhub digest [--preview]` | Today's top 3 trends + 3 ideas, sent to your phone/Discord |
| `creatorhub stats` | Pull your YouTube channel stats and see which niches beat your median |

```
 ┌──────────── creatorhub watch (always running) ────────────┐
 │  Reddit · Hacker News · YouTube · RSS                     │
 │        │                                                  │
 │        ▼                                                  │
 │  keyword + momentum + freshness score (free, every item)  │
 │        │  top 25 new candidates                           │
 │        ▼                                                  │
 │  × your channel's niche boost (from `creatorhub stats`)   │
 │        │                                                  │
 │  Claude: core / adjacent-niche / noise                    │
 │        │                                                  │
 │        ▼                                                  │
 │  alerts + 8am digest ──► desktop · phone (ntfy) · Discord │
 └────────┬──────────────────────────────────────────────────┘
          │ shared SQLite (~/.creatorhub/creatorhub.db)
 ┌────────▼──────── creatorhub serve (MCP) ──────────────────┐   ┌── creatorhub dashboard ──┐
 │  get_alerts · get_trending · scan_now · generate_ideas    │   │  React + TypeScript UI   │
 │  save_idea · list_ideas · send_idea_to_notion · add_niche │   │  on a local JSON API     │
 │  get_digest · get_my_performance                          │   │  (127.0.0.1 only)        │
 └───────────────────────────────────────────────────────────┘   └──────────────────────────┘
          ▲
   Claude Desktop / Claude Code / any MCP client
```

## Why two processes?

An MCP server only runs while your MCP client (Claude Desktop, Claude Code...) has it open, and MCP
servers can't push a message into your chat on their own. So the part that has to be always-on (the
**watcher**) runs as its own small daemon and notifies you through your OS, your phone or Discord.
The **MCP server** reads the same database, so when you open Claude, everything the watcher found is
already there. If you only want one process, set `CREATORHUB_WATCH_IN_SERVER=1` and the server will
scan too while it's open.

## Quick start

```bash
git clone https://github.com/Danielomoregie/creatorhub-ai && cd creatorhub-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

creatorhub init            # writes ~/.creatorhub/profile.toml. Edit it: niches, keywords, subreddits
cp .env.example ~/.creatorhub/.env   # add ANTHROPIC_API_KEY, and NTFY_TOPIC for phone pings
creatorhub scan            # one scan, prints alerts + top trends
creatorhub watch           # leave running (see "Run it on boot")
```

Without `ANTHROPIC_API_KEY` everything still works on keyword/momentum scores. The key adds Claude's
judgment (filtering noise, spotting adjacent niches) and lets the watcher write ideas on its own.

## Connect to Claude

**Claude Code**

```bash
claude mcp add creatorhub -- /absolute/path/to/creatorhub-ai/.venv/bin/creatorhub serve
```

**Claude Desktop**: Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "creatorhub": {
      "command": "/absolute/path/to/creatorhub-ai/.venv/bin/creatorhub",
      "args": ["serve"]
    }
  }
}
```

Then try: *"Check my CreatorHub alerts"*, *"Give me 3 TikTok ideas off what's trending in tech careers"*,
*"Save #2 and send it to Notion"*, or run the `weekly_plan` prompt.

## Run it on boot

- **macOS**: a `launchd` agent running `creatorhub watch` (`~/Library/LaunchAgents/com.creatorhub.watch.plist`).
- **Linux**: `systemd --user` service with `ExecStart=/path/.venv/bin/creatorhub watch`.
- **Windows**: Task Scheduler → "At log on" → `C:\path\.venv\Scripts\creatorhub.exe watch`.
- **Always on, even with your laptop closed**: deploy `creatorhub watch` to a small VM/Fly.io/Railway box and
  use ntfy or Discord for alerts.

## Configuration

| Where | What |
|---|---|
| `~/.creatorhub/profile.toml` | Who you are, niches + keywords, sources, alert threshold ([example](src/creatorhub/profile.example.toml)) |
| `~/.creatorhub/.env` | API keys + notification channels ([example](.env.example)) |

Notion: create an integration, share your content database with it, and set `NOTION_TOKEN` and
`NOTION_DATABASE_ID`. Optional select properties `Status`, `Niche`, `Format` and url property `Source`
get filled automatically.

## Development

```bash
pytest                       # Python tests
cd dashboard && npm run dev  # UI with hot reload at :5173 (run `creatorhub dashboard` alongside for the API)
npm run build                # type-check + production build into dashboard/dist
```

Layout: `src/creatorhub/` (Python: sources, scoring, watcher, service, MCP server, API) and
`dashboard/` (React + TypeScript + Vite).

See [ROADMAP.md](ROADMAP.md) for where this goes next.
