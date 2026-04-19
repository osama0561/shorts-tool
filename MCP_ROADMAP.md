# MCP Roadmap

MCP (Model Context Protocol) servers wired into Claude Code for this
project, and ones we may want later.

## In use

### n8n — workflow orchestration
- **Host:** `https://n8n.srv1200431.hstgr.cloud`
- **Purpose:** schedule pipeline runs, wire Drive delivery, send
  run-status notifications.
- **Status:** pending — waiting on the user to supply the MCP
  endpoint URL and auth token. Install command will be
  `claude mcp add n8n …` once those arrive.

### Google Drive — delivery
- **Purpose:** upload finished shorts from `outputs/` to a shared
  folder for review / publishing, so we don't ship the VPS off-box.
- **Status:** pending — waiting on the user to supply OAuth client
  credentials (client ID, client secret, refresh token) and the
  target folder ID. Install command will be
  `claude mcp add google-drive …` once those arrive.

## Candidates for later

Add with `claude mcp add <name> …` in a future session when the need
lands:

- **GitHub** — issue / PR / release management once the repo is
  public. Probably first addition after MVP ships.
- **Slack** — run-done notifications, error pings.
- **Notion** — editorial calendar for the shorts we produce.
- **Linear** — ticketed bug tracking if the project outgrows one
  maintainer.
- **Postgres / Turso** — if `shorts.db` outgrows single-file SQLite.
- **S3 / R2** — if artifact storage moves off the VPS.
- **Sentry** — error monitoring once runs happen unattended in
  production.
- **YouTube Data API** — upload finished shorts directly, skipping
  the Drive hop.

## Adding a new MCP

When the user says "add the X MCP":

1. Confirm what this MCP will be used for on this project (scope
   creep check).
2. Ask for the exact endpoint URL + auth credentials. Never guess.
3. Run `claude mcp add <name> …` with those values.
4. Add a short entry to the "In use" section above with purpose and
   install command used (without secrets).
