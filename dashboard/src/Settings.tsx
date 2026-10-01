import { useState } from "react";
import { api } from "./api";
import type { Summary } from "./types";
import { useAction, useLoad } from "./ui";

const INTEGRATIONS: { key: keyof Summary["integrations"]; name: string; what: string; env: string }[] = [
  { key: "claude", name: "Claude", what: "Filters noise, spots new niches, writes ideas", env: "ANTHROPIC_API_KEY" },
  { key: "notion", name: "Notion", what: "Sends ideas to your content database", env: "NOTION_TOKEN + NOTION_DATABASE_ID" },
  { key: "youtube_trends", name: "YouTube trends", what: "Adds trending YouTube videos as a source", env: "YOUTUBE_API_KEY" },
  { key: "youtube_stats", name: "My YouTube stats", what: "Learns what works on your channel", env: "YOUTUBE_API_KEY + YOUTUBE_CHANNEL_ID" },
  { key: "ntfy", name: "Phone alerts (ntfy)", what: "Push notifications to your phone", env: "NTFY_TOPIC" },
  { key: "discord", name: "Discord", what: "Alerts in a Discord channel", env: "DISCORD_WEBHOOK_URL" },
];

export function Settings({ summary, refresh }: { summary: Summary; refresh: () => void }) {
  const profile = useLoad(() => api.profile());
  const { busy, run } = useAction();
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");

  const add = () => {
    const kws = keywords.split(",").map((k) => k.trim()).filter(Boolean);
    run("add", () => api.addNiche(name.trim(), kws), () => {
      setName("");
      setKeywords("");
      profile.reload();
      refresh();
      return `Now tracking “${name.trim()}”. The next scan includes it.`;
    });
  };

  const p = profile.data;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Your profile lives in <code>~/.creatorhub/profile.toml</code> and keys in <code>~/.creatorhub/.env</code>.</p>
        </div>
      </div>
      <div className="grid two">
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card">
            <h2>Niches you're tracking</h2>
            <div className="list">
              {p?.niches.map((n) => (
                <div className="row" key={n.name}>
                  <div className="row-main">
                    <span className="row-title">{n.name}</span>
                    <div className="row-meta">{n.keywords.map((k) => <span className="badge" key={k}>{k}</span>)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <h2>Add a niche</h2>
            <div className="grid">
              <div className="field">
                <label htmlFor="nn">Name</label>
                <input id="nn" placeholder="e.g. Robotics" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="kw">Keywords (comma separated)</label>
                <input id="kw" placeholder="humanoid robot, robotics club, first robotics" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
              </div>
              <div>
                <button className="btn primary" disabled={!name.trim() || !keywords.trim() || busy === "add"} onClick={add}>Add niche</button>
              </div>
            </div>
          </div>
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card">
            <h2>Connections</h2>
            {INTEGRATIONS.map((i) => {
              const on = summary.integrations[i.key];
              return (
                <div className="integration" key={i.key}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{i.name}</div>
                    <div className="muted small">{on ? i.what : <>Add <code>{i.env}</code></>}</div>
                  </div>
                  <span className={`badge ${on ? "good" : ""}`}>
                    <span className="status-dot" style={{ background: on ? "var(--good)" : "var(--text-3)" }} />
                    {on ? "Connected" : "Not set"}
                  </span>
                </div>
              );
            })}
            <p className="muted small" style={{ marginBottom: 0 }}>After editing <code>.env</code>, restart <code>creatorhub dashboard</code>.</p>
          </div>
          {p && (
            <div className="card">
              <h2>About you</h2>
              <p className="small" style={{ marginTop: 0 }}>{p.bio}</p>
              <p className="small muted">Audience: {p.audience}<br />Voice: {p.voice}</p>
              <p className="small muted" style={{ marginBottom: 0 }}>
                Alerts at score ≥ {p.alerts.min_score}, max {p.alerts.max_alerts_per_scan} per scan · Sources: {p.sources.subreddits.map((s) => `r/${s}`).join(", ")}
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
