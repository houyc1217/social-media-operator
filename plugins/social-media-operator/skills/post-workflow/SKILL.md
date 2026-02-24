---
name: post-workflow
description: Post creation workflow - generates professional captions from user descriptions or images for dual-platform publishing to X and Instagram
user-invocable: true
argument-hint: [description or image path]
metadata:
  openclaw:
    requires:
      env: []
---

## Overview

This workflow creates and saves posts to local JSON. Publishing happens later via **publish-workflow** using available MCP tools (Twitter MCP and Composio).

**Platforms:**
- **X (Twitter)**: Published via Twitter MCP tools
- **Instagram**: Published via Composio Instagram tools (requires at least 1 image)
- **Telegram**: Publish confirmations sent via Telegram MCP

---

## Trigger Conditions

Invoke when the user:
- Provides an image or a text description to post
- Says "post this", "create a post", "make a post", or similar

## Character Limits

| Platform | Limit | Notes |
|---|---|---|
| X | 25,000 chars | Premium account; no practical limit |
| Instagram | 2,200 chars | Requires at least 1 image |

## Workflow Philosophy

**ACT FIRST, ASK LATER** — Generate the post immediately with sensible defaults. Show the user what you created and let them approve or request changes. Never ask "what caption do you want?" or "which platforms?" — just do it.

### 1. Receive User Input

The user may provide:
- A text description ("Today we did a silk press transformation...")
- An image file (`.jpg`, `.png`, etc.)
- Both text and image
- Minimal info ("post this", "new haircut", even just an image with no text)

**Note**: Instagram does not support text-only posts. If no image is provided, the post will be published to X only.

### 2. Generate Caption IMMEDIATELY

**Don't ask** — just generate a professional English caption based on whatever info the user provided:

**Rules:**
- Write in English
- Professional and engaging tone
- No fixed footer - keep captions focused on the content itself

**De-AI Writing Guidelines (Critical):**

