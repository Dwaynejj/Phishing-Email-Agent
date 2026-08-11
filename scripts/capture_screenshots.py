"""Capture screenshots of every PhishShield UI view into screenshots/."""
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5001"
OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)

VIEWPORT = {"width": 1280, "height": 900}


def shot(page, name: str, full_page: bool = True):
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full_page)
    print(f"saved {path}")


def fill_history(page):
    """Seed localStorage history so History section looks populated."""
    page.evaluate(
        """() => {
        const now = new Date().toISOString();
        const history = [
          {
            id: 101,
            timestamp: now,
            prediction: 'phishing',
            probability: 0.92,
            confidence: 0.94,
            subject: 'Urgent: Verify your account now',
            preview: 'Click here immediately to restore access...',
            fullText: 'Click here immediately to restore access to your account.',
            filename: null,
            features: { links_count: 2, urgent_keywords: 1, has_attachment: 0 },
            requestData: null
          },
          {
            id: 102,
            timestamp: now,
            prediction: 'legitimate',
            probability: 0.12,
            confidence: 0.88,
            subject: 'Weekly team notes',
            preview: 'Here are the notes from Thursday meeting...',
            fullText: 'Here are the notes from Thursday meeting. See you next week.',
            filename: null,
            features: { links_count: 0, urgent_keywords: 0, has_attachment: 0 },
            requestData: null
          }
        ];
        const stats = { total: 2, phishing: 1, legitimate: 1 };
        localStorage.setItem('phishingAnalysisHistory', JSON.stringify(history));
        localStorage.setItem('phishingStats', JSON.stringify(stats));
    }"""
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = context.new_page()

        # Fresh empty home
        page.goto(BASE, wait_until="networkidle")
        page.evaluate("() => { localStorage.clear(); }")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "01-home-upload")

        # Manual input tab (empty form)
        page.locator('.tab[data-tab="manual"]').click()
        page.wait_for_timeout(300)
        shot(page, "02-manual-input")

        # About modal
        page.locator("#aboutNav").click()
        page.wait_for_selector("#aboutModal.open")
        page.wait_for_timeout(200)
        shot(page, "03-about", full_page=False)
        page.locator('[data-close-modal="aboutModal"]').click()
        page.wait_for_timeout(200)

        # Settings modal
        page.locator("#settingsNav").click()
        page.wait_for_selector("#settingsModal.open")
        page.wait_for_timeout(200)
        shot(page, "04-settings", full_page=False)
        page.locator('[data-close-modal="settingsModal"]').click()
        page.wait_for_timeout(200)

        # Upload tab with a staged file (no analyze yet)
        page.locator('.tab[data-tab="drag-drop"]').click()
        sample = OUT / "_sample_phish.eml"
        sample.write_text(
            "From: Security Desk <alerts@secure-login-update.com>\n"
            "To: user@example.com\n"
            "Subject: Urgent: Action Required - Verify your account now\n"
            "MIME-Version: 1.0\n"
            "Content-Type: text/plain; charset=utf-8\n\n"
            "Dear customer,\n"
            "Your account has been suspended. Click here immediately:\n"
            "https://secure-login-update.com/verify?user=1\n"
            "Please verify now or your password expired access will be lost.\n",
            encoding="utf-8",
        )
        page.set_input_files("#fileInput", str(sample))
        page.wait_for_selector("#uploadActions:not([hidden])")
        page.wait_for_timeout(300)
        shot(page, "05-file-ready-to-check")

        # Phishing result
        page.locator("#checkEmailBtn").click()
        page.wait_for_selector(".result-card.phishing", timeout=30000)
        page.wait_for_timeout(600)
        shot(page, "06-result-phishing")

        # Legitimate result via manual form
        page.locator('.tab[data-tab="manual"]').click()
        page.fill("#emailText", "Hi team, attached are the meeting notes from Thursday. See you next week.")
        page.fill("#subject", "Meeting notes")
        page.fill("#senderDomain", "company.com")
        page.locator("#analysisForm button[type='submit']").click()
        page.wait_for_selector(".result-card.legitimate", timeout=30000)
        page.wait_for_timeout(600)
        shot(page, "07-result-legitimate")

        # History section (seed + reload for clean stats/history UI)
        fill_history(page)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        page.locator("#history-section").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        shot(page, "08-history")

        # Full dashboard with history + empty result area after reload
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        shot(page, "09-dashboard-overview")

        # Extension popup page (static HTML)
        ext = Path("Extension/popup.html").resolve().as_uri()
        ext_page = context.new_page()
        ext_page.set_viewport_size({"width": 360, "height": 520})
        ext_page.goto(ext, wait_until="domcontentloaded")
        # Avoid chrome API errors breaking layout — inject stub if needed
        ext_page.wait_for_timeout(400)
        ext_page.screenshot(path=str(OUT / "10-extension-popup.png"))
        print(f"saved {OUT / '10-extension-popup.png'}")
        ext_page.close()

        sample.unlink(missing_ok=True)
        browser.close()
        print("done")


if __name__ == "__main__":
    main()
