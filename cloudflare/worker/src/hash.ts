import { HASH_ALPHABET, SNAPSHOT_HASH_LENGTH } from "./constants";

export function generateSnapshotHash(): string {
  const randomValues = new Uint32Array(SNAPSHOT_HASH_LENGTH);
  crypto.getRandomValues(randomValues);

  let hash = "";
  for (const value of randomValues) {
    hash += HASH_ALPHABET[value % HASH_ALPHABET.length];
  }
  return hash;
}
