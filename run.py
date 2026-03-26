"""
BenchPro Run Script
Searches Google → saves results to JSON → commits & pushes to GitHub.

Usage:
    python run.py          # search all keywords and push
    python run.py --no-push   # search only, don't push (for testing)
"""
import sys
import subprocess
import logging
from collector.search_runner import run_all_keywords

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("benchpro")


def git_push():
    """Commit updated results.json and push to GitHub."""
    try:
        subprocess.run(["git", "add", "docs/data/results.json"], check=True)

        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/data/results.json"],
            capture_output=True, text=True,
        )

        if not result.stdout.strip():
            log.info("No changes to push — results unchanged.")
            return

        from datetime import datetime
        msg = f"Update SERP data — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
        log.info("✓ Pushed updated results to GitHub")

    except subprocess.CalledProcessError as e:
        log.error(f"✗ Git push failed: {e}")
        log.info("  Make sure you're in the repo directory and have push access.")
    except FileNotFoundError:
        log.error("✗ Git not found — install git or push manually.")


def main():
    no_push = "--no-push" in sys.argv

    # Step 1: Run searches
    run_all_keywords()

    # Step 1b: Fetch Google Trends
    try:
        from collector.trends import run_trends
        run_trends()
    except Exception as e:
        log.warning("Trends fetch failed: %s", e)

    # Step 2: Push to GitHub (unless --no-push)
    if no_push:
        log.info("Skipping git push (--no-push flag)")
    else:
        git_push()

    log.info("Done! Dashboard will update at: https://newtonmac.github.io/benchpro")


if __name__ == "__main__":
    main()
