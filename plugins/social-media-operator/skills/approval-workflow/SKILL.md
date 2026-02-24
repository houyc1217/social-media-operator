---
name: approval-workflow
description: Post approval workflow - handles user approval requests, converts Pending posts to Approved, and schedules them for publication on X and Instagram
user-invocable: false
---

## Overview

This workflow handles post approvals - reads Pending posts from local JSON, updates status to Approved, and schedules them for tomorrow at 12:00 London time. Publishing happens later via **publish-workflow** using available MCP tools.

---

## Trigger Conditions

Invoke this workflow when the user says:
- "approve" / "approve all" / "approve 1,3" / "approve 0205a"
- "批准" / "审批" / "通过"

## Workflow Philosophy

**ACT FIRST** — When user says "approve" without specifying which posts:
1. If there's only 1 pending post → approve it immediately
2. If there are multiple → show them and ask which ones
3. If user says "approve all" → do it immediately

**Default behavior: APPROVE and SCHEDULE immediately, then confirm.**

### 1. Load Pending Posts from Local JSON

**Read from:** `./data/posts.json`

**Implementation:**
```python
import json

with open('./data/posts.json', 'r') as f:
    data = json.load(f)

pending_posts = [post for post in data['posts'] if post['status'] == 'Pending']
```

### 2. Smart Approval Logic

**Case A: User says "approve" and there's ONLY 1 pending post**
→ Approve it immediately, schedule for tomorrow 12:00, then show confirmation

**Case B: User says "approve" and there are MULTIPLE pending posts**
→ Show the list with numbers and ask which ones

**Case C: User says "approve all" or "approve 1,3" or "approve 0205a"**
→ Approve those specific ones immediately

### 3. Show Pending Posts (only when needed)

Format:
```
Pending posts (X total):

1. 0205a — [first 50 chars of caption]... (1 image, X+IG)
2. 0206b — [first 50 chars of caption]... (2 images, X+IG)

Which ones? Reply: "1", "all", "1,2"
```

**Keep it concise** — don't show full captions unless user asks.

### 4. Process Approval (IMMEDIATELY)

Update posts in local JSON file:

**Implementation:**
```python
import json
from datetime import datetime

# Read current data
with open('./data/posts.json', 'r') as f:
    data = json.load(f)

# Find and update post by uid
for post in data['posts']:
    if post['uid'] == target_uid:
        post['status'] = 'Approved'
        post['approvedAt'] = datetime.now().isoformat() + 'Z'
        break

# Write back
with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)
```

**Update logic:**
- **Approve**: Set `status` → `"Approved"`, record `approvedAt`
- **Reject**: Set `status` → `"Rejected"`
- **Edit**: Update `generatedContent`, then approve

### 5. Auto-Schedule

After approval, update `scheduledAt` to tomorrow at 12:00 London time:

**Calculate and update:**
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

scheduled_time = (datetime.now(ZoneInfo("Europe/London")) + timedelta(days=1)).replace(
    hour=12, minute=0, second=0, microsecond=0
).isoformat() + '+00:00'
# Example: "2026-02-21T12:00:00+00:00"

# Update in the same operation as Step 4
post['scheduledAt'] = scheduled_time
```

This is done in the SAME write operation as Step 4 (combine status + approvedAt + scheduledAt updates).

### 6. Confirmation (Show what you DID)

```
✅ Approved and scheduled!

- 0205a → publishes tomorrow 12:00 (X + Instagram)

All set. I'll auto-publish at noon tomorrow.
```

**Concise and action-oriented** — tell them it's done, not what will happen.

### 7. Proactive Sync Check (CRITICAL)

**At the end of every conversation turn**, check if posts.json needs updating:
- Did we approve any posts? → Verify posts.json is updated
- Did we edit any captions? → Ensure changes are saved
- Any status changes? → Confirm posts.json reflects current state

**Always sync proactively** — don't wait for user to ask.

## Data Storage

**Primary:** `./data/posts.json` (local JSON file - ALWAYS use this)

**Success Pattern:**
1. Read entire posts.json file
2. Find target post by matching `uid`
3. Modify post object fields
4. Write entire file back with `json.dump(data, f, indent=2)`
5. Verify file was written successfully

## Response Format

- Use English at all times
- List action results clearly
- Show scheduled time for each approved post
- Confirm which platforms the post will be published to
