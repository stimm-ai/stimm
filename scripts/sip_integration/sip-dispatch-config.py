#!/usr/bin/env python3
"""
Configure SIP dispatch rules for LiveKit SIP server.

This script sets up routing rules that determine which agent or room
should handle incoming SIP calls based on the dialed number.

Usage:
    python sip-dispatch-config.py
"""

import json
import sys

import redis


def main():
    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        print("Make sure Redis is running (docker compose up -d redis)")
        sys.exit(1)

    # Example dispatch rule: route calls to +1234567 to the 'sip-inbound' agent
    dispatch_rules = [{"pattern": "+1234567", "target_type": "agent", "target": "sip-inbound", "priority": 1}, {"pattern": "+*", "target_type": "room", "target": "sip-call-{number}", "priority": 10}]

    DISPATCH_KEY = "sip_dispatch_rules"
    r.set(DISPATCH_KEY, json.dumps(dispatch_rules))

    print(f"Set SIP dispatch rules in Redis key '{DISPATCH_KEY}':")
    print(json.dumps(dispatch_rules, indent=2))

    # Verify
    stored = r.get(DISPATCH_KEY)
    if stored:
        print("\nStored rules:")
        print(stored)
    else:
        print("\nWarning: Rules not stored correctly.")


if __name__ == "__main__":
    main()