Avoid these AI clichés at all costs:
- ❌ "Delve", "meticulously", "navigating", "complexities", "realm", "bespoke", "tailored", "towards", "underpinning", "ever-evolving", "landscape"
- ❌ "It's important to note", "It's worth noting", "In today's world", "In summary"
- ❌ "Not just...but...", "more than just", "X meets Y"
- ❌ Em dashes (—) for emphasis
- ❌ Overly symmetrical structures: "Faster. Smarter. Scalable."
- ❌ Starting with questions: "Looking for X?"
- ❌ Excessive adjectives: "revolutionary", "game-changing", "cutting-edge", "innovative"
- ❌ Hashtags (#)

Write naturally:
- ✅ Use simple, direct language
- ✅ Vary sentence length naturally
- ✅ Include specific details (names, numbers, outcomes)
- ✅ Write like a human who knows the product well
- ✅ Be conversational but professional

**Emoji limits:**
- Caption > 150 chars: max 2 emojis
- Caption 75–150 chars: max 1 emoji
- Caption < 75 chars: no emojis
- General rule: avoid emojis unless they add clear value

**Example:**
```
Input:  "New seasonal menu item, grilled salmon with lemon butter"
Output: "Grilled salmon with lemon butter is on the menu now.

Seared to order, served with roasted vegetables and a side of herb rice. Available for lunch and dinner this week."
```

---

## Universal Product Templates (English Only)

Use these templates for general products (physical or digital). Adapt the footer to match the product context.

### Template 1: Feature Highlight (Physical/Digital)
```
[Product name] + [main benefit/result]

[Specific detail about how it works or what it does]. [One concrete example or use case].
```

**Example (Physical Product):**
```
Our ceramic travel mug keeps coffee hot for 6 hours.

Double-wall insulation and a leak-proof lid mean no spills in your bag. Sarah uses hers on her 2-hour commute every morning.
```

**Example (Digital Product):**
```
Dashboard that shows your metrics in real time.

Connect your data sources once and see everything update automatically. Over 2,000 teams track their weekly goals this way.
```

### Template 2: Problem → Solution (Physical/Digital)
```
[Common problem statement]

[Your product name] [how it solves the problem]. [Specific feature or benefit].
```

**Example (Physical Product):**
```
Tired of tangled charging cables?

Our magnetic cable organizer clips to your desk and holds 5 cables in place. Each cable snaps into its own slot and stays put.
```

**Example (Digital Product):**
```
Spending hours on manual data entry?

Our import tool reads your CSV files and maps fields automatically. Most users finish setup in under 10 minutes.
```

### Template 3: Customer Story (Physical/Digital)
```
[Customer name/type] [what they needed/wanted]

[What they did with your product]. [Specific result or outcome].
```

**Example (Physical Product):**
```
James needed a standing desk that fit his small apartment.

He got our compact model that folds flat when not in use. Now he switches between sitting and standing without losing floor space.
```

**Example (Digital Product):**
```
A 5-person marketing team needed faster approval workflows.

They set up our review system with 3 approval stages. Their campaign launch time dropped from 2 weeks to 5 days.
```

### Template 4: Simple Announcement (Physical/Digital)
```
[New product/feature] is here.

[What it is]. [Key benefit or what makes it different].
```

**Example (Physical Product):**
```
New color options for our backpack line.

Navy, forest green, and charcoal grey. Same water-resistant material and laptop compartment you know.
```

**Example (Digital Product):**
```
Calendar sync is live.

Connect your Google or Outlook calendar and we'll block time for your tasks automatically. No more double-booking.
```

---

## Template Selection Guide

- **Feature Highlight**: When product has a clear main benefit
- **Problem → Solution**: When audience has a known pain point
- **Customer Story**: When you have specific user results/testimonials
- **Simple Announcement**: For new launches or updates

**No footers** - keep captions focused on the content. Let the message stand on its own.

### 3. Save Post to Local JSON (IMMEDIATELY)

**Data File:** `./data/posts.json`

**Schema:**
```json
{
  "posts": [
    {
      "uid": "0220a",
      "status": "Pending",
      "media": ["./data/0220a.jpg"],
      "userDescription": "original user input",
      "generatedContent": "AI-generated caption",
      "createdAt": "2026-02-20T14:20:00Z",
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

**Implementation Steps:**

1. **Generate uid**: Use format `MMDD[a-z]` (e.g., "0220a", "0220b")
   ```python
   from datetime import datetime
   date_str = datetime.now().strftime("%m%d")
   # Find next available letter suffix by checking existing uids
   uid = f"{date_str}a"  # or b, c, etc.
   ```

2. **Save media files with uid naming**: If user uploads image(s), save them to `./data/` with uid as filename
   ```python
   import shutil
   from pathlib import Path

   # For single image
   data_dir = Path("./data")
   data_dir.mkdir(exist_ok=True)

   # Get file extension from original file
   file_ext = Path(original_file).suffix  # e.g., ".jpg"
   new_filename = f"{uid}{file_ext}"  # e.g., "0220a.jpg"
   target_path = data_dir / new_filename

   shutil.copy(original_file, target_path)
   media_path = f"./data/{new_filename}"

   # For multiple images, use suffixes: 0220a-1.jpg, 0220a-2.jpg, etc.
   ```

3. **Read existing posts.json**:
   ```python
   import json
   with open('./data/posts.json', 'r') as f:
       data = json.load(f)
   ```

4. **Append new post**:
   ```python
   new_post = {
       "uid": uid,
       "status": "Pending",
       "media": [media_path],  # e.g., ["./data/0220a.jpg"]
       "userDescription": user_input,
       "generatedContent": generated_caption,
       "createdAt": datetime.now().isoformat() + "Z",
       "scheduledAt": None,
       "approvedAt": None,
       "postedAt": None,
       "tweetId": None,
       "tweetUrl": None,
       "igPostId": None,
       "igPermalink": None
   }
   data['posts'].append(new_post)
   ```

5. **Write back to file**:
   ```python
   with open('./data/posts.json', 'w') as f:
       json.dump(data, f, indent=2)
   ```

### 4. Show Result and Ask for Approval

**Show what you DID, not what you CAN do:**

```
✅ Post 0205a created and ready to go!

Caption:
[generated caption content...]

Images: 1
Platforms: X + Instagram

Like it? Reply:
- "approve" — I'll schedule it for publishing
- "change to: [new caption]" — I'll update it
- "add emoji" / "remove emoji" / "shorter" — I'll adjust it
```

## Data Storage

**Primary:** `./data/posts.json` (local JSON file - ALWAYS use this)

**Media Storage:** All media files are saved in the same `./data/` directory as `posts.json`

**Naming Convention:**
- Single image: `{uid}.jpg` (e.g., `0220a.jpg`)
- Multiple images: `{uid}-1.jpg`, `{uid}-2.jpg`, etc. (e.g., `0220a-1.jpg`, `0220a-2.jpg`)
- Media paths in JSON: `"media": ["./data/0220a.jpg"]`

**Directory Structure:**
```
./data/
├── posts.json
├── 0220a.jpg
├── 0220b.jpg
└── 0220c-1.jpg
```

**Critical: End-of-Turn Sync Check**

At the end of EVERY conversation turn, proactively check if posts.json needs updating:
- Did we create a new post? → Verify it's saved to posts.json
- Did user upload an image? → Verify media is saved to `./data/{uid}.jpg` and path is recorded
- Any caption edits? → Ensure changes are written
- Status changes? → Confirm posts.json reflects current state

**Always sync proactively** — don't wait for user to ask.

**Operations:**
1. **Create**: Save media to `./data/{uid}.jpg`, append new post object to `posts` array
2. **Read**: Load entire file, filter by status or uid
3. **Update**: Find post by uid, modify fields, write back entire file
4. **Delete**: Filter out by uid, optionally delete associated media files, write back remaining posts

## Notes

- Posts require user approval before publishing
- After approval, posts are automatically scheduled and published to X and Instagram
- Posts without images are published to X only
- Images are saved to the workspace directory
- Always respond in English
