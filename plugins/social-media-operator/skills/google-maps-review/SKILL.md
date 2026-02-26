---
name: google-maps-review
description: Automatically captures real Google Maps review screenshots using Playwright, generates post content, and saves to posts.json for approval and publishing.
user-invocable: true
argument-hint: "[optional: Google Maps share URL]"
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

Google credentials (`GOOGLE_EMAIL` / `GOOGLE_PASSWORD`) are **not required**. Google Maps reviews are publicly visible without login. The script works fine without them:
- **With credentials** → logs in to Google before navigating (may help in regions with strict consent flows)
- **Without credentials** → skips login entirely, navigates directly to Maps, captures real reviews

Do **not** ask the user for credentials. The script should capture real reviews without them.

#### If GOOGLE_MAPS_URL and PLACE_NAME are already present → skip asking, proceed to Step 1

---

### Step 0.5: Playwright Preflight — Auto-Install (ALWAYS run before Step 1)

Run all three checks and fixes automatically, without asking the user. Goal: get
Playwright + Chromium fully working so real screenshots are possible.

#### Check 1 — playwright package

```bash
python3 -c "import playwright; print('OK')" 2>&1
```

If output is not `OK` → install immediately, no prompt:

```bash
pip install playwright
```

Then continue to Check 2.

#### Check 2 — Chromium binary

```bash
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    exe = p.chromium.executable_path()
    import os; print('OK' if os.path.exists(exe) else 'MISSING')
" 2>&1
```

If output is not `OK` → install immediately:

```bash
playwright install chromium
```

Then continue to Check 3.

#### Check 3 — Chromium can actually launch (catches missing system libraries)

```bash
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    b.close()
    print('OK')
" 2>&1
```

If output contains `cannot open shared object`, `exitCode=127`, or `shared libraries` → fix immediately:

```bash
playwright install-deps chromium
```

Then re-run Check 3 once to confirm it passes.

#### All three checks pass → proceed to Step 1.

Only if Check 3 still fails after the fix → inform the user briefly ("Chromium could not be
set up — proceeding with simplified card") and continue to Step 1. The script will use the
Pillow renderer automatically.

---

### Step 1: Run the capture script

Find and run the capture script from your workspace root:

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "capture_gmap_review.py" -path "*/social-media-operator/*" 2>/dev/null | head -1)
GOOGLE_MAPS_URL="<your-maps-url>" PLACE_NAME="<your-business-name>" \
python3 "$SCRIPT"
```

If `GOOGLE_MAPS_URL` and `PLACE_NAME` are already exported in the environment:

```bash
SCRIPT=$(find ~/.claude/plugins/cache -name "capture_gmap_review.py" -path "*/social-media-operator/*" 2>/dev/null | head -1)
python3 "$SCRIPT"
```

The script automatically:
1. Launches Playwright headless Chromium (anti-detection configured)
2. Skips Google login (credentials not required — reviews are publicly visible)
3. Navigates to the business Maps page
4. Waits for Google Maps SPA to render, then clicks the Reviews tab
5. Scrolls to load more reviews
6. Selects the best 5-star review (longest text, skips duplicates)
7. Screenshots the review card element
8. Saves to `./data/posts.json` with status `"Pending"`

**Fallback**: If the browser cannot launch (missing system libraries), the script automatically
uses a Pillow-based card renderer — no browser required. You should only reach this path if
you explicitly chose "skip" during the preflight check above.

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

Handled by the **publish** skill — publishes to X and Instagram at the scheduled time.

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
| Reviews tab not visible | Page may not have rendered; script falls back to HTML template |
| No 5-star reviews | Degrades to 4-star reviews |
| Screenshot fails | Retries once using bounding box clip |
| Duplicate review detected | Reports existing post UID, skips saving |
| `GOOGLE_MAPS_URL` not set | Script exits with configuration instructions |
| Script not found | Run `find ~/.claude/plugins/cache -name "capture_gmap_review.py"` to locate |
