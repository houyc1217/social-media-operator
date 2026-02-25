---
name: publish
description: Publishing engine — publishes Approved posts to X and Instagram using dc.missuo.ru image hosting, then sends a Telegram notification with the publish report
user-invocable: false
allowed-tools: Bash(python3 *, curl *), Read, Write
---

## Publishing Overview

**Publishing to social media is irreversible.** This skill reads Approved posts from local JSON, uploads images to dc.missuo.ru image hosting service (following the redirect to get the direct signed CDN URL), publishes to X and Instagram using native MCP tools, then updates post status.

### Required MCP Tools

**Twitter MCP (ALREADY CONFIGURED ✅)**
- **X (Twitter)**: `McpTwitterOuath2McpPostTwitter_tool`

**Instagram MCP (ALREADY CONFIGURED ✅)**
- **Instagram**: `McpInstagramMcpInstagramCreateMediaContainer_tool`, `McpInstagramMcpInstagramPostIgUserMediaPublish_tool`

**Telegram Bot MCP**
- Send publish reports via `McpTelegramBotSendMessage_tool`

**Image Hosting Service**
- **dc.missuo.ru**: Free image hosting for public image URLs

---

## Platform Limits

| Platform | Account | Limit | Notes |
|---|---|---|---|
| X | your X account | Premium | Up to 4 images per post |
| Instagram | your Instagram account | 2,200 chars | Must have at least 1 image; no text-only posts |

---

## Trigger Conditions

1. Cron job (daily at 12:00 London time, auto-triggered)
2. User explicitly requests immediate publishing

## Precondition

Post `status` must be `"Approved"`.

---

## Workflow

### 0. Load Posts from Local JSON

**Read Approved posts from:** `./data/posts.json`
- Filter where `status` = "Approved" and `scheduledAt` ≤ current time

```python
import json
from datetime import datetime

with open('./data/posts.json', 'r') as f:
    data = json.load(f)

approved_posts = [
    post for post in data['posts']
    if post['status'] == 'Approved' and
       (post['scheduledAt'] is None or post['scheduledAt'] <= datetime.now().isoformat())
]
```

---

### 1. Upload Images to dc.missuo.ru Image Hosting

**All images must be uploaded to dc.missuo.ru first** to get direct signed CDN URLs for both X and Instagram.

**CRITICAL:** After uploading, you MUST follow the redirect to get the direct CDN URL. The `/file/...` shortlink URL causes failures on both X (server disconnect) and Instagram (9004 error). Always pass the direct signed CDN URL.

**Process:**
1. Upload via curl multipart form-data → get `/file/` shortlink
2. Follow the redirect → get direct signed CDN URL (e.g. `https://dc.missuo.ru/attachments/.../image.jpg?ex=...&hm=...`)
3. Pass the **direct signed CDN URL** to both X and Instagram

**Python Implementation:**
```python
import subprocess, json

def upload_to_image_host(image_path):
    """
    Upload to dc.missuo.ru and return the DIRECT CDN URL (after following redirect).
    CRITICAL: Always follow the redirect — the /file/ URL itself causes failures on both
    X (server disconnect) and Instagram (9004 error). The direct signed CDN URL works.
    """
    # Step 1: Upload and get the /file/ shortlink
    cmd = ['curl', '-s', '--max-time', '30', '-X', 'POST',
           'https://dc.missuo.ru/upload', '-F', f'image=@{image_path}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout.strip())
    shortlink = data['url']  # e.g. https://dc.missuo.ru/file/147xxxx

    # Step 2: Follow the redirect to get the direct CDN URL
    cmd2 = ['curl', '-s', '--max-time', '10', '-Ls', '-o', '/dev/null',
            '-w', '%{url_effective}', shortlink]
    result2 = subprocess.run(cmd2, capture_output=True, text=True)
    direct_url = result2.stdout.strip()
    # e.g. https://dc.missuo.ru/attachments/.../image.jpg?ex=...&hm=...

    return direct_url

# Usage
image_url = upload_to_image_host('./data/0220c.jpg')
print(f"Direct CDN URL: {image_url}")
```

**Store this for later use:**
- `image_url` → direct signed CDN URL for both X and Instagram

---

### 2. Publish to X (Twitter)

