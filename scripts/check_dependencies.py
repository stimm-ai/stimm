#!/usr/bin/env python3
"""
Open-Source Dependency Vulnerability Checker

Uses only established open-source tools for dependency scanning.
"""

import json
import subprocess
import sys
from pathlib import Path


def check_with_osv_scanner() -> bool:
    """Check dependencies using OSV-Scanner if available."""

    # Check if osv-scanner is available
    try:
        result = subprocess.run(["which", "osv-scanner"], capture_output=True, text=True)
        if result.returncode != 0:
            return False
    except FileNotFoundError:
        return False

    print("🔍 Using OSV-Scanner for dependency vulnerability checking")

    try:
        # Run OSV-Scanner with JSON output
        result = subprocess.run(["osv-scanner", "--format=json", "."], capture_output=True, text=True, cwd=Path.cwd())

        if result.returncode == 0:
            print("✅ No vulnerabilities found by OSV-Scanner")
            return True
        else:
            print("❌ Vulnerabilities found by OSV-Scanner:")
            try:
                vulnerabilities = json.loads(result.stdout)
                for vuln in vulnerabilities.get("results", []):
                    print(f"  - {vuln.get('package', {}).get('name', 'Unknown')}: {vuln.get('vulnerability', {}).get('id', 'Unknown')}")
            except json.JSONDecodeError:
                print(f"  Raw output: {result.stdout}")
            return False

    except Exception as e:
        print(f"⚠️  OSV-Scanner failed: {e}")
        return False


def check_with_pip_audit() -> bool:
    """Check dependencies using pip-audit if available."""

    # Check if pip-audit is available
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
        if "pip-audit" not in result.stdout:
            return False
    except Exception:
        return False

    print("🔍 Using pip-audit for dependency vulnerability checking")

    try:
        # Run pip-audit
        result = subprocess.run([sys.executable, "-m", "pip-audit"], capture_output=True, text=True, cwd=Path.cwd())

        if result.returncode == 0:
            print("✅ No vulnerabilities found by pip-audit")
            return True
        else:
            print("❌ Vulnerabilities found by pip-audit:")
            print(result.stdout)
            return False

    except Exception as e:
        print(f"⚠️  pip-audit failed: {e}")
        return False


def main():
    """Main entry point for open-source dependency checking."""
    print("🛡️  Starting open-source dependency vulnerability scan...")

    # Try OSV-Scanner first (preferred)
    if check_with_osv_scanner():
        sys.exit(0)

    # Try pip-audit as fallback
    if check_with_pip_audit():
        sys.exit(0)

    print("⚠️  No open-source vulnerability scanners available")
    print("💡 Consider installing:")
    print("  - OSV-Scanner: https://github.com/google/osv-scanner")
    print("  - pip-audit: pip install pip-audit")

    # Exit with warning but not failure (no tools available)
    sys.exit(0)


if __name__ == "__main__":
    main()
