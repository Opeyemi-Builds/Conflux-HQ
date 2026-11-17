export interface SocialAlias {
  value: string;
  kind: "name" | "handle" | "hashtag" | "contextual";
  platform: "x" | "instagram" | "facebook" | null;
}

export interface TopSocialPost {
  post_id: string;
  platform: string;
  source_url: string | null;
  engagement: number;
  impressions: number;
  issue_type: string | null;
  reputation_flags: string[];
  reputation_score: number;
  received_at: string;
  snippet: string | null;
}

export interface SocialAnalytics {
  window_start: string;
  window_end: string;
  total_posts: number;
  unique_authors: number;
  total_engagement: number;
  total_impressions: number;
  high_reach_posts: number;
  reputation_risk_posts: number;
  average_reputation_score?: number;
  top_reputation_flags: Record<string, number>;
  by_issue_type: Record<string, number>;
  by_platform: Record<string, number>;
  top_posts: TopSocialPost[];
  hourly_velocity: { bucket_start: string; posts: number }[];
}
