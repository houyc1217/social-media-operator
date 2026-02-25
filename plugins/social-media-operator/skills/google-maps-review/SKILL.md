---
name: google-maps-review
description: Automatically captures real Google Maps review screenshots using Playwright, generates post content, and saves to posts.json for approval and publishing.
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(python3 *), Bash(find *), Read, Write
---

## Trigger Conditions

Invoke when the user says:
- "get a Google Maps review" / "capture review screenshot"
- "create a review post" / "Google Maps review"
- "5-star review" / "screenshot review"
- "截图好评" / "谷歌地图评论" / "五星评论"

## Prerequisites

Configure these before running (via environment variables or `config.json` in the workspace root):

| Variable | Description |
|---|---|
| `GOOGLE_EMAIL` | Google account email for Maps login |
| `GOOGLE_PASSWORD` | Google account password |
| `GOOGLE_MAPS_URL` | Google Maps **Share link** for your business (use Share → Copy link, not the browser URL) |
| `PLACE_NAME` | Your business name (used in search fallback) |

## Workflow

### Step 0: Configuration Check (ALWAYS run first)

**Before doing anything else**, check whether the required configuration exists.

#### How to check

Check shell environment with:

```bash
echo "URL=${GOOGLE_MAPS_URL} NAME=${PLACE_NAME}"
```

Also check if `config.json` exists in the workspace root and has a `googleMaps` section.

#### Required: GOOGLE_MAPS_URL and PLACE_NAME

If either is missing → STOP and ask the user:

```
To capture Google Maps reviews, I need two things:

1. Google Maps URL for your business
   ⚠️ Please use the Share link, not the browser address bar URL:
      - Open your business page on Google Maps
      - Click "Share" → "Copy link"
      - Paste the short link here (e.g. https://maps.app.goo.gl/xxxxx)
   (The browser URL is very long and may not work reliably with automation)
   →

2. Your business name
   (used as fallback search if the URL doesn't resolve directly)
   →
```

Wait for the user's reply, then save to `config.json` in the workspace root (create if it doesn't exist):

```json
{
  "googleMaps": {
    "url": "<url>",
    "placeName": "<business name>"
  }
}
```

Confirm: `Configuration saved to config.json. Starting capture now...`

#### Optional: Google credentials

Google credentials (`GOOGLE_EMAIL` / `GOOGLE_PASSWORD`) are **not required**. The script works without them:
- **With credentials** → logs in to Google, attempts real review screenshot from Maps
- **Without credentials** → skips login, tries Maps anyway; if Reviews tab is hidden, falls back to HTML-rendered review card

Do **not** ask the user for credentials unless they specifically want real screenshots and the fallback is not acceptable to them.

#### If GOOGLE_MAPS_URL and PLACE_NAME are already present → skip asking, proceed to Step 1

---

### Step 1: Run the capture script

Find and run the capture script from your workspace root:

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "capture_gmap_review.py" -path "*/social-media-operator/*" 2>/dev/null | head -1)
GOOGLE_EMAIL="<your-email>" GOOGLE_PASSWORD="<your-password>" \
GOOGLE_MAPS_URL="<your-maps-url>" PLACE_NAME="<your-business-name>" \
python3 "$SCRIPT"
```

If credentials are already exported in the environment:

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "capture_gmap_review.py" -path "*/social-media-operator/*" 2>/dev/null | head -1)
python3 "$SCRIPT"
```

The script automatically:
1. Launches Playwright headless Chromium (anti-detection configured)
2. Logs in to Google account
3. Navigates to the business Maps page
4. Clicks Reviews tab (only visible when logged in)
5. Scrolls to load more reviews
6. Selects the best 5-star review (longest text, skips duplicates)
7. Screenshots the review card element
8. Saves to `./data/posts.json` with status `"Pending"`

**Fallback**: If login or screenshot fails, renders an HTML-based review card template instead.

### Step 2: Read script output

The script returns:
- `post_id` — post UID (e.g., `0225a`)
- `rating` — star rating
- `screenshot` — screenshot file path
- `review_text` — actual review text
- `reviewer_name` — reviewer's name
- `status` — `"success"` (real screenshot) or `"fallback"` (HTML template)

### Step 3: Generate post caption

Based on the extracted review text:

```
"{review excerpt, max 150 characters}"

Thank you for sharing your experience!

Link to our Google Map in comments.
```

**Caption rules:**
- English only
- No hashtags (#)
- No em dashes (—), "not...but...", excessive parallelism
- Emoji: max 2 for >150 chars, max 1 for 75–150 chars, none for <75 chars

### Step 4: Notify user for approval

```
Review card captured!

Reviewer: {reviewer_name}
Rating: ⭐⭐⭐⭐⭐ ({rating}/5)
Preview: "{review_text[:60]}..."
Source: Google Maps real screenshot

Post ID: {uid}
Status: Pending

Reply "approve" to schedule for publishing.
```

### Step 5: After approval, schedule

1. `status` → `"Approved"`
2. `approvedAt` → current timestamp
3. `scheduledAt` → **tomorrow 12:00 London time** (Europe/London)

### Step 6: Publishing

Handled by **publish-workflow** — publishes to X and Instagram at the scheduled time.

## CSS Selectors (2025 verified)

| Element | Selector |
|---|---|
| Review card | `div.jftiEf` |
| Star rating | `.kvMYJc` (aria-label) |
| Review text | `.wiI7pd` |
| Reviewer name | `.d4r55` |
| Review date | `.rsqaWe` |
| Scroll container | `.DxyBCb` |

## Data Files

- **Screenshots**: `./screenshots/`
- **Post data**: `./data/posts.json`

## Error Handling

| Scenario | Resolution |
|---|---|
| Google login blocked by 2FA | Tries "Try another way"; falls back to HTML template |
| Reviews tab not visible | Login may have failed; falls back to HTML template |
| No 5-star reviews | Degrades to 4-star reviews |
| Screenshot fails | Retries once using bounding box clip |
| Duplicate review detected | Reports existing post UID, skips saving |
| `GOOGLE_MAPS_URL` not set | Script exits with configuration instructions |
| Script not found | Run `find ~/.claude/plugins/cache -name "capture_gmap_review.py"` to locate |
