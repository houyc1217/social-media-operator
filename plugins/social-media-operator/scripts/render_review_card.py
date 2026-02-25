#!/usr/bin/env python3
"""
Render a Google Maps-style review card as a screenshot image.

Uses the self-populating HTML template with URL query parameters.
Can also be used as an importable module.

Usage:
    python3 render_review_card.py \
        --name "Sarah M." --rating 5 \
        --text "Absolutely wonderful service!" \
        --date "1 week ago" --store "Your Business Name"
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "review_card_template.html"
DEFAULT_OUTPUT_DIR = Path.cwd() / "screenshots"


def build_template_url(
    name: str,
    rating: int,
    text: str,
    date: str,
    store: str,
    badge: str = "",
) -> str:
    """Build a file:// URL with query params for the review card template."""
    params = {
        "name": name,
        "rating": str(rating),
        "text": text,
        "date": date,
        "store": store,
    }
    if badge:
        params["badge"] = badge
    return "file://" + str(TEMPLATE_PATH) + "?" + urlencode(params)


def render_card(
    name: str,
    rating: int,
    text: str,
    date: str,
    store: str,
    badge: str = "",
    output_dir: Optional[str] = None,
) -> str:
    """Render the review card and screenshot it with Playwright.

    Returns the path to the saved screenshot.
    """
    if not TEMPLATE_PATH.exists():
        print("Error: template not found at %s" % TEMPLATE_PATH, file=sys.stderr)
        sys.exit(1)

    url = build_template_url(name, rating, text, date, store, badge)

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "review_card_%s.png" % timestamp
    output_path = out_dir / filename

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 700, "height": 600})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(300)

        card = page.query_selector("#review-card")
        if card:
            card.screenshot(path=str(output_path))
        else:
            page.screenshot(path=str(output_path), full_page=True)

        browser.close()

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Render a Google Maps-style review card image."
    )
    parser.add_argument("--name", required=True, help="Reviewer name")
    parser.add_argument(
        "--rating", required=True, type=int, choices=range(1, 6), help="Star rating 1-5"
    )
    parser.add_argument("--text", required=True, help="Review text")
    parser.add_argument("--date", required=True, help='Review date (e.g. "2 weeks ago")')
    parser.add_argument("--store", required=True, help="Store / place name")
    parser.add_argument("--badge", default="", help='Optional badge (e.g. "Local Guide")')
    parser.add_argument("--output-dir", default=None, help="Output directory for screenshot")

    args = parser.parse_args()

    output = render_card(
        name=args.name,
        rating=args.rating,
        text=args.text,
        date=args.date,
        store=args.store,
        badge=args.badge,
        output_dir=args.output_dir,
    )
    print(output)


if __name__ == "__main__":
    main()
