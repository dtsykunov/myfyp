import {
  MAX_RECOMMENDATIONS_PER_LIST,
  VIDEO_HASH_PATTERN
} from "./constants";
import { HttpError } from "./errors";
import type { RecommendationItem, SnapshotPayload } from "./types";

const TOP_LEVEL_KEYS = new Set(["capturedAt", "pageUrl", "videos", "shorts"]);
const ITEM_KEYS = new Set([
  "videoHash",
  "title",
  "channelName",
  "channelLink",
  "channelAvatar",
  "publishedAt",
  "viewCount"
]);

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function ensureNoExtraKeys(record: JsonRecord, allowed: Set<string>, context: string): void {
  const extraKeys = Object.keys(record).filter((key) => !allowed.has(key));
  if (extraKeys.length > 0) {
    throw new HttpError(422, `Unexpected field(s) in ${context}: ${extraKeys.join(", ")}.`);
  }
}

function parseRequiredString(
  value: unknown,
  fieldName: string,
  minLength: number,
  maxLength: number
): string {
  if (typeof value !== "string") {
    throw new HttpError(422, `${fieldName} must be a string.`);
  }
  if (value.length < minLength || value.length > maxLength) {
    throw new HttpError(422, `${fieldName} must be between ${minLength} and ${maxLength} characters.`);
  }
  return value;
}

function parseOptionalString(
  value: unknown,
  fieldName: string,
  minLength: number,
  maxLength: number
): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  return parseRequiredString(value, fieldName, minLength, maxLength);
}

function parseOptionalUrl(value: unknown, fieldName: string): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new HttpError(422, `${fieldName} must be a URL string.`);
  }
  try {
    return new URL(value).toString();
  } catch {
    throw new HttpError(422, `${fieldName} must be a valid URL.`);
  }
}

function parseOptionalDateTime(value: unknown, fieldName: string): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new HttpError(422, `${fieldName} must be an ISO datetime string.`);
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    throw new HttpError(422, `${fieldName} must be a valid datetime.`);
  }
  return new Date(timestamp).toISOString();
}

function parseOptionalViewCount(value: unknown): number | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (!Number.isInteger(value) || Number(value) < 0) {
    throw new HttpError(422, "viewCount must be a non-negative integer.");
  }
  return Number(value);
}

function parseRecommendationItem(value: unknown, listName: string, index: number): RecommendationItem {
  if (typeof value === "string") {
    if (!VIDEO_HASH_PATTERN.test(value)) {
      throw new HttpError(422, `${listName}[${index}].videoHash is invalid.`);
    }
    return {
      videoHash: value,
      title: value
    };
  }

  if (!isRecord(value)) {
    throw new HttpError(422, `${listName}[${index}] must be an object or video hash string.`);
  }

  ensureNoExtraKeys(value, ITEM_KEYS, `${listName}[${index}]`);

  const videoHash = parseRequiredString(value.videoHash, `${listName}[${index}].videoHash`, 11, 11);
  if (!VIDEO_HASH_PATTERN.test(videoHash)) {
    throw new HttpError(422, `${listName}[${index}].videoHash is invalid.`);
  }

  const item: RecommendationItem = {
    videoHash,
    title: parseRequiredString(value.title, `${listName}[${index}].title`, 1, 300)
  };

  const channelName = parseOptionalString(value.channelName, `${listName}[${index}].channelName`, 1, 200);
  if (channelName !== undefined) {
    item.channelName = channelName;
  }

  const channelLink = parseOptionalUrl(value.channelLink, `${listName}[${index}].channelLink`);
  if (channelLink !== undefined) {
    item.channelLink = channelLink;
  }

  const channelAvatar = parseOptionalUrl(value.channelAvatar, `${listName}[${index}].channelAvatar`);
  if (channelAvatar !== undefined) {
    item.channelAvatar = channelAvatar;
  }

  const publishedAt = parseOptionalDateTime(value.publishedAt, `${listName}[${index}].publishedAt`);
  if (publishedAt !== undefined) {
    item.publishedAt = publishedAt;
  }

  const viewCount = parseOptionalViewCount(value.viewCount);
  if (viewCount !== undefined) {
    item.viewCount = viewCount;
  }

  return item;
}

function parseRecommendationList(value: unknown, listName: "videos" | "shorts"): RecommendationItem[] {
  if (value === undefined) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new HttpError(422, `${listName} must be an array.`);
  }
  if (value.length > MAX_RECOMMENDATIONS_PER_LIST) {
    throw new HttpError(422, `${listName} exceeds maximum size of ${MAX_RECOMMENDATIONS_PER_LIST}.`);
  }

  const parsedItems = value.map((entry, index) => parseRecommendationItem(entry, listName, index));
  const uniqueHashes = new Set(parsedItems.map((item) => item.videoHash));
  if (uniqueHashes.size !== parsedItems.length) {
    throw new HttpError(422, `Duplicate videoHash values are not allowed in ${listName}.`);
  }
  return parsedItems;
}

export function parseSnapshotPayload(value: unknown): SnapshotPayload {
  if (!isRecord(value)) {
    throw new HttpError(422, "Payload must be a JSON object.");
  }

  ensureNoExtraKeys(value, TOP_LEVEL_KEYS, "payload");

  const payload: SnapshotPayload = {
    videos: parseRecommendationList(value.videos, "videos"),
    shorts: parseRecommendationList(value.shorts, "shorts")
  };

  const capturedAt = parseOptionalDateTime(value.capturedAt, "capturedAt");
  if (capturedAt !== undefined) {
    payload.capturedAt = capturedAt;
  }

  const pageUrl = parseOptionalUrl(value.pageUrl, "pageUrl");
  if (pageUrl !== undefined) {
    payload.pageUrl = pageUrl;
  }

  return payload;
}
