---
name: post
description: Create and schedule social media posts — generates professional captions from user input, images, or menu data; handles inline approval and auto-schedules for publishing to X and Instagram
user-invocable: true
argument-hint: [description, image path, or "generate N posts from menu"]
---

## Overview

This skill covers the full pipeline: **generate → show → approve → schedule**. Publishing at the scheduled time is handled by the **publish** skill via cron.

**Platforms:**
- **X (Twitter)**: Published via Twitter MCP tools
- **Instagram**: Published via Composio Instagram tools (requires at least 1 image)
- **Telegram**: Publish confirmations sent via Telegram MCP

---

## Trigger Conditions

Invoke when the user:
- Provides an image or text description to post
- Says "post this", "create a post", "make a post"
- Says "write me posts", "generate posts from menu", "batch posts", "schedule a week of posts"
- Proactively: offer to create posts after menu import, after a review is captured, or any other content is ready

---

## Core Philosophy

**ACT FIRST, CLOSE THE LOOP** — Generate immediately, show the result, and complete the approval + scheduling **right here in the same conversation**. Do not hand off to another skill for approval. Do not ask "what caption do you want?" — just generate, show, and ask for a yes/no.

**PROACTIVE by default** — After menu import or review capture, suggest: "Want me to write posts for these? I can generate and schedule them now."

---

## Workflow

### Step 1: Receive Input

Accept any form of input:
- A text description ("New seasonal special, grilled salmon with lemon butter")
- An image file (`.jpg`, `.png`, etc.)
- Both text and image
- Minimal input ("post this", just an image)
- Batch request ("write 5 posts from the menu", "schedule this week")
- Proactive generation from available menu/review data

**Note**: Instagram does not support text-only posts. Posts without an image are published to X only.

---

### Step 2: Generate Caption IMMEDIATELY

Generate without asking questions first.

