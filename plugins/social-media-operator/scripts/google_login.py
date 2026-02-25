#!/usr/bin/env python3
"""
Reusable Google login module for Playwright.

Handles the Google sign-in flow including email entry, password entry,
and common post-login prompts (recovery phone, "Stay signed in?", etc.).

Returns True on successful login, False if blocked by 2FA/CAPTCHA.
Saves diagnostic screenshots on failure.

Usage:
    from scripts.google_login import google_login

    result = await google_login(page, email, password)
"""

import asyncio
from pathlib import Path
from datetime import datetime

SCREENSHOTS_DIR = Path.cwd() / "screenshots"


async def _save_diag(page, label: str) -> str:
    """Save a diagnostic screenshot and return the path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"login_diag_{label}_{ts}.png"
    try:
        await page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass
    return str(path)


async def _dismiss_prompt(page, texts, timeout=3000):
    """Try to click a button matching any of the given texts."""
    for text in texts:
        try:
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.count() > 0:
                await btn.click(timeout=timeout)
                await asyncio.sleep(1.5)
                return True
        except Exception:
            continue
    return False


async def _check_blocked(page) -> bool:
    """Check whether we hit a 2FA, CAPTCHA, or other blocker page."""
    try:
        pw_field = page.locator('input[type="password"]')
        if await pw_field.count() > 0:
            try:
                if await pw_field.first.is_visible():
                    return False
            except Exception:
                pass

        content = await page.content()
        lower = content.lower()
        url_lower = page.url.lower()

        url_blockers = [
            "/challenge/",
            "/interstitialpage",
            "/speedbump",
        ]
        for b in url_blockers:
            if b in url_lower:
                return True

        content_blockers = [
            "2-step verification",
            "confirm your recovery phone",
            "unusual activity",
            "this device isn't recognized",
        ]
        for b in content_blockers:
            if b in lower:
                return True

        if "recaptcha" in lower or "g-recaptcha" in lower:
            return True

    except Exception:
        pass
    return False


async def google_login(page, email: str, password: str) -> bool:
    """Log in to Google via the accounts sign-in page.

    Args:
        page: A Playwright page object (async API).
        email: Google account email address.
        password: Google account password.

    Returns:
        True if login succeeded, False if blocked by 2FA/CAPTCHA.
    """
    try:
        print("[google_login] Navigating to Google sign-in...")
        await page.goto(
            "https://accounts.google.com/signin",
            wait_until="networkidle",
            timeout=30000,
        )
        await asyncio.sleep(2)

        await _dismiss_prompt(page, ["Accept all", "Reject all", "I agree"])

        print("[google_login] Entering email...")
        email_input = page.locator('input[type="email"]').first
        if await email_input.count() == 0:
            email_input = page.locator('input#identifierId').first

        if await email_input.count() == 0:
            print("[google_login] ERROR: Cannot find email input field")
            await _save_diag(page, "no_email_field")
            return False

        await email_input.fill(email)
        await asyncio.sleep(0.5)

        next_clicked = await _dismiss_prompt(
            page,
            ["Next", "Suivant", "Weiter", "Avanti"],
            timeout=5000,
        )
        if not next_clicked:
            await email_input.press("Enter")

        await asyncio.sleep(2)

        print("[google_login] Waiting for password field...")
        try:
            await page.wait_for_selector(
                'input[type="password"]', state="visible", timeout=15000
            )
        except Exception:
            if await _check_blocked(page):
                print("[google_login] BLOCKED after email entry (2FA/CAPTCHA)")
                await _save_diag(page, "blocked_after_email")
                return False
            print("[google_login] ERROR: Password field did not appear")
            await _save_diag(page, "no_password_field")
            return False

        print("[google_login] Entering password...")
        password_input = page.locator('input[type="password"]').first
        if await password_input.count() == 0:
            print("[google_login] ERROR: Cannot find password input field")
            await _save_diag(page, "no_password_field")
            return False

        await password_input.fill(password)
        await asyncio.sleep(0.5)

        next_clicked = await _dismiss_prompt(
            page,
            ["Next", "Suivant", "Weiter", "Avanti"],
            timeout=5000,
        )
        if not next_clicked:
            await password_input.press("Enter")

        await asyncio.sleep(4)

        if await _check_blocked(page):
            print("[google_login] BLOCKED after password entry (2FA/CAPTCHA)")
            await _save_diag(page, "blocked_after_password")
            return False

        print("[google_login] Handling post-login prompts...")

        await _dismiss_prompt(page, ["Yes", "Not now", "No", "Skip"])
        await asyncio.sleep(1)

        await _dismiss_prompt(page, ["Not now", "Done", "Confirm", "Skip"])
        await asyncio.sleep(1)

        await _dismiss_prompt(page, ["Not now", "Done", "Remind me later"])
        await asyncio.sleep(1)

        print("[google_login] Verifying login state...")
        current_url = page.url

        success_indicators = [
            "myaccount.google.com",
            "mail.google.com",
            "accounts.google.com/Default",
            "accounts.google.com/SignOutOptions",
            "google.com/maps",
        ]

        failure_indicators = [
            "accounts.google.com/signin",
            "accounts.google.com/v3/signin",
            "challenge",
        ]

        for indicator in success_indicators:
            if indicator in current_url:
                print(f"[google_login] SUCCESS - URL indicates login: {current_url}")
                return True

        for indicator in failure_indicators:
            if indicator in current_url:
                try:
                    avatar = page.locator(
                        'img[aria-label*="Account"], a[aria-label*="Account"], '
                        'img[data-profile-identifier], header a[href*="SignOut"]'
                    ).first
                    if await avatar.count() > 0:
                        print("[google_login] SUCCESS - Found account avatar on page")
                        return True
                except Exception:
                    pass

                if await _check_blocked(page):
                    print(f"[google_login] BLOCKED - URL: {current_url}")
                    await _save_diag(page, "blocked_final")
                    return False

        try:
            body_text = await page.locator("body").inner_text()
            signed_in_signals = [
                "Sign out",
                "My Account",
                "Google Account",
                email.split("@")[0],
            ]
            for signal in signed_in_signals:
                if signal.lower() in body_text.lower():
                    print(f"[google_login] SUCCESS - Found '{signal}' on page")
                    return True
        except Exception:
            pass

        if not await _check_blocked(page):
            print(f"[google_login] Likely SUCCESS (no blockers detected, URL: {current_url})")
            return True

        print(f"[google_login] UNCERTAIN - saving diagnostic. URL: {current_url}")
        await _save_diag(page, "uncertain")
        return False

    except Exception as e:
        print(f"[google_login] ERROR: {e}")
        await _save_diag(page, "exception")
        return False
