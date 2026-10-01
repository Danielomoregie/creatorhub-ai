import { useState } from "react";
import { api } from "./api";
import { Empty, TrendRow, useLoad } from "./ui";

const WINDOWS = [
  { label: "24h", hours: 24 },
  { label: "3 days", hours: 72 },
  { label: "Week", hours: 168 },
];

export function Trends({ niches }: { niches: string[] }) {
  const [niche, setNiche] = useState("");
  const [hours, setHours] = useState(72);
  const [onlyNew, setOnlyNew] = useState(false);
  const trends = useLoad(() => api.trends({ niche, hours }), [niche, hours]);
  const shown = (trends.data ?? []).filter((t) => !onlyNew || t.kind === "adjacent");

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Trends</h1>
          <p>Ranked by fit with your niches, how fast they're growing, and how fresh they are.</p>
        </div>
      </div>
      <div className="filters">
        <button className={`chip ${niche === "" && !onlyNew ? "on" : ""}`} onClick={() => (setNiche(""), setOnlyNew(false))}>All</button>
        {niches.map((n) => (
          <button key={n} className={`chip ${niche === n ? "on" : ""}`} onClick={() => (setNiche(n), setOnlyNew(false))}>{n}</button>
        ))}
        <button className={`chip ${onlyNew ? "on" : ""}`} onClick={() => (setOnlyNew(true), setNiche(""))}>🧭 New niche openings</button>
        <span style={{ flex: 1 }} />
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))} aria-label="Time window">
          {WINDOWS.map((w) => <option key={w.hours} value={w.hours}>{w.label}</option>)}
        </select>
      </div>
      <div className="card">
        {trends.error && <Empty title="Couldn't load trends">{trends.error}</Empty>}
        {shown.length ? (
          <div className="list">{shown.map((t) => <TrendRow key={t.id} t={t} />)}</div>
        ) : (
          !trends.error && <Empty title="Nothing here yet">Try a wider time window, or run a scan from Today.</Empty>
        )}
      </div>
    </>
  );
}
