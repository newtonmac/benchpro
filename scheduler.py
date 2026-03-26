"""
BenchPro Scheduler — runs searches 3× daily and pushes to GitHub.

Usage:
    python scheduler.py

Keep running in background (screen, tmux, or systemd service).
"""
import schedule
import time
import logging
from run import main as run_and_push
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("benchpro-scheduler")

if __name__ == "__main__":
    print(f"\n  ⏰ BenchPro Scheduler")
    print(f"  Keywords: {', '.join(config.KEYWORDS)}")
    print(f"  Times: {', '.join(config.SEARCH_TIMES)}")
    print(f"  Dashboard: https://newtonmac.github.io/benchpro")
    print(f"  Press Ctrl+C to stop.\n")

    for t in config.SEARCH_TIMES:
        schedule.every().day.at(t).do(run_and_push)
        log.info(f"  Scheduled at {t}")

    while True:
        schedule.run_pending()
        time.sleep(30)
