"""
Set the dashboard password.

Usage:
    python set_password.py                  # uses password from config.py
    python set_password.py mypassword123    # sets a custom password

This updates the password hash in the dashboard JS file.
"""
import sys
import hashlib
import os

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def main():
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        try:
            from config import DASHBOARD_PASSWORD
            password = DASHBOARD_PASSWORD
        except ImportError:
            password = "benchpro2026"

    pw_hash = sha256(password)

    # Write hash to a file the dashboard JS reads
    config_path = os.path.join(os.path.dirname(__file__), "docs", "data", "auth.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    import json
    with open(config_path, "w") as f:
        json.dump({"hash": pw_hash}, f)

    print(f"  ✓ Password set successfully")
    print(f"  Password: {password}")
    print(f"  Hash saved to: docs/data/auth.json")
    print(f"  Dashboard URL: https://newtonmac.github.io/benchpro")

if __name__ == "__main__":
    main()
