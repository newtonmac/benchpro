"""
Search Runner — scrapes Google SERP using a headless browser.
No API keys or signups required.
"""
import sys, os, time, random, logging
from urllib.parse import urlparse, urlencode
from datetime import datetime
from playwright.sync_api import sync_playwright
import config
from collector.storage import save_search_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("benchpro")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

def _domain_from_display(text):
    if not text: return ""
    text = text.strip()
    for p in ["https://","http://","www."]:
        if text.lower().startswith(p): text = text[len(p):]
    for sep in ["/", " >", " ", ">"]:
        if sep in text: text = text[:text.index(sep)]
    text = text.strip().lower()
    if text.startswith("www."): text = text[4:]
    return text

def _extract_domain(url):
    if not url: return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        d = parsed.netloc.lower()
        if d.startswith("www."): d = d[4:]
        if "google." in d: return ""
        return d
    except: return ""

def _build_url(keyword):
    return f"https://www.google.com/search?{urlencode({'q':keyword,'hl':config.SEARCH_LANGUAGE,'gl':config.SEARCH_COUNTRY,'num':10})}"

def _parse_all_results(page):
    return page.evaluate("""() => {
        const output = { sponsored: [], organic: [] };
        function findAds() {
            const ads = []; const seen = new Set();
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            const sponsoredNodes = [];
            while (walker.nextNode()) {
                const t = walker.currentNode.textContent.trim();
                if (t === 'Sponsored' || t === 'Ad' || t === 'Ads') sponsoredNodes.push(walker.currentNode.parentElement);
            }
            for (const labelEl of sponsoredNodes) {
                let container = labelEl;
                for (let i = 0; i < 15; i++) {
                    container = container.parentElement;
                    if (!container) break;
                    if (container.querySelector('[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit')) continue;
                    if (container.closest('[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit')) continue;
                    const headings = container.querySelectorAll('h3, div[role="heading"]');
                    if (headings.length > 0) {
                        for (const heading of headings) {
                            let adBlock = heading;
                            for (let j = 0; j < 8; j++) {
                                adBlock = adBlock.parentElement;
                                if (!adBlock) break;
                                const cite = adBlock.querySelector('cite, span[data-dtld], .qzEoUe');
                                if (!cite) continue;
                                const displayUrl = cite.textContent.trim();
                                if (!displayUrl || seen.has(displayUrl)) break;
                                seen.add(displayUrl);
                                let snippet = '';
                                adBlock.querySelectorAll('.MUxGbd, .yDYNvb, .lyLwlc, [role="text"]').forEach(d => {
                                    const t = d.textContent.trim();
                                    if (t.length > snippet.length && t !== heading.textContent.trim()) snippet = t;
                                });
                                ads.push({ title: heading.textContent.trim(), displayUrl, snippet: snippet.substring(0,250) });
                                break;
                            }
                        }
                        if (ads.length > 0) break;
                    }
                }
            }
            if (ads.length === 0) {
                for (const id of ['tads','tadsb']) {
                    const c = document.getElementById(id);
                    if (!c) continue;
                    c.querySelectorAll('h3, div[role="heading"]').forEach(heading => {
                        let block = heading;
                        for (let j = 0; j < 8; j++) {
                            block = block.parentElement;
                            if (!block) break;
                            const cite = block.querySelector('cite, span[data-dtld]');
                            if (!cite) continue;
                            const du = cite.textContent.trim();
                            if (seen.has(du)) break;
                            seen.add(du);
                            let sn = '';
                            block.querySelectorAll('.MUxGbd, .yDYNvb').forEach(d => { const t=d.textContent.trim(); if(t.length>sn.length) sn=t; });
                            ads.push({ title: heading.textContent.trim(), displayUrl: du, snippet: sn.substring(0,250) });
                            break;
                        }
                    });
                }
            }
            return ads;
        }
        function findOrganic() {
            const items = []; const seen = new Set();
            const sc = document.querySelector('#search, #rso, #main');
            if (!sc) return items;
            let blocks = sc.querySelectorAll('.g:not(.g .g)');
            if (!blocks.length) blocks = sc.querySelectorAll('[data-sokoban-container] .g');
            for (const block of blocks) {
                if (block.closest('#tads, #tadsb, [data-pla], .commercial-unit-desktop-top')) continue;
                if (block.closest('[data-initq], .related-question-pair, .kno-kp')) continue;
                const link = block.querySelector('a[href^="http"]:not([href*="google.com/search"]):not([href*="google.com/aclk"])');
                if (!link) continue;
                const href = link.href || '';
                if (!href.startsWith('http') || href.includes('google.com')) continue;
                const titleEl = block.querySelector('h3');
                if (!titleEl) continue;
                const title = titleEl.textContent.trim();
                if (!title || seen.has(href)) continue;
                seen.add(href);
                let snippet = '';
                block.querySelectorAll('.VwiC3b, .lEBKkf, [data-sncf], .IsZvec, .st').forEach(s => { const t=s.textContent.trim(); if(t.length>snippet.length) snippet=t; });
                items.push({ href, title, snippet: snippet.substring(0,250) });
            }
            return items;
        }
        output.sponsored = findAds();
        output.organic = findOrganic();
        return output;
    }""")