**Flow:** Local image → dc.missuo.ru (follow redirect) → direct signed CDN URL → `McpTwitterOuath2McpPostTwitter_tool`

**Tool:** `McpTwitterOuath2McpPostTwitter_tool`

```
Parameters:
  post: "<caption text>"
  media_url: "<direct signed CDN URL from upload_to_image_host()>"

Returns: { "id": "tweet_id_here", "text": "..." }
```

**Extract tweet_id:**
```python
tweet_id = response["id"]
tweet_url = f"https://x.com/i/status/{tweet_id}"
```

**Complete X Publishing Example:**
```python
# Step 1: Upload image to dc.missuo.ru (follow redirect to get direct URL)
image_url = upload_to_image_host('./data/0220c.jpg')

# Step 2: Post to X with direct CDN URL
# Use McpTwitterOuath2McpPostTwitter_tool
# Parameters: post=caption, media_url=image_url (direct signed CDN URL)

# Step 3: Extract tweet_id and construct URL
tweet_id = response["id"]
tweet_url = f"https://x.com/i/status/{tweet_id}"
```

---

### 3. Publish to Instagram

**Flow:** dc.missuo.ru direct signed CDN URL → `McpInstagramMcpInstagramCreateMediaContainer_tool` → `McpInstagramMcpInstagramPostIgUserMediaPublish_tool`

#### 3.1 Single Image Post

**Step 1: Create Media Container**
```
Tool: McpInstagramMcpInstagramCreateMediaContainer_tool
Parameters:
  ig_user_id: "me"
  image_url: "<direct signed CDN URL from upload_to_image_host()>"
  caption: "<post caption>"
  content_type: "photo"

Returns: { "data": { "id": "creation_id" } }
```

**Extract creation_id:**
```python
creation_id = response["data"]["id"]
```

**Step 2: Publish Post**
```
Tool: McpInstagramMcpInstagramPostIgUserMediaPublish_tool
Parameters:
  ig_user_id: "me"
  creation_id: "<creation_id from step 1>"

Returns: { "data": { "id": "ig_post_id" } }
```

**Extract ig_post_id:**
```python
ig_post_id = response["data"]["id"]
```

**Note:** `ig_post_id` is a numeric ID only, NOT a shortcode permalink. Store `igPermalink` as `null` — permalink is not returned by this tool.

#### 3.2 Multi-Image Carousel (2+ images)

**Step 1: Create Carousel Items**
For each image:
```
Tool: McpInstagramMcpInstagramCreateMediaContainer_tool
Parameters:
  ig_user_id: "me"
  image_url: "<direct signed CDN URL>"
  is_carousel_item: true

Returns: { "data": { "id": "child_id_1" } }
```

Repeat for all images to get `child_id_1`, `child_id_2`, etc.

**Step 2: Create Carousel Container**
```
Tool: McpInstagramMcpInstagramCreateMediaContainer_tool
Parameters:
  ig_user_id: "me"
  media_type: "CAROUSEL"
  children: ["child_id_1", "child_id_2", ...]
  caption: "<post caption>"

Returns: { "data": { "id": "carousel_creation_id" } }
```

**Step 3: Wait for Instagram Processing**
```python
import time
time.sleep(3)  # Instagram needs processing time
```

**Step 4: Publish Carousel**
```
Tool: McpInstagramMcpInstagramPostIgUserMediaPublish_tool
Parameters:
  ig_user_id: "me"
  creation_id: "<carousel_creation_id>"

Returns: { "data": { "id": "ig_post_id" } }
```

**Note**: Instagram does not support text-only posts. Posts without images are published to X only.

---

### 4. Update Post Status in Local JSON

After a successful publish, update `./data/posts.json` **immediately**:

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
        post['status'] = 'Posted'
        post['postedAt'] = datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
        post['tweetId'] = tweet_id
        post['tweetUrl'] = f"https://x.com/i/status/{tweet_id}"
        if ig_post_id:
            post['igPostId'] = ig_post_id
            post['igPermalink'] = None  # Not returned by Instagram MCP tool
        break

# Write back
with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)
```

**Update fields:**
- `status` → `"Posted"`
- `postedAt` → current timestamp (ISO 8601)
- `tweetId` → X post ID
- `tweetUrl` → X post URL
- `igPostId` → Instagram post numeric ID (if published to IG)
- `igPermalink` → `null` (permalink not returned by Instagram MCP tool)

---

## Complete Implementation Flow

### Python Script Structure

```python
import json
import time
import subprocess
from datetime import datetime

