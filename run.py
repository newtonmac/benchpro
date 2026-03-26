"""
BenchPro Run Script — search + trends + push
"""
import sys, subprocess, logging
from collector.search_runner import run_all_keywords

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("benchpro")

def git_push():
    try:
        subprocess.run(["git", "add", "docs/data/results.json", "docs/data/trends.json"], check=True)
        result = subprocess.run(["git", "status", "--porcelain", "docs/data/"], capture_output=True, text=True)
        if not result.stdout.strip():
            log.info("No changes to push.")
            return
        from datetime import datetime
        msg = f"Update SERP data — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
        log.info("Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        log.error("Git push failed: %s", e)
    except FileNotFoundError:
        log.error("Git not found")

def main():
    no_push = "--no-push" in sys.argv
    run_all_keywords()
    try:
        from collector.trends import run_trends
        run_trends()
    except Exception as e:
        log.warning("Trends failed: %s", e)
    if no_push:
        log.info("Skipping push (--no-push)")
    else:
        git_push()
    log.info("Done! https://newtonmac.github.io/benchpro")

if __name__ == "__main__":
    main()
