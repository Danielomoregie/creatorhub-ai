import { useEffect, useState } from "react";
import { api } from "./api";
import { Ideas } from "./Ideas";
import { Settings } from "./Settings";
import { Stats } from "./Stats";
import { Today } from "./Today";
import { Trends } from "./Trends";
import { Empty, timeAgo, useLoad } from "./ui";

const TABS = [
  { id: "today", label: "Today", icon: "☀️" },
  { id: "trends", label: "Trends", icon: "📈" },
  { id: "ideas", label: "Ideas", icon: "💡" },
  { id: "stats", label: "My stats", icon: "📊" },
  { id: "settings", label: "Settings", icon: "⚙️" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export function App() {
  const fromHash = () => TABS.find((t) => `#${t.id}` === location.hash)?.id ?? "today";
  const [tab, setTab] = useState<Tab>(fromHash);
  const summary = useLoad(() => api.summary());
  useEffect(() => {
    const onHash = () => setTab(fromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);
  const go = (t: string) => {
    location.hash = t; // hashchange updates the tab, so the back button works too
  };
  const s = summary.data;

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <svg width="18" height="18" viewBox="0 0 32 32"><path d="M5 23l7-8 6 4 9-11" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          CreatorHub
        </div>
        {TABS.map((t) => (
          <button key={t.id} className={`nav-btn ${tab === t.id ? "active" : ""}`} onClick={() => go(t.id)} aria-current={tab === t.id ? "page" : undefined}>
            <span>{t.icon} {t.label}</span>
            {t.id === "today" && !!s?.counts.unread_alerts && <span className="badge accent">{s.counts.unread_alerts}</span>}
          </button>
        ))}
        <div className="sidebar-foot">Last scan {timeAgo(s?.last_scan)}</div>
      </nav>
      <main>
        {summary.error && (
          <div className="card">
            <Empty title="Can't reach CreatorHub">
              Make sure <code>creatorhub dashboard</code> is running. ({summary.error})
            </Empty>
          </div>
        )}
        {s && tab === "today" && <Today summary={s} refresh={summary.reload} go={go} />}
        {s && tab === "trends" && <Trends niches={s.niches} />}
        {s && tab === "ideas" && <Ideas summary={s} refresh={summary.reload} />}
        {s && tab === "stats" && <Stats summary={s} refresh={summary.reload} />}
        {s && tab === "settings" && <Settings summary={s} refresh={summary.reload} />}
      </main>
    </div>
  );
}
