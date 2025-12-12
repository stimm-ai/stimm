#!/usr/bin/env python3
"""
Update an existing SIP trunk configuration.

Usage:
    python update_trunk.py --trunk-id <id> --number <new_number> --allowed <new_allowed>
"""

import argparse
import json
import sys

import redis


def main():
    parser = argparse.ArgumentParser(description="Update SIP trunk configuration")
    parser.add_argument("--trunk-id", help="Trunk ID to update (if not provided, list trunks)")
    parser.add_argument("--number", help="New phone number to add/replace")
    parser.add_argument("--allowed", help="New allowed address CIDR")
    args = parser.parse_args()

    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    TRUNK_KEY = "sip_inbound_trunk"

    if not args.trunk_id:
        # List trunks
        trunks = r.hgetall(TRUNK_KEY)
        if not trunks:
            print("No trunks found.")
            return
        print("Existing trunks:")
        for tid, cfg in trunks.items():
            print(f"- {tid}: {cfg}")
        return

    # Fetch existing trunk
    trunk_json = r.hget(TRUNK_KEY, args.trunk_id)
    if not trunk_json:
        print(f"Trunk {args.trunk_id} not found.")
        sys.exit(1)

    trunk = json.loads(trunk_json)

    # Update fields
    if args.number:
        # Replace numbers list with new number
        trunk["numbers"] = [args.number]
    if args.allowed:
        trunk["allowed_addresses"] = [args.allowed]

    # Save back
    r.hset(TRUNK_KEY, args.trunk_id, json.dumps(trunk))
    print(f"Updated trunk {args.trunk_id}: {json.dumps(trunk, indent=2)}")


if __name__ == "__main__":
    main()
