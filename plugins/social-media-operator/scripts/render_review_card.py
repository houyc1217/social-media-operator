#!/usr/bin/env python3
"""
Render a Google Maps-style review card as a screenshot image.

Two rendering backends are supported, tried in order:
  1. Playwright (Chromium) — renders the full HTML template; highest fidelity.
  2. Pillow (pure Python)  — no browser or system display required; used when
     Playwright/Chromium is unavailable (e.g. minimal Docker containers).

Can be used as a script or as an importable module:
    render_card(...)          — auto-selects backend
    render_card_pillow(...)   — Pillow backend only (no browser dependency)

Usage:
    python3 render_review_card.py \
        --name "Sarah M." --rating 5 \
        --text "Absolutely wonderful service!" \
        --date "1 week ago" --store "Your Business Name"
"""

import argparse
import math
import sys
import textwrap
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


def render_card_pillow(
    name: str,
    rating: int,
    text: str,
    date: str,
    store: str,
    badge: str = "",
    output_path: Optional[str] = None,
) -> str:
    """Render a Google Maps-style review card using Pillow only.

    No browser, no system display libraries, and no internet access required.
    Produces a clean 580 × auto-height PNG rendered at 2× then downscaled for
    natural anti-aliasing.

    Returns the path to the saved PNG file.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError(
            "Pillow is required for browser-free rendering. "
            "Install it with: pip install Pillow"
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    W        = 580   # card width (px, 1×)
    PAD_H    = 32    # horizontal padding
    PAD_TOP  = 28    # top padding
    PAD_BOT  = 24    # bottom padding
    INNER_W  = W - PAD_H * 2   # 516 px content width
    SCALE    = 2     # render at 2× then resize to 1× for anti-aliasing

    # ── Colours ───────────────────────────────────────────────────────────────
    C_BG       = (255, 255, 255)
    C_PAGE_BG  = (241, 243, 244)
    C_BORDER   = (232, 234, 237)
    C_SEP      = (232, 234, 237)
    C_DARK     = (32,  33,  36)
    C_GRAY     = (95,  99, 104)
    C_LGRAY    = (128, 134, 139)
    C_STAR_ON  = (251, 188,   4)
    C_STAR_OFF = (218, 220, 224)
    C_AVATAR   = (66,  133, 244)
    C_PIN_R    = (234,  67,  53)
    C_G_BLUE   = (66,  133, 244)
    C_G_RED    = (234,  67,  53)
    C_G_YEL    = (251, 188,   4)
    C_G_GRN    = (52,  168,  83)

    # ── Font loader ───────────────────────────────────────────────────────────
    def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
        suf = "-Bold" if bold else ""
        candidates = [
            f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suf}.ttf",
            f"/usr/share/fonts/truetype/liberation/LiberationSans{suf if bold else '-Regular'}.ttf",
            f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
            f"/usr/share/fonts/truetype/ubuntu/Ubuntu-{'B' if bold else 'R'}.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for p in candidates:
            try:
                return ImageFont.truetype(p, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    # ── Text size helper (Pillow 8–10 compatible) ─────────────────────────────
    def _tsz(fnt: ImageFont.ImageFont, s: str):
        try:
            bb = fnt.getbbox(s)
            return bb[2] - bb[0], bb[3] - bb[1]
        except AttributeError:
            return fnt.getsize(s)  # type: ignore[attr-defined]

    # ── 5-pointed star polygon ────────────────────────────────────────────────
    def _star_pts(cx: float, cy: float, R: float, r: float):
        pts = []
        for i in range(10):
            a = math.radians(-90 + i * 36)
            rad = R if i % 2 == 0 else r
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        return pts

    def S(v: float) -> int:
        """Scale a 1× value to 2× canvas coords."""
        return int(v * SCALE)

    # ── Preload fonts at 2× size ──────────────────────────────────────────────
    f_brand  = _font(S(18), bold=True)
    f_maps   = _font(S(13))
    f_store  = _font(S(13))
    f_name   = _font(S(15), bold=True)
    f_badge  = _font(S(12))
    f_avini  = _font(S(18), bold=True)
    f_body   = _font(S(15))
    f_date   = _font(S(12))
    f_footer = _font(S(11))

    # ── Wrap review text ──────────────────────────────────────────────────────
    # ~58 chars per line at 15 px on 516 px content width
    lines  = textwrap.wrap(text, width=58) or [""]
    LINE_H = S(24)   # line height at 15 px (≈1.6 line-height)

    # ── Dynamic card height ───────────────────────────────────────────────────
    HEADER_H   = S(26 + 14)   # brand row (26) + gap-to-separator (14)
    SEP1_H     = S(1 + 16)    # separator + gap below
    REVIEWER_H = S(40 + 16)   # avatar row (40 px) + gap
    STARS_H    = S(18 + 14)   # stars row + gap below text
    TEXT_H     = len(lines) * LINE_H
    SEP2_H     = S(14 + 1 + 14)  # gap + separator + gap
    FOOTER_H   = S(18)
    card_h = S(PAD_TOP) + HEADER_H + SEP1_H + REVIEWER_H + STARS_H + TEXT_H + SEP2_H + FOOTER_H + S(PAD_BOT)

    # ── Create 2× canvas ─────────────────────────────────────────────────────
    img = Image.new("RGB", (S(W), card_h), C_PAGE_BG)
    d   = ImageDraw.Draw(img)

    # Card background (rounded if Pillow ≥ 8.2, plain rectangle otherwise)
    card_rect = [0, 0, S(W) - 1, card_h - 1]
    try:
        d.rounded_rectangle(card_rect, radius=S(12), fill=C_BG)
    except AttributeError:
        d.rectangle(card_rect, fill=C_BG)

    # ── Header: "Google Maps" + store name ───────────────────────────────────
    y = S(PAD_TOP)
    google_chars = [
        ("G", C_G_BLUE), ("o", C_G_RED), ("o", C_G_YEL),
        ("g", C_G_BLUE), ("l", C_G_GRN), ("e", C_G_RED),
    ]
    x = S(PAD_H)
    for ch, col in google_chars:
        d.text((x, y), ch, fill=col, font=f_brand)
        cw, _ = _tsz(f_brand, ch)
        x += cw
    d.text((x + S(4), y + S(3)), "Maps", fill=C_GRAY, font=f_maps)

    # Store name — right-aligned, truncated if too long
    store_label = (store[:28] + "…") if len(store) > 29 else store
    sw, _ = _tsz(f_store, store_label)
    d.text((S(W) - S(PAD_H) - sw, y + S(3)), store_label, fill=C_GRAY, font=f_store)

    y += S(26)
    # Separator
    d.line([(S(PAD_H), y), (S(W - PAD_H), y)], fill=C_SEP, width=SCALE)
    y += S(16)

    # ── Reviewer row: avatar + name + badge ───────────────────────────────────
    AV = S(40)
    d.ellipse([S(PAD_H), y, S(PAD_H) + AV, y + AV], fill=C_AVATAR)
    initials = "".join(w[0].upper() for w in name.split() if w)[:2] or "U"
    iw, ih   = _tsz(f_avini, initials)
    d.text(
        (S(PAD_H) + AV // 2 - iw // 2, y + AV // 2 - ih // 2),
        initials, fill=(255, 255, 255), font=f_avini,
    )

    name_x = S(PAD_H + 40 + 14)
    d.text((name_x, y), name, fill=C_DARK, font=f_name)
    badge_label = badge if badge else "Local Guide"
    d.text((name_x, y + S(20)), badge_label, fill=C_LGRAY, font=f_badge)
    y += S(40 + 16)

    # ── Stars + date ──────────────────────────────────────────────────────────
    STAR_R    = 7.0   # outer radius (1× px)
    STAR_r    = 3.0   # inner radius
    STAR_STEP = 17    # centre-to-centre spacing
    star_cy   = y + S(8)  # vertical centre of stars
    for i in range(5):
        cx = PAD_H + i * STAR_STEP + STAR_R
        pts = _star_pts(S(cx), star_cy, S(STAR_R), S(STAR_r))
        d.polygon(pts, fill=(C_STAR_ON if i < rating else C_STAR_OFF))

    date_x = PAD_H + 5 * STAR_STEP + 6
    d.text((S(date_x), star_cy - S(2)), date, fill=C_LGRAY, font=f_date)
    y += S(18 + 14)

    # ── Review text ───────────────────────────────────────────────────────────
    for line in lines:
        d.text((S(PAD_H), y), line, fill=C_DARK, font=f_body)
        y += LINE_H

    # ── Footer separator + "Posted on Google Maps" ────────────────────────────
    y += S(14)
    d.line([(S(PAD_H), y), (S(W - PAD_H), y)], fill=C_SEP, width=SCALE)
    y += S(14)

    # Simplified map pin: red circle + white dot
    PIN_W = S(14)
    d.ellipse([S(PAD_H), y, S(PAD_H) + PIN_W, y + PIN_W], fill=C_PIN_R)
    dot = S(4)
    d.ellipse(
        [S(PAD_H) + PIN_W // 2 - dot // 2, y + PIN_W // 2 - dot // 2,
         S(PAD_H) + PIN_W // 2 + dot // 2, y + PIN_W // 2 + dot // 2],
        fill=(255, 255, 255),
    )
    d.text((S(PAD_H) + PIN_W + S(6), y + S(1)), "Posted on Google Maps", fill=C_LGRAY, font=f_footer)

    # ── Downscale to 1× (anti-aliasing) ──────────────────────────────────────
    final = img.resize((W, card_h // SCALE), Image.LANCZOS)  # type: ignore[attr-defined]

    # ── Save ──────────────────────────────────────────────────────────────────
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(DEFAULT_OUTPUT_DIR / f"review_card_{ts}.png")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, "PNG")
    print(f"Review card (Pillow) saved: {output_path}")
    return output_path


def render_card(
    name: str,
    rating: int,
    text: str,
    date: str,
    store: str,
    badge: str = "",
    output_dir: Optional[str] = None,
) -> str:
    """Render the review card. Tries Playwright + HTML template first; falls
    back to the Pillow renderer automatically if the browser cannot be launched
    (e.g. missing system libraries in a minimal Docker container).

    Returns the path to the saved screenshot.
    """
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(out_dir / f"review_card_{timestamp}.png")

    # ── Try Playwright path ───────────────────────────────────────────────────
    if TEMPLATE_PATH.exists():
        try:
            from playwright.sync_api import sync_playwright

            url = build_template_url(name, rating, text, date, store, badge)
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                except Exception as launch_err:
                    print(f"Browser launch failed ({launch_err}); falling back to Pillow renderer.")
                    return render_card_pillow(name, rating, text, date, store, badge, output_path)

                page = browser.new_page(viewport={"width": 700, "height": 600})
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(300)
                card = page.query_selector("#review-card")
                if card:
                    card.screenshot(path=output_path)
                else:
                    page.screenshot(path=output_path, full_page=True)
                browser.close()
            return output_path

        except ImportError:
            print("Playwright not installed; falling back to Pillow renderer.")
        except Exception as e:
            print(f"Playwright render failed ({e}); falling back to Pillow renderer.")
    else:
        print(f"HTML template not found at {TEMPLATE_PATH}; falling back to Pillow renderer.")

    # ── Pillow fallback ───────────────────────────────────────────────────────
    return render_card_pillow(name, rating, text, date, store, badge, output_path)


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
