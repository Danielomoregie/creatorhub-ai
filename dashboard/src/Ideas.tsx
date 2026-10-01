import { useState } from "react";
import { api } from "./api";
import type { Idea, IdeaStatus, Summary } from "./types";
import { Empty, useAction, useLoad } from "./ui";

const COLUMNS: { status: IdeaStatus; label: string }[] = [
  { status: "new", label: "💡 New" },
  { status: "saved", label: "📌 Planned" },
  { status: "made", label: "✅ Made" },
];
const PLATFORMS = ["", "YouTube", "YouTube Shorts", "TikTok", "Instagram Reels", "Instagram carousel", "LinkedIn"];

export function Ideas({ summary, refresh }: { summary: Summary; refresh: () => void }) {
  const ideas = useLoad(() => api.ideas());
  const { busy, run } = useAction();
  const [count, setCount] = useState(3);
  const [niche, setNiche] = useState("");
  const [platform, setPlatform] = useState("");
  const [direction, setDirection] = useState("");

  const setStatus = (idea: Idea, status: IdeaStatus) =>
    run(`s${idea.id}`, () => api.setIdeaStatus(idea.id, status), () => (ideas.reload(), refresh(), undefined));

  const generate = () =>
    run("gen", () => api.generateIdeas({ count, niche: niche || undefined, platform: platform || undefined, direction: direction || undefined }),
      (r) => (ideas.reload(), refresh(), `${r.length} fresh ideas added to New`));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Ideas</h1>
          <p>Pitched from live trends{summary.has_performance ? " and what's worked on your channel" : ""}. Move them along as you make them.</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h2>Generate ideas</h2>
        {!summary.integrations.claude ? (
          <p className="muted" style={{ margin: 0 }}>
            Add <code>ANTHROPIC_API_KEY</code> to <code>~/.creatorhub/.env</code> and restart the dashboard to generate ideas here.
            (You can also ask Claude Desktop through the MCP server.)
          </p>
        ) : (
          <div className="form-row">
            <div className="field">
              <label htmlFor="count">How many</label>
              <input id="count" type="number" min={1} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))} />
            </div>
            <div className="field">
              <label htmlFor="niche">Niche</label>
              <select id="niche" value={niche} onChange={(e) => setNiche(e.target.value)}>
                <option value="">Any</option>
                {summary.niches.map((n) => <option key={n}>{n}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="platform">Platform</label>
              <select id="platform" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {PLATFORMS.map((p) => <option key={p} value={p}>{p || "Any"}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="direction">Direction (optional)</label>
              <input id="direction" placeholder="e.g. something for my internship series" value={direction} onChange={(e) => setDirection(e.target.value)} />
            </div>
            <button className="btn primary" disabled={busy === "gen"} onClick={generate}>
              {busy === "gen" ? "Thinking…" : "✨ Generate"}
            </button>
          </div>
        )}
      </div>

      <div className="board">
        {COLUMNS.map((col) => {
          const items = (ideas.data ?? []).filter((i) => i.status === col.status);
          return (
            <section key={col.status}>
              <div className="col-head">{col.label}<span className="badge">{items.length}</span></div>
              {items.length ? items.map((idea) => (
                <IdeaCard key={idea.id} idea={idea} busy={busy} notion={summary.integrations.notion}
                  onStatus={(s) => setStatus(idea, s)}
                  onNotion={() => run(`n${idea.id}`, () => api.toNotion(idea.id), () => (ideas.reload(), "Sent to Notion"))} />
              )) : <div className="card"><Empty title="Empty">{col.status === "new" ? "Generate some ideas above." : "Move ideas here as you go."}</Empty></div>}
            </section>
          );
        })}
      </div>
    </>
  );
}

function IdeaCard({ idea, busy, notion, onStatus, onNotion }: {
  idea: Idea; busy: string | null; notion: boolean; onStatus: (s: IdeaStatus) => void; onNotion: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className="idea">
      <div className="row-meta" style={{ marginTop: 0 }}>
        <span className="badge accent">{idea.format}</span>
        <span className="badge">{idea.niche}</span>
        {idea.notion_page_id && <span className="badge good">in Notion</span>}
      </div>
      <h3>{idea.title}</h3>
      <p className="hook">“{idea.hook}”</p>
      {open && (
        <>
          <p className="small" style={{ margin: 0 }}>{idea.angle}</p>
          <ol>{idea.outline.map((b, i) => <li key={i}>{b}</li>)}</ol>
        </>
      )}
      <div className="idea-actions">
        <button className="btn small ghost" onClick={() => setOpen(!open)}>{open ? "Less" : "Outline"}</button>
        {idea.status === "new" && <button className="btn small" disabled={!!busy} onClick={() => onStatus("saved")}>📌 Plan it</button>}
        {idea.status === "saved" && <button className="btn small" disabled={!!busy} onClick={() => onStatus("made")}>✅ Made it</button>}
        {notion && !idea.notion_page_id && (
          <button className="btn small" disabled={busy === `n${idea.id}`} onClick={onNotion}>{busy === `n${idea.id}` ? "Sending…" : "→ Notion"}</button>
        )}
        {idea.status !== "made" && <button className="btn small ghost" disabled={!!busy} onClick={() => onStatus("dismissed")} title="Dismiss">✕</button>}
      </div>
    </article>
  );
}
