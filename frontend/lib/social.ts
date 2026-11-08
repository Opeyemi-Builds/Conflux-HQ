export interface SocialAlias {
  value: string;
  kind: "name" | "handle" | "hashtag" | "contextual";
  platform: "x" | "instagram" | "facebook" | null;
}

export interface SocialAnalytics {
  window_start: string;
  window_end: string;
  total_posts: number;
  unique_authors: number;
  total_engagement: number;
  high_reach_posts: number;
  reputation_risk_posts: number;
  top_reputation_flags: Record<string, number>;
  hourly_velocity: { bucket_start: string; posts: number }[];
}

export interface XResult {
  source?: string;
  reason?: string;
  fetched?: number;
  replayed?: number;
  accepted_count?: number;
  accepted?: number | boolean;
  complaints_created?: number;
  duplicates?: number;
}

export function describeXResult(result: XResult): string {
  if (result.source !== "live_recent_search" && result.source !== "live_filtered_stream" &&
      result.source !== "replay_fallback" && result.source !== "recorded_replay") {
    return `X pull failed · ${result.reason ?? result.source ?? "Unknown connector outcome"}`;
  }
  const source = result.source.startsWith("live") ? "Live X" : "Recorded X replay";
  return `${source} · ${result.fetched ?? result.replayed ?? 0} posts read · ${result.complaints_created ?? 0} complaints created · ${result.duplicates ?? 0} duplicates`;
}
