export type IdeaStatus = "new" | "saved" | "made" | "dismissed";

export interface Summary {
  name: string;
  niches: string[];
  counts: { trends_24h: number; unread_alerts: number; ideas: number; ideas_made: number };
  last_scan: string | null;
  digest_last_sent: string | null;
  digest_hour: number | null;
  integrations: Record<"claude" | "notion" | "youtube_trends" | "youtube_stats" | "ntfy" | "discord", boolean>;
  has_performance: boolean;
}

export interface Trend {
  id: string;
  source: string;
  title: string;
  url: string;
  summary: string | null;
  published_at: string;
  engagement: number;
  comments: number;
  score: number;
  matched_niche: string | null;
  matched_keywords: string[];
  kind: "core" | "adjacent" | "noise" | null;
  why_now: string | null;
}

export interface Alert {
  id: number;
  kind: "trend" | "adjacent_niche" | "idea" | "digest";
  title: string;
  body: string;
  url: string | null;
  created_at: string;
  read: boolean;
}

export interface Idea {
  id: number;
  status: IdeaStatus;
  created_at?: string;
  notion_page_id?: string | null;
  title: string;
  format: string;
  hook: string;
  angle: string;
  outline: string[];
  niche: string;
  source_trend_ids: string[];
}

export interface Video {
  id: string;
  title: string;
  url: string;
  views: number;
  published_at: string;
}

export interface Performance {
  channel_id: string;
  videos_analyzed: number;
  median_views: number;
  niches: { niche: string; videos: number; avg_ratio: number; multiplier: number }[];
  top: Video[];
  bottom: Video[];
  updated_at: string;
}

export interface Profile {
  name: string;
  bio: string;
  audience: string;
  voice: string;
  platforms: string[];
  niches: { name: string; keywords: string[] }[];
  sources: { subreddits: string[]; rss_feeds: string[] };
  alerts: { min_score: number; adjacent_niches: boolean; max_alerts_per_scan: number };
}

export interface DigestPreview {
  date: string;
  title: string;
  text: string;
  trends: Trend[];
  ideas: Idea[];
}
