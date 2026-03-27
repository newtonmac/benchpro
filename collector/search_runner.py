"""
Search Runner — one fresh browser per keyword.
Captures: Sponsored text ads, Organic, Shopping/product ads.
Records search location. Filters junk. UTC timestamps.
"""
import sys, os, time, random, logging
from urllib.parse import urlparse, urlencode
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
import config
from collector.storage import save_search_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("benchpro")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

US_LOCATIONS = [
    "Houston, Texas", "Chicago, Illinois", "Los Angeles, California",
    "New York, New York", "Dallas, Texas", "Atlanta, Georgia",
    "Detroit, Michigan", "Phoenix, Arizona", "Philadelphia, Pennsylvania",
    "San Diego, California", "Seattle, Washington", "Denver, Colorado",
]

# Domains to ignore (not workbench product sellers)
JUNK_DOMAINS = {"workbench.developerforce.com", "mysql.com", "postgresql.org", "ubuntu.com"}

# Junk shopping store names (Google UI artifacts)
JUNK_STORES = {"cancel", "(4)", "(2k+)", "more", "see more", "show more", "sponsored", "ad", ""}

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
        parsed = urlparse(url if "://" in url else "https://"+url)
        d = parsed.netloc.lower()
        if d.startswith("www."): d = d[4:]
        if "google." in d or "gstatic" in d or "youtube.com" in d: return ""
        if d in JUNK_DOMAINS: return ""
        return d
    except: return ""

def _is_junk_domain(domain):
    return domain in JUNK_DOMAINS

def _is_junk_store(store):
    return store.lower().strip() in JUNK_STORES or len(store) < 3 or store.startswith("(")

def _build_url(keyword, location):
    params = {
        "q": keyword,
        "hl": config.SEARCH_LANGUAGE,
        "gl": config.SEARCH_COUNTRY,
        "num": "10",
        "near": location,
    }
    return "https://www.google.com/search?" + urlencode(params)

