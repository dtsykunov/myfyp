# Cloudflare Worker Scaffold

This directory contains the Cloudflare deployment target for `For Us Page`.

## Scope in this scaffold commit

- Worker entrypoint with health endpoint.
- Wrangler configuration and D1 binding placeholder.
- Initial D1 schema migration.
- Baseline Worker tests.

## Local commands

```bash
npm install
npm run typecheck
npm run test
npm run dev
```

## D1 migration commands

```bash
npx wrangler d1 migrations apply for-us-page --local
npx wrangler d1 migrations apply for-us-page --remote
```

Before remote apply, replace `database_id` in `wrangler.toml` with the created D1 database id.
