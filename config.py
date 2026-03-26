"""
BenchPro Configuration
No API keys needed — uses headless browser scraping.
"""
import os

# --- Search Settings ---
KEYWORDS = [
    "workbench",
    "work bench",
    "workbenches",
    "work benches",
]

# Your domain — highlighted in dashboard
OUR_DOMAIN = "benchdepot.com"

# How many results to capture per result type
TOP_N_SPONSORED = 5
TOP_N_ORGANIC = 5

# Google search parameters
SEARCH_LANGUAGE = "en"
SEARCH_COUNTRY = "us"

# Seconds between each keyword search (be polite to Google)
DELAY_BETWEEN_SEARCHES = 8

# --- Schedule (24h format, local time) ---
SEARCH_TIMES = ["08:00", "12:00", "17:00"]

# --- Data output (committed to repo → GitHub Pages reads it) ---
DATA_FILE = os.path.join(os.path.dirname(__file__), "docs", "data", "results.json")

# --- Dashboard password ---
# Change this! It's the password you and your colleague use to view the dashboard.
DASHBOARD_PASSWORD = "benchpro2026"
