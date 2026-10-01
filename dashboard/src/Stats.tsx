import { api } from "./api";
import type { Summary } from "./types";
import { Empty, compact, useAction, useLoad, timeAgo } from "./ui";

/** Horizontal diverging bars around 1x (your channel median): blue = beats median, red = below. */
function NicheChart({ niches }: { niches: { niche: string; videos: number; avg_ratio: number }[] }) {
  // Log scale so 2x above and 2x below are the same length. Clamp at 4x either way.
  const MAX = Math.log2(4);
  const pct = (r: number) => (Math.min(MAX, Math.abs(Math.log2(Math.max(r, 0.01)))) / MAX) * 50;
  return (
    <div className="perf-chart" role="img" aria-label="Average views per niche relative to your channel median">
      {niches.map((n) => {
        const up = n.avg_ratio >= 1;
        return (
          <div className="perf-row" key={n.niche} title={`${n.niche}: ${n.avg_ratio}x your median across ${n.videos} videos`}>
            <span>{n.niche}</span>
            <div className="perf-track">
              <div className={`perf-bar ${up ? "up" : "down"}`} style={{ width: `${Math.max(pct(n.avg_ratio), 0.6)}%` }} />
            </div>
            <span className="perf-value">{n.avg_ratio.toFixed(1)}x</span>
          </div>
        );
      })}
      <div className="perf-axis"><span /><span><span>¼x</span><span>1x = your median</span><span>4x</span></span><span /></div>
    </div>
  );
}

export function Stats({ summary, refresh }: { summary: Summary; refresh: () => void }) {
  const perf = useLoad(() => api.performance());
  const { busy, run } = useAction();
  const p = perf.data;
  const configured = summary.integrations.youtube_stats;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My stats</h1>
          <p>What actually works for your audience. Niches that beat your median get a boost in trend scores and idea prompts.</p>
        </div>
        {configured && (
          <button className="btn primary" disabled={busy === "p"} onClick={() =>
            run("p", api.refreshPerformance, (r) => (perf.setData(r), refresh(), `Analysed ${r.videos_analyzed} videos`))}>
            {busy === "p" ? "Pulling stats…" : "↻ Refresh from YouTube"}
          </button>
        )}
      </div>

      {!configured ? (
        <div className="card">
          <Empty title="Connect your YouTube channel">
            <p className="muted">
              Add <code>YOUTUBE_API_KEY</code> and <code>YOUTUBE_CHANNEL_ID</code> (starts with <code>UC</code>, found at
              youtube.com/account_advanced) to <code>~/.creatorhub/.env</code>, then restart the dashboard.
            </p>
          </Empty>
        </div>
      ) : !p || !p.videos_analyzed ? (
        <div className="card"><Empty title="No stats yet">Click “Refresh from YouTube” to analyse your uploads.</Empty></div>
      ) : (
        <div className="grid two">
          <div className="card">
            <h2>Views by niche vs your median <span className="badge">{p.videos_analyzed} videos · median {compact(p.median_views)}</span></h2>
            {p.niches.length ? <NicheChart niches={p.niches} /> : <Empty title="No niche matches">Your video titles don't match your niche keywords yet.</Empty>}
            {!!p.niches.length && (
              <table style={{ marginTop: 18 }}>
                <thead><tr><th>Niche</th><th className="num">Videos</th><th className="num">vs median</th><th className="num">Trend boost</th></tr></thead>
                <tbody>
                  {p.niches.map((n) => (
                    <tr key={n.niche}>
                      <td>{n.niche}</td>
                      <td className="num">{n.videos}</td>
                      <td className="num">{n.avg_ratio.toFixed(2)}x</td>
                      <td className="num">{n.multiplier === 1 ? "—" : `×${n.multiplier.toFixed(2)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="muted small" style={{ marginBottom: 0 }}>Updated {timeAgo(p.updated_at)}. Niches need 2+ videos before they get a boost.</p>
          </div>
          <div className="card">
            <h2>Your best videos</h2>
            <div className="list">
              {p.top.map((v) => (
                <div className="row" key={v.id}>
                  <div className="row-main">
                    <a className="row-title" href={v.url} target="_blank" rel="noreferrer">{v.title}</a>
                    <div className="row-meta">{compact(v.views)} views · {timeAgo(v.published_at)}</div>
                  </div>
                </div>
              ))}
            </div>
            {!!p.bottom.length && (
              <>
                <h2 style={{ marginTop: 18 }}>Didn't land</h2>
                <div className="list">
                  {p.bottom.map((v) => (
                    <div className="row" key={v.id}>
                      <div className="row-main">
                        <a className="row-title" href={v.url} target="_blank" rel="noreferrer">{v.title}</a>
                        <div className="row-meta">{compact(v.views)} views</div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
