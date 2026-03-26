"""
Generate sample data so the dashboard has something to show immediately.

Usage:
    python seed_data.py

Creates ~3 days of fake data in docs/data/results.json.
Once real data starts coming in, this gets pushed down naturally.
"""
import json
import os
import random
from datetime import datetime, timedelta

import config

# Realistic competitor domains for workbench keywords
COMPETITOR_DOMAINS = [
    "globalindustrial.com",
    "uline.com",
    "grainger.com",
    "homedepot.com",
    "lowes.com",
    "amazon.com",
    "samsclub.com",
    "benchdepot.com",
    "lista.com",
    "shure-america.com",
    "iaborsa.com",
    "stackbin.com",
    "proliantinc.com",
]

ORGANIC_DOMAINS = [
    "homedepot.com",
    "lowes.com",
    "amazon.com",
    "walmart.com",
    "globalindustrial.com",
    "benchdepot.com",
    "wayfair.com",
    "grainger.com",
    "harborfreight.com",
    "uline.com",
]


def gen_title(domain, keyword):
    titles = {
        "globalindustrial.com": f"Industrial {keyword.title()}es | Global Industrial",
        "uline.com": f"Heavy Duty {keyword.title()}es - Uline",
        "grainger.com": f"Shop {keyword.title()}es | Grainger",
        "homedepot.com": f"{keyword.title()} - The Home Depot",
        "lowes.com": f"{keyword.title()}es at Lowe's",
        "amazon.com": f"Amazon.com: {keyword.title()}",
        "benchdepot.com": f"Industrial {keyword.title()}es | BenchDepot",
        "lista.com": f"Lista {keyword.title()} Solutions",
    }
    return titles.get(domain, f"{keyword.title()} - {domain}")


def generate():
    runs = []
    now = datetime.now()

    # Generate 3 days × 3 runs/day × 4 keywords = 36 runs
    for day_offset in range(3, 0, -1):
        for hour in [8, 12, 17]:
            timestamp = (now - timedelta(days=day_offset)).replace(
                hour=hour, minute=random.randint(0, 5), second=0, microsecond=0
            )

            for keyword in config.KEYWORDS:
                # Pick 3-5 sponsored results (benchdepot appears ~70% of the time)
                sp_pool = random.sample(COMPETITOR_DOMAINS, k=random.randint(3, 5))
                if random.random() < 0.7 and "benchdepot.com" not in sp_pool:
                    sp_pool[random.randint(0, min(2, len(sp_pool) - 1))] = "benchdepot.com"

                sponsored = []
                for i, domain in enumerate(sp_pool[:5]):
                    sponsored.append({
                        "position": i + 1,
                        "title": gen_title(domain, keyword),
                        "domain": domain,
                        "display_url": f"{domain}/{keyword.replace(' ', '-')}",
                        "snippet": f"Shop premium {keyword}s. Free shipping on orders over $500.",
                    })

                # Pick 5 organic results (benchdepot appears ~50% of the time)
                org_pool = random.sample(ORGANIC_DOMAINS, k=5)
                if random.random() < 0.5 and "benchdepot.com" not in org_pool:
                    org_pool[random.randint(2, 4)] = "benchdepot.com"

                organic = []
                for i, domain in enumerate(org_pool):
                    organic.append({
                        "position": i + 1,
                        "title": gen_title(domain, keyword),
                        "domain": domain,
                        "link": f"https://{domain}/{keyword.replace(' ', '-')}",
                        "snippet": f"Browse our selection of {keyword}s for workshop and industrial use.",
                    })

                run_id = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{keyword.replace(' ', '_')}"
                runs.append({
                    "id": run_id,
                    "timestamp": timestamp.isoformat(timespec="seconds"),
                    "keyword": keyword,
                    "sponsored": sponsored,
                    "organic": organic,
                })

    # Save
    data = {"runs": runs}
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"  ✓ Generated {len(runs)} sample search runs")
    print(f"  Saved to: {config.DATA_FILE}")
    print(f"  Now push to GitHub and check the dashboard!")


if __name__ == "__main__":
    generate()
