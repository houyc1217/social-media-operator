---
name: publish-workflow
description: Post publishing workflow - publishes Approved posts to X and Instagram using dc.missuo.ru image hosting, then sends a Telegram notification with the publish report
user-invocable: false
allowed-tools: Bash(python3 *, curl *), Read, Write
---

## Publishing Overview

**Publishing to social media is irreversible.** This workflow reads Approved posts from local JSON, uploads images to dc.missuo.ru image hosting service, publishes to X and Instagram using Composio MCP tools, then updates post status.

### Required MCP Tools

**Composio MCP (ALREADY CONFIGURED ✅)**
- **X (Twitter)**: `TWITTER_UPLOAD_MEDIA`, `TWITTER_CREATION_OF_A_POST`
- **Instagram**: `INSTAGRAM_CREATE_MEDIA_CONTAINER`, `INSTAGRAM_CREATE_POST`

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

**All images must be uploaded to dc.missuo.ru first** to get public URLs for both X and Instagram.

**Process:**
1. Read local image file
2. Upload via curl multipart form-data
3. Get public image URL

**Bash Implementation:**
```bash
# Upload image to dc.missuo.ru
response=$(curl -X POST 'https://dc.missuo.ru/upload' \
  -F "image=@/path/to/image.jpg" 2>/dev/null)

# Extract URL from JSON response
image_url=$(echo "$response" | grep -oP '(?<="url":")[^"]+')

echo "$image_url"
# Output: https://dc.missuo.ru/file/1474441169546117323
```

**Expected Response:**
```json
{
  "url": "https://dc.missuo.ru/file/1474441169546117323"
}
```

**Python Implementation:**
```python
import subprocess
import json
import re

def upload_to_image_host(image_path):
    """Upload image to dc.missuo.ru and return public URL"""
    cmd = [
        'curl', '-X', 'POST', 'https://dc.missuo.ru/upload',
        '-F', f'image=@{image_path}'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.DEVNULL)
    response = result.stdout.strip()

    # Parse JSON response
    try:
        data = json.loads(response)
        return data.get('url')
    except json.JSONDecodeError:
        # Fallback: use regex to extract URL
        match = re.search(r'"url":"([^"]+)"', response)
        if match:
            return match.group(1)

    raise Exception(f"Failed to upload image: {image_path}")

# Usage
image_url = upload_to_image_host('./data/0220c.jpg')
print(f"Image URL: {image_url}")
```

**Store this for later use:**
- `image_url` → public URL for both X and Instagram

---

### 2. Publish to X (Twitter)

**Flow:** Local image → dc.missuo.ru → Download to temp → TWITTER_UPLOAD_MEDIA → TWITTER_CREATION_OF_A_POST

**Steps:**

#### 2.1 Download Image from Image Host (for X compatibility)

Since X's `TWITTER_UPLOAD_MEDIA` requires local file or s3key, we need to download the image first:

```python
import requests

def download_image(image_url, local_path):
    """Download image from URL to local path"""
    response = requests.get(image_url)
    with open(local_path, 'wb') as f:
        f.write(response.content)
    return local_path

# Usage
local_temp_path = '/tmp/twitter_upload.jpg'
download_image(image_url, local_temp_path)
```

**Alternative:** Use original local image directly for X upload (skip download step if original file still exists)

#### 2.2 Upload Media to X
```
Tool: McpTwitterOuath2McpPostTwitter_tool
Parameters:
  post: "<caption text>"
  media_url: "<image_url from dc.missuo.ru>"

Response: { tweet_id: "123456789..." }
```

**Note:** The Twitter MCP tool accepts `media_url` directly, so you can pass the dc.missuo.ru URL without downloading.

#### 2.3 Construct X URL
```python
tweet_url = f"https://x.com/i/status/{tweet_id}"
```

**Complete X Publishing Example:**
```python
# Step 1: Upload image to dc.missuo.ru
image_url = upload_to_image_host('./data/0220c.jpg')

# Step 2: Post to X with media URL
# Use McpTwitterOuath2McpPostTwitter_tool
# Parameters: post=caption, media_url=image_url

# Step 3: Extract tweet_id and construct URL
tweet_url = f"https://x.com/i/status/{tweet_id}"
```

---

### 3. Publish to Instagram

**Flow:** Image → dc.missuo.ru public URL → INSTAGRAM_CREATE_MEDIA_CONTAINER → INSTAGRAM_CREATE_POST

Instagram requires a publicly accessible image URL. The URL returned by dc.missuo.ru (`https://dc.missuo.ru/file/...`) can be used directly.

#### 3.1 Single Image Post

**Step 1: Create Media Container**
```
Tool: INSTAGRAM_CREATE_MEDIA_CONTAINER
Parameters:
  ig_user_id: "<YOUR_IG_USER_ID>"
  image_url: "<public_url from dc.missuo.ru>"
  caption: "<post caption>"

Response: { data: { id: "creation_id_123" } }
```

**Step 2: Publish Post**
```
Tool: INSTAGRAM_CREATE_POST
Parameters:
  ig_user_id: "<YOUR_IG_USER_ID>"
  creation_id: "<creation_id from step 1>"

Response: { data: { id: "ig_post_id_456" } }
```

#### 3.2 Multi-Image Carousel (2+ images)

**Step 1: Create Carousel Items**
For each image:
```
Tool: INSTAGRAM_CREATE_MEDIA_CONTAINER
Parameters:
  ig_user_id: "<YOUR_IG_USER_ID>"
  image_url: "<public_url from dc.missuo.ru>"
  is_carousel_item: true

Response: { data: { id: "child_id_1" } }
```

