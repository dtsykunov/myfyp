export interface Env {
  DB: D1Database;
}

export interface RecommendationItem {
  videoHash: string;
  title: string;
  channelName?: string;
  channelLink?: string;
  channelAvatar?: string;
  publishedAt?: string;
  viewCount?: number;
}

export interface SnapshotPayload {
  capturedAt?: string;
  pageUrl?: string;
  videos: RecommendationItem[];
  shorts: RecommendationItem[];
}

export interface StoredSnapshotRecord {
  hash: string;
  createdAt: string;
  expiresAt: string;
  payload: SnapshotPayload;
}
