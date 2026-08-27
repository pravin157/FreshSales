# Freshsales MCP Server

An MCP (Model Context Protocol) server that exposes your Freshsales CRM
(contacts, leads, deals, tasks, notes, appointments, and global search) as
tools any MCP-compatible client — Claude Desktop, Claude Code, Cowork, etc. —
can call directly.

Built on MCP Python SDK **v2** (`MCPServer`, released alongside the
2026-07-28 MCP spec). If you've seen older MCP server code using
`FastMCP`, that's the same API under a new name — this server uses the
current one.

---

## 1. Get your Freshsales domain and API key

You need two things: your **domain** and your **API key**.

### Domain
This is the subdomain in your Freshsales URL. If you log in at
`https://acmecorp.freshsales.io`, your domain is just `acmecorp`.

### API key
1. Log in to Freshsales.
2. Click your **profile icon** (top right) → **Settings**.
3. Under **API Settings** (sometimes listed under your personal profile
   settings, not admin settings), you'll find your **API Key** —
   it's a per-user token tied to your account's permissions.
4. Copy it — treat it like a password, it grants full API access as you.

> If you don't see an API Settings option, it's usually because your
> user role doesn't have API access enabled — ask your Freshsales admin
> to enable it for your user, or generate a key under an admin account.

Official reference: [Freshsales API docs](https://developers.freshworks.com/crm/api/)

---

## 2. Install

```bash
cd freshsales-mcp
pip install -r requirements.txt
```

## 3. Configure credentials

The server auto-loads a `.env` file in this directory (via `python-dotenv`),
so the simplest path is to edit the included `.env`:

```
FRESHSALES_DOMAIN=https://your-domain.myfreshworks.com/
FRESHSALES_API_KEY=paste-your-crm-api-key-here
```

Just replace `paste-your-crm-api-key-here` with your real **CRM API key**
(not the Chat/Freshchat one — see note below).

Alternatively, set real environment variables — these override `.env`:

```bash
export FRESHSALES_DOMAIN="your-domain.myfreshworks.com"
export FRESHSALES_API_KEY="your-api-key-here"
```

> `FRESHSALES_DOMAIN` accepts either a bare subdomain (`acmecorp`) or a
> full host like `your-domain.myfreshworks.com` — the client detects
> which format you've given it and builds the right base URL.

> Freshsales gives you two API keys: **CRM API** and **Chat (Freshchat) API**.
> Use the **CRM API key** — the Chat key is for a different product and
> won't authenticate against these endpoints.

## 4. Run it standalone (sanity check)

```bash
python server.py
```

This starts the server on stdio. It won't print anything if it's working —
that's normal for stdio-transport MCP servers. Ctrl+C to stop.

## 5. Connect it to an MCP client

### Claude Desktop
Add to your `claude_desktop_config.json` (Settings → Developer → Edit Config).
A ready-to-copy version with your domain filled in is in
`claude_desktop_config.snippet.json` — just swap in the real path to
`server.py` and your CRM API key:

```json
{
  "mcpServers": {
    "freshsales": {
      "command": "python",
      "args": ["/absolute/path/to/freshsales-mcp/server.py"],
      "env": {
        "FRESHSALES_DOMAIN": "your-domain.myfreshworks.com",
        "FRESHSALES_API_KEY": "paste-your-crm-api-key-here"
      }
    }
  }
}
```

Restart Claude Desktop afterward. (If you're using the `.env` file
instead, the `env` block above is optional — the server will pick up
`.env` on its own — but the config's `env` still overrides it if both
are set.)

### Claude Code
```bash
claude mcp add freshsales -- python /absolute/path/to/freshsales-mcp/server.py
```
(then set the two env vars in your shell, or add an `env` block if your
Claude Code version's `mcp add` supports it — check `claude mcp add --help`).

---

## Tools exposed

| Area | Tools |
|---|---|
| Contacts | `list_contacts`, `get_contact`, `create_contact`, `update_contact`, `delete_contact` |
| Leads | `list_leads`, `get_lead`, `create_lead`, `update_lead`, `delete_lead` |
| Deals | `list_deals`, `get_deal`, `create_deal`, `update_deal`, `delete_deal` |
| Tasks | `list_tasks`, `get_task`, `create_task`, `update_task`, `delete_task` |
| Notes | `list_notes`, `create_note` |
| Appointments | `list_appointments`, `get_appointment`, `create_appointment`, `update_appointment`, `delete_appointment` |
| Search | `search_freshsales` |

All `create_*`/`update_*` tools take a `fields` dict matching Freshsales'
field names for that entity (e.g. `first_name`, `email`, `amount`,
`deal_stage_id`). Field names and required IDs (pipelines, stages, lead
sources, owners) are specific to your Freshsales account — use
`list_deals`/`list_contacts` on existing records first to see the shape,
or check **Admin Settings → APIs & Webhooks** in Freshsales for your
account's schema.

## Files

- `server.py` — MCP server definition, one tool per Freshsales operation
- `freshsales_client.py` — thin REST client (auth, generic CRUD, notes, search)
- `requirements.txt` — `mcp`, `httpx`

## Notes / gotchas

- **Rate limits**: Freshsales enforces per-plan API rate limits; the
  client surfaces `429` responses as a `FreshsalesError` with the status
  code so you can see it in tool output rather than a silent failure.
- **Notes' `targetable_type`**: pass the plural form used in the URL
  (`contacts`, `leads`, `deals`, `sales_accounts`) — the client maps it
  internally to the singular capitalized form Freshsales expects in the
  payload.
- **IDs over names**: deals/leads reference pipelines, stages, and lead
  sources by numeric ID, not name. Fetch these once via the Freshsales UI
  or the `/selector` metadata endpoints (not wrapped here, but a
  straightforward add if you need it) and hardcode the IDs you use often.
