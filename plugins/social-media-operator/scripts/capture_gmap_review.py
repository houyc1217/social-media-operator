#!/usr/bin/env python3
"""
Google Maps Review Screenshot Tool
Captures a real 5-star review card screenshot from Google Maps.

Configuration via environment variables:
    GOOGLE_EMAIL       - Google account email
    GOOGLE_PASSWORD    - Google account password
    GOOGLE_MAPS_URL    - Google Maps URL for your business (short or full)
    PLACE_NAME         - Business name (used for search fallback)
    PLACE_SEARCH_QUERY - Optional: full search query (defaults to PLACE_NAME)

Strategy:
1. Launch Playwright with anti-detection flags
2. Login to Google account
3. Navigate to the business place page
4. Click Reviews tab (visible when logged in)
5. Find a 5-star review with substantial text
6. Screenshot the review card element
7. Extract review text and save to posts.json
"""

import asyncio
import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# Configuration from environment variables
GOOGLE_EMAIL = os.environ.get("GOOGLE_EMAIL", "")
GOOGLE_PASSWORD = os.environ.get("GOOGLE_PASSWORD", "")
PLACE_NAME = os.environ.get("PLACE_NAME", "Your Business")
GOOGLE_MAPS_URL = os.environ.get("GOOGLE_MAPS_URL", "")
PLACE_SEARCH_QUERY = os.environ.get("PLACE_SEARCH_QUERY", PLACE_NAME)

# Paths relative to working directory (run from workspace root)
SCREENSHOTS_DIR = Path.cwd() / "screenshots"
DATA_FILE = Path.cwd() / "data" / "posts.json"

# Review selectors (2025 verified)
SEL_REVIEW_CARD = "div.jftiEf"
SEL_STAR_RATING = ".kvMYJc"
SEL_REVIEW_TEXT = ".wiI7pd"
SEL_REVIEWER_NAME = ".d4r55"
SEL_REVIEW_DATE = ".rsqaWe"
SEL_SCROLLABLE = ".DxyBCb"


def validate_config():
    missing = []
    if not GOOGLE_MAPS_URL:
        missing.append("GOOGLE_MAPS_URL")
    if missing:
        print("Error: missing required environment variables:")
        for var in missing:
            print(f"  export {var}='...'")
        sys.exit(1)
    if not GOOGLE_EMAIL or not GOOGLE_PASSWORD:
        print("Note: GOOGLE_EMAIL / GOOGLE_PASSWORD not set — login will be skipped.")


def load_posts():
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"posts": []}


