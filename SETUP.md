# Setting up CreatorHub AI in VS Code

About 15 minutes. Windows commands come first; Mac/Linux differences are noted.

## 0. What you need installed

- **Python 3.11+**: python.org/downloads. On Windows, tick **"Add python.exe to PATH"** in the installer.
- **Node.js LTS**: nodejs.org (only used to build the dashboard).
- **VS Code** with the **Python** extension (VS Code will offer it when you open the folder).

Check in a VS Code terminal (**Terminal → New Terminal**):

```powershell
python --version   # 3.11 or newer
node --version
```

## 1. Install CreatorHub

In VS Code: **File → Open Folder → `creatorhub-ai`**, open a terminal, then:

```powershell
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -e ".[dev]"
creatorhub init
```

You should see `(.venv)` at the start of your terminal line. If PowerShell blocks `activate`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

If VS Code asks "We noticed a new environment... select it for the workspace?", click **Yes**.

## 2. Make the profile yours

`creatorhub init` created `profile.toml` in your home folder:

- Windows: `C:\Users\<you>\.creatorhub\profile.toml`
- Mac/Linux: `~/.creatorhub/profile.toml`

Open it with `code $HOME\.creatorhub\profile.toml` (Mac: `code ~/.creatorhub/profile.toml`). Edit your niches,
keywords and subreddits. **Keywords are what get matched**, so use the phrases people actually type.

## 3. Add your keys

Copy the example file next to your profile and fill it in:

```powershell
copy .env.example $HOME\.creatorhub\.env      # Mac: cp .env.example ~/.creatorhub/.env
code $HOME\.creatorhub\.env
```

| Key | Where to get it | What it unlocks |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | Claude filters noise, spots new niches, writes ideas and the digest |
| `NTFY_TOPIC` | Install the **ntfy** app on your phone, subscribe to a long random topic name, e.g. `daniel-creatorhub-8f3k2` | Phone notifications |
| `YOUTUBE_API_KEY` | console.cloud.google.com → new project → enable **YouTube Data API v3** → Credentials → API key | YouTube trends + your stats |
| `YOUTUBE_CHANNEL_ID` | youtube.com/account_advanced (starts with `UC`) | "My stats": learns what works on your channel |
| `NOTION_TOKEN`, `NOTION_DATABASE_ID` | notion.so/my-integrations → new integration; share your content database with it; the id is the 32 characters in the database URL | One-click "→ Notion" on ideas |
| `DISCORD_WEBHOOK_URL` | Discord channel → Edit → Integrations → Webhooks | Alerts in Discord |

Everything is optional. With no keys at all, trends and alerts still work on keyword and momentum scores.

**Never commit `.env`.** It lives outside the repo on purpose, and `.gitignore` blocks it too.

## 4. Try it

```powershell
creatorhub scan          # one scan, prints alerts + top trends
creatorhub dashboard     # opens http://127.0.0.1:8765 (first run builds the UI, ~1 min)
creatorhub stats         # pulls your YouTube stats (needs the two YouTube keys)
creatorhub digest --preview
```

Or use **Terminal → Run Task...** and pick any "CreatorHub: ..." task; they're already set up.

## 5. Keep it running in the background

`creatorhub watch` scans every hour (`CREATORHUB_SCAN_INTERVAL`) and sends the daily digest at 8am
(`CREATORHUB_DIGEST_HOUR`). It only runs while your computer is on.

**Windows (starts when you log in):**

1. Run `where creatorhub` and copy the path (ends in `.venv\Scripts\creatorhub.exe`).
2. Open **Task Scheduler** → **Create Basic Task** → name it "CreatorHub" → trigger **When I log on**.
3. Action **Start a program** → Program: the path from step 1 → Arguments: `watch`.
4. In the task's Properties, tick **Run whether user is logged on or not** to hide the window.

**Mac**: create `~/Library/LaunchAgents/com.creatorhub.watch.plist` that runs
`/path/to/creatorhub-ai/.venv/bin/creatorhub watch` with `RunAtLoad` and `KeepAlive` set to true, then
`launchctl load ~/Library/LaunchAgents/com.creatorhub.watch.plist`.

## 6. Connect it to Claude

**Claude Desktop**: Settings → Developer → Edit Config:

```json
{
  "mcpServers": {
    "creatorhub": {
      "command": "C:\\Users\\<you>\\path\\to\\creatorhub-ai\\.venv\\Scripts\\creatorhub.exe",
      "args": ["serve"]
    }
  }
}
```

(Mac: `"/Users/<you>/path/to/creatorhub-ai/.venv/bin/creatorhub"`.) Restart Claude Desktop and ask
*"Check my CreatorHub alerts."*

**Claude Code**: `claude mcp add creatorhub -- <same path as above> serve`

## Troubleshooting

| Problem | Fix |
|---|---|
| `creatorhub` is not recognized | The venv isn't active: run `.venv\Scripts\activate` again |
| Dashboard says "Can't reach CreatorHub" | `creatorhub dashboard` stopped; start it again |
| Dashboard page says "not built yet" | Install Node.js, then `cd dashboard`, `npm install`, `npm run build` |
| A button says to add a key | Add it to `~/.creatorhub/.env`, then restart the dashboard |
| Scan finds 0 items | Check your internet connection; Reddit sometimes rate-limits, so try again in a few minutes |
| No phone notifications | Make sure the ntfy app is subscribed to exactly the same `NTFY_TOPIC` |
| Port 8765 already in use | `creatorhub dashboard --port 8800` |
