# Resources (Local Copies)

This folder contains local copies/snapshots of external resources so MCP tools can read them quickly without re-fetching.

## What's Included
- `pdf/`: downloaded PDFs
- `web/`: single-page HTML snapshots (not full site mirrors)

## How To Use With MCP
- For PDFs: use the `document-loader` MCP server (profile `research`/`full`) or read via filesystem tools.
- For HTML snapshots: read via filesystem tools; for live browsing use the `fetch` MCP server.

## Adding New Resources (No Code Changes)
- Edit `ramshare/resources/sources.json`:
  - Add PDFs under `pdf[]`
  - Add HTML snapshots under `html[]`
  - For untrusted mirrors, add to `record_only[]` (record, don't fetch)
- Then run `scripts/ingest-and-index.ps1` (which calls `scripts/pull-resources.ps1`).

## Safety Notes
- Only download from reputable sources. If a link is an unverified mirror, record it in the manifest but don't fetch it by default.

