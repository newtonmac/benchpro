"""
Data storage — JSON file for GitHub Pages dashboard.
"""
import os, json
from datetime import datetime, timezone
import config

def _load_data():
    if os.path.exists(config.DATA_FILE):
        try:
            with open(config.DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"runs": []}

def _save_data(data):
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_search_run(keyword, sponsored, organic, shopping=None, location=None):
    data = _load_data()
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%d_%H%M%S") + "_" + keyword.replace(" ", "_")
    run = {
        "id": run_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "keyword": keyword,
        "location": location or "US",
        "sponsored": sponsored,
        "organic": organic,
        "shopping": shopping or [],
    }
    data["runs"].append(run)
    # Keep last 90 days (~6 runs/day × 4 kw × 90 days = 2160)
    if len(data["runs"]) > 2200:
        data["runs"] = data["runs"][-2200:]
    _save_data(data)
    return run_id
