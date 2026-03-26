"""
Search Runner — scrapes Google SERP using a headless browser.
No API keys or signups required.

Usage:
    python -m collector.search_runner              # run all keywords
    python -m collector.search_runner "workbench"  # run one keyword
"""
import sys
import time
import random
import logging
from urllib.parse import urlparse, urlencode
from datetime import datetime

from playwright.sync_api import sync_playwright

import config
from collector.storage import save_search_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("benchpro")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def _extract_domain(url):
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _build_url(keyword):
    params = {
        "q": keyword,
        "hl": config.SEARCH_LANGUAGE,
        "gl": config.SEARCH_COUNTRY,
        "num": 10,
    }
    return f"https://www.google.com/search?{urlencode(params)}"


def _parse_sponsored(page):
    """Extract sponsored text-ad results. Skips shopping."""
    try:
        results = page.evaluate("""() => {
            const ads = [];
            // Google text ads live in #tads (top) and #tadsb (bottom)
            const containers = document.querySelectorAll('#tads, #tadsb');
            for (const container of containers) {
                // Skip if this is a shopping block
                if (container.querySelector('[data-pla], .commercial-unit-desktop-top, .cu-container'))
                    continue;

                // Each ad block
                const blocks = container.querySelectorAll('.uEierd, [data-text-ad="1"]');
                for (const block of blocks) {
                    // Skip shopping within the ad container
                    if (block.closest('[data-pla], .commercial-unit-desktop-top')) continue;

                    const titleEl = block.querySelector('h3, div[role="heading"]');
                    const title = titleEl ? titleEl.textContent.trim() : '';

                    // Display URL (the green URL shown)
                    const citeEl = block.querySelector('cite, .qzEoUe, span[data-dtld]');
                    const displayUrl = citeEl ? citeEl.textContent.trim() : '';

                    // Snippet
                    const snippetEl = block.querySelector('.MUxGbd, .yDYNvb, .lyLwlc');
                    const snippet = snippetEl ? snippetEl.textContent.trim() : '';

                    if (displayUrl || title) {
                        ads.push({ title, displayUrl, snippet: snippet.substring(0, 250) });
                    }
                }
            }

            // Fallback: look for any "Sponsored" labels if #tads not found
            if (ads.length === 0) {
                const allSpans = document.querySelectorAll('span');
                for (const span of allSpans) {
                    if (span.textContent.trim() !== 'Sponsored') continue;
                    let node = span;
                    for (let i = 0; i < 10; i++) {
                        node = node.parentElement;
                        if (!node) break;
                        if (node.closest('.commercial-unit-desktop-top, [data-pla]')) break;
                        const titleEl = node.querySelector('h3, div[role="heading"]');
                        const citeEl = node.querySelector('cite');
                        if (titleEl && citeEl) {
                            const snippetEl = node.querySelector('.MUxGbd, .yDYNvb');
                            ads.push({
                                title: titleEl.textContent.trim(),
                                displayUrl: citeEl.textContent.trim(),
                                snippet: snippetEl ? snippetEl.textContent.trim().substring(0, 250) : ''
                            });
                            break;
                        }
                    }
                }
            }

            return ads;
        }""")

        sponsored = []
        seen = set()
        for i, ad in enumerate(results[:config.TOP_N_SPONSORED]):
            domain = _extract_domain(ad["displayUrl"])
            if not domain or domain in seen:
                continue
            seen.add(domain)
            sponsored.append({
                "position": len(sponsored) + 1,
                "title": ad["title"],
                "domain": domain,
                "display_url": ad["displayUrl"],
                "snippet": ad["snippet"],
            })
        return sponsored

    except Exception as e:
        log.warning(f"  Error parsing sponsored: {e}")
        return []


def _parse_organic(page):
    """Extract organic results (non-ad, non-shopping)."""
    try:
        results = page.evaluate("""() => {
            const items = [];
            const container = document.querySelector('#search, #rso');
            if (!container) return items;

            const gBlocks = container.querySelectorAll('.g');
            for (const g of gBlocks) {
                if (g.closest('#tads, #tadsb, .commercial-unit-desktop-top, [data-pla]')) continue;
                if (g.closest('[data-initq], .related-question-pair')) continue;

                const link = g.querySelector('a[href^="http"]:not([href*="google.com/search"])');
                if (!link) continue;

                const href = link.href;
                if (href.includes('google.com')) continue;

                const titleEl = g.querySelector('h3');
                const title = titleEl ? titleEl.textContent.trim() : '';

                let snippet = '';
                g.querySelectorAll('.VwiC3b, .lEBKkf, [data-sncf], .IsZvec')
                 .forEach(s => { snippet += s.textContent.trim() + ' '; });

                items.push({ href, title, snippet: snippet.trim().substring(0, 250) });
            }
            return items;
        }""")

        organic = []
        seen = set()
        for item in results[:config.TOP_N_ORGANIC + 5]:  # extra buffer
            if len(organic) >= config.TOP_N_ORGANIC:
                break
            domain = _extract_domain(item["href"])
            if not domain or domain in seen or "google." in domain:
                continue
            seen.add(domain)
            organic.append({
                "position": len(organic) + 1,
                "title": item["title"],
                "domain": domain,
                "link": item["href"],
                "snippet": item["snippet"],
            })
        return organic

    except Exception as e:
        log.warning(f"  Error parsing organic: {e}")
        return []


def search_keyword(keyword, browser):
    """Run one Google search with a headless browser."""
    url = _build_url(keyword)
    log.info(f"Searching: '{keyword}' ...")

    context = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 900},
        locale="en-US",
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    page = context.new_page()

    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_selector("#search, #rso", timeout=15000)
        page.wait_for_timeout(2500)

        # Dismiss consent banners
        for btn_text in ["Accept all", "I agree", "Reject all"]:
            btn = page.query_selector(f'button:has-text("{btn_text}")')
            if btn:
                btn.click()
                page.wait_for_timeout(2000)
                break

        # Check for CAPTCHA
        if page.query_selector("#captcha-form, #recaptcha, iframe[src*='recaptcha']"):
            log.error("  ✗ CAPTCHA detected — skipping. Increase DELAY_BETWEEN_SEARCHES.")
            context.close()
            return [], []

        sponsored = _parse_sponsored(page)
        organic = _parse_organic(page)
        log.info(f"  ✓ '{keyword}': {len(sponsored)} sponsored, {len(organic)} organic")
        context.close()
        return sponsored, organic

    except Exception as e:
        log.error(f"  ✗ Error: {e}")
        try:
            page.screenshot(path=f"debug_{keyword.replace(' ', '_')}.png")
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass
        return [], []


def run_all_keywords(keywords=None):
    """Run searches for all keywords and save to JSON."""
    keywords = keywords or config.KEYWORDS
    log.info(f"═══ BenchPro search run at {datetime.now().strftime('%Y-%m-%d %H:%M')} ═══")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
                  "--disable-dev-shm-usage"],
        )

        for i, kw in enumerate(keywords):
            try:
                sponsored, organic = search_keyword(kw, browser)
                run_id = save_search_run(kw, sponsored, organic)
                log.info(f"  → Saved: {run_id}")
            except Exception as e:
                log.error(f"  ✗ Failed '{kw}': {e}")

            if i < len(keywords) - 1:
                delay = config.DELAY_BETWEEN_SEARCHES + random.uniform(2, 5)
                log.info(f"  ⏳ Waiting {delay:.0f}s ...")
                time.sleep(delay)

        browser.close()

    log.info("═══ Done ═══\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_all_keywords([sys.argv[1]])
    else:
        run_all_keywords()
