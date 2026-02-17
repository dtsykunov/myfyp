import type { Env } from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8"
    }
  });
}

export default {
  async fetch(request: Request, _env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({ status: "ok" });
    }

    return jsonResponse(
      {
        detail: "Worker scaffold is ready. Endpoint implementation is in progress."
      },
      501
    );
  },

  async scheduled(_event: ScheduledEvent, _env: Env, _ctx: ExecutionContext): Promise<void> {
    // Cleanup logic will be added once snapshot routes are implemented.
  }
};
