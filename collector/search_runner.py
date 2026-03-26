"""
Search Runner — scrapes Google SERP including Shopping results.
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
        parsed = urlparse(url if "://" in url else "https://"+url)
        d = parsed.netloc.lower()
        if d.startswith("www."): d = d[4:]
        if "google." in d or "gstatic" in d or "youtube.com" in d: return ""
        return d
    except: return ""

def _build_url(keyword):
    return "https://www.google.com/search?"+urlencode({"q":keyword,"hl":config.SEARCH_LANGUAGE,"gl":config.SEARCH_COUNTRY,"num":"10"})

def _parse_all_results(page):
    return page.evaluate(r"""() => {
        const output = { sponsored: [], organic: [], shopping: [] };
        const seen_sp = new Set();
        const seen_org = new Set();
        const seen_shop = new Set();

        // === SPONSORED TEXT ADS ===
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
        const spNodes = [];
        while (walker.nextNode()) {
            const t = walker.currentNode.textContent.trim();
            if (t === 'Sponsored' || t === 'Ad' || t === 'Ads')
                spNodes.push(walker.currentNode.parentElement);
        }
        for (const labelEl of spNodes) {
            let container = labelEl;
            for (let i = 0; i < 15; i++) {
                container = container.parentElement;
                if (!container) break;
                if (container.querySelector('[data-pla], .pla-unit, .commercial-unit-desktop-top, .cu-container')) continue;
                if (container.closest('[data-pla], .pla-unit, .commercial-unit-desktop-top, .cu-container')) continue;
                const headings = container.querySelectorAll('h3, div[role="heading"]');
                if (headings.length > 0) {
                    for (const heading of headings) {
                        let ab = heading;
                        for (let j = 0; j < 8; j++) {
                            ab = ab.parentElement;
                            if (!ab) break;
                            const cite = ab.querySelector('cite, span[data-dtld], .qzEoUe, .x2VHCd');
                            if (!cite) continue;
                            const du = cite.textContent.trim();
                            if (!du || seen_sp.has(du)) break;
                            seen_sp.add(du);
                            let sn = '';
                            ab.querySelectorAll('.MUxGbd, .yDYNvb, .lyLwlc, [role="text"]').forEach(d => {
                                const t = d.textContent.trim();
                                if (t.length > sn.length && t !== heading.textContent.trim()) sn = t;
                            });
                            output.sponsored.push({title: heading.textContent.trim(), displayUrl: du, snippet: sn.substring(0,250)});
                            break;
                        }
                    }
                    if (output.sponsored.length > 0) break;
                }
            }
        }
        if (output.sponsored.length === 0) {
            for (const id of ['tads','tadsb']) {
                const c = document.getElementById(id);
                if (!c) continue;
                c.querySelectorAll('h3, div[role="heading"]').forEach(heading => {
                    let bl = heading;
                    for (let j = 0; j < 8; j++) {
                        bl = bl.parentElement;
                        if (!bl) break;
                        const ci = bl.querySelector('cite, span[data-dtld], .x2VHCd');
                        if (!ci) continue;
                        const du = ci.textContent.trim();
                        if (seen_sp.has(du)) break;
                        seen_sp.add(du);
                        let sn = '';
                        bl.querySelectorAll('.MUxGbd, .yDYNvb').forEach(d => {const t=d.textContent.trim();if(t.length>sn.length)sn=t;});
                        output.sponsored.push({title: heading.textContent.trim(), displayUrl: du, snippet: sn.substring(0,250)});
                        break;
                    }
                });
            }
        }

        // === GOOGLE SHOPPING / SPONSORED PRODUCTS ===
        // These are the product cards with images, prices, and store names
        // They appear in carousels labeled "Sponsored" with data-pla or in commercial units
        const shopContainers = document.querySelectorAll(
            '[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit, .mnr-c.pla-unit, .sh-dgr__grid-result'
        );
        // Also try finding product cards by structure: image + price + store
        const allProductCards = document.querySelectorAll(
            '.pla-unit, .sh-dgr__content, [data-docid], .mnr-c, .commercial-unit-desktop-top .pla-unit-container'
        );
        const productEls = shopContainers.length > 0 ? shopContainers : allProductCards;

        // Broader approach: find all elements with a price pattern
        const priceRegex = /\$[\d,]+\.?\d*/;
        const shopItems = document.querySelectorAll('.pla-unit, [data-dtld], .sh-dgr__grid-result');

        // Walk through elements looking for product card patterns
        const allEls = document.querySelectorAll('a[href*="shopping"], a[href*="merchant"], a[href*="aclk"]');
        for (const el of allEls) {
            // Walk up to find the product card container
            let card = el;
            for (let i = 0; i < 5; i++) {
                card = card.parentElement;
                if (!card) break;
                const text = card.textContent || '';
                const priceMatch = text.match(priceRegex);
                if (!priceMatch) continue;

                // Found a product card with a price
                // Get product title - usually the most prominent text
                const titleEl = card.querySelector('h3, [role="heading"], .pymv4e, .sh-np__product-title, a[aria-label]');
                let title = '';
                if (titleEl) {
                    title = titleEl.textContent.trim() || titleEl.getAttribute('aria-label') || '';
                }
                if (!title) {
                    // Try aria-label on the link itself
                    title = el.getAttribute('aria-label') || '';
                }
                if (!title || title.length < 3) continue;

                // Get store/merchant name - usually at the bottom
                const storeEls = card.querySelectorAll('.aULzUe, .sh-dgr__merchant-name, .LGOjhe, .zPEcBd, span');
                let store = '';
                for (const se of storeEls) {
                    const st = se.textContent.trim();
                    // Store names are typically short, not a price, and not the title
                    if (st.length > 2 && st.length < 40 && !priceRegex.test(st) && st !== title && !st.includes('$')) {
                        // Heuristic: store name is usually after the price
                        store = st;
                    }
                }

                const price = priceMatch[0];
                const key = title.substring(0,30) + price;
                if (seen_shop.has(key)) continue;
                seen_shop.add(key);

                output.shopping.push({
                    title: title.substring(0, 150),
                    price: price,
                    store: store,
                    domain: store.toLowerCase().replace(/\s+/g, '').replace(/\.com$/,'')
                });
                break;
            }
        }

        // Fallback: look for "Sponsored products" section directly
        if (output.shopping.length === 0) {
            const allText = document.querySelectorAll('span, div');
            for (const el of allText) {
                if (el.textContent.trim() === 'Sponsored products' || el.textContent.trim() === 'Sponsored') {
                    let container = el;
                    for (let i = 0; i < 8; i++) {
                        container = container.parentElement;
                        if (!container) break;
                        // Look for product cards within
                        const cards = container.querySelectorAll('a');
                        for (const card of cards) {
                            const text = card.textContent || '';
                            const pm = text.match(priceRegex);
                            if (!pm) continue;
                            const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                            let title = '', store = '', price = pm[0];
                            for (const line of lines) {
                                if (priceRegex.test(line)) continue;
                                if (!title && line.length > 5) title = line;
                                else if (title && line.length > 1 && line.length < 40) store = line;
                            }
                            if (!title) continue;
                            const key = title.substring(0,30) + price;
                            if (seen_shop.has(key)) continue;
                            seen_shop.add(key);
                            output.shopping.push({
                                title: title.substring(0,150), price, store,
                                domain: store.toLowerCase().replace(/\s+/g,'')
                            });
                        }
                        if (output.shopping.length > 0) break;
                    }
                    if (output.shopping.length > 0) break;
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

def search_keyword(keyword, browser):
    url = _build_url(keyword)
    log.info("Searching: '%s' ...", keyword)
    context = browser.new_context(user_agent=random.choice(USER_AGENTS), viewport={"width":1366,"height":900}, locale="en-US")
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")
    page = context.new_page()
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#search, #rso, #main, #center_col, #rcnt, body", timeout=10000)
        except: pass
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo(0, 1200)")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo(0, 2400)")
        page.wait_for_timeout(1500)
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
            context.close()
            return [], [], []
        raw = _parse_all_results(page)
        sponsored, organic, shopping = [], [], []
        seen_sp, seen_org = set(), set()
        for ad in raw.get("sponsored",[]):
            domain = _domain_from_display(ad["displayUrl"])
            if not domain or domain in seen_sp: continue
            seen_sp.add(domain)
            sponsored.append({"position":len(sponsored)+1,"title":ad["title"],"domain":domain,"display_url":ad["displayUrl"],"snippet":ad["snippet"]})
            if len(sponsored) >= config.TOP_N_SPONSORED: break
        for item in raw.get("organic",[]):
            domain = _extract_domain(item["href"])
            if not domain or domain in seen_org: continue
            seen_org.add(domain)
            organic.append({"position":len(organic)+1,"title":item["title"],"domain":domain,"link":item["href"],"snippet":item["snippet"]})
            if len(organic) >= config.TOP_N_ORGANIC: break
        for i, item in enumerate(raw.get("shopping",[])):
            shopping.append({"position":i+1,"title":item["title"],"price":item["price"],"store":item["store"],"domain":item.get("domain","")})
            if i >= 9: break
        log.info("  Found: %d sponsored, %d organic, %d shopping", len(sponsored), len(organic), len(shopping))
        for s in sponsored: log.info("    Ad #%d: %s", s["position"], s["domain"])
        for o in organic: log.info("    Org #%d: %s", o["position"], o["domain"])
        for s in shopping: log.info("    Shop #%d: %s (%s) %s", s["position"], s["title"][:40], s["price"], s["store"])
        context.close()
        return sponsored, organic, shopping
    except Exception as e:
        log.error("  Error: %s", e)
        try: context.close()
        except: pass
        return [], [], []

def run_all_keywords(keywords=None):
    keywords = keywords or config.KEYWORDS
    log.info("=== BenchPro run at %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"])
        for i, kw in enumerate(keywords):
            try:
                sp, org, shop = search_keyword(kw, browser)
                rid = save_search_run(kw, sp, org, shop)
                log.info("  Saved: %s", rid)
            except Exception as e:
                log.error("  Failed '%s': %s", kw, e)
            if i < len(keywords)-1:
                delay = config.DELAY_BETWEEN_SEARCHES + random.uniform(3,7)
                log.info("  Waiting %ds ...", delay)
                time.sleep(delay)
        browser.close()
    log.info("=== Done ===")

if __name__ == "__main__":
    run_all_keywords([sys.argv[1]] if len(sys.argv)>1 else None)
