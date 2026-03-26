"""
Data storage — JSON file committed to repo, read by GitHub Pages.
"""
import os, json
from datetime import datetime
import config

def _load_data():
    if os.path.exists(config.DATA_FILE):
        try:
            with open(config.DATA_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"runs": []}

def _save_data(data):
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_search_run(keyword, sponsored, organic, shopping=None):
    data = _load_data()
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S") + "_" + keyword.replace(" ", "_")
    run = {
        "id": run_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "keyword": keyword,
        "sponsored": sponsored,
        "organic": organic,
        "shopping": shopping or [],
    }
    data["runs"].append(run)
    cutoff_count = 90 * 12
    if len(data["runs"]) > cutoff_count:
        data["runs"] = data["runs"][-cutoff_count:]
    _save_data(data)
    return run_id