def _parse_all_results(page):
    return page.evaluate(r"""() => {
        const output = { sponsored: [], organic: [], shopping: [] };
        const seen_sp = new Set();
        const seen_org = new Set();

        // === SPONSORED TEXT ADS ===
        // Simple approach: find ALL cite elements on the page, then check if they're inside a sponsored section
        const allCites = document.querySelectorAll('cite');
        for (const cite of allCites) {
            // Walk up to check if this cite is inside a sponsored/ad section
            let node = cite;
            let isAd = false;
            let isShopping = false;
            for (let i = 0; i < 15; i++) {
                node = node.parentElement;
                if (!node) break;
                // Check if in shopping
                if (node.querySelector('[data-pla]') || node.closest('[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit')) {
                    isShopping = true; break;
                }
                // Check if in sponsored text ads
                const text = node.innerText || '';
                if (text.includes('Sponsored') || node.id === 'tads' || node.id === 'tadsb') {
                    isAd = true; break;
                }
            }
            if (!isAd || isShopping) continue;
            
            const du = cite.textContent.trim();
            if (!du || seen_sp.has(du)) continue;
            
            // Find the heading (h3) that belongs to this ad
            let adBlock = cite;
            let title = '';
            let snippet = '';
            for (let i = 0; i < 8; i++) {
                adBlock = adBlock.parentElement;
                if (!adBlock) break;
                const h3 = adBlock.querySelector('h3, div[role="heading"]');
                if (h3) {
                    title = h3.textContent.trim();
                    const descEls = adBlock.querySelectorAll('.MUxGbd, .yDYNvb, .lyLwlc');
                    descEls.forEach(d => {
                        const t = d.textContent.trim();
                        if (t.length > snippet.length && t !== title) snippet = t;
                    });
                    break;
                }
            }
            if (!title) continue;
            seen_sp.add(du);
            output.sponsored.push({title: title, displayUrl: du, snippet: snippet.substring(0,250)});
        }

        // === GOOGLE SHOPPING ===
        const priceRx = /\$[\d,]+\.?\d*/;
        const seen_shop = new Set();
        const shopGrids = document.querySelectorAll(
            '.commercial-unit-desktop-top, .cu-container, .sh-dgr__grid-result, .pla-unit-container, .sh-pr__product-results, [data-pla="1"]'
        );
        for (const grid of shopGrids) {
            const cards = grid.querySelectorAll('a[href]');
            for (const card of cards) {
                const text = card.innerText || card.textContent || '';
                const pm = text.match(priceRx);
                if (!pm) continue;
                const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0 && l.length < 200);
                let title = '', store = '', price = pm[0];
                for (const line of lines) {
                    if (priceRx.test(line)) continue;
                    if (line.length < 3) continue;
                    if (!title && line.length >= 5) title = line;
                    else if (title && !store && line.length >= 2 && line.length < 50 && line !== title) store = line;
                }
                if (!title || title.length < 3) continue;
                const key = title.substring(0,40) + price;
                if (seen_shop.has(key)) continue;
                seen_shop.add(key);
                output.shopping.push({title: title.substring(0,150), price, store: store||'unknown', domain: ''});
            }
        }
        if (output.shopping.length === 0) {
            const links = document.querySelectorAll('a[href*="shopping"], a[href*="aclk"], a[href*="merchant"]');
            for (const link of links) {
                let card = link;
                for (let i = 0; i < 6; i++) {
                    card = card.parentElement;
                    if (!card) break;
                    const text = card.innerText || '';
                    const pm = text.match(priceRx);
                    if (!pm) continue;
                    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                    let title = '', store = '', price = pm[0];
                    for (const line of lines) {
                        if (priceRx.test(line)) continue;
                        if (line.length < 3) continue;
                        if (!title && line.length >= 5) title = line;
                        else if (title && !store && line.length >= 2 && line.length < 50) store = line;
                    }
                    if (!title) continue;
                    const key = title.substring(0,40) + price;
                    if (seen_shop.has(key)) continue;
                    seen_shop.add(key);
                    output.shopping.push({title: title.substring(0,150), price, store: store||'unknown', domain: ''});
                    break;
                }
            }
        }

        // === ORGANIC RESULTS ===
        const allLinks = document.querySelectorAll('a[href^="http"]');
        for (const link of allLinks) {
            const href = link.href || '';
            if (!href.startsWith('http')) continue;
            if (href.includes('google.com') || href.includes('googleadservices') || href.includes('youtube.com') || href.includes('gstatic')) continue;
            let h3 = link.querySelector('h3');
            if (!h3) { const p = link.parentElement; if (p) h3 = p.querySelector('h3'); }
            if (!h3) continue;
            if (link.closest('#tads, #tadsb')) continue;
            if (link.closest('[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit')) continue;
            if (link.closest('[data-initq], .related-question-pair')) continue;
            let inSponsored = false;
            let cn = link;
            for (let i = 0; i < 10; i++) {
                cn = cn.parentElement;
                if (!cn) break;
                const texts = cn.querySelectorAll('span');
                for (const sp of texts) { if (sp.textContent.trim() === 'Sponsored') { inSponsored = true; break; } }
                if (inSponsored) break;
                if (cn.id === 'search' || cn.id === 'rso') break;
            }
            if (inSponsored) continue;
            const title = h3.textContent.trim();
            if (!title || seen_org.has(href)) continue;
            seen_org.add(href);
            let snippet = '';
            let sn = link.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!sn) break;
                sn.querySelectorAll('.VwiC3b, .lEBKkf, [data-sncf], .IsZvec, .st, span').forEach(d => {
                    const t = d.textContent.trim();
                    if (t.length > 40 && t.length > snippet.length && t !== title) snippet = t;
                });
                if (snippet) break;
                sn = sn.parentElement;
            }
            output.organic.push({href, title, snippet: snippet.substring(0,250)});
            if (output.organic.length >= 10) break;
        }
        return output;
    }""")

