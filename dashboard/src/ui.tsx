import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Alert, Trend } from "./types";

type Toast = { text: string; error?: boolean } | null;
const ToastCtx = createContext<(text: string, error?: boolean) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast>(null);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.error ? 7000 : 3500);
    return () => clearTimeout(t);
  }, [toast]);
  const show = useCallback((text: string, error = false) => setToast({ text, error }), []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && (
        <div className={`toast ${toast.error ? "error" : ""}`} role="status" onClick={() => setToast(null)}>
          {toast.text}
        </div>
      )}
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/** Load data on mount (and when deps change); `reload` re-fetches. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    fn().then(
      (d) => live && (setData(d), setError(null)),
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, reload: () => setTick((t) => t + 1), setData };
}

/** Wrap an action so the button shows progress and errors become toasts. */
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const run = async <T,>(key: string, fn: () => Promise<T>, done?: (r: T) => string | void) => {
    setBusy(key);
    try {
      const r = await fn();
      const msg = done?.(r);
      if (msg) toast(msg);
      return r;
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

export function timeAgo(iso: string | null | undefined) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const compact = (n: number) => Intl.NumberFormat("en", { notation: "compact" }).format(n);

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  );
}

const SOURCE_LABEL: Record<string, string> = { reddit: "Reddit", hackernews: "Hacker News", youtube: "YouTube", rss: "RSS" };

export function TrendRow({ t }: { t: Trend }) {
  return (
    <div className="row">
      <div className={`score ${t.score >= 65 ? "hot" : ""}`} title="Score out of 100: fit with your niches + momentum + freshness">
        {Math.round(t.score)}
      </div>
      <div className="row-main">
        <a className="row-title" href={t.url} target="_blank" rel="noreferrer">
          {t.title}
        </a>
        {t.why_now && <div className="muted small">{t.why_now}</div>}
        <div className="row-meta">
          {t.kind === "adjacent" ? (
            <span className="badge accent">🧭 New niche: {t.matched_niche}</span>
          ) : (
            t.matched_niche && <span className="badge">{t.matched_niche}</span>
          )}
          <span>{SOURCE_LABEL[t.source] ?? t.source}</span>
          {t.engagement > 0 && <span>· {compact(t.engagement)} {t.source === "youtube" ? "views" : "pts"}</span>}
          <span>· {timeAgo(t.published_at)}</span>
        </div>
      </div>
    </div>
  );
}

const ALERT_ICON: Record<Alert["kind"], string> = { trend: "📈", adjacent_niche: "🧭", idea: "💡", digest: "☀️" };

export function AlertRow({ a }: { a: Alert }) {
  return (
    <div className="row">
      <span aria-hidden style={{ fontSize: 20 }}>{ALERT_ICON[a.kind]}</span>
      <div className="row-main">
        {a.url ? (
          <a className="row-title" href={a.url} target="_blank" rel="noreferrer">{a.title}</a>
        ) : (
          <span className="row-title">{a.title}</span>
        )}
        <div className="muted small" style={{ whiteSpace: "pre-line" }}>{a.body}</div>
        <div className="row-meta">{timeAgo(a.created_at)}{!a.read && <span className="badge accent">new</span>}</div>
      </div>
    </div>
  );
}