**Writing rules:**
- English only
- Professional, conversational, direct — no fixed footer
- No hashtags (#)
- No em dashes (—) for emphasis

**De-AI checklist (avoid all of these):**
- ❌ "Delve", "meticulously", "navigating", "complexities", "realm", "bespoke", "tailored", "underpinning", "ever-evolving", "landscape"
- ❌ "It's important to note", "In today's world", "In summary"
- ❌ "Not just...but...", "more than just", "X meets Y"
- ❌ Symmetrical structures: "Faster. Smarter. Scalable."
- ❌ Starting with questions: "Looking for X?"
- ❌ Excessive adjectives: "revolutionary", "game-changing", "cutting-edge", "innovative"

**Write naturally:**
- ✅ Simple, direct language
- ✅ Vary sentence length
- ✅ Include specific details (names, numbers, outcomes)
- ✅ Conversational but professional

**Emoji limits:**
- Caption > 150 chars: max 2 emojis
- Caption 75–150 chars: max 1 emoji
- Caption < 75 chars: no emojis

**Caption templates:**

| Template | Use when |
|---|---|
| **Feature Highlight**: `[Product] + [main benefit]` / `[How it works]. [Concrete example].` | Product has a clear main benefit |
| **Problem → Solution**: `[Pain point]` / `[Product] [solves it]. [Feature or result].` | Audience has a known pain point |
| **Customer Story**: `[Customer] [needed X]` / `[What they did]. [Outcome].` | Have specific results or testimonials |
| **Simple Announcement**: `[New thing] is here.` / `[What it is]. [What makes it different].` | New launches or updates |

**Example:**
```
Input:  "New seasonal menu item, grilled salmon with lemon butter"
Output: "Grilled salmon with lemon butter is on the menu now.

Seared to order, served with roasted vegetables and a side of herb rice. Available for lunch and dinner this week."
```

---

### Step 3: Save Post to JSON Immediately

**Data file:** `./data/posts.json`

**Schema:**
```json
{
  "posts": [
    {
      "uid": "0225a",
      "status": "Pending",
      "media": ["./data/0225a.jpg"],
      "userDescription": "original user input",
      "generatedContent": "AI-generated caption",
      "createdAt": "2026-02-25T14:20:00Z",
      "scheduledAt": null,
      "approvedAt": null,
      "postedAt": null,
      "tweetId": null,
      "tweetUrl": null,
      "igPostId": null,
      "igPermalink": null
    }
  ]
}
```

**Implementation:**

```python
import json, shutil
from datetime import datetime
from pathlib import Path

# 1. Generate uid (MMDD[a-z], next available letter)
date_str = datetime.now().strftime("%m%d")
with open('./data/posts.json', 'r') as f:
    data = json.load(f)
existing = {p['uid'] for p in data['posts']}
for letter in 'abcdefghijklmnopqrstuvwxyz':
    uid = f"{date_str}{letter}"
    if uid not in existing:
        break

# 2. Save media to ./data/{uid}.ext
data_dir = Path("./data")
data_dir.mkdir(exist_ok=True)
media_paths = []
if original_file:
    ext = Path(original_file).suffix
    dest = data_dir / f"{uid}{ext}"
    shutil.copy(original_file, dest)
    media_paths = [f"./data/{uid}{ext}"]
# Multiple images: ./data/{uid}-1.jpg, ./data/{uid}-2.jpg

# 3. Append and save
new_post = {
    "uid": uid, "status": "Pending",
    "media": media_paths,
    "userDescription": user_input,
    "generatedContent": generated_caption,
    "createdAt": datetime.now().isoformat() + "Z",
    "scheduledAt": None, "approvedAt": None, "postedAt": None,
    "tweetId": None, "tweetUrl": None, "igPostId": None, "igPermalink": None
}
data['posts'].append(new_post)
with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)
```

---

### Step 4: Show Result and Ask for Inline Approval

Show what was created, then ask for a one-word answer **in the same turn**:

```
✅ Post 0225a ready

Caption:
[generated caption]

Images: 1  |  Platforms: X + Instagram

Approve to schedule for tomorrow 12:00 London time?
- "yes" / "approve" — schedules immediately, done
- "change to: [new text]" — update caption, then approve
- "shorter" / "add emoji" / "remove emoji" — quick adjustment
- "skip" — save as draft, approve later via "approve 0225a"
```

**Wait for the user's reply before closing the loop.**

---

### Step 5: Handle Approval In-Line (SAME CONVERSATION)

**If user says "yes", "approve", "ok", or any affirmative:**

Immediately update posts.json to Approved + schedule:

```python
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

with open('./data/posts.json', 'r') as f:
    data = json.load(f)

london = ZoneInfo("Europe/London")
scheduled_time = (datetime.now(london) + timedelta(days=1)).replace(
    hour=12, minute=0, second=0, microsecond=0
).isoformat()

for post in data['posts']:
    if post['uid'] == uid:
        post['status'] = 'Approved'
        post['approvedAt'] = datetime.now().isoformat() + 'Z'
        post['scheduledAt'] = scheduled_time
        break

with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)
```

Confirm:
```
✅ Scheduled — 0225a publishes tomorrow 12:00 London time
Platforms: X + Instagram
```

**If user wants edits** ("change to: ...", "shorter", "add emoji", etc.):

Apply the edit, update posts.json with new caption, show updated post, ask for approval again. Repeat until approved or skipped.

**If user says "skip":**

Leave as Pending, reply:
```
Saved as draft (0225a). Say "approve 0225a" anytime to schedule it.
```

---

### Step 6: Batch Post Generation

When user says "generate N posts", "write posts from menu", "schedule a week of content":

1. Read `./data/menu.json` to get available dishes
2. Pick N dishes (prioritize those not featured recently — check posts.json)
3. Generate a caption for each
4. Save all as Pending in posts.json (consecutive uids: 0225a, 0225b, ...)
5. Show a numbered summary:

```
Generated 5 posts for the week:

1. 0225a — "Grilled salmon with lemon butter is on the menu now..."
2. 0225b — "The lamb burger has been a staple since we opened..."
3. 0225c — "Soft-boiled eggs, chilli oil, and sesame — our breakfast bowl."
4. 0225d — "Mango sticky rice. Simple, fresh, and made to order."
5. 0225e — "New addition: pan-fried dumplings with black vinegar dipping sauce."

Reply "approve all" to schedule all on consecutive days starting tomorrow noon.
Or "1,3,5" to approve specific ones. Or "edit 2" to revise a caption.
```

**Batch approval logic:**
- "approve all" → schedule each on consecutive days (tomorrow, +2, +3...) at 12:00 London time
- "1,3" or "approve 1,3" → approve those, leave others as Pending
- "edit 2" → show full caption, let user revise, then ask again for that one

Consecutive scheduling:
```python
for i, uid in enumerate(approved_uids):
    scheduled_time = (datetime.now(london) + timedelta(days=1+i)).replace(
        hour=12, minute=0, second=0, microsecond=0
    ).isoformat()
```

---

## Data Storage

**Primary:** `./data/posts.json`

**Media:** `./data/{uid}.jpg` (single) or `./data/{uid}-1.jpg`, `./data/{uid}-2.jpg` (multiple)

**Directory:**
```
./data/
├── posts.json
├── 0225a.jpg
└── 0225b-1.jpg
```

**End-of-turn sync check:**
- New post created? → Verify it's in posts.json
- Image uploaded? → Verify file copied to `./data/`, path recorded
- Caption edited? → Verify change written
- Approved? → Verify `status=Approved`, `scheduledAt` set

---

## Skill Boundaries

| Situation | Handled by |
|---|---|
| Creating a new post and approving right now | **this skill (post)** |
| Reviewing previously saved Pending posts later | **approval** skill |
| Publishing Approved posts at scheduled time | **publish** skill (cron) |
| Importing menu data | **menu-import** skill |
| Capturing a Google Maps review | **google-maps-review** skill |

---

## Notes

- Always respond in English
- Posts without images are published to X only
- Keep captions focused — no footers, no filler