Repeat for all images to get `child_id_1`, `child_id_2`, etc.

**Step 2: Create Carousel Container**
```
Tool: INSTAGRAM_CREATE_MEDIA_CONTAINER
Parameters:
  ig_user_id: "<YOUR_IG_USER_ID>"
  media_type: "CAROUSEL"
  children: ["child_id_1", "child_id_2", ...]
  caption: "<post caption>"

Response: { data: { id: "carousel_creation_id" } }
```

**Step 3: Wait for Instagram Processing**
```python
import time
time.sleep(3)  # Instagram needs processing time
```

**Step 4: Publish Carousel**
```
Tool: INSTAGRAM_CREATE_POST
Parameters:
  ig_user_id: "<YOUR_IG_USER_ID>"
  creation_id: "<carousel_creation_id>"

Response: { data: { id: "ig_post_id_789" } }
```

**Note**: Instagram does not support text-only posts. Posts without images are published to X only.

---

### 4. Update Post Status in Local JSON

After a successful publish, update `./data/posts.json`:

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
            post['igPermalink'] = f"https://www.instagram.com/p/{ig_shortcode}/"
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
- `igPostId` → Instagram post ID (if published to IG)
- `igPermalink` → Instagram post URL (if published to IG)

---

## Complete Implementation Flow

### Python Script Structure

```python
import json
import base64
import time
from datetime import datetime

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

    # Step 1: Upload images to dc.missuo.ru
    uploaded_images = []
    for media_path in media_paths:
            # Upload to dc.missuo.ru
        image_url = upload_to_image_host(abs_path)
        uploaded_images.append(image_url)

    # Step 2: Publish to X
    # Use McpTwitterOuath2McpPostTwitter_tool
    # Parameters: post=caption, media_url=uploaded_images[0]
    tweet_id = '...'
    tweet_url = f"https://x.com/i/status/{tweet_id}"

    # Step 3: Publish to Instagram
    if len(uploaded_images) == 1:
        # Single image
        # INSTAGRAM_CREATE_MEDIA_CONTAINER(image_url=uploaded_images[0]) → creation_id
        # INSTAGRAM_CREATE_POST → ig_post_id
        ig_post_id = '...'
    elif len(uploaded_images) >= 2:
        # Carousel
        child_ids = []
        for img_url in uploaded_images:
            # INSTAGRAM_CREATE_MEDIA_CONTAINER(image_url=img_url, is_carousel_item=True)
            child_ids.append('...')

        # INSTAGRAM_CREATE_MEDIA_CONTAINER(media_type='CAROUSEL', children=child_ids)
        time.sleep(3)
        # INSTAGRAM_CREATE_POST
        ig_post_id = '...'

    # Step 4: Update posts.json
    for p in data['posts']:
        if p['uid'] == uid:
            p['status'] = 'Posted'
            p['postedAt'] = datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
            p['tweetId'] = tweet_id
            p['tweetUrl'] = tweet_url
            if ig_post_id:
                p['igPostId'] = ig_post_id
                p['igPermalink'] = '...'
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
  📸 IG: https://www.instagram.com/p/xxxxx/

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
2. **Upload all images to dc.missuo.ru first** to get public URLs
3. Publish to X using `McpTwitterOuath2McpPostTwitter_tool` with media_url
4. Publish to Instagram using image URLs via `INSTAGRAM_CREATE_MEDIA_CONTAINER`
5. **IMMEDIATELY update posts.json** with results (status="Posted", tweetId, tweetUrl, etc.)
6. Verify file write succeeded

### Tool Chain

**Image Hosting (dc.missuo.ru):**
```bash
curl -X POST 'https://dc.missuo.ru/upload' -F "image=@/path/to/image.jpg"
# Returns: {"url": "https://dc.missuo.ru/file/..."}
```

**X (Twitter) - via MCP:**
- `McpTwitterOuath2McpPostTwitter_tool` — create post with text and media_url
  - Parameters: `{post: "<text>", media_url: "<image_url>"}`
  - Returns: `{tweet_id: "..."}`

**Instagram - via MCP:**
- `INSTAGRAM_CREATE_MEDIA_CONTAINER` — create media container
  - Single: `{image_url, caption}`
  - Carousel item: `{image_url, is_carousel_item: true}`
  - Carousel: `{media_type: 'CAROUSEL', children: [id1, id2, ...], caption}`
- `INSTAGRAM_CREATE_POST` — publish post `{ig_user_id, creation_id}`

---

## Troubleshooting

| Error | Resolution |
|---|---|
| dc.missuo.ru upload failed | Check network connection; ensure image file exists and is readable; verify file size < 10MB |
| Instagram: image URL not accessible | Ensure image was uploaded to dc.missuo.ru and the URL is valid and publicly accessible |
| Instagram: missing image | Instagram requires at least 1 image — text-only posts are skipped |
| Instagram: `creation_id` is empty | Check `INSTAGRAM_CREATE_MEDIA_CONTAINER` response — `creation_id` is at `response.data.id` |
| X: media upload failed | Verify image URL is valid; ensure dc.missuo.ru URL is accessible |
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

**Backup Strategy:**
- Keep original images in `data/` folder
- Consider using multiple image hosting services for critical content
- Monitor published posts regularly to ensure images are still accessible

---

*Updated: 2026-02-20 — Migrated from Rube S3 to dc.missuo.ru image hosting for simplified workflow*
