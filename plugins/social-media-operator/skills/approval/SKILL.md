---
name: approval
description: Review and approve previously saved Pending posts — shows drafts, lets user select which to approve, and schedules them for publishing
user-invocable: false
---

## Overview

This skill handles **deferred approval** — reviewing Pending posts saved in a previous conversation. If a user is approving a post right after creating it, that is handled inline by the **post** skill.

Publishing at the scheduled time is handled by the **publish** skill.

---

## Trigger Conditions

Invoke when the user says:
- "approve" / "approve all" / "approve 1,3" / "approve 0225a"
- "show pending posts" / "what's pending?" / "what posts are waiting?"
- "批准" / "审批" / "通过"

---

## Philosophy

**ACT FIRST** — when user says "approve" without specifying:
1. Only 1 pending post → approve immediately, then confirm
2. Multiple pending posts → show compact list, ask which ones
3. "approve all" → do it immediately

---

## Workflow

### Step 1: Load Pending Posts

```python
import json

with open('./data/posts.json', 'r') as f:
    data = json.load(f)

pending = [p for p in data['posts'] if p['status'] == 'Pending']
```

If no pending posts:
```
No pending posts. All caught up.
```

---

### Step 2: Smart Approval Logic

**Case A — 1 pending, user said "approve":**
→ Approve and schedule immediately, show confirmation.

**Case B — Multiple pending, user said "approve":**
→ Show compact list, ask which ones.

**Case C — User specified:** "approve all", "1,3", "approve 0225a"
→ Process those immediately.

**Compact list format:**
```
Pending posts (3 total):

1. 0223a — "Grilled salmon with lemon butter is on the menu..." (1 image, X+IG)
2. 0224b — "The lamb burger has been a staple since we opened..." (no image, X only)
3. 0225c — "Soft-boiled eggs, chilli oil and sesame — our breakfast bowl." (1 image, X+IG)

Reply: "all", "1", "1,3", or "0224b"
```

---

### Step 3: Approve, Schedule, and Register Task

For each post being approved: update posts.json AND register a scheduled publish task.

**Scheduling is dual-mode** — OpenClaw xyz task (primary) or local queue file (fallback):

```python
import json, uuid, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

london = ZoneInfo("Europe/London")

with open('./data/posts.json', 'r') as f:
    data = json.load(f)

def register_publish_task(uid, scheduled_dt, scheduled_ms):
    openclaw_jobs = Path.home() / '.openclaw' / 'cron' / 'jobs.json'
    if openclaw_jobs.exists():
        # Primary: OpenClaw xyz task — fires automatically at scheduled time
        with open(openclaw_jobs, 'r') as f:
            jobs = json.load(f)
        now_ms = int(time.time() * 1000)
        jobs['jobs'].append({
            "id": str(uuid.uuid4()),
            "agentId": "main",
            "name": f"Publish {uid}",
            "enabled": True,
            "createdAtMs": now_ms,
            "updatedAtMs": now_ms,
            "schedule": {"kind": "at", "atMs": scheduled_ms},
            "sessionTarget": "main",
            "wakeMode": "next-heartbeat",
            "payload": {"kind": "systemEvent", "text": f"run skill=publish uid={uid}"},
            "state": {"nextRunAtMs": scheduled_ms, "lastRunAtMs": None,
                      "lastStatus": None, "lastDurationMs": None}
        })
        with open(openclaw_jobs, 'w') as f:
            json.dump(jobs, f, indent=2)
        return "openclaw"
    else:
        # Fallback: local queue — requires manual "publish now" or system cron
        tasks_file = Path('./data/scheduled_tasks.json')
        tasks = json.loads(tasks_file.read_text()) if tasks_file.exists() else {"tasks": []}
        tasks["tasks"].append({
            "uid": uid,
            "scheduledAt": scheduled_dt.isoformat(),
            "status": "pending"
        })
        tasks_file.write_text(json.dumps(tasks, indent=2))
        return "local"

# Space multiple approvals 1 day apart starting tomorrow
modes = []
for i, uid in enumerate(uids_to_approve):
    scheduled_dt = (datetime.now(london) + timedelta(days=1+i)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    scheduled_ms = int(scheduled_dt.timestamp() * 1000)

    for post in data['posts']:
        if post['uid'] == uid:
            post['status'] = 'Approved'
            post['approvedAt'] = datetime.now().isoformat() + 'Z'
            post['scheduledAt'] = scheduled_dt.isoformat()
            break

    modes.append(register_publish_task(uid, scheduled_dt, scheduled_ms))

with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)

scheduling_mode = "openclaw" if "openclaw" in modes else "local"
```

**Scheduling:**
- Single post → tomorrow 12:00 London
- Multiple posts → consecutive days (tomorrow, +2, +3...) all at 12:00 London
- Each post gets its own task — no daily cron needed

---

### Step 4: Confirm

OpenClaw mode (auto-publishes):
```
✅ Approved and scheduled!

- 0223a → 26 Feb 12:00 (X + Instagram)
- 0225c → 27 Feb 12:00 (X + Instagram)

Will auto-publish at noon each day.
```

Local fallback mode (manual publish required):
```
✅ Approved and scheduled!

- 0223a → 26 Feb 12:00 (X + Instagram)
- 0225c → 27 Feb 12:00 (X + Instagram)

⚠️ Auto-publishing requires OpenClaw runtime. Say "publish now" at noon each day, or set up a system cron job (see CLAUDE.md).
```

---

### Step 5: Handle Caption Edits

If user says "edit 2" or "change caption for 0224b before approving":
- Show current caption
- Accept new text or instructions ("shorter", "add emoji")
- Update `generatedContent` in posts.json
- Show updated version, ask for approval

---

## Sync Check

At end of every turn:
- Approved posts? → Verify `status=Approved` and `scheduledAt` set in posts.json
- Edited captions? → Verify `generatedContent` updated

---

## Notes

- Always respond in English
- Multiple approvals are spaced 1 day apart — no double-booking on the same slot
- This skill handles Pending → Approved only. For Approved → Posted, see the **publish** skill
