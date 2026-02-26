# Social Media Operator

Restaurant social media management agent — creates, schedules, and publishes posts to X (Twitter) and Instagram.

---

## Plugin Installation

Install once per environment from the project root:

```bash
claude plugin install ./plugins/social-media-operator
```

Verify: open Claude Code in this directory and confirm the skills appear in the system prompt skills list (`post`, `menu-import`, `google-maps-review`, `approval`, `publish`).

---

## Data Directory Initialization

All post and menu data is stored in `./data/`. On first use, run:

```bash
mkdir -p data
echo '{"posts": []}' > data/posts.json
echo '{"dishes": [], "lastUpdated": ""}' > data/menu.json
```

**Or skip this step** — the `post` and `menu-import` skills will auto-create missing files.

---

## Required MCP Servers

Configure these before using the `publish` skill.

### X (Twitter) — twitter-ouath2-mcp

Provides: `McpTwitterOuath2McpPostTwitter_tool`

```bash
# Add to your MCP config (e.g. ~/.claude/mcp.json or project .mcp.json):
{
  "twitter-ouath2-mcp": {
    "command": "npx",
    "args": ["-y", "twitter-ouath2-mcp"]
  }
}
```

Then authorize via the MCP dashboard OAuth flow.

### Instagram — via Composio MCP

Provides: `McpInstagramMcpInstagramCreateMediaContainer_tool`, `McpInstagramMcpInstagramPostIgUserMediaPublish_tool`

```bash
# Install Composio MCP and connect your Instagram account:
npx @composio/cli add instagram
```

See Composio docs at https://docs.composio.dev for account linking.

### Telegram Bot

Provides: `McpTelegramBotSendMessage_tool`

Create a bot via [@BotFather](https://t.me/BotFather), then add to MCP config:

```json
{
  "telegram-bot-mcp": {
    "command": "npx",
    "args": ["-y", "telegram-bot-mcp", "--token", "YOUR_BOT_TOKEN"]
  }
}
```

Get your chat ID by sending `/start` to your bot and calling `getUpdates`.

---

## Scheduling Modes

The `post` and `approval` skills schedule posts for auto-publishing at noon (London time).

### Mode A — OpenClaw Runtime (primary)

If `~/.openclaw/cron/jobs.json` exists, scheduled tasks are registered there and fire automatically via OpenClaw's xyz task system — no manual action needed.

### Mode B — Local Fallback (standard Claude Code)

If OpenClaw is not present, scheduled tasks are saved to `./data/scheduled_tasks.json`. Publishing does **not** happen automatically. Options:

1. **Manual**: Say "publish now" or "publish `<uid>`" at the scheduled time.
2. **System cron**: Add a crontab entry to run publishing automatically:
   ```bash
   # Publish daily at noon London time — adjust path and chat trigger as needed
   0 12 * * * cd /home/ecs-user/social-media-operator && claude -p "publish now" --dangerously-skip-permissions
   ```

---

## Project Structure

```
./
├── CLAUDE.md                        # This file
├── data/
│   ├── posts.json                   # All posts (Pending → Approved → Posted)
│   ├── menu.json                    # Menu/dish database
│   ├── scheduled_tasks.json         # Scheduled publish queue (fallback mode)
│   └── *.jpg                        # Post images
└── plugins/
    └── social-media-operator/
        ├── README.md                # Plugin install guide
        ├── .claude-plugin/
        │   └── plugin.json
        ├── scripts/                 # Python helper scripts (Google Maps capture)
        └── skills/
            ├── post/
            ├── approval/
            ├── publish/
            ├── menu-import/
            └── google-maps-review/
```

---

## Available Skills

| Skill | Trigger phrases | Description |
|---|---|---|
| `post` | "post this", "create a post", "generate N posts" | Generate caption → approve → schedule |
| `approval` | "approve", "approve all", "批准" | Review and approve saved Pending posts |
| `publish` | "publish now", "publish `<uid>`", or auto at scheduled time | Publish Approved posts to X + Instagram |
| `menu-import` | Upload CSV/image/text with menu data | Import dishes into `data/menu.json` |
| `google-maps-review` | "get a review", "capture review screenshot", "截图好评" | Capture a Google Maps review + create post |

---

## Post Lifecycle

```
[user input]
     │
     ▼
  Pending  ──(approve)──▶  Approved  ──(publish)──▶  Posted
     │                        │
  saved in               scheduled task
  posts.json             created (auto-publishes at noon)
```

---

## Environment Variables (optional)

For the `google-maps-review` skill:

| Variable | Description |
|---|---|
| `GOOGLE_EMAIL` | Google account email |
| `GOOGLE_PASSWORD` | Google account password |
| `GOOGLE_MAPS_URL` | Business Share link from Google Maps |
| `PLACE_NAME` | Business name |

Set in `.env` or export before starting Claude Code.