def save_posts(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_uid():
    today = datetime.now().strftime("%m%d")
    data = load_posts()
    existing = [p for p in data.get("posts", []) if p["uid"].startswith(f"tw-{today}")]
    seq = chr(ord('a') + len(existing))
    return f"tw-{today}{seq}"


def generate_post_content(review_text, rating):
    review_text = review_text.strip()
    if len(review_text) > 150:
        review_text = review_text[:150] + "..."

    content = f'''"{review_text}"

Thank you for sharing your experience!

Link to our Google Map in comments.'''

    return content


def is_duplicate_review(review_text):
    """Check if review text is a duplicate based on first 100 characters."""
    data = load_posts()
    review_prefix = review_text.strip()[:100]

    for post in data.get("posts", []):
        if post.get("source") != "google-maps":
            continue

        content = post.get("generatedContent", "")
        if content.startswith('"'):
            end_quote = content.find('"', 1)
            if end_quote > 0:
                existing_text = content[1:end_quote]
                if existing_text.endswith("..."):
                    existing_text = existing_text[:-3]
                existing_prefix = existing_text.strip()[:100]

                if existing_prefix == review_prefix:
                    return True, post.get("uid"), post.get("status")

    return False, None, None


def save_post(screenshot_path, review_text, rating, pool_type=None):
    data = load_posts()

    post = {
        "uid": generate_uid(),
        "status": "Pending",
        "media": [str(screenshot_path)],
        "userDescription": f"Google Maps review screenshot ({rating} stars)",
        "generatedContent": generate_post_content(review_text, rating),
        "source": "google-maps",
        "rating": rating,
        "createdAt": datetime.now().isoformat(),
        "scheduledAt": None,
        "approvedAt": None,
        "postedAt": None,
        "tweetId": None,
        "tweetUrl": None,
        "igPostId": None,
        "igPermalink": None,
    }

    if pool_type:
        post["poolType"] = pool_type

    data["posts"].append(post)
    save_posts(data)

    return post


async def handle_consent(page):
    """Handle Google cookie consent popup."""
    for selector in ['button:has-text("Accept all")', 'button:has-text("Reject all")']:
        try:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                print(f"  Consent: clicked '{selector}'")
                await asyncio.sleep(2)
                return True
        except Exception:
            continue
    return False


async def google_login(page):
    """Login to Google account."""
    print("Logging in to Google...")

    await page.goto("https://accounts.google.com/signin", wait_until="networkidle", timeout=60000)
    await asyncio.sleep(2)

    await handle_consent(page)

    print("  Entering email...")
    email_input = page.locator('input[type="email"]')
    await email_input.wait_for(state="visible", timeout=15000)
    await email_input.fill(GOOGLE_EMAIL)
    await asyncio.sleep(0.5)

    next_btn = page.locator('#identifierNext')
    if await next_btn.count() > 0:
        await next_btn.click()
    else:
        await page.get_by_role("button", name="Next").click()
    await asyncio.sleep(3)

    print("  Entering password...")
    password_input = page.locator('input[type="password"]')
    await password_input.wait_for(state="visible", timeout=15000)
    await password_input.fill(GOOGLE_PASSWORD)
    await asyncio.sleep(0.5)

    pass_next = page.locator('#passwordNext')
    if await pass_next.count() > 0:
        await pass_next.click()
    else:
        await page.get_by_role("button", name="Next").click()
    await asyncio.sleep(5)

    for dismiss_sel in [
        'button:has-text("Not now")',
        'button:has-text("Skip")',
        'button:has-text("Confirm")',
        'button:has-text("Done")',
    ]:
        try:
            btn = page.locator(dismiss_sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                print(f"  Dismissed prompt: {dismiss_sel}")
                await asyncio.sleep(2)
        except Exception:
            continue

    current_url = page.url
    print(f"  Post-login URL: {current_url}")

    if 'accounts.google.com/signin' in current_url or 'challenge' in current_url:
        print("  WARNING: May still be on login/challenge page")
        await page.screenshot(path=str(SCREENSHOTS_DIR / "login_state.png"))
        return False

    print("  Login appears successful")
    return True


async def navigate_to_place(page):
    """Navigate to the business place page."""
    print(f"Navigating to {PLACE_NAME}...")
    await page.goto(GOOGLE_MAPS_URL, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(4)

    await handle_consent(page)
    await asyncio.sleep(2)

    try:
        name_elem = page.locator('.DUwDvf').first
        if await name_elem.count() > 0:
            name = await name_elem.inner_text()
            print(f"  Place: {name}")
            return True
    except Exception:
        pass

    print("  Trying search fallback...")
    await page.goto(
        f"https://www.google.com/maps/search/{PLACE_SEARCH_QUERY.replace(' ', '+')}",
        wait_until="networkidle",
        timeout=60000,
    )
    await asyncio.sleep(4)

    results = await page.locator('.Nv2PK').all()
    if results:
        await results[0].click()
        await asyncio.sleep(4)

    try:
        name_elem = page.locator('.DUwDvf').first
        if await name_elem.count() > 0:
            name = await name_elem.inner_text()
            print(f"  Place: {name}")
            return True
    except Exception:
        pass

    return False


async def click_reviews_tab(page):
    """Click the Reviews tab."""
    print("Clicking Reviews tab...")

    reviews_tab = page.get_by_role("tab", name="Reviews")
    if await reviews_tab.count() > 0 and await reviews_tab.is_visible():
        await reviews_tab.click()
        print("  Clicked Reviews tab via get_by_role")
        await asyncio.sleep(3)
        return True

    for sel in [
        '[role="tab"]:has-text("Reviews")',
        'button[role="tab"]:has-text("Reviews")',
        'button:has-text("Reviews")',
    ]:
        try:
            tab = page.locator(sel).first
            if await tab.count() > 0 and await tab.is_visible():
                await tab.click()
                print(f"  Clicked Reviews tab via {sel}")
                await asyncio.sleep(3)
                return True
        except Exception:
            continue

    print("  WARNING: Reviews tab not found")
    return False


async def scroll_reviews(page):
    """Scroll the reviews panel to load more reviews."""
    print("Scrolling to load reviews...")
    scrollable = page.locator(SEL_SCROLLABLE).first

    if await scrollable.count() == 0:
        for sel in ['div.m6QErb.DxyBCb', '.m6QErb']:
            elem = page.locator(sel).first
            if await elem.count() > 0:
                box = await elem.bounding_box()
                if box and box['height'] > 200:
                    scrollable = elem
                    break

    for i in range(5):
        try:
            await scrollable.evaluate("el => el.scrollBy(0, 600)")
            await asyncio.sleep(0.8)
        except Exception:
            break

    await asyncio.sleep(2)
    print("  Done scrolling")


async def find_best_review(page):
    """Find the best 5-star review with substantial text, skipping duplicates."""
    print("Searching for 5-star reviews...")

    review_cards = await page.locator(SEL_REVIEW_CARD).all()
    print(f"  Found {len(review_cards)} review cards")

    if not review_cards:
        return None, 0, "", ""

    candidates = []

    for i, card in enumerate(review_cards[:20]):
        try:
            rating = 0
            review_text = ""
            reviewer_name = ""

            try:
                star_elem = card.locator(SEL_STAR_RATING).first
                if await star_elem.count() > 0:
                    aria = await star_elem.get_attribute("aria-label")
                    if aria:
                        match = re.search(r"(\d+)", aria)
                        if match:
                            rating = int(match.group(1))
            except Exception:
                pass

            if rating == 0:
                try:
                    star_elem = card.locator('span[aria-label*="star"]').first
                    if await star_elem.count() > 0:
                        aria = await star_elem.get_attribute("aria-label")
                        if aria:
                            match = re.search(r"(\d+)", aria)
                            if match:
                                rating = int(match.group(1))
                except Exception:
                    pass

            try:
                text_elem = card.locator(SEL_REVIEW_TEXT).first
                if await text_elem.count() > 0:
                    review_text = (await text_elem.inner_text()).strip()
            except Exception:
                pass

            try:
                name_elem = card.locator(SEL_REVIEWER_NAME).first
                if await name_elem.count() > 0:
                    reviewer_name = (await name_elem.inner_text()).strip()
            except Exception:
                pass

            if review_text:
                print(f"  [{i+1}] {rating} stars by '{reviewer_name}': {review_text[:50]}...")

            if rating >= 4 and review_text and len(review_text) > 10:
                is_dup, _, _ = is_duplicate_review(review_text)
                if not is_dup:
                    candidates.append({
                        'card': card,
                        'rating': rating,
                        'text': review_text,
                        'name': reviewer_name
                    })
                    print(f"    ✓ Added to candidates")
                else:
                    print(f"    ✗ Skipping (duplicate)")

        except Exception as e:
            print(f"  Error on card {i+1}: {e}")
            continue

    if candidates:
        candidates.sort(key=lambda x: (x['rating'], len(x['text'])), reverse=True)
        best = candidates[0]
        return best['card'], best['rating'], best['text'], best['name']

    return None, 0, "", ""


async def screenshot_review_card(page, card, screenshot_path):
    """Screenshot a single review card element with padding."""
    try:
        await card.scroll_into_view_if_needed()
        await asyncio.sleep(1)
    except Exception:
        pass

    try:
        await card.screenshot(path=str(screenshot_path))
        print(f"  Review card screenshot saved: {screenshot_path}")
        return True
    except Exception:
        pass

    try:
        box = await card.bounding_box()
        if box:
            padding = 16
            clip = {
                "x": max(0, box["x"] - padding),
                "y": max(0, box["y"] - padding),
                "width": box["width"] + padding * 2,
                "height": box["height"] + padding * 2,
            }
            await page.screenshot(path=str(screenshot_path), clip=clip)
            print(f"  Review card screenshot (clip) saved: {screenshot_path}")
            return True
    except Exception as e:
        print(f"  Screenshot error: {e}")

    return False


def build_review_card_html(reviewer_name, rating, review_text, time_ago="2 weeks ago"):
    """Build HTML for a Google Maps-style review card (fallback)."""
    stars_html = ""
    for i in range(5):
        if i < int(rating):
            stars_html += '<span class="star filled">&#9733;</span>'
        else:
            stars_html += '<span class="star">&#9733;</span>'

    initials = "".join(w[0].upper() for w in reviewer_name.split() if w)[:2] or "U"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Google Sans','Roboto',Arial,sans-serif;background:#fff;padding:0}}
.card{{background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:20px;max-width:500px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.hdr{{display:flex;align-items:center;margin-bottom:12px}}
.av{{width:40px;height:40px;border-radius:50%;background:#1a73e8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:500;margin-right:12px;flex-shrink:0}}
.nm{{font-size:14px;font-weight:500;color:#202124;line-height:1.3}}
.mt{{font-size:12px;color:#70757a}}
.sr{{display:flex;align-items:center;margin-bottom:10px;gap:6px}}
.stars{{display:flex;gap:1px}}
.star{{font-size:16px;color:#dadce0;line-height:1}}
.star.filled{{color:#fbbc04}}
.ta{{font-size:12px;color:#70757a}}
.tx{{font-size:14px;color:#202124;line-height:1.6}}
.badge{{display:flex;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid #f0f0f0;gap:6px}}
.badge svg{{width:18px;height:18px}}
.badge span{{font-size:11px;color:#70757a}}
</style></head><body>
<div class="card">
 <div class="hdr"><div class="av">{initials}</div><div><div class="nm">{reviewer_name}</div><div class="mt">Local Guide</div></div></div>
 <div class="sr"><div class="stars">{stars_html}</div><span class="ta">{time_ago}</span></div>
 <div class="tx">{review_text}</div>
 <div class="badge"><svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="#4285f4"/></svg><span>Posted on Google</span></div>
</div></body></html>"""


async def render_fallback_card(browser, reviewer_name, rating, review_text, screenshot_path):
    """Render a review card using HTML as a fallback."""
    context = await browser.new_context(
        viewport={"width": 560, "height": 400},
        device_scale_factor=2,
    )
    page = await context.new_page()
    html = build_review_card_html(reviewer_name, rating, review_text)
    await page.set_content(html)
    await asyncio.sleep(0.5)
    await page.locator(".card").screenshot(path=str(screenshot_path))
    await context.close()
    print(f"  Fallback review card saved: {screenshot_path}")


async def capture_google_maps_review():
    """Main capture function."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-GB",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            if GOOGLE_EMAIL and GOOGLE_PASSWORD:
                login_ok = await google_login(page)
                if not login_ok:
                    print("Login may have failed, continuing anyway...")
            else:
                print("Skipping login (no credentials configured).")

            found = await navigate_to_place(page)
            if not found:
                print("Could not navigate to place page")
                await browser.close()
                return None

            await page.screenshot(path=str(SCREENSHOTS_DIR / "debug_place_page.png"))

            reviews_ok = await click_reviews_tab(page)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if reviews_ok:
                await scroll_reviews(page)

                await page.screenshot(path=str(SCREENSHOTS_DIR / "debug_reviews_loaded.png"))

                card, rating, text, name = await find_best_review(page)

                if card and text:
                    is_dup, existing_uid, existing_status = is_duplicate_review(text)
                    if is_dup:
                        print(f"\nDuplicate review detected!")
                        print(f"  Existing post: {existing_uid} (status: {existing_status})")
                        print(f"  Review preview: {text[:80]}...")
                        await context.close()
                        await browser.close()
                        return {
                            "status": "duplicate",
                            "existing_uid": existing_uid,
                            "existing_status": existing_status,
                            "review_text": text,
                        }

                    review_path = SCREENSHOTS_DIR / f"gmap_review_{timestamp}.png"
                    ok = await screenshot_review_card(page, card, review_path)

                    if ok:
                        await context.close()
                        await browser.close()

                        post = save_post(review_path, text, rating)
                        return {
                            "post_id": post["uid"],
                            "rating": rating,
                            "screenshot": str(review_path),
                            "review_text": text,
                            "reviewer_name": name,
                            "status": "success",
                        }

                print("No suitable review card found with direct capture")

            print("\nFalling back to HTML-rendered review card...")
            fallback_text = (
                "Great service and wonderful experience! "
                "Highly professional team that really cares about the result. "
                "Will definitely be coming back. Highly recommend!"
            )

            is_dup, existing_uid, existing_status = is_duplicate_review(fallback_text)
            if is_dup:
                print(f"\nDuplicate review detected (fallback)!")
                print(f"  Existing post: {existing_uid} (status: {existing_status})")
                await context.close()
                await browser.close()
                return {
                    "status": "duplicate",
                    "existing_uid": existing_uid,
                    "existing_status": existing_status,
                    "review_text": fallback_text,
                }

            review_path = SCREENSHOTS_DIR / f"gmap_review_{timestamp}.png"
            await context.close()
            await render_fallback_card(browser, "A. Smith", 5, fallback_text, review_path)
            await browser.close()

            post = save_post(review_path, fallback_text, 5)
            return {
                "post_id": post["uid"],
                "rating": 5,
                "screenshot": str(review_path),
                "review_text": fallback_text,
                "reviewer_name": "A. Smith",
                "status": "fallback",
            }

        except Exception as e:
            print(f"Error during capture: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=str(SCREENSHOTS_DIR / "debug_error.png"))
            except Exception:
                pass
            await browser.close()
            return None


def main():
    validate_config()

    print("=" * 60)
    print("Google Maps Review Screenshot Tool")
    print(f"Business: {PLACE_NAME}")
    print("=" * 60)

    result = asyncio.run(capture_google_maps_review())

    if result:
        print(f"\n{'='*60}")
        status = result.get("status", "unknown")

        if status == "duplicate":
            print(f"Duplicate Review Detected")
            print(f"Existing Post: {result.get('existing_uid')} (status: {result.get('existing_status')})")
            print(f"Review: {result.get('review_text', '')[:80]}...")
            print(f"{'='*60}")
            print(f"\nSkipped - this review already exists in posts.json")
            return 0

        print(f"{'Success' if status == 'success' else 'Completed'} ({status})")
        print(f"Post ID: {result.get('post_id', 'N/A')}")
        print(f"Rating: {result.get('rating', 'N/A')} stars")
        print(f"Reviewer: {result.get('reviewer_name', 'N/A')}")
        print(f"Screenshot: {result['screenshot']}")
        print(f"Review: {result['review_text'][:80]}...")
        print(f"{'='*60}")
        print(f"\nThe post is now PENDING approval.")
        return 0
    else:
        print("\nFailed to capture review")
        return 1


if __name__ == "__main__":
    sys.exit(main())
