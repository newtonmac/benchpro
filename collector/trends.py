"""
Fetch Google Trends data for our keywords.
Shows relative search interest (0-100 scale) over time.
"""
import json
import os
import logging
from datetime import datetime

log = logging.getLogger("benchpro")

def fetch_trends(keywords, timeframe="today 3-m", geo="US"):
    """Fetch Google Trends data. Returns dict of keyword -> list of {date, value}."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.warning("pytrends not installed, skipping trends")
        return {}

    try:
        pytrends = TrendReq(hl="en-US", tz=480)  # 480 = Pacific time
        pytrends.build_payload(keywords[:5], cat=0, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()

        if df.empty:
            log.warning("No trends data returned")
            return {}

        result = {}
        for kw in keywords:
            if kw in df.columns:
                points = []
                for date, row in df.iterrows():
                    points.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "value": int(row[kw])
                    })
                result[kw] = points
                log.info("  Trends for '%s': %d data points", kw, len(points))

        return result

    except Exception as e:
        log.error("  Trends error: %s", e)
        return {}


def save_trends(trends_data):
    """Save trends data to a JSON file for the dashboard."""
    import config
    trends_file = os.path.join(os.path.dirname(config.DATA_FILE), "trends.json")
    os.makedirs(os.path.dirname(trends_file), exist_ok=True)

    # Load existing
    existing = {}
    if os.path.exists(trends_file):
        try:
            with open(trends_file) as f:
                existing = json.load(f)
        except:
            pass

    existing["updated"] = datetime.now().isoformat(timespec="seconds")
    existing["keywords"] = trends_data

    with open(trends_file, "w") as f:
        json.dump(existing, f, indent=2)

    log.info("  Saved trends to %s", trends_file)


def run_trends():
    """Main entry point."""
    import config
    log.info("Fetching Google Trends data...")
    data = fetch_trends(config.KEYWORDS)
    if data:
        save_trends(data)
    else:
        log.warning("No trends data collected")
