"""
Debug script - saves HTML + screenshot + detailed parse report.
Run via: python -m collector.debug_scrape
"""
import os, json, random
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

US_LOCATIONS = ["Houston, Texas", "Chicago, Illinois", "Los Angeles, California", "San Diego, California"]

def run_debug():
    keyword = "workbench"
    location = random.choice(US_LOCATIONS)
    params = {"q": keyword, "hl": "en", "gl": "us", "num": "10", "near": location}
    url = "https://www.google.com/search?" + urlencode(params)

    print(f"Searching: '{keyword}' from {location}")
    print(f"URL: {url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled","--no-sandbox","--disable-dev-shm-usage"
        ])
        context = browser.new_context(
            user_agent=USER_AGENTS[0],
            viewport={"width":1366,"height":900}, locale="en-US",
        )
        context.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            window.chrome={runtime:{}};
        """)
        page = context.new_page()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("#search, #rso, #main, #center_col, body", timeout=10000)
        except: pass
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo(0, 1200)")
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 2400)")
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # Save screenshot
        os.makedirs("debug_output", exist_ok=True)
        page.screenshot(path="debug_output/page.png", full_page=True)
        print("Saved: debug_output/page.png")

        # Save HTML
        html = page.content()
        with open("debug_output/page.html", "w") as f:
            f.write(html)
        print(f"Saved: debug_output/page.html ({len(html)} bytes)\n")

        # Detailed analysis
        report = page.evaluate(r"""() => {
            const r = {};

            // Count key elements
            r.total_cites = document.querySelectorAll('cite').length;
            r.total_h3 = document.querySelectorAll('h3').length;
            r.total_links = document.querySelectorAll('a[href]').length;

            // Find "Sponsored" text occurrences
            r.sponsored_labels = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            while (walker.nextNode()) {
                const t = walker.currentNode.textContent.trim();
                if (t === 'Sponsored' || t === 'Sponsored results' || t === 'Ad' || t === 'Ads') {
                    const parent = walker.currentNode.parentElement;
                    r.sponsored_labels.push({
                        text: t,
                        tag: parent ? parent.tagName : 'null',
                        class: parent ? parent.className.substring(0,60) : '',
                        parentId: parent && parent.parentElement ? parent.parentElement.id : '',
                    });
                }
            }

            // Check for #tads and #tadsb
            r.has_tads = !!document.getElementById('tads');
            r.has_tadsb = !!document.getElementById('tadsb');
            if (r.has_tads) {
                const tads = document.getElementById('tads');
                r.tads_h3_count = tads.querySelectorAll('h3').length;
                r.tads_cite_count = tads.querySelectorAll('cite').length;
                r.tads_html_length = tads.innerHTML.length;
            }

            // List ALL cite elements with context
            r.all_cites = [];
            document.querySelectorAll('cite').forEach((cite, i) => {
                let inShopping = !!cite.closest('[data-pla], .commercial-unit-desktop-top, .cu-container, .pla-unit');
                let inTads = !!cite.closest('#tads, #tadsb');

                // Check if any ancestor has "Sponsored" text
                let hasSponsored = false;
                let node = cite;
                for (let j = 0; j < 10; j++) {
                    node = node.parentElement;
                    if (!node) break;
                    if (node.id === 'tads' || node.id === 'tadsb') { hasSponsored = true; break; }
                    // Check direct text content (not innerText which is expensive)
                    for (const child of node.childNodes) {
                        if (child.nodeType === 3 && (child.textContent.trim() === 'Sponsored' || child.textContent.trim() === 'Sponsored results')) {
                            hasSponsored = true; break;
                        }
                    }
                    if (hasSponsored) break;
                    // Also check for span with "Sponsored" as direct child
                    const spans = node.querySelectorAll(':scope > span');
                    for (const span of spans) {
                        if (span.textContent.trim() === 'Sponsored') { hasSponsored = true; break; }
                    }
                    if (hasSponsored) break;
                }

                // Find nearby h3
                let h3Text = '';
                let searchNode = cite;
                for (let j = 0; j < 8; j++) {
                    searchNode = searchNode.parentElement;
                    if (!searchNode) break;
                    const h3 = searchNode.querySelector('h3, div[role="heading"]');
                    if (h3) { h3Text = h3.textContent.trim().substring(0, 60); break; }
                }

                r.all_cites.push({
                    index: i,
                    text: cite.textContent.trim().substring(0, 80),
                    inShopping: inShopping,
                    inTads: inTads,
                    hasSponsored: hasSponsored,
                    h3: h3Text,
                });
            });

            // Find all h3 elements with their context
            r.all_h3s = [];
            document.querySelectorAll('h3').forEach((h3, i) => {
                let inTads = !!h3.closest('#tads, #tadsb');
                let inShopping = !!h3.closest('[data-pla], .commercial-unit-desktop-top');
                let inOrganic = !!h3.closest('#search, #rso');
                
                // Find cite nearby
                let citeText = '';
                let searchNode = h3;
                for (let j = 0; j < 8; j++) {
                    searchNode = searchNode.parentElement;
                    if (!searchNode) break;
                    const cite = searchNode.querySelector('cite');
                    if (cite) { citeText = cite.textContent.trim().substring(0, 60); break; }
                }

                r.all_h3s.push({
                    index: i,
                    text: h3.textContent.trim().substring(0, 60),
                    inTads: inTads,
                    inShopping: inShopping,
                    inOrganic: inOrganic,
                    cite: citeText,
                });
            });

            return r;
        }""")

        browser.close()

    # Print report
    print("=" * 60)
    print("ELEMENT COUNTS:")
    print(f"  Total <cite>: {report['total_cites']}")
    print(f"  Total <h3>:   {report['total_h3']}")
    print(f"  Total <a>:    {report['total_links']}")
    print(f"  #tads exists: {report['has_tads']}")
    print(f"  #tadsb exists: {report['has_tadsb']}")
    if report.get('has_tads'):
        print(f"  #tads h3 count: {report.get('tads_h3_count')}")
        print(f"  #tads cite count: {report.get('tads_cite_count')}")

    print(f"\n'SPONSORED' LABELS FOUND ({len(report['sponsored_labels'])}):")
    for s in report['sponsored_labels']:
        print(f"  '{s['text']}' in <{s['tag']}> class='{s['class']}' parentId='{s['parentId']}'")

    print(f"\nALL CITE ELEMENTS ({len(report['all_cites'])}):")
    for c in report['all_cites']:
        flags = []
        if c['inTads']: flags.append('TADS')
        if c['inShopping']: flags.append('SHOPPING')
        if c['hasSponsored']: flags.append('SPONSORED')
        flag_str = ' [' + ', '.join(flags) + ']' if flags else ''
        print(f"  #{c['index']}: {c['text']}{flag_str}")
        if c['h3']: print(f"         h3: {c['h3']}")

    print(f"\nALL H3 ELEMENTS ({len(report['all_h3s'])}):")
    for h in report['all_h3s']:
        flags = []
        if h['inTads']: flags.append('TADS')
        if h['inShopping']: flags.append('SHOPPING')
        if h['inOrganic']: flags.append('ORGANIC')
        flag_str = ' [' + ', '.join(flags) + ']' if flags else ''
        print(f"  #{h['index']}: {h['text']}{flag_str}")
        if h['cite']: print(f"         cite: {h['cite']}")

    # Save report
    with open("debug_output/report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved: debug_output/report.json")

if __name__ == "__main__":
    run_debug()