def search_keyword(keyword, browser):
    url = _build_url(keyword)
    log.info(f"Searching: '{keyword}' ...")
    context = browser.new_context(user_agent=random.choice(USER_AGENTS), viewport={"width":1366,"height":900}, locale="en-US")
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")
    page = context.new_page()
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_selector("#search, #rso, #main", timeout=15000)
        page.wait_for_timeout(3000)
        for btn_text in ["Accept all","I agree","Reject all","Accept"]:
            btn = page.query_selector(f'button:has-text("{btn_text}")')
            if btn:
                btn.click(); page.wait_for_timeout(2000); break
        if page.query_selector("#captcha-form, #recaptcha, iframe[src*='recaptcha']"):
            log.error("  CAPTCHA"); context.close(); return [], []
        raw = _parse_all_results(page)
        sponsored = []
        seen_sp = set()
        for ad in raw.get("sponsored",[])[:config.TOP_N_SPONSORED+3]:
            domain = _domain_from_display(ad["displayUrl"])
            if not domain or domain in seen_sp: continue
            seen_sp.add(domain)
            sponsored.append({"position":len(sponsored)+1,"title":ad["title"],"domain":domain,"display_url":ad["displayUrl"],"snippet":ad["snippet"]})
        sponsored = sponsored[:config.TOP_N_SPONSORED]
        organic = []
        seen_org = set()
        for item in raw.get("organic",[]):
            if len(organic)>=config.TOP_N_ORGANIC: break
            domain = _extract_domain(item["href"])
            if not domain or domain in seen_org: continue
            seen_org.add(domain)
            organic.append({"position":len(organic)+1,"title":item["title"],"domain":domain,"link":item["href"],"snippet":item["snippet"]})
        log.info(f"  Found: {len(sponsored)} sponsored, {len(organic)} organic")
        for s in sponsored: log.info(f"    Ad #{s['position']}: {s['domain']}")
        for o in organic: log.info(f"    Org #{o['position']}: {o['domain']}")
        context.close()
        return sponsored, organic
    except Exception as e:
        log.error(f"  Error: {e}")
        try: context.close()
        except: pass
        return [], []

def run_all_keywords(keywords=None):
    keywords = keywords or config.KEYWORDS
    log.info(f"=== BenchPro run at {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"])
        for i, kw in enumerate(keywords):
            try:
                sp, org = search_keyword(kw, browser)
                rid = save_search_run(kw, sp, org)
                log.info(f"  Saved: {rid}")
            except Exception as e: log.error(f"  Failed '{kw}': {e}")
            if i < len(keywords)-1:
                delay = config.DELAY_BETWEEN_SEARCHES + random.uniform(2,5)
                log.info(f"  Waiting {delay:.0f}s ..."); time.sleep(delay)
        browser.close()
    log.info("=== Done ===")

if __name__ == "__main__":
    run_all_keywords([sys.argv[1]] if len(sys.argv)>1 else None)
