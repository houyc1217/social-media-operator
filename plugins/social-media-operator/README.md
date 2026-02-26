# social-media-operator

Claude Code plugin for restaurant social media management — creates, approves, and publishes posts to X (Twitter) and Instagram.

---

## Quick Start

```bash
# 1. Clone / open the project
cd /path/to/social-media-operator

# 2. Install the plugin
claude plugin install ./plugins/social-media-operator

# 3. Initialize data directory
mkdir -p data
echo '{"posts": []}' > data/posts.json
echo '{"dishes": [], "lastUpdated": ""}' > data/menu.json

# 4. Open Claude Code — skills will be available immediately
claude
```

---

## Skills

| Skill | Invocable | Trigger |
|---|---|---|
| `post` | ✅ user | "post this", "create a post", "generate 5 posts" |
| `menu-import` | ✅ user | Upload any menu file/image/text |
| `google-maps-review` | ✅ user | "get a review", "截图好评" |
| `approval` | 🤖 auto | "approve", "approve all", "批准" |
| `publish` | 🤖 auto | "publish now", or auto via scheduled task |

---

## MCP Requirements

The `publish` skill requires three MCP servers. See `CLAUDE.md` (project root) for full setup instructions.

| MCP Server | Purpose | Tool name prefix |
|---|---|---|
| twitter-ouath2-mcp | Post to X (Twitter) | `McpTwitterOuath2Mcp` |
| Composio Instagram MCP | Post to Instagram | `McpInstagramMcp` |
| telegram-bot-mcp | Publish notifications | `McpTelegramBot` |

---

## Scheduling

Scheduled auto-publishing works in two modes:

- **OpenClaw runtime** (`~/.openclaw/cron/jobs.json` exists): tasks fire automatically at noon London time — no action needed.
- **Standard Claude Code** (no OpenClaw): schedule is saved to `./data/scheduled_tasks.json`. Say "publish now" manually, or configure system cron.

---

## Plugin Structure

```
social-media-operator/
├── README.md
├── .claude-plugin/
│   └── plugin.json            # Plugin manifest
├── scripts/
│   ├── capture_gmap_review.py
│   ├── google_login.py
│   ├── render_review_card.py
│   └── review_card_template.html
└── skills/
    ├── post/SKILL.md
    ├── approval/SKILL.md
    ├── publish/SKILL.md
    ├── menu-import/SKILL.md
    └── google-maps-review/SKILL.md
```

---

## Version

`1.7.0` — See `CLAUDE.md` for full documentation.