def search_one_keyword(keyword):
    location = random.choice(US_LOCATIONS)
    log.info("Searching: '%s' (from %s) ...", keyword, location)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox","--disable-dev-shm-usage"
        ])
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width":1366,"height":900}, locale="en-US",
        )
        context.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
            window.chrome={runtime:{}};
        """)
        page = context.new_page()
        try:
            url = _build_url(keyword, location)
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_selector("#search, #rso, #main, #center_col, #rcnt, body", timeout=10000)
            except: pass
            page.wait_for_timeout(6000)
            page.evaluate("window.scrollTo(0, 800)")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollTo(0, 1600)")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollTo(0, 2400)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
            for sel in ['button:has-text("Accept all")', 'button:has-text("Reject all")', 'button:has-text("I agree")']:
                btn = page.query_selector(sel)
                if btn:
                    try: btn.click(); page.wait_for_timeout(2000)
                    except: pass
                    break
            if page.query_selector("#captcha-form, #recaptcha"):
                log.error("  CAPTCHA on '%s'", keyword)
                browser.close()
                return [], [], [], location
            raw = _parse_all_results(page)

            # Process + filter sponsored
            sponsored = []
            seen_sp = set()
            for ad in raw.get("sponsored",[]):
                domain = _domain_from_display(ad["displayUrl"])
                if not domain or domain in seen_sp or _is_junk_domain(domain): continue
                seen_sp.add(domain)
                sponsored.append({"position":len(sponsored)+1,"title":ad["title"],"domain":domain,"display_url":ad["displayUrl"],"snippet":ad["snippet"]})
                if len(sponsored) >= config.TOP_N_SPONSORED: break

            # Process + filter organic
            organic = []
            seen_org = set()
            for item in raw.get("organic",[]):
                domain = _extract_domain(item["href"])
                if not domain or domain in seen_org or _is_junk_domain(domain): continue
                seen_org.add(domain)
                organic.append({"position":len(organic)+1,"title":item["title"],"domain":domain,"link":item["href"],"snippet":item["snippet"]})
                if len(organic) >= config.TOP_N_ORGANIC: break

            # Process + filter shopping
            shopping = []
            for i, item in enumerate(raw.get("shopping",[])):
                store = item.get("store","unknown")
                if _is_junk_store(store): continue
                shopping.append({"position":len(shopping)+1,"title":item["title"],"price":item["price"],"store":store,"domain":item.get("domain","")})
                if len(shopping) >= 10: break

            log.info("  Found: %d sponsored, %d organic, %d shopping", len(sponsored), len(organic), len(shopping))
            for s in sponsored: log.info("    Ad #%d: %s — %s", s["position"], s["domain"], s["title"][:50])
            for o in organic: log.info("    Org #%d: %s", o["position"], o["domain"])
            for s in shopping: log.info("    Shop #%d: %s %s (%s)", s["position"], s["title"][:35], s["price"], s["store"])
            browser.close()
            return sponsored, organic, shopping, location
        except Exception as e:
            log.error("  Error: %s", e)
            try: browser.close()
            except: pass
            return [], [], [], location

def run_all_keywords(keywords=None):
    keywords = keywords or config.KEYWORDS
    log.info("=== BenchPro run at %s UTC ===", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    for i, kw in enumerate(keywords):
        try:
            sp, org, shop, loc = search_one_keyword(kw)
            rid = save_search_run(kw, sp, org, shop, loc)
            log.info("  Saved: %s", rid)
        except Exception as e:
            log.error("  Failed '%s': %s", kw, e)
        if i < len(keywords)-1:
            delay = config.DELAY_BETWEEN_SEARCHES + random.uniform(15, 25)
            log.info("  Waiting %ds ...", delay)
            time.sleep(delay)
    log.info("=== Done ===")

if __name__ == "__main__":
    run_all_keywords([sys.argv[1]] if len(sys.argv)>1 else None)
