"""Real-browser checks of the website (needs: pip install playwright  +  Google Chrome or Edge installed).
Why this exists: the other web tests only read files. They cannot see what a browser actually shows, so a half-old page
(raw translation keys, giant images, a second navigation) passed every test. This loads each page for real and checks:
no failed requests, no console errors, no raw translation keys, no horizontal scroll, images inside their boxes,
exactly one visible navigation, a working mobile menu, a styled page (fonts + layout CSS really applied).
It uses the fake engine, so it needs no model files. Skipped (not failed) when Playwright is not installed.
Run: python tests/test_browser.py        Optional: CHROME_PATH=<path to chrome.exe>"""
import os
import re
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "src"), HERE]
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("browser tests skipped: Playwright is not installed (pip install playwright)")
    sys.exit(0)
import uvicorn  # noqa: E402
from fake_engine import FakeEngine  # noqa: E402
from service.main import create_app  # noqa: E402

PORT = 8765
PAGES = ["index.html", "check.html", "details.html", "monitoring.html"]
WIDTHS = [375, 430, 768, 1440]
RAW_KEY = re.compile(r"\b[a-z]{1,8}_[a-z0-9]+(?:_[a-z0-9]+)*\b")   # looks like an untranslated key, e.g. p_h_title, cond_balding
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def start_server():
    app = create_app(FakeEngine(), log_path=os.path.join(tempfile.mkdtemp(), "l.jsonl"))
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        if srv.started:
            return srv
        time.sleep(0.1)
    raise RuntimeError("server did not start")


def launch(p):
    exe = os.environ.get("CHROME_PATH")
    if exe:
        return p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    for ch in ("chrome", "msedge"):
        try:
            return p.chromium.launch(channel=ch)
        except Exception:
            pass
    return p.chromium.launch()


def audit(page, lang, width, url, name):
    tag = f"[{name} {lang} {width}px]"
    page.goto(f"http://127.0.0.1:{PORT}/{url}", wait_until="networkidle")
    if lang == "th":
        page.click("[data-lang=th]")
    page.wait_for_timeout(300)
    text = page.evaluate("document.body.innerText + ' ' + [...document.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label')).join(' ')")
    raw = sorted(set(RAW_KEY.findall(text)) - {"hair_care_summary"})
    check(not raw, f"{tag} untranslated keys visible: {raw[:5]}")
    check(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0, f"{tag} horizontal scroll")
    check("Plex" in page.evaluate("getComputedStyle(document.querySelector('h1')).fontFamily"), f"{tag} main stylesheet not applied (heading font)")
    big = page.evaluate("[...document.querySelectorAll('main img')].filter(i => i.getBoundingClientRect().width > Math.min(window.innerWidth, 760)).map(i => i.getAttribute('src'))")
    check(not big, f"{tag} oversized images: {big[:3]}")
    nav = page.evaluate("[...document.querySelectorAll('nav.nav, #mnav')].filter(e => { const r = e.getBoundingClientRect(); return getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none' && r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 }).map(e => e.id || e.className)")
    if width > 1100:
        check(nav == ["nav"], f"{tag} desktop should show exactly the top navigation, got {nav}")
    else:       # narrow screens: the menu is closed, so NO navigation list may be showing; only the menu button
        check(nav == [], f"{tag} a navigation is visible while the menu is closed: {nav}")
        check(page.is_visible("#menu-btn"), f"{tag} menu button missing")


def main():
    srv = start_server()
    with sync_playwright() as p:
        browser = launch(p)
        for lang in ("en", "th"):
            for w in WIDTHS:
                ctx = browser.new_context(viewport={"width": w, "height": 900})
                page = ctx.new_page()
                problems = []
                page.on("pageerror", lambda e: problems.append("script error: " + str(e)))
                page.on("console", lambda m: problems.append("console " + m.type + ": " + m.text) if m.type == "error" else None)
                page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
                page.on("requestfailed", lambda r: problems.append("request failed " + r.url))
                for u in PAGES:
                    audit(page, lang, w, u, u)
                check(not problems, f"[{lang} {w}px] network/console problems: {problems[:4]}")
                if w <= 430 and lang == "en":      # mobile menu really opens, navigates and closes
                    page.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="networkidle")
                    page.click("#menu-btn")
                    try:
                        page.wait_for_selector("#mnav a[href='details.html']", state="visible", timeout=3000)   # it fades in
                    except Exception:
                        check(False, "mobile menu did not open")
                    page.keyboard.press("Escape")
                    try:
                        page.wait_for_selector("#mnav a[href='details.html']", state="hidden", timeout=3000)
                    except Exception:
                        check(False, "mobile menu did not close with Escape")
                ctx.close()
        # keyboard: the first Tab stop must show a visible focus outline
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/check.html", wait_until="networkidle")
        page.keyboard.press("Tab")
        check(page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none", "no visible focus on keyboard Tab")
        # a stale browser cache must not matter: asset URLs carry a version tag
        urls = page.evaluate("[...document.querySelectorAll('link[rel=stylesheet],script[src]')].map(e => e.href || e.src)")
        check(all("?v=" in u for u in urls), f"asset URLs without ?v=: {urls}")
        ctx.close(); browser.close()
    srv.should_exit = True
    if FAILS:
        print("browser tests FAILED:\n  " + "\n  ".join(FAILS))
        sys.exit(1)
    print(f"browser tests passed ({len(PAGES)} pages x {len(WIDTHS)} widths x EN/TH)")


if __name__ == "__main__":
    main()
