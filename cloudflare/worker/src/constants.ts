export const RETENTION_DAYS = 7;
export const MAX_RECOMMENDATIONS_PER_LIST = 200;
export const MAX_SNAPSHOT_BODY_BYTES = 64 * 1024;
export const SNAPSHOT_HASH_LENGTH = 12;
export const MAX_HASH_GENERATION_ATTEMPTS = 5;
export const HASH_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

export const VIDEO_HASH_PATTERN = /^[A-Za-z0-9_-]{11}$/;
export const SNAPSHOT_HASH_PATTERN = /^[A-Za-z0-9_-]{8,64}$/;
