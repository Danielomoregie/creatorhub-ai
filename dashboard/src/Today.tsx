import { api } from "./api";
import type { Summary } from "./types";
import { AlertRow, Empty, TrendRow, timeAgo, useAction, useLoad } from "./ui";

export function Today({ summary, refresh, go }: { summary: Summary; refresh: () => void; go: (tab: string) => void }) {
  const alerts = useLoad(() => api.alerts(true));
  const trends = useLoad(() => api.trends({ hours: 48 }));
  const digest = useLoad(() => api.digest());
  const { busy, run } = useAction();
  const reloadAll = () => (alerts.reload(), trends.reload(), digest.reload(), refresh());
  const c = summary.counts;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Hey {summary.name} 👋</h1>
          <p>Last scan {timeAgo(summary.last_scan)}. Here's what's moving in your world.</p>
        </div>
        <button className="btn primary" disabled={busy === "scan"} onClick={() =>
          run("scan", api.scan, (r) => (reloadAll(), `Scanned ${r.fetched} posts: ${r.new} new, ${r.alerts.length} alerts`))}>
          {busy === "scan" ? "Scanning…" : "↻ Scan now"}
        </button>
      </div>

      {!summary.integrations.claude && (
        <div className="notice">
          Add <code>ANTHROPIC_API_KEY</code> to <code>~/.creatorhub/.env</code> to turn on Claude: smarter trend filtering, new-niche
          spotting and one-click ideas. Everything else works without it.
        </div>
      )}

      <div className="grid stats" style={{ marginBottom: 16 }}>
        <Stat label="New trends (24h)" value={c.trends_24h} />
        <Stat label="Unread alerts" value={c.unread_alerts} />
        <Stat label="Ideas in backlog" value={c.ideas} />
        <Stat label="Ideas made" value={c.ideas_made} />
      </div>

      <div className="grid two">
        <div className="card">
          <h2>
            Top trends right now
            <button className="btn small ghost" onClick={() => go("trends")}>See all →</button>
          </h2>
          {trends.data?.length ? (
            <div className="list">{trends.data.slice(0, 6).map((t) => <TrendRow key={t.id} t={t} />)}</div>
          ) : (
            <Empty title="No trends yet">Hit “Scan now”, or leave <code>creatorhub watch</code> running.</Empty>
          )}
        </div>

        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card">
            <h2>
              Alerts
              {!!alerts.data?.some((a) => !a.read) && (
                <button className="btn small ghost" onClick={() => run("read", () => api.markAlertsRead(), () => (alerts.reload(), refresh(), undefined))}>
                  Mark all read
                </button>
              )}
            </h2>
            {alerts.data?.length ? (
              <div className="list">{alerts.data.slice(0, 5).map((a) => <AlertRow key={a.id} a={a} />)}</div>
            ) : (
              <Empty title="All quiet">You'll be pinged when something takes off.</Empty>
            )}
          </div>

          <div className="card">
            <h2>
              Daily digest
              <span className="badge">
                {summary.digest_hour === null ? "off" : `sends at ${summary.digest_hour}:00`}
              </span>
            </h2>
            {digest.data && <pre className="digest">{digest.data.text}</pre>}
            <div style={{ marginTop: 12 }}>
              <button className="btn small" disabled={busy === "digest"} onClick={() =>
                run("digest", api.sendDigest, () => (digest.reload(), "Digest sent to your notification channels"))}>
                {busy === "digest" ? "Sending…" : "Send it now"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
