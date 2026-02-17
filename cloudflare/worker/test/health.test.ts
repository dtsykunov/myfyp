import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, expect, it } from "vitest";

import worker from "../src/index";

describe("worker scaffold", () => {
  it("returns health payload", async () => {
    const request = new Request("https://example.com/health", {
      method: "GET"
    });
    const ctx = createExecutionContext();

    const response = await worker.fetch(request, {} as never, ctx);
    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });

  it("returns 501 for unimplemented routes", async () => {
    const request = new Request("https://example.com/api/snapshots", {
      method: "POST"
    });
    const ctx = createExecutionContext();

    const response = await worker.fetch(request, {} as never, ctx);
    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(501);
  });
});
