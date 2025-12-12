#!/usr/bin/env python3
"""
Quick test of SIP Bridge Integration.
"""

import logging
import os
import sys
import time


def setup_path():
    """Add project root and src to path before imports."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    actual_root = os.path.join(project_root, "..", "..")
    sys.path.insert(0, actual_root)
    sys.path.insert(0, os.path.join(actual_root, "src"))


def main():
    # Set up path before using imports
    setup_path()

    # Import after path adjustment
    from services.sip_bridge_integration import sip_bridge_integration

    # Patch environment variable to enable SIP bridge
    os.environ["ENABLE_SIP_BRIDGE"] = "true"

    logging.basicConfig(level=logging.DEBUG)

    print("Testing SIP Bridge Integration...")

    # Check if enabled
    if not sip_bridge_integration.is_enabled():
        print("WARNING: SIP Bridge is disabled (ENABLE_SIP_BRIDGE != true)")
        # Force enable for test
        os.environ["ENABLE_SIP_BRIDGE"] = "true"

    print("Starting SIP Bridge...")
    sip_bridge_integration.start()

    # Wait a bit for initialization
    time.sleep(2)

    # Check status
    status = sip_bridge_integration.get_status()
    print(f"Status: {status}")

    # Let it run for a few seconds
    print("Monitoring for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        if not sip_bridge_integration.is_running():
            print("SIP Bridge stopped unexpectedly!")
            break
        print(f"  ... {i + 1}s")

    print("Stopping SIP Bridge...")
    sip_bridge_integration.stop()

    time.sleep(1)
    print("Test completed.")


if __name__ == "__main__":
    main()