def upload_to_image_host(image_path):
    """Upload to dc.missuo.ru and return DIRECT signed CDN URL (after following redirect)."""
    cmd = ['curl', '-s', '--max-time', '30', '-X', 'POST',
           'https://dc.missuo.ru/upload', '-F', f'image=@{image_path}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout.strip())
    shortlink = data['url']

    cmd2 = ['curl', '-s', '--max-time', '10', '-Ls', '-o', '/dev/null',
            '-w', '%{url_effective}', shortlink]
    result2 = subprocess.run(cmd2, capture_output=True, text=True)
    return result2.stdout.strip()

# Step 0: Load Approved posts
with open('./data/posts.json', 'r') as f:
    data = json.load(f)

approved_posts = [
    post for post in data['posts']
    if post['status'] == 'Approved'
]

for post in approved_posts:
    uid = post['uid']
    caption = post['generatedContent']
    media_paths = post.get('media', [])

    # Step 1: Upload images to dc.missuo.ru → follow redirect → direct signed CDN URL
    uploaded_images = []
    for media_path in media_paths:
        image_url = upload_to_image_host(media_path)
        uploaded_images.append(image_url)

    # Step 2: Publish to X
    # Use McpTwitterOuath2McpPostTwitter_tool
    # Parameters: post=caption, media_url=uploaded_images[0] (direct signed CDN URL)
    # tweet_id = response["id"]
    tweet_id = '...'
    tweet_url = f"https://x.com/i/status/{tweet_id}"

    # Step 3: Publish to Instagram
    ig_post_id = None
    if len(uploaded_images) == 1:
        # Single image
        # McpInstagramMcpInstagramCreateMediaContainer_tool(ig_user_id="me", image_url=uploaded_images[0], caption=caption, content_type="photo")
        # creation_id = response["data"]["id"]
        # McpInstagramMcpInstagramPostIgUserMediaPublish_tool(ig_user_id="me", creation_id=creation_id)
        # ig_post_id = response["data"]["id"]
        ig_post_id = '...'
    elif len(uploaded_images) >= 2:
        # Carousel
        child_ids = []
        for img_url in uploaded_images:
            # McpInstagramMcpInstagramCreateMediaContainer_tool(ig_user_id="me", image_url=img_url, is_carousel_item=True)
            # child_ids.append(response["data"]["id"])
            child_ids.append('...')

        # McpInstagramMcpInstagramCreateMediaContainer_tool(ig_user_id="me", media_type='CAROUSEL', children=child_ids, caption=caption)
        time.sleep(3)
        # McpInstagramMcpInstagramPostIgUserMediaPublish_tool(ig_user_id="me", creation_id=carousel_creation_id)
        # ig_post_id = response["data"]["id"]
        ig_post_id = '...'

    # Step 4: Update posts.json IMMEDIATELY
    for p in data['posts']:
        if p['uid'] == uid:
            p['status'] = 'Posted'
            p['postedAt'] = datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
            p['tweetId'] = tweet_id
            p['tweetUrl'] = tweet_url
            if ig_post_id:
                p['igPostId'] = ig_post_id
                p['igPermalink'] = None  # Not returned by Instagram MCP tool
            break

# Save posts.json
with open('./data/posts.json', 'w') as f:
    json.dump(data, f, indent=2)
```

---

## Telegram Publish Report

After each publish run, send a report via Telegram:

**Format:**
```
📮 Scheduled publish complete (12:00 London time)

✅ Successfully published: 1 post
- 0220c:
  🐦 X: https://x.com/i/status/2024872469316682221
  📸 IG: (no permalink — numeric ID only)

✓ No posts pending.
```

**Send via:**
```
Tool: McpTelegramBotSendMessage_tool
Parameters:
  chatId: "<user_chat_id>"
  text: "<publish report>"
```

---

## Technical Notes

### Data Files
- **data/posts.json** — primary data source (read Approved posts, update to Posted)

### Critical Success Pattern
1. Read Approved posts from posts.json
2. Upload image to dc.missuo.ru → **follow redirect** → get direct signed CDN URL
3. Publish to X using `McpTwitterOuath2McpPostTwitter_tool` with `media_url` = direct signed CDN URL
4. Publish to Instagram using `McpInstagramMcpInstagramCreateMediaContainer_tool` (`ig_user_id="me"`) then `McpInstagramMcpInstagramPostIgUserMediaPublish_tool`
5. **IMMEDIATELY update posts.json** with `tweetId`, `tweetUrl`, `igPostId`
6. Verify file write succeeded

### Tool Chain

**Image Hosting (dc.missuo.ru) — MUST follow redirect:**
```bash
# Step 1: Upload → get shortlink
curl -s --max-time 30 -X POST 'https://dc.missuo.ru/upload' -F "image=@/path/to/image.jpg"
# Returns: {"url": "https://dc.missuo.ru/file/..."}

# Step 2: Follow redirect → get direct signed CDN URL
curl -s --max-time 10 -Ls -o /dev/null -w '%{url_effective}' 'https://dc.missuo.ru/file/...'
# Returns: https://dc.missuo.ru/attachments/.../image.jpg?ex=...&hm=...
```

**X (Twitter) - via native Twitter MCP:**
- `McpTwitterOuath2McpPostTwitter_tool` — create post with text and media_url
  - Parameters: `{post: "<text>", media_url: "<direct signed CDN URL>"}`
  - Returns: `{"id": "tweet_id", "text": "..."}`

**Instagram - via native Instagram MCP:**
- `McpInstagramMcpInstagramCreateMediaContainer_tool` — create media container
  - Single: `{ig_user_id: "me", image_url, caption, content_type: "photo"}`
  - Carousel item: `{ig_user_id: "me", image_url, is_carousel_item: true}`
  - Carousel: `{ig_user_id: "me", media_type: "CAROUSEL", children: [id1, id2, ...], caption}`
  - Returns: `{"data": {"id": "creation_id"}}`
- `McpInstagramMcpInstagramPostIgUserMediaPublish_tool` — publish post
  - Parameters: `{ig_user_id: "me", creation_id}`
  - Returns: `{"data": {"id": "ig_post_id"}}` (numeric ID only, no permalink)

---

## Troubleshooting

| Error | Resolution |
|---|---|
| X: Server disconnected | dc.missuo.ru `/file/` shortlink was passed directly — must follow redirect first to get signed CDN URL |
| X: 401 Unauthorized on media | Signed CDN URL with query params is fine for Twitter MCP. If 401 appears, re-authorize the twitter-ouath2-mcp |
| Instagram: 9004 error | dc.missuo.ru `/file/` shortlink was passed directly — must follow redirect to get direct URL |
| Instagram: `creation_id` empty | Check `response["data"]["id"]`, not `response["id"]` |
| Imgur 429 | Imgur rate-limits the MCP server IP — do not use Imgur. Use dc.missuo.ru only |
| catbox.moe disconnect | MCP server cannot reach catbox.moe — use dc.missuo.ru only |
| dc.missuo.ru upload failed | Check network connection; ensure image file exists and is readable; verify file size < 10MB |
| Instagram: missing image | Instagram requires at least 1 image — text-only posts are skipped |
| X/Instagram: auth error | Verify accounts are connected in MCP dashboard |
| Image host timeout | Increase timeout in curl command or retry upload |

---

## Image Hosting Notes

**dc.missuo.ru Service:**
- **Free service** with no authentication required
- **Supported formats**: JPEG, PNG, GIF, WebP
- **File size limit**: Recommended max 10MB
- **Availability**: Third-party service, no uptime guarantee
- **Privacy**: Uploaded images get public URLs - do not upload sensitive content
- **Link persistence**: Long-term availability depends on service provider
- **IMPORTANT**: Always follow the redirect from `/file/` to get the direct signed CDN URL

**Backup Strategy:**
- Keep original images in `data/` folder
- Consider using multiple image hosting services for critical content
- Monitor published posts regularly to ensure images are still accessible

---

*Updated: 2026-02-25 — Fixed image URL redirect (must follow redirect from /file/ shortlink to direct CDN URL); replaced Composio tools with native Twitter and Instagram MCP tools; fixed Instagram response parsing (response["data"]["id"]); igPermalink set to null (not returned by MCP)*
