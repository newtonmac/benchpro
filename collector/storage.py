"""
Data storage — reads/writes a JSON file that gets committed to the repo.
GitHub Pages serves this file and the dashboard JS reads it directly.

Data structure:
{
    "runs": [
        {
            "id": "20260326_080000",
            "timestamp": "2026-03-26T08:00:00",
            "keyword": "workbench",
            "sponsored": [ { "position": 1, "domain": "...", "title": "...", ... } ],
            "organic":   [ { "position": 1, "domain": "...", "title": "...", ... } ]
        },
        ...
    ]
}
"""
import os
import json
from datetime import datetime

import config


def _load_data():
    """Load existing data from JSON file."""
    if os.path.exists(config.DATA_FILE):
        try:
            with open(config.DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"runs": []}


def _save_data(data):
    """Write data back to JSON file."""
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_search_run(keyword, sponsored, organic):
    """
    Append one search run to the data file.
    Returns the run ID.
    """
    data = _load_data()
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S") + f"_{keyword.replace(' ', '_')}"

    run = {
        "id": run_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "keyword": keyword,
        "sponsored": sponsored,
        "organic": organic,
    }
    data["runs"].append(run)

    # Keep last 90 days of data (~1080 runs max at 12/day)
    # to keep the JSON file manageable for GitHub Pages
    cutoff_count = 90 * 12  # 90 days × 4 keywords × 3 runs
    if len(data["runs"]) > cutoff_count:
        data["runs"] = data["runs"][-cutoff_count:]

    _save_data(data)
    return run_id
